"""Independent raw-block embeddings and the original candidate-interaction head."""
import re
import torch
from torch import nn
from torch.nn import functional as F
from .head import HeadConfig, ValueHead


def block_list(encoder):
    for name in ('layers', 'blocks'):
        value = getattr(encoder, name, None)
        if isinstance(value, nn.ModuleList):
            return name, value
    raise ValueError('Text encoder has no recognized decoder block list')


def select_targets(encoder, last_n=7):
    prefix, blocks = block_list(encoder)
    wanted = set(range(len(blocks) - last_n, len(blocks)))
    if min(wanted) < 0:
        raise ValueError('Insufficient decoder blocks')
    pattern = re.compile(r'^' + prefix + r'\.(\d+)\.')
    targets = []
    for name, module in encoder.named_modules():
        match = pattern.match(name)
        if match and int(match[1]) in wanted and isinstance(module, nn.Linear):
            # Keep routing fixed. Adapt expert/shared-expert projections and Mamba linears.
            if name.rsplit('.', 1)[-1] in ('gate', 'router'):
                continue
            targets.append(name)
    covered = {int(pattern.match(name)[1]) for name in targets}
    if covered != wanted:
        raise ValueError(f'Linear adapter coverage {covered} differs from {wanted}')
    # MoE implementations storing expert matrices as raw Parameters need explicit
    # parameter adapters. Refuse to silently omit such expert tensors.
    for name, p in encoder.named_parameters():
        match = pattern.match(name)
        if match and int(match[1]) in wanted and 'expert' in name and p.ndim >= 2:
            if not any(name == target + '.weight' or name.startswith(target + '.') for target in targets):
                raise ValueError(f'Unsupported expert parameter layout: {name}; audit before training')
    return sorted(targets), sorted(wanted), prefix


def audit_trainable(encoder, blocks, prefix):
    observed, params = set(), {}
    for name, p in encoder.named_parameters():
        if not p.requires_grad:
            continue
        match = re.search(r'(?:^|\.)' + prefix + r'\.(\d+)\.', name)
        if not match or int(match[1]) not in blocks or not re.search(r'\.lora_[AB]\.', name):
            raise ValueError(f'Unexpected trainable base parameter: {name}')
        observed.add(int(match[1]))
        params[name] = p.numel()
    if observed != set(blocks):
        raise ValueError('Not all selected blocks have trainable adapters')
    return params


def load_model(config, device):
    from transformers import AutoModel, AutoTokenizer, BitsAndBytesConfig
    from peft import LoraConfig, get_peft_model
    if not config.get('revision'):
        raise ValueError('Pin model revision with decision_model.prepare before loading')
    tokenizer = AutoTokenizer.from_pretrained(config['model'], revision=config['revision'], trust_remote_code=True)
    tokenizer.padding_side = 'left'
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    kwargs = dict(revision=config['revision'], trust_remote_code=True,
                  dtype=torch.bfloat16, device_map={'': device})
    if config['quantization'] == 'nf4':
        kwargs['quantization_config'] = BitsAndBytesConfig(load_in_4bit=True,
            bnb_4bit_quant_type='nf4', bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=torch.bfloat16)
    full = AutoModel.from_pretrained(config['model'], **kwargs)
    encoder = full.language_model.model
    # Frozen prefix requires no autograd graph. Do not call
    # prepare_model_for_kbit_training: it casts nonquantized weights to FP32.
    if getattr(full, 'is_loaded_in_4bit', False):
        encoder.is_loaded_in_4bit = True
        encoder.hf_quantizer = full.hf_quantizer
    encoder.requires_grad_(False)
    targets, blocks, prefix = select_targets(encoder, config['adapt_last_n'])
    hidden = encoder.config.hidden_size
    if config['head']['embedding_dim'] != 2 * hidden:
        raise ValueError('Head embedding dimension must match two raw block outputs')
    target_regex = '(?:' + '|'.join(re.escape(t) for t in targets) + ')'
    encoder = get_peft_model(encoder, LoraConfig(r=config['rank'], lora_alpha=config['lora_alpha'],
        lora_dropout=config['lora_dropout'], bias='none', target_modules=target_regex))
    trainable = audit_trainable(encoder, blocks, prefix)
    del full  # Drop the unused vision model, projector and vocabulary readout.
    model = DecisionModel(encoder, tokenizer, config).to_head_device(device)
    if model.head.parameter_count != config['expected_head_parameters']:
        raise ValueError(f'Head size mismatch: {model.head.parameter_count}')
    audit = dict(blocks=blocks, targets=targets, adapter_parameters=sum(trainable.values()),
                 head_parameters=model.head.parameter_count,
                 trainable_encoder=trainable)
    return model, tokenizer, audit


