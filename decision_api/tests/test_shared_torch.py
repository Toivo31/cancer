"""Optional CPU tensor checks for owners with Torch installed; no GPU/HF downloads."""
import importlib.util
import threading
import unittest
from decision_api.shared_generation import capture_unadapted_branch,SharedNemotronGenerator


@unittest.skipUnless(importlib.util.find_spec('torch'), 'Optional Torch runtime is not installed')
class TensorSharingTests(unittest.TestCase):
    def make_full(self):
        import torch
        from torch import nn
        class Encoder(nn.Module):
            def __init__(self):
                super().__init__();self.layers=nn.ModuleList([nn.Linear(4,4),nn.Linear(4,4),nn.Linear(4,4)])
                self.embedding=nn.Embedding(16,4)
            def forward(self,x):
                for layer in self.layers:x=layer(x)
                return x
        class Language(nn.Module):
            def __init__(self):super().__init__();self.model=Encoder();self.lm_head=nn.Linear(4,5)
            def forward(self,x):return self.lm_head(self.model(x))
            def get_input_embeddings(self):return self.model.embedding
            def generate(self,input_ids,**kwargs):
                assert self.lm_head is self.original_head
                added=torch.ones((1,kwargs['max_new_tokens']),dtype=input_ids.dtype,device=input_ids.device)
                return torch.cat([input_ids,added],dim=1)
        class Full(nn.Module):
            def __init__(self):super().__init__();self.language_model=Language()
        return Full().eval().requires_grad_(False)

    def test_original_logits_shared_prefix_and_restored_decision_logits(self):
        import torch
        from torch import nn
        full=self.make_full();x=torch.randn(2,4)
        original=full.language_model(x).detach().clone()
        reference=capture_unadapted_branch(full,last_n=1)
        prefix=full.language_model.model.layers[0].weight
        with torch.no_grad():full.language_model.model.layers[-1].weight.add_(.5)
        full.language_model.lm_head=nn.Identity()
        decision=full.language_model(x).detach().clone()
        runner=SharedNemotronGenerator(full,None,reference,lock=threading.Lock())
        with runner.original_branch():
            self.assertIs(full.language_model.model.layers[0].weight,prefix)
            torch.testing.assert_close(full.language_model(x),original)
        torch.testing.assert_close(full.language_model(x),decision)
        self.assertFalse(any(p.requires_grad for layer in reference.layers for p in layer.parameters()))

    def test_native_driver_counts_only_new_tokens_and_restores_head(self):
        import torch
        from torch import nn
        full=self.make_full();reference=capture_unadapted_branch(full,last_n=1)
        full.language_model.original_head=reference.vocabulary_head
        full.language_model.lm_head=nn.Identity()
        class Tokenizer:
            pad_token_id=0;eos_token_id=1
            def apply_chat_template(self,messages,**kwargs):
                assert kwargs['enable_thinking'] is False
                return 'prompt'
            def __call__(self,prompt,**kwargs):return dict(input_ids=torch.tensor([[2,3]]),attention_mask=torch.ones((1,2),dtype=torch.long))
            def decode(self,tokens,**kwargs):return '{"summary":"Available evidence only."}'
        runner=SharedNemotronGenerator(full,Tokenizer(),reference,lock=threading.Lock(),max_input_tokens=16)
        output=runner.generate([dict(role='user',content='Case')],max_new_tokens=3)
        self.assertEqual(output['tokens_used'],3)
        self.assertIsInstance(full.language_model.lm_head,nn.Identity)
        with self.assertRaises(ValueError):runner.generate([],max_new_tokens=17)

    def test_generation_cache_reuses_only_identical_prompt_and_budget(self):
        from torch import nn
        full=self.make_full();reference=capture_unadapted_branch(full,last_n=1)
        full.language_model.original_head=reference.vocabulary_head
        full.language_model.lm_head=nn.Identity()
        calls=[];original=full.language_model.generate
        def generate(**kwargs):calls.append(1);return original(**kwargs)
        full.language_model.generate=generate
        import torch
        class Tokenizer:
            pad_token_id=0;eos_token_id=1
            def apply_chat_template(self,*args,**kwargs):return 'prompt'
            def __call__(self,*args,**kwargs):return dict(input_ids=torch.tensor([[2,3]]))
            def decode(self,*args,**kwargs):return '{"summary":"Visible facts only."}'
        runner=SharedNemotronGenerator(full,Tokenizer(),reference,lock=threading.Lock())
        messages=[dict(role='user',content='patient A source version1')]
        first=runner.generate(messages,max_new_tokens=3)
        again=runner.generate(messages,max_new_tokens=3)
        self.assertEqual((first['tokens_generated'],again['tokens_generated']),(3,0))
        self.assertTrue(again['cache_hit']);self.assertEqual(len(calls),1)
        runner.generate([dict(role='user',content='patient A source version2')],max_new_tokens=3)
        runner.generate(messages,max_new_tokens=2)
        self.assertEqual(len(calls),3)
        self.assertIsInstance(full.language_model.lm_head,nn.Identity)
