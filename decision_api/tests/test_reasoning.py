import copy
import json
from pathlib import Path
import threading
from types import SimpleNamespace
import unittest
from decision_api.reasoning import refine, settings, PatientTools, DemoGenerator, ROOT
from decision_api.shared_generation import ReferenceBranch, SharedNemotronGenerator, capture_unadapted_branch
from decision_api.server import DecisionAPI, APIError


class Script:
    mode='test_generator'
    def __init__(self, actions):self.actions=iter(actions);self.budgets=[];self.messages=[]
    def generate(self,messages,*,max_new_tokens):
        self.budgets.append(max_new_tokens);self.messages.append(copy.deepcopy(messages))
        action,used=next(self.actions)
        return dict(text=json.dumps(action),tokens_used=used)


class RefinementTests(unittest.TestCase):
    def setUp(self):
        self.request=json.loads((ROOT/'web/score.json').read_text())
        self.patient='sim:demo-record'

    def test_off_by_default_is_exact_noop_and_never_generates_or_retrieves(self):
        gen=Script([]);tools=PatientTools(self.patient)
        result=refine(self.request,options={'additional_prompt':'Give a quick review'},generator=gen,tools=tools)
        self.assertEqual(result['request'],self.request)
        self.assertFalse(result['refinement']['includes_question'])
        self.assertFalse(tools.calls);self.assertFalse(gen.budgets)

    def test_question_instructions_actual_records_and_summary_are_separate(self):
        gen=Script([({'tool':'retrieve_information','arguments':{'patient':self.patient}},20),({'summary':'Two available history records need review.'},10)])
        tools=PatientTools(self.patient)
        result=refine(self.request,options={'enabled':True,'max_tokens':64,'additional_prompt':'Give a quick review'},tools=tools,generator=gen)
        context=result['request']['context'];r=result['refinement']
        self.assertIn(self.request['questions'][0]['text'],gen.messages[0][1]['content'])
        self.assertIn('Give a quick review',context)
        self.assertIn('Actual tool result: retrieve_information(patient)',context)
        self.assertIn('Generated evidence summary (may contain errors',context)
        self.assertNotIn('Future simulator event',context);self.assertNotIn('Withheld simulator truth',context)
        self.assertEqual(r['tokens_used'],30);self.assertEqual(gen.budgets,[64,44])
        self.assertEqual(r['source_ids'],['sim:intake-01','sim:review-02'])
        self.assertEqual(result['request']['questions'],self.request['questions'])

    def test_cached_generation_still_charges_output_budget_and_runs_real_tools(self):
        class Cached:
            mode='frozen_pretrained_nemotron'
            def generate(_,messages,**kwargs):
                action={'summary':'Available evidence only.'} if any(m['role']=='tool' for m in messages) else {'tool':'retrieve_information','arguments':{'patient':self.patient}}
                return dict(text=json.dumps(action),tokens_used=8,tokens_generated=0,cache_hit=True)
        tools=PatientTools(self.patient)
        result=refine(self.request,options=dict(enabled=True,max_tokens=16),tools=tools,generator=Cached())['refinement']
        self.assertEqual(result['tokens_used'],16)
        self.assertEqual(result['tokens_generated'],0)
        self.assertEqual(result['generation_cache_hits'],2)
        self.assertEqual(len(tools.calls),1)
        self.assertEqual(result['stop_reason'],'summary_complete')

    def test_tool_round_and_token_budgets_stop_without_invented_context(self):
        action={'tool':'retrieve_information','arguments':{'patient':self.patient}}
        gen=Script([(action,8),(action,8),(action,8)])
        tools=PatientTools(self.patient)
        result=refine(self.request,options={'enabled':True,'max_tokens':16,'max_tool_calls':1},generator=gen,tools=tools)
        self.assertEqual(len(tools.calls),1)
        self.assertEqual(result['refinement']['stop_reason'],'tool_budget')
        self.assertEqual(result['refinement']['tokens_used'],16)
        gen=Script([(action,8),(action,8)])
        r=refine(self.request,options={'enabled':True,'max_rounds':1},generator=gen,tools=PatientTools(self.patient))
        self.assertEqual(r['refinement']['rounds_used'],1)
        self.assertEqual(len(gen.budgets),1)
        r=refine(self.request,options={'enabled':True,'max_tokens':0},generator=Script([]),tools=PatientTools(self.patient))
        self.assertEqual(r['refinement']['stop_reason'],'token_budget')

    def test_unknown_tools_arguments_and_future_steps_are_rejected(self):
        for action in [{'tool':'write_patient_record','arguments':{'patient':self.patient}},
                       {'tool':'retrieve_information','arguments':{'patient':'sim:other-record'}}]:
            tools=PatientTools(self.patient)
            with self.assertRaises(ValueError):refine(self.request,options={'enabled':True},generator=Script([(action,5)]),tools=tools)
            self.assertFalse(tools.calls)
        with self.assertRaises(ValueError):PatientTools(self.patient,as_of_step=99)
        with self.assertRaises(ValueError):PatientTools('sim:other-record')

    def test_invalid_budget_types_and_overlong_prompts_fail_before_generation(self):
        for cfg in [{'enabled':'yes'},{'max_tokens':True},{'max_tokens':513},{'max_rounds':5},{'max_tool_calls':-1},{'additional_prompt':'x'*2001}]:
            with self.assertRaises(ValueError):settings(cfg)
        request=copy.deepcopy(self.request);request['context']='x'*1500
        gen=Script([])
        with self.assertRaises(ValueError):refine(request,options={'enabled':True,'max_context_chars':1000},generator=gen)
        self.assertFalse(gen.budgets)

    def test_demo_preview_is_explicit_and_does_not_claim_real_token_generation(self):
        tools=PatientTools(self.patient)
        r=refine(self.request,options={'enabled':True},tools=tools,generator=DemoGenerator(self.patient))['refinement']
        self.assertEqual(r['mode'],'scripted_tool_demo');self.assertEqual(r['tokens_used'],0)
        self.assertEqual(r['tool_calls_used'],1)

    def test_incomplete_generation_is_not_appended_as_patient_evidence(self):
        class Truncated:
            mode='test_generator'
            def generate(self,messages,*,max_new_tokens):return dict(text='{"summary":"unfinished',tokens_used=max_new_tokens)
        r=refine(self.request,options={'enabled':True,'max_tokens':16},generator=Truncated())['refinement']
        self.assertEqual(r['stop_reason'],'token_budget')
        self.assertNotIn('unfinished',r['context'])


