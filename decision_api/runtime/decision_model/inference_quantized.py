"""Inference-only NF4 experts; preserve the pinned base and trained decision head.

Restore checkpoint adapters on CPU, merge them into that exact BF16 base, then
quantize routed experts only. Fused Mamba projections, routers, vision, embeddings
and the decision head retain their original precision. Never used by training.
"""
import hashlib
import json
from pathlib import Path
import torch
from torch import nn


class NF4Experts(nn.Module):
    """Native Nemotron expert routing with independently packed expert matrices."""
    def __init__(self, source, device='cuda:0', *, linear_factory=None):
        super().__init__()
        self.num_experts = source.num_experts
        self.act_fn = source.act_fn
        if linear_factory is None:
            import bitsandbytes as bnb
            def linear_factory(weight):
                # Avoid randomly initializing tens of thousands of matrices
                # that are immediately replaced by the actual checkpoint.
                with torch.device('meta'):
                    layer = bnb.nn.Linear4bit(weight.shape[1], weight.shape[0], bias=False,
                        compute_dtype=torch.bfloat16, compress_statistics=True, quant_type='nf4')
                layer.weight = bnb.nn.Params4bit(weight.detach().contiguous(), requires_grad=False,
                    compress_statistics=True, quant_type='nf4')
                return layer.to(device)
        self.up = nn.ModuleList([linear_factory(weight) for weight in source.up_proj.unbind(0)])
        self.down = nn.ModuleList([linear_factory(weight) for weight in source.down_proj.unbind(0)])

    def forward(self, hidden_states, top_k_index, top_k_weights):
        result = torch.zeros_like(hidden_states, dtype=top_k_weights.dtype)
        with torch.no_grad():
            mask = torch.nn.functional.one_hot(top_k_index, num_classes=self.num_experts+1).permute(2, 1, 0)
            hits = (mask.sum(dim=(-1, -2)) > 0).nonzero().squeeze(-1)
        for index in hits:
            expert = index.item()
            position, token = torch.where(mask[expert])
            value = self.down[expert](self.act_fn(self.up[expert](hidden_states[token])))
            value = value * top_k_weights[token, position, None]
            result.index_add_(0, token, value.to(result.dtype))
        return result.to(hidden_states.dtype)


def load_nf4_predictor(checkpoint, *, enable_refinement=False):
    from safetensors.torch import load_file
    from transformers import AutoModel, AutoProcessor
    from .nemotron import attach_nemotron_adapters, NemotronDecisionModel, guard_cuda_forward
    if torch.cuda.device_count() != 1:
        raise ValueError('The NF4 inference preflight requires exactly one GPU')
    checkpoint = Path(checkpoint)
    manifest = json.loads((checkpoint/'sha256.json').read_text())
    for name in ('state.json', 'trainable.safetensors'):
        with (checkpoint/name).open('rb') as source:
            if hashlib.file_digest(source, 'sha256').hexdigest() != manifest[name]:
                raise ValueError('Checkpoint checksum mismatch: '+name)
    record = json.loads((checkpoint/'state.json').read_text())
    config = dict(record['config'], prefix_cache_bytes=0, encoder_microbatch_size=1, padded_token_budget=4096)
    if config['architecture'] != 'nemotron_super_vl' or config['quantization'] != 'none':
        raise ValueError('Expected the original BF16 Nemotron decision checkpoint')
    # CPU staging avoids needing the full BF16 base in GPU memory during conversion.
    full = AutoModel.from_pretrained(config['model'], revision=config['revision'],
        code_revision=config['revision'], trust_remote_code=True, dtype=torch.bfloat16,
        device_map={'': 'cpu'}, low_cpu_mem_usage=True)
    processor = AutoProcessor.from_pretrained(config['model'], revision=config['revision'], trust_remote_code=True)
    processor.tokenizer.padding_side = 'left'
    if processor.tokenizer.pad_token_id is None:
        processor.tokenizer.pad_token = processor.tokenizer.eos_token
    reference = None
    if enable_refinement:
        from decision_api.shared_generation import capture_unadapted_branch
        reference = capture_unadapted_branch(full, last_n=config['adapt_last_n'])
    audit = attach_nemotron_adapters(full, config)
    full.language_model.lm_head = nn.Identity()
    model = NemotronDecisionModel(full, processor, config).to_head_device('cpu')
    if model.head.parameter_count != config['expected_head_parameters']:
        raise ValueError('Head size differs from checkpoint')
    if audit['adapter_parameters'] != config['expected_adapter_parameters']:
        raise ValueError('Adapter size differs from checkpoint')
    parameters = {name: parameter for name, parameter in model.named_parameters() if parameter.requires_grad}
    saved = load_file(str(checkpoint/'trainable.safetensors'), device='cpu')
    if set(parameters) != set(saved):
        raise ValueError('Checkpoint/architecture trainable-name mismatch')
    with torch.no_grad():
        for name, value in saved.items():
            parameters[name].copy_(value.to(parameters[name].dtype))
    del saved, parameters
    # PEFT merges expert parameter adapters and ordinary linear adapters. Retain
    # the wrapper references used by the existing encoder/pooling implementation.
    model.encoder.merge_and_unload(safe_merge=True)
    layers = model.encoder.get_base_model().layers
    for layer in layers:
        mixer = layer.mixer
        if hasattr(mixer, 'out_proj') and torch.nn.utils.parametrize.is_parametrized(mixer.out_proj, 'weight'):
            torch.nn.utils.parametrize.remove_parametrizations(mixer.out_proj, 'weight', leave_parametrized=True)
    model.requires_grad_(False)
    converted = 0
    for layer in layers:
        if layer.block_type == 'moe':
            layer.mixer.experts = NF4Experts(layer.mixer.experts)
            converted += 1
    if not converted:
        raise ValueError('No expert modules quantized; refusing an uncompressed GPU load')
    model.to('cuda:0')
    for layer in layers:
        guard_cuda_forward(layer)
    guard_cuda_forward(model.encoder.get_base_model().norm_f)
    guard_cuda_forward(full.vision_model)
    guard_cuda_forward(full.vision_projector)
    if reference is not None:
        from decision_api.shared_generation import prepare_nf4_reference, SharedNemotronGenerator
        prepare_nf4_reference(reference, quantize_experts=NF4Experts, guard=guard_cuda_forward)
        model.base_generator = SharedNemotronGenerator(full, processor.tokenizer, reference,
            lock=model._prediction_lock, max_input_tokens=config['max_input_tokens'])
    model.eval()
    print(f'NF4 experts loaded: {converted} MoE layers; GPU allocated {torch.cuda.memory_allocated()/1024**3:.2f} GiB')
    return model
