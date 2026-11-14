"""Frozen vision + final-seven text adapters + original interaction head.

Text and image/text contexts use the same raw-block pooling. Candidate text is
encoded independently and is never inserted into the shared image context.
"""
import re
import threading
from pathlib import Path
import torch
from torch.nn import functional as F
from .model import DecisionModel, select_targets, audit_trainable


def attach_text_adapters(backbone, config):
    from peft import LoraConfig, get_peft_model
    backbone.requires_grad_(False)
    text = backbone.language_model
    if len(text.layers) != config['expected_blocks']:
        raise ValueError('Unexpected Gemma decoder block count')
    targets, blocks, prefix = select_targets(text, config['adapt_last_n'])
    if getattr(backbone, 'is_loaded_in_4bit', False):
        text.is_loaded_in_4bit = True
        text.hf_quantizer = backbone.hf_quantizer
    text = get_peft_model(text, LoraConfig(
        r=config['rank'], lora_alpha=config['lora_alpha'],
        lora_dropout=config['lora_dropout'], bias='none',
        target_modules='(?:'+'|'.join(re.escape(t) for t in targets)+')'))
    backbone.language_model = text
    params = audit_trainable(text, blocks, prefix)
    expected = config.get('expected_adapter_parameters')
    if expected is not None and sum(params.values()) != expected:
        raise ValueError('Adapter parameter count differs from structural audit')
    # Audit the WHOLE backbone, including the vision tower and projector.
    for name, p in backbone.named_parameters():
        if p.requires_grad and not (name.startswith('language_model.') and '.lora_' in name):
            raise ValueError(f'Unexpected trainable multimodal parameter: {name}')
    return dict(blocks=blocks, target_paths=targets,
                adapter_parameters=sum(params.values()), vision_trainable_parameters=0,
                projector_trainable_parameters=0)


def load_gemma(config, device='cuda:0'):
    from transformers import AutoModel, AutoProcessor, BitsAndBytesConfig
    if not config.get('revision'):
        raise ValueError('An immutable model revision is required')
    processor = AutoProcessor.from_pretrained(config['model'], revision=config['revision'])
    processor.tokenizer.padding_side = 'left'
    kwargs = dict(revision=config['revision'], dtype=torch.bfloat16, device_map={'': device})
    if config['quantization'] == 'nf4':
        kwargs['quantization_config'] = BitsAndBytesConfig(load_in_4bit=True,
            bnb_4bit_quant_type='nf4', bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=torch.bfloat16,
            llm_int8_skip_modules=['vision_tower', 'embed_vision'])
    backbone = AutoModel.from_pretrained(config['model'], **kwargs)
    audit = attach_text_adapters(backbone, config)
    model = GemmaDecisionModel(backbone, processor, config).to_head_device(device)
    if model.head.parameter_count != config['expected_head_parameters']:
        raise ValueError('Head size differs from plan')
    audit['head_parameters'] = model.head.parameter_count
    return model, processor, audit


class GemmaDecisionModel(DecisionModel):
    def __init__(self, backbone, processor, config):
        super().__init__(backbone.language_model, processor.tokenizer, config)
        self.multimodal = backbone
        self.processor = processor
        self._prediction_lock = threading.Lock()
        self.train(False)

    def train(self, mode=True):
        super().train(mode)
        # Freeze stochastic behavior as well as weights on the vision side.
        if hasattr(self, 'multimodal'):
            for name in ('vision_tower', 'embed_vision'):
                module = getattr(self.multimodal, name, None)
                if module is not None:
                    module.eval()
        return self

    def encode_context(self, context, images=()):
        if not images:
            return self.encode([context])
        from PIL import Image
        loaded = []
        for value in images:
            if isinstance(value, (str, Path)):
                with Image.open(value) as im:
                    loaded.append(im.convert('RGB'))
            else:
                loaded.append(value.convert('RGB'))
        # Raw scoring format, no chat-template or generated rationale.
        # Google processor expands image markers and creates image positions.
        text = '\n'.join([self.processor.image_token] * len(loaded)) + '\n' + context
        inputs = self.processor(text=text, images=loaded, return_tensors='pt')
        if inputs['input_ids'].shape[-1] > self.config['max_input_tokens']:
            raise ValueError('Image/text input exceeds limit; no silent truncation')
        device = next(self.encoder.parameters()).device
        inputs = inputs.to(device)
        # Keep integer image position IDs and masks intact.
        if 'pixel_values' in inputs:
            vision = getattr(self.multimodal, 'vision_tower')
            dtype = next(vision.parameters()).dtype
            inputs['pixel_values'] = inputs['pixel_values'].to(dtype=dtype)
        mask = inputs['attention_mask'].bool()
        positions = torch.arange(mask.shape[1], device=device).expand_as(mask)
        self.pool_indices = positions.masked_fill(~mask, -1).max(-1).values
        self.raw = {}
        # Do NOT wrap this entire call in no_grad: text adapters must learn
        # from the frozen image features. Frozen vision computes no grad graph.
        self.multimodal(**inputs, use_cache=False)
        result = F.normalize(torch.cat([self.raw['final'], self.raw['penultimate']], -1).float(), dim=-1)
        self.raw = {}
        return result

    def forward(self, rows):
        if not any(row.get('images') for row in rows):
            return super().forward(rows)
        counts = {len(row['choices']) for row in rows}
        if len(counts) != 1:
            raise ValueError('Group microbatches by choice count')
        contexts, unique, lookup, indices = [], [], {}, []
        for row in rows:
            contexts.append(self.encode_context(row['context'], row.get('images', ())))
            positions = []
            for choice in row['choices']:
                if choice not in lookup:
                    lookup[choice] = len(unique)
                    unique.append(choice)
                positions.append(lookup[choice])
            indices.append(positions)
        candidates = self.encode(unique)
        selected = candidates[torch.tensor(indices, device=candidates.device)]
        return self.head(torch.cat(contexts), selected)

    @torch.inference_mode()
    def predict(self, context, questions, images=()):
        with self._prediction_lock:
            self.eval()
            c = self.encode_context(context, images)
            texts, lookup, indices = [], {}, []
            for question in questions:
                positions = []
                if not question['choices']:
                    raise ValueError('Each question needs at least one choice')
                for choice in question['choices']:
                    text = f"Question: {question['question']}\nCandidate answer: {choice}"
                    if text not in lookup:
                        lookup[text] = len(texts)
                        texts.append(text)
                    positions.append(lookup[text])
                indices.append(positions)
            if not texts:
                return {'probabilities': []}
            values = self.encode(texts)
            return {'probabilities': [self.head(c, values[index].unsqueeze(0)).softmax(-1)[0].tolist()
                                      for index in indices]}
