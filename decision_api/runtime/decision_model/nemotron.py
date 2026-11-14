"""NVIDIA challenge model: Super VL 120B, frozen vision, final-seven LoRA."""
import re
import torch
from torch import nn
from .model import block_list, audit_trainable
from .gemma import GemmaDecisionModel


def guard_cuda_forward(module):
    """Mamba/Triton must launch on the device owning this sharded module.

    Accelerate moves tensors but does not change CUDA's current device. Some
    custom kernels use the latter; an explicit guard avoids cross-device stream
    races when a frozen model spans multiple GPUs.
    """
    if getattr(module,'_decision_device_guard',False):return
    original=module.forward
    def guarded(*args,**kwargs):
        device=next(module.parameters()).device
        if device.type=='cuda':
            with torch.cuda.device(device):return original(*args,**kwargs)
        return original(*args,**kwargs)
    module.forward=guarded
    module._decision_device_guard=True


class FusedProjectionLoRA(nn.Module):
    """Weight parametrization so Mamba's fused kernel sees the adapted weight."""
    def __init__(self,weight,rank,alpha):
        super().__init__()
        self.lora_A=nn.Linear(weight.shape[1],rank,bias=False,device=weight.device,dtype=torch.float32)
        self.lora_B=nn.Linear(rank,weight.shape[0],bias=False,device=weight.device,dtype=torch.float32)
        nn.init.kaiming_uniform_(self.lora_A.weight,a=5**.5)
        nn.init.zeros_(self.lora_B.weight)
        self.scale=alpha/rank

    def forward(self,original):
        return original+(self.lora_B.weight@self.lora_A.weight).to(original.dtype)*self.scale


def nemotron_targets(encoder,last_n=7):
    prefix,layers=block_list(encoder)
    blocks=list(range(len(layers)-last_n,len(layers)))
    pattern=re.compile(r'^'+prefix+r'\.(\d+)\.')
    modules=[];parameters=[]
    for name,module in encoder.named_modules():
        m=pattern.match(name)
        if m and int(m[1]) in blocks and isinstance(module,nn.Linear):
            if name.rsplit('.',1)[-1] not in ('gate','router','out_proj'):
                modules.append(name)
    for name,p in encoder.named_parameters():
        m=pattern.match(name)
        if m and int(m[1]) in blocks and 'experts' in name and p.ndim==3:
            parameters.append(name)
    coverage={int(pattern.match(name)[1]) for name in modules+parameters}
    if coverage!=set(blocks):raise ValueError('Incomplete final-block adapter coverage')
    return sorted(modules),sorted(parameters),blocks,prefix


def attach_nemotron_adapters(full,config):
    from peft import LoraConfig,get_peft_model
    full.requires_grad_(False)
    encoder=full.language_model.model
    modules,parameters,blocks,prefix=nemotron_targets(encoder,config['adapt_last_n'])
    fused_targets=[]
    for block in blocks:
        mixer=encoder.layers[block].mixer
        if getattr(encoder.layers[block],'block_type',None) in ('mamba','linear_attention'):
            projection=mixer.out_proj
            torch.nn.utils.parametrize.register_parametrization(projection,'weight',
                FusedProjectionLoRA(projection.weight,config['rank'],config['lora_alpha']))
            fused_targets.append(f'layers.{block}.mixer.out_proj.weight')
    encoder=get_peft_model(encoder,LoraConfig(r=config['rank'],lora_alpha=config['lora_alpha'],
        lora_dropout=0,bias='none',
        target_modules='(?:'+'|'.join(re.escape(t) for t in modules)+')',
        target_parameters=parameters or None))
    # PEFT freezes parameters not registered under its adapter namespace.
    # Re-enable our explicitly audited fused-weight adapter factors only.
    for block in blocks:
        mixer=encoder.get_base_model().layers[block].mixer
        if hasattr(mixer,'out_proj') and torch.nn.utils.parametrize.is_parametrized(mixer.out_proj,'weight'):
            mixer.out_proj.parametrizations.weight[0].requires_grad_(True)
    full.language_model.model=encoder
    trainable=audit_trainable(encoder,blocks,prefix)
    for name,p in full.named_parameters():
        if p.requires_grad and not (name.startswith('language_model.model.') and '.lora_' in name):
            raise ValueError(f'Unexpected trainable parameter: {name}')
    return dict(blocks=blocks,module_targets=modules,parameter_targets=parameters,fused_projection_targets=fused_targets,
                adapter_parameters=sum(trainable.values()),vision_trainable_parameters=0,
                projector_trainable_parameters=0)