class SharedBranchTests(unittest.TestCase):
    def make_full(self):
        layers=[SimpleNamespace(name='prefix'),SimpleNamespace(name='decision-tail')]
        return SimpleNamespace(language_model=SimpleNamespace(model=SimpleNamespace(layers=layers),lm_head=SimpleNamespace(name='pretrained-vocabulary-head')))
    def test_capture_before_adaptation_and_keep_prefix_identity(self):
        full=self.make_full();prefix=full.language_model.model.layers[0]
        original_tail=full.language_model.model.layers[-1]
        reference=capture_unadapted_branch(full,last_n=1)
        self.assertIs(full.language_model.model.layers[0],prefix)
        self.assertIsNot(reference.layers[0],original_tail)
        original_tail.name='adapted'
        self.assertEqual(reference.layers[0].name,'decision-tail')
        full.language_model.model.peft_config={}
        with self.assertRaises(ValueError):capture_unadapted_branch(full,last_n=1)

    def test_generation_uses_original_tail_and_head_then_restores_on_error(self):
        full=self.make_full();layers=full.language_model.model.layers
        prefix,decision_tail=layers[0],layers[-1];decision_head=full.language_model.lm_head
        reference=ReferenceBranch([SimpleNamespace(name='original-tail')],SimpleNamespace(name='original-head'))
        lock=threading.Lock();generator=SharedNemotronGenerator(full,None,reference,lock=lock)
        with self.assertRaisesRegex(RuntimeError,'test failure'):
            with generator.original_branch():
                self.assertIs(layers[0],prefix)
                self.assertIs(layers[-1],reference.layers[0]);self.assertIs(full.language_model.lm_head,reference.vocabulary_head)
                self.assertFalse(lock.acquire(blocking=False))
                raise RuntimeError('test failure')
        self.assertIs(layers[-1],decision_tail);self.assertIs(full.language_model.lm_head,decision_head)
        self.assertTrue(lock.acquire(blocking=False));lock.release()


class ReasoningRouteTests(unittest.TestCase):
    def test_scripted_preview_and_fixture_final_decision_keep_distinct_modes(self):
        api=DecisionAPI(mode='fixture')
        body=dict(example_id='pathway',reasoning=dict(enabled=True,max_tokens=128,additional_prompt='Give a quick review'))
        preview=api.call('POST','/refine-preview',body)
        self.assertEqual(preview['delivery'],'scripted_tool_preview')
        self.assertNotIn('decision',preview)
        result=api.call('POST','/reason',body)
        self.assertEqual(result['decision']['backend']['mode'],'fixture')
        self.assertEqual(result['refinement']['mode'],'scripted_tool_demo')
        self.assertIn('Give a quick review',result['refinement']['context'])

    def test_unsupported_native_refinement_is_visible_and_never_starts_a_model(self):
        api=DecisionAPI(api_key='test-secret')
        body=dict(example_id='pathway',reasoning=dict(enabled=True))
        with self.assertRaises(APIError) as caught:api.call('POST','/reason',body)
        self.assertEqual(caught.exception.status,503)
        preview=api.call('POST','/refine-preview',body)
        self.assertEqual(preview['refinement']['mode'],'scripted_tool_demo')
