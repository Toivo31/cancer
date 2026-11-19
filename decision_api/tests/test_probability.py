import unittest
from unittest.mock import patch
from decision_api.probability import predict_proba, STEP, WEIGHTS_SHA256

class ProbabilityTests(unittest.TestCase):
    def reply(self,step=STEP):
        return dict(decision=dict(id='a'*32,backend=dict(step=step,checkpoint_sha256=WEIGHTS_SHA256),questions=[dict(choices=[dict(id='choice-1',score=.3),dict(id='choice-0',score=.7)])]),refinement=dict(enabled=False))
    def test_order_budget_and_default_off(self):
        with patch('decision_api.probability._hosted',return_value=self.reply()) as call:
            self.assertEqual(predict_proba('Visible context','Which?',['A','B']),[.7,.3])
            self.assertFalse(call.call_args.args[0]['reasoning']['enabled'])
            r=predict_proba('Visible context','Which?',['A','B'],reasoning_budget=128,additional_prompt='Be concise',return_details=True,candidate_format='inline')
            cfg=call.call_args.args[0]['reasoning']
            self.assertTrue(cfg['enabled']);self.assertEqual(cfg['max_tokens'],128);self.assertEqual(cfg['max_tool_calls'],0)
            self.assertEqual(r['backend']['step'],2881)
            self.assertEqual(call.call_args.args[0]['request']['questions'][0]['candidate_format'],'inline')
    def test_invalid_budget_and_old_checkpoint_are_rejected(self):
        with patch('decision_api.probability._hosted',return_value=self.reply(2350)) as call:
            for budget in (True,-1,513,1.5):
                with self.assertRaises(ValueError):predict_proba('Context','Q',['A','B'],reasoning_budget=budget)
            self.assertFalse(call.called)
            with self.assertRaises(RuntimeError):predict_proba('Context','Q',['A','B'])