def load_nemotron(config,devices=None):
    from transformers import AutoModel,AutoProcessor
    if config['quantization']!='none':
        raise ValueError('Initial Super VL baseline uses sharded BF16; raw MoE parameters are not automatically NF4 linears')
    devices=devices or list(range(torch.cuda.device_count()))
    if not devices:raise ValueError('CUDA GPUs required')
    placement='balanced'
    if len(devices)==8:
        # Keep the frozen prefix on GPUs 0–3 and spread the four adapted MoE
        # blocks over GPUs 4–7. PEFT expert updates materialize delta weights;
        # putting all tail experts on one GPU would waste the available memory.
        placement={'vision_model':devices[0],'vision_projector':devices[0],
                   'language_model.model.embeddings':devices[0],
                   'language_model.model.norm_f':devices[7],
                   'language_model.lm_head':devices[7]}
        small_cards=config.get('gpu_layout')=='8x48gb'
        for index in range(88):
            if small_cards:
                # Six ~34-GiB prefix shards; two tail shards leave room for
                # expert LoRA materialization, gradients and Adam state.
                if index<=80:gpu=next(g for g,end in enumerate((13,27,40,53,66,80)) if index<=end)
                else:gpu=6+(index-81)//4
            elif index<=80:gpu=min(3,index//20)
            else:gpu=4+(index-81)//2
            placement[f'language_model.model.layers.{index}']=devices[gpu]
    kwargs=dict(revision=config['revision'],code_revision=config['revision'],
                trust_remote_code=True,dtype=torch.bfloat16,
                device_map=placement,max_memory={i:config.get('gpu_max_memory','84GiB') for i in devices})
    full=AutoModel.from_pretrained(config['model'],**kwargs)
    placement=getattr(full,'hf_device_map',{})
    if any(v in ('cpu','disk') for v in placement.values()):
        raise ValueError('Baseline requires GPU-resident weights; no silent CPU/disk offload')
    processor=AutoProcessor.from_pretrained(config['model'],revision=config['revision'],trust_remote_code=True)
    processor.tokenizer.padding_side='left'
    if processor.tokenizer.pad_token_id is None:processor.tokenizer.pad_token=processor.tokenizer.eos_token
    audit=attach_nemotron_adapters(full,config)
    for layer in full.language_model.model.get_base_model().layers:guard_cuda_forward(layer)
    guard_cuda_forward(full.language_model.model.get_base_model().norm_f)
    guard_cuda_forward(full.vision_model);guard_cuda_forward(full.vision_projector)
    # The custom head consumes representations; vocabulary logits are unused.
    # Preserve the official multimodal merge without allocating vocabulary logits.
    generation_head=full.language_model.lm_head if config.get('enable_context_refinement') else None
    full.language_model.lm_head=nn.Identity()
    tail=full.language_model.model.get_base_model().layers[-1]
    device=next(tail.parameters()).device
    model=NemotronDecisionModel(full,processor,config).to_head_device(device)
    if generation_head is not None:
        model.generation_lm_head=generation_head.requires_grad_(False)
    audit.update(device_map=placement,head_parameters=model.head.parameter_count)
    if model.head.parameter_count!=config['expected_head_parameters']:
        raise ValueError('Head size differs from plan')
    if config.get('expected_adapter_parameters') and audit['adapter_parameters']!=config['expected_adapter_parameters']:
        raise ValueError('Adapter size differs from plan')
    return model,processor,audit


class NemotronDecisionModel(GemmaDecisionModel):
    def __init__(self,full,processor,config):
        # Adapt the shared independent-encoding implementation, retaining the
        # NVIDIA outer model for image-token merging and frozen C-RADIO encoding.
        from .model import DecisionModel
        import threading
        DecisionModel.__init__(self,full.language_model.model,processor.tokenizer,config)
        self.multimodal=full;self.processor=processor;self._prediction_lock=threading.Lock()
        from collections import OrderedDict
        self.prefix_cache=OrderedDict();self.prefix_cache_bytes=0
        self.prefix_cache_hits=0;self.prefix_cache_misses=0
        self.train(False)

    def train(self,mode=True):
        super().train(mode)
        if hasattr(self,'multimodal'):
            for name in ('vision_model','vision_projector'):
                module=getattr(self.multimodal,name,None)
                if module is not None:module.eval()
            # Prefix activations are reusable only with fixed weights and
            # fixed stochastic behavior, including Mamba's train/eval path.
            for block in self.encoder.get_base_model().layers[:-7]:block.eval()
        return self

    def forward_tokens(self,batch,multimodal=False,cache_key=None):
        import hashlib
        limit=self.config.get('prefix_cache_bytes',0)
        if not limit:
            return (self.multimodal if multimodal else self.encoder)(**batch,use_cache=False)
        if cache_key is None:
            material=b''.join(str(tuple(batch[k].shape)).encode()+
                              batch[k].detach().cpu().contiguous().numpy().tobytes()
                              for k in ('input_ids','attention_mask'))
            cache_key=hashlib.sha256(material).hexdigest()
        else:cache_key='image:'+cache_key
        layers=self.encoder.get_base_model().layers
        tail=layers[-7:]
        if any(layer.block_type not in ('moe','linear_attention','mamba') for layer in tail):
            raise ValueError('Cached-tail runner supports this audited MoE/Mamba suffix only')
        if cache_key in self.prefix_cache:
            self.prefix_cache_hits+=1
            prefix=self.prefix_cache.pop(cache_key);self.prefix_cache[cache_key]=prefix
        else:
            self.prefix_cache_misses+=1
            class PrefixReady(Exception):
                def __init__(self,hidden):self.hidden=hidden
            def capture_prefix(module,args,kwargs):
                hidden=args[0] if args else kwargs['hidden_states']
                # A cache first filled during inference must still be usable
                # later in training, where the tail saves these inputs for grad.
                with torch.inference_mode(False),torch.no_grad():
                    saved=hidden.detach().to('cpu',copy=True)
                raise PrefixReady(saved)
            handle=tail[0].register_forward_pre_hook(capture_prefix,with_kwargs=True)
            try:
                with torch.no_grad():
                    (self.multimodal if multimodal else self.encoder)(**batch,use_cache=False)
                raise RuntimeError('Prefix capture did not execute')
            except PrefixReady as captured:prefix=captured.hidden
            finally:handle.remove()
            size=prefix.numel()*prefix.element_size()
            if size<=limit:
                while self.prefix_cache and self.prefix_cache_bytes+size>limit:
                    _,old=self.prefix_cache.popitem(last=False)
                    self.prefix_cache_bytes-=old.numel()*old.element_size()
                self.prefix_cache[cache_key]=prefix;self.prefix_cache_bytes+=size
        hidden=prefix.to(next(tail[0].parameters()).device)
        for layer in tail:
            mask=batch['attention_mask'] if layer.block_type in ('linear_attention','mamba') else None
            hidden=layer(hidden,attention_mask=mask,past_key_values=None,use_cache=False)
        return hidden

    def encode_context(self,context,images=()):
        if not images:return self.encode([context])
        from PIL import Image
        from pathlib import Path
        loaded=[]
        for value in images:
            if isinstance(value,(str,Path)):
                with Image.open(value) as image:loaded.append(image.convert('RGB'))
            else:loaded.append(value.convert('RGB'))
        text='\n'.join([self.processor.image_token]*len(loaded))+'\n'+context
        inputs=self.processor(text=text,images=loaded,return_tensors='pt')
        if inputs['input_ids'].shape[-1]>self.config['max_input_tokens']:
            raise ValueError('Image/text input too long; no silent truncation')
        device=next(self.encoder.parameters()).device
        inputs=inputs.to(device)
        # Processor bookkeeping is not a model input.
        for key in ('num_patches','num_tokens'):inputs.pop(key,None)
        if 'pixel_values' in inputs:
            pixels=inputs['pixel_values'];dtype=next(self.multimodal.vision_model.parameters()).dtype
            if isinstance(pixels,(list,tuple)):
                inputs['pixel_values']=[v.to(dtype=dtype) for v in pixels]
            else:inputs['pixel_values']=pixels.to(dtype=dtype)
        mask=inputs['attention_mask'].bool()
        pos=torch.arange(mask.shape[1],device=device).expand_as(mask)
        self.pool_indices=pos.masked_fill(~mask,-1).max(-1).values
        self.raw={}
        import hashlib
        cache_key=hashlib.sha256(context.encode()+b''.join(str(image.size).encode()+
            hashlib.sha256(image.tobytes()).digest() for image in loaded)).hexdigest()
        self.forward_tokens(inputs,multimodal=True,cache_key=cache_key)
        final=self.raw['final'];penultimate=self.raw['penultimate'].to(final.device)
        result=torch.nn.functional.normalize(torch.cat([final,penultimate],-1).float(),dim=-1)
        self.raw={}
        return result
