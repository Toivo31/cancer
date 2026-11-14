"""Optional model-server helper. Imports no ML libraries until generation is used.

Capture the reference suffix/head BEFORE attaching or merging decision LoRA.
The first N-7 layers are shared, not copied. Only the unadapted suffix is copied.
"""
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
from collections import OrderedDict
import hashlib
import json


@dataclass
class ReferenceBranch:
    layers: list
    vocabulary_head: object


def encoder_of(full):
    encoder = full.language_model.model
    return encoder.get_base_model() if hasattr(encoder,'get_base_model') else encoder


def capture_unadapted_branch(full, *, last_n=7):
    if hasattr(full.language_model.model,'peft_config'):
        raise ValueError('Capture the original branch before attaching/merging LoRA')
    encoder=encoder_of(full)
    if not 0<last_n<len(encoder.layers): raise ValueError('Invalid reference suffix size')
    head=full.language_model.lm_head
    if type(head).__name__=='Identity': raise ValueError('Original vocabulary head has already been removed')
    branch=ReferenceBranch(deepcopy(list(encoder.layers[-last_n:])),head)
    for module in branch.layers+[head]:
        if hasattr(module,'requires_grad_'):module.requires_grad_(False)
        if hasattr(module,'eval'):module.eval()
    return branch


def prepare_nf4_reference(branch, *, quantize_experts, device='cuda:0', guard=None):
    """Use the SAME expert quantizer as the decision model; dense/Mamba/head stay frozen."""
    for layer in branch.layers:
        if layer.block_type=='moe': layer.mixer.experts=quantize_experts(layer.mixer.experts)
        layer.to(device).eval().requires_grad_(False)
        if guard: guard(layer)
    branch.vocabulary_head.to(device).eval().requires_grad_(False)
    return branch


class SharedNemotronGenerator:
    mode='frozen_pretrained_nemotron'
    def __init__(self, full, tokenizer, reference, *, lock, max_input_tokens=4096):
        self.full,self.tokenizer,self.reference,self.lock=full,tokenizer,reference,lock
        self.max_input_tokens=max_input_tokens
        self.response_cache=OrderedDict()
        self.response_cache_limit=64

    @contextmanager
    def original_branch(self):
        # The identical lock must also guard all decision inference/cache calls.
        with self.lock:
            layers=encoder_of(self.full).layers
            start=len(layers)-len(self.reference.layers)
            old_suffix=list(layers[start:]);old_head=self.full.language_model.lm_head
            try:
                for index,layer in enumerate(self.reference.layers,start):layers[index]=layer
                self.full.language_model.lm_head=self.reference.vocabulary_head
                yield self.full.language_model
            finally:
                for index,layer in enumerate(old_suffix,start):layers[index]=layer
                self.full.language_model.lm_head=old_head

    def generate(self,messages,*,max_new_tokens):
        import torch
        if type(max_new_tokens) is not int or not 1<=max_new_tokens<=512:
            raise ValueError('Invalid remaining generation token budget')
        key=hashlib.sha256(json.dumps([messages,max_new_tokens],sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        with self.lock:
            cached=self.response_cache.pop(key,None)
            if cached is not None:
                self.response_cache[key]=cached
                return dict(cached,cache_hit=True,tokens_generated=0)
        # Show an evidence summary, not a hidden chain of thought. The vocabulary
        # head is pretrained/frozen, not a randomly initialized "untrained head".
        # Encode tool returns as user-side quoted evidence for template portability.
        chat=[dict(role=('user' if m['role']=='tool' else m['role']),content=m['content']) for m in messages]
        prompt=self.tokenizer.apply_chat_template(chat,tokenize=False,add_generation_prompt=True,enable_thinking=False)
        inputs=self.tokenizer(prompt,return_tensors='pt',add_special_tokens=False,truncation=False)
        count=inputs['input_ids'].shape[-1]
        if count+max_new_tokens>self.max_input_tokens:
            raise ValueError('Refinement prompt plus output budget exceeds token limit; no silent truncation')
        with self.original_branch() as language_model, torch.inference_mode():
            device=language_model.get_input_embeddings().weight.device
            batch={name:value.to(device) for name,value in inputs.items() if name in ('input_ids','attention_mask')}
            output=language_model.generate(**batch,max_new_tokens=max_new_tokens,do_sample=False,use_cache=True,
                return_dict_in_generate=False,pad_token_id=self.tokenizer.pad_token_id,eos_token_id=self.tokenizer.eos_token_id)
            added=output[0,count:]
            text=self.tokenizer.decode(added,skip_special_tokens=True)
            result=dict(text=text,tokens_used=int(added.numel()),tokens_generated=int(added.numel()),cache_hit=False)
        with self.lock:
            self.response_cache[key]=result
            while len(self.response_cache)>self.response_cache_limit:self.response_cache.popitem(last=False)
        return dict(result)