class DecisionModel(nn.Module):
    def __init__(self, encoder, tokenizer, config):
        super().__init__()
        self.encoder, self.tokenizer, self.config = encoder, tokenizer, config
        self.head = ValueHead(HeadConfig(**config['head']))
        self.raw, self.pool_indices = {}, None
        self.handles = []
        _, blocks = block_list(encoder.get_base_model())
        for key, block in [('final', blocks[-1]), ('penultimate', blocks[-2])]:
            def capture(module, inputs, output, label=key):
                if getattr(self, '_generation_active', False):
                    return
                hidden = output[0] if isinstance(output, tuple) else output
                indices = self.pool_indices.to(hidden.device)
                self.raw[label] = hidden[torch.arange(hidden.shape[0], device=hidden.device), indices]
            self.handles.append(block.register_forward_hook(capture))

    def to_head_device(self, device):
        self.head.to(device=device, dtype=torch.float32)
        return self

    def forward_tokens(self, batch):
        return self.encoder(**batch, use_cache=False)

    def encode(self, texts):
        encoded = self.tokenizer(texts, add_special_tokens=False, truncation=False)['input_ids']
        if any(not ids or len(ids) > self.config['max_input_tokens'] for ids in encoded):
            raise ValueError('Empty or overlength input; no silent truncation')
        order = sorted(range(len(texts)), key=lambda i: len(encoded[i]))
        chunks, current, longest = [], [], 0
        for i in order:
            new_longest = max(longest, len(encoded[i]))
            if current and (len(current) >= self.config['encoder_microbatch_size'] or
                new_longest * (len(current)+1) > self.config['padded_token_budget']):
                chunks.append(current)
                current, longest = [], 0
            current.append(i)
            longest = max(longest, len(encoded[i]))
        if current:
            chunks.append(current)
        pooled, flattened = [], []
        device = next(self.encoder.parameters()).device
        for indices in chunks:
            batch = self.tokenizer.pad({'input_ids': [encoded[i] for i in indices]},
                                        padding=True, return_tensors='pt').to(device)
            mask = batch['attention_mask'].bool()
            positions = torch.arange(mask.shape[1], device=device).expand_as(mask)
            self.pool_indices = positions.masked_fill(~mask, -1).max(-1).values
            self.raw = {}
            self.forward_tokens(batch)
            final = self.raw['final']
            vectors = torch.cat([final, self.raw['penultimate'].to(final.device)], dim=-1).float()
            pooled.append(F.normalize(vectors, dim=-1))
            flattened.extend(indices)
            self.raw = {}
        restore = torch.argsort(torch.tensor(flattened, device=pooled[0].device))
        return torch.cat(pooled)[restore]

    def forward(self, rows):
        texts, lookup, row_indices = [], {}, []
        for row in rows:
            indices = []
            for text in [row['context'], *row['choices']]:
                if text not in lookup:
                    lookup[text] = len(texts)
                    texts.append(text)
                indices.append(lookup[text])
            row_indices.append(indices)
        values = self.encode(texts)
        if len({len(i) for i in row_indices}) != 1:
            raise ValueError('Group training microbatches by candidate count')
        grouped = values[torch.tensor(row_indices, device=values.device)]
        return self.head(grouped[:, 0], grouped[:, 1:])
