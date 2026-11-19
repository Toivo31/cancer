"""Nemotron-Birch checkpoint2881 probability helper; hosted mode uses only stdlib."""
from pathlib import Path
import json
import math
import re
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError

STEP = 2881
WEIGHTS_SHA256 = 'ec2bc28fd13d1933b6d18bee23e23928f326b24940467db7db4729426e7de16f'
STATE_SHA256 = 'dbeec932ba150caf14b083553607531a495afaa088619e15a22e19b91da88875'
API_URL = 'https://cancer123--birch-decision-1138-demo.us-east.modal.run'


def _hosted(payload, api_url, timeout):
    deadline=time.monotonic()+timeout
    path='/reason'
    while True:
        remaining=deadline-time.monotonic()
        if remaining<=0:raise TimeoutError(f'Job {path} may still be running; poll it before resubmitting')
        request=Request(api_url.rstrip('/')+'/api/decision'+path,
            data=None if payload is None else json.dumps(payload).encode(),
            headers={'Content-Type':'application/json'})
        try:
            with urlopen(request,timeout=min(30,remaining)) as response:result=json.load(response)
        except HTTPError as error:
            raise RuntimeError(f'Birch HTTP {error.code}: {error.read(4000).decode()}') from None
        if result.get('delivery')!='pending':return result
        path=result.get('status_url','')
        if not re.fullmatch(r'/jobs/[a-f0-9]{32}',path):raise RuntimeError('Invalid Birch job URL')
        payload=None
        time.sleep(min(1,max(0,deadline-time.monotonic())))


def load_model(checkpoint_dir=None, *, enable_reasoning=True, revision=None):
    """Load verified local NF4 experts on one96GB-class CUDA GPU (~78.5GiB used); needs ~320GiB host RAM.

    Download this repository's snapshot if checkpoint_dir is omitted. The pinned
    NVIDIA base is downloaded separately by Transformers. See INFERENCE.md.
    """
    if checkpoint_dir is None:
        from huggingface_hub import snapshot_download
        checkpoint_dir=snapshot_download('Toivo31/Nemotron-Birch',revision=revision,
            allow_patterns=['state.json','sha256.json','trainable.safetensors','birch_runtime/**'])
    root=Path(checkpoint_dir).resolve()
    manifest=json.loads((root/'sha256.json').read_text())
    if manifest.get('state.json')!=STATE_SHA256 or manifest.get('trainable.safetensors')!=WEIGHTS_SHA256:
        raise ValueError('Expected the published immutable checkpoint2881 manifest')
    import sys
    sys.path.insert(0,str(root))
    from birch_runtime.inference_quantized import load_nf4_predictor
    from birch_runtime.inference_backend import CachedPredictor
    model=load_nf4_predictor(root,enable_refinement=enable_reasoning)
    record=json.loads((root/'state.json').read_text())
    if record['state']['step']!=STEP:raise ValueError('Unexpected checkpoint step')
    return CachedPredictor(model,dict(step=STEP,checkpoint_sha256=WEIGHTS_SHA256,
        model=record['config']['model'],revision=record['config']['revision'],training_identity=record['identity'],
        quantization='nf4-experts-merged-adapters'))


def predict_proba(context, question, choices, *, reasoning_budget=0, additional_prompt='',
                  model=None, api_url=API_URL, timeout=660, return_details=False, candidate_format='newline'):
    """Return relative probabilities in the SAME order as choices.

    reasoning_budget=0 skips generation; 1..512 bounds total refinement output
    tokens across turns (including cached output). It is not a time budget.
    The question/choices/instructions are appended automatically when enabled.
    With model=None, call the hosted demo without credentials. Pass the result
    of load_model() for local inference with no prediction requests to the API.
    Generated summaries are fallible; probabilities are not calibrated risks.
    """
    if not isinstance(context,str) or not context.strip() or len(context)>12000:raise ValueError('context must contain1..12000 characters')
    if not isinstance(question,str) or not question.strip() or len(question)>2000:raise ValueError('question must contain1..2000 characters')
    if not isinstance(choices,(list,tuple)) or not 2<=len(choices)<=8 or any(not isinstance(c,str) or not c.strip() or len(c)>2000 for c in choices):raise ValueError('Provide2..8 nonempty choice texts, each at most2000 characters')
    if type(reasoning_budget) is not int or not 0<=reasoning_budget<=512:raise ValueError('reasoning_budget must be an integer0..512')
    if not isinstance(additional_prompt,str) or len(additional_prompt)>2000:raise ValueError('additional_prompt must be at most2000 characters')
    if not isinstance(timeout,(int,float)) or isinstance(timeout,bool) or not math.isfinite(timeout) or timeout<=0:raise ValueError('timeout must be positive and finite')
    if candidate_format not in ('newline','inline'):raise ValueError('candidate_format must be newline or inline')
    request=dict(context=context,questions=[dict(id='question',text=question,candidate_format=candidate_format,
        choices=[dict(id=f'choice-{i}',text=c) for i,c in enumerate(choices)])])
    options=dict(enabled=reasoning_budget>0,max_tokens=reasoning_budget,max_tool_calls=0,additional_prompt=additional_prompt)
    if model is None:
        result=_hosted(dict(request=request,reasoning=options),api_url,timeout)
        decision=result['decision'];backend=decision['backend'];refinement=result['refinement']
        scored={c['id']:c['score'] for c in decision['questions'][0]['choices']}
        if set(scored)!={f'choice-{i}' for i in range(len(choices))}:raise RuntimeError('Returned choice IDs differ from the request')
        probabilities=[scored[f'choice-{i}'] for i in range(len(choices))]
        decision_id=decision['id']
    else:
        from birch_runtime.reasoning import refine
        generator=getattr(model.model,'base_generator',None)
        if reasoning_budget and generator is None:raise ValueError('Load with enable_reasoning=True before enabling a reasoning budget')
        result=refine(request,options=options,generator=generator)
        refinement=result['refinement'];backend=model.metadata;decision_id=None
        probabilities=model.predict(result['request']['context'],[dict(question=question,choices=list(choices),candidate_format=candidate_format)])['probabilities'][0]
    if backend.get('step')!=STEP or backend.get('checkpoint_sha256')!=WEIGHTS_SHA256:raise RuntimeError('Expected checkpoint2881; refusing a different model identity')
    if len(probabilities)!=len(choices) or any(not isinstance(p,(int,float)) or not math.isfinite(p) or not 0<=p<=1 for p in probabilities) or not math.isclose(sum(probabilities),1,abs_tol=1e-4):raise RuntimeError('Invalid probability distribution')
    if return_details:return dict(probabilities=probabilities,choices=list(choices),backend=backend,refinement=refinement,decision_id=decision_id,requires_review=True,score_kind='candidate_softmax')
    return probabilities
