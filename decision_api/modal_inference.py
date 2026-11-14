"""Separate, scale-to-zero inference for the explicitly selected HF checkpoint.

Stage weights on CPU: python -m modal run deploy/modal_inference.py
Deploy API + /demo:   python -m modal deploy deploy/modal_inference.py
No training instance, source, checkpoint or timer is modified.
"""
import os
from pathlib import Path
import modal

ROOT = Path(__file__).resolve().parents[1]
BUCKET = 'Toivo31/project-birch-03'
PREFIX = 'birch04-run-v1/checkpoint-00001138'
MODEL = 'nvidia/NVIDIA-Nemotron-3.5-Super-VL-120B-A12B-BF16'
REVISION = 'fb0ee0bc6b3f70342afd8d84cb80dbadbaa8a1fe'
STATE_SHA256 = '18af7a9b7b979cf98a11fc9f8012e3a1cc04707d77e9dbb389a172da0d2d7ff7'
WEIGHTS_SHA256 = '43ff62d125eef476fffbd32aaf43ee9130a5ec7212c973592aa91625b3e883a5'
CHECKPOINT = Path('/weights/checkpoint-00001138')
app = modal.App('birch-decision-1138')
weights = modal.Volume.from_name('birch-inference-weights', create_if_missing=True)
data = modal.Volume.from_name('birch-inference-reviews', create_if_missing=True)
secret = modal.Secret.from_name('birch-inference', required_keys=['HF_TOKEN', 'BIRCH_API_KEY'])

stage_image = (modal.Image.debian_slim(python_version='3.12')
    .pip_install('huggingface_hub==2.4.0')
    .env({'HF_HOME': '/weights/hf'}))
image = (modal.Image.from_registry('nvidia/cuda:12.8.1-cudnn-devel-ubuntu24.04', add_python='3.12')
    .apt_install('build-essential', 'git', 'ninja-build')
    .pip_install('torch==2.10.0', 'torchvision==0.25.0', index_url='https://download.pytorch.org/whl/cu128')
    .pip_install('transformers==5.23.0', 'peft==0.21.3', 'accelerate==1.15.0',
                 'huggingface_hub==2.4.0', 'safetensors==0.8.0', 'pillow==13.0.0',
                 'einops', 'ninja', 'packaging', 'kernels', 'timm',
                 'bitsandbytes==0.48.2',
                 'fastapi==0.162.7', 'uvicorn==0.54.0', 'pydantic==2.14.3')
    .env({'HF_HOME': '/weights/hf', 'OMP_NUM_THREADS': '4', 'MAX_JOBS': '8',
          'TORCH_CUDA_ARCH_LIST': '12.0', 'PYTHONPATH': '/app'})
    .pip_install('mamba-ssm==2.3.2.post1', 'causal-conv1d==1.7.0', extra_options='--no-build-isolation')
    # Include only reviewed inference source/examples, never outputs, credentials,
    # datasets, training deployments or the working tree's other files.
    .add_local_dir(ROOT/'decision_api/runtime/decision_model', '/app/decision_model', ignore=['__pycache__', '*.pyc'])
    .add_local_dir(ROOT/'decision_api/runtime/examples', '/app/examples')
    .add_local_file(ROOT/'decision_api/__init__.py', '/app/decision_api/__init__.py')
    .add_local_file(ROOT/'decision_api/shared_generation.py', '/app/decision_api/shared_generation.py')
    .add_local_file(ROOT/'decision_api/reasoning.py', '/app/decision_api/reasoning.py')
    .add_local_file(ROOT/'decision_api/native_refinement.py', '/app/decision_api/native_refinement.py')
    .add_local_file(ROOT/'decision_api/patient_records.json', '/app/decision_api/patient_records.json'))


def verify_checkpoint(path):
    import hashlib
    import json
    expected = {'state.json': STATE_SHA256, 'trainable.safetensors': WEIGHTS_SHA256}
    manifest = json.loads((path/'sha256.json').read_text())
    for name, digest in expected.items():
        if manifest.get(name) != digest:
            raise ValueError('Pinned checkpoint manifest mismatch: '+name)
        with (path/name).open('rb') as source:
            actual = hashlib.file_digest(source, 'sha256').hexdigest()
        if actual != digest:
            raise ValueError('Pinned checkpoint content mismatch: '+name)
    state = json.loads((path/'state.json').read_text())
    if (state['state']['step'] != 1138 or state['config']['model'] != MODEL
            or state['config']['revision'] != REVISION):
        raise ValueError('Unexpected checkpoint identity')


@app.function(image=stage_image, secrets=[secret], volumes={'/weights': weights},
              cpu=8, memory=16384, timeout=7200, max_containers=1)
def stage_weights():
    from huggingface_hub import HfApi, snapshot_download
    CHECKPOINT.mkdir(parents=True, exist_ok=True)
    names = ('state.json', 'sha256.json', 'trainable.safetensors')
    if not all((CHECKPOINT/name).is_file() for name in names):
        HfApi().download_bucket_files(BUCKET, [(PREFIX+'/'+n, CHECKPOINT/n) for n in names],
                                      raise_on_missing_files=True)
    verify_checkpoint(CHECKPOINT)
    snapshot_download(MODEL, revision=REVISION, max_workers=8,
                      allow_patterns=['*.safetensors', '*.json', '*.py', '*.jinja', '*.model', '*.txt', '*.tiktoken'])
    weights.commit()
    print('Pinned base and checkpoint 1138 staged and verified; no GPU allocated.')


@app.cls(image=image, secrets=[secret], volumes={'/weights': weights, '/data': data},
         gpu='RTX-PRO-6000', cpu=16, memory=327680, min_containers=0,
         env={'BIRCH_ENABLE_REFINEMENT': '1'},
         max_containers=1, scaledown_window=120, timeout=600, startup_timeout=1800,
         enable_memory_snapshot=True, experimental_options={'enable_gpu_snapshot': True})
@modal.concurrent(max_inputs=1)
class Inference:
    @modal.enter(snap=True)
    def load(self):
        import torch
        import json
        from decision_model.inference_backend import CachedPredictor
        from decision_model.inference_quantized import load_nf4_predictor
        if torch.cuda.device_count() != 1:
            raise RuntimeError('This deployment requires exactly one RTX PRO GPU')
        verify_checkpoint(CHECKPOINT)
        os.environ['HF_HUB_OFFLINE'] = '1'
        model = load_nf4_predictor(CHECKPOINT, enable_refinement=True)
        record = json.loads((CHECKPOINT/'state.json').read_text())
        metadata = dict(model=MODEL, revision=REVISION, training_identity=record['identity'],
                        step=1138, checkpoint_sha256=WEIGHTS_SHA256,
                        quantization='nf4-experts-merged-adapters')
        self.predictor = CachedPredictor(model, metadata, cache_bytes=64*1024**2)
        self.predictor.predict('Synthetic integration warmup.', [dict(
            question='Which allowed action should be reviewed?',
            choices=['Review available history', 'Request missing information'])])
        torch.cuda.synchronize()
        torch.cuda.empty_cache()
        print('Live checkpoint 1138 loaded and warmed; creating GPU snapshot for future cold starts.')

    @modal.enter()
    def open_store(self):
        import shutil
        from decision_model.inference_service import DecisionStore, ImageStore, DecisionService
        # SQLite runs on the local filesystem. Closed backup snapshots are
        # committed to the Volume after every successful mutation.
        self.local_db = Path('/tmp/birch-decisions.sqlite')
        snapshot = Path('/data/decisions.sqlite')
        if snapshot.exists():
            shutil.copyfile(snapshot, self.local_db)
        self.store = DecisionStore(self.local_db)
        self.service = DecisionService(self.predictor, self.store, ImageStore('/data/images'))
        print('Live checkpoint 1138 ready; fixture fallback is disabled.')

    @modal.method()
    def warmup(self):
        return self.service.predictor.metadata

    @modal.method()
    def preflight(self):
        import torch, time
        from decision_api.reasoning import refine, PatientTools
        from decision_api.shared_generation import encoder_of
        generator=self.predictor.model.base_generator
        prefix_ids=[id(p) for layer in encoder_of(generator.full).layers[:-7] for p in layer.parameters()]
        tail_ids=[id(layer) for layer in encoder_of(generator.full).layers[-7:]]
        head=generator.full.language_model.lm_head
        context='Synthetic intake: the patient reports a changing skin lesion. Only the currently visible record is available.'
        questions=[dict(question='What should be reviewed next?',choices=['Review available history','Invent missing test results'])]
        limit=self.predictor.limit; self.predictor.limit=0
        try:
            self.predictor.cache.clear();self.predictor.bytes=0
            before=self.predictor.predict(context,questions)['probabilities']
            start=time.monotonic()
            request=dict(context=context,questions=[dict(id='next',text=questions[0]['question'],choices=[dict(id='history',text=questions[0]['choices'][0]),dict(id='invent',text=questions[0]['choices'][1])])])
            refined=refine(request,options=dict(enabled=True,max_tokens=128,additional_prompt='Retrieve the available patient history, then give a quick evidence summary.'),tools=PatientTools('sim:demo-record'),generator=generator)
            elapsed=time.monotonic()-start
            after=self.predictor.predict(context,questions)['probabilities']
            error=max(abs(a-b) for row_a,row_b in zip(before,after) for a,b in zip(row_a,row_b))
            assert error<1e-5, error
            assert tail_ids==[id(layer) for layer in encoder_of(generator.full).layers[-7:]]
            assert head is generator.full.language_model.lm_head
            assert prefix_ids==[id(p) for layer in encoder_of(generator.full).layers[:-7] for p in layer.parameters()]
            return dict(refinement=refined['refinement'],generation_seconds=elapsed,classifier_before=before,classifier_after=after,max_score_error=error,shared_prefix=True,decision_branch_restored=True,allocated_gib=torch.cuda.memory_allocated()/1024**3,peak_gib=torch.cuda.max_memory_allocated()/1024**3)
        finally:self.predictor.limit=limit

    def persist(self):
        import sqlite3
        target = Path('/data/decisions-next.sqlite')
        with self.store.lock:
            connection = sqlite3.connect(target)
            try:
                self.store.db.backup(connection)
            finally:
                connection.close()
        target.replace('/data/decisions.sqlite')
        data.commit()

    @modal.asgi_app()
    def web(self):
        import asyncio
        from decision_model.serve import create_app
        api = create_app(self.service, api_key=os.environ['BIRCH_API_KEY'])

        @api.middleware('http')
        async def persist_mutation(request, call_next):
            response = await call_next(request)
            if request.method == 'POST' and 200 <= response.status_code < 300:
                await asyncio.to_thread(self.persist)
            return response
        return api

    @modal.exit()
    def close(self):
        if hasattr(self, 'store'):
            self.persist()
            self.store.close()


@app.function(image=image, gpu='RTX-PRO-6000', cpu=2, memory=8192,
              timeout=300, scaledown_window=2, max_containers=1)
def probe_nf4():
    import torch
    from types import SimpleNamespace
    from decision_model.inference_quantized import NF4Experts
    torch.manual_seed(85)
    source = SimpleNamespace(num_experts=2, act_fn=torch.relu,
        up_proj=torch.randn(2, 128, 128, dtype=torch.bfloat16)*.05,
        down_proj=torch.randn(2, 128, 128, dtype=torch.bfloat16)*.05)
    packed = NF4Experts(source).to('cuda:0')
    inputs = torch.randn(3, 128, dtype=torch.bfloat16, device='cuda:0')
    indices = torch.tensor([[0, 1], [1, 0], [0, 1]], device='cuda:0')
    mixing = torch.tensor([[.8, .2], [.3, .7], [.4, .6]], device='cuda:0')
    output = packed(inputs, indices, mixing)
    expected = torch.zeros_like(inputs, dtype=torch.float32)
    for token in range(3):
        for slot in range(2):
            expert = indices[token, slot].item()
            hidden = torch.relu(source.up_proj[expert].cuda() @ inputs[token])
            expected[token] += mixing[token, slot] * (source.down_proj[expert].cuda() @ hidden)
    if not torch.isfinite(output).all():
        raise RuntimeError('NF4 produced nonfinite results')
    relative_error = float((output.float()-expected).norm()/expected.norm())
    if relative_error > .3:
        raise RuntimeError(f'NF4 tiny-probe relative error {relative_error:.3f} exceeds limit')
    return dict(device=torch.cuda.get_device_name(), relative_error=relative_error,
                allocated_mib=torch.cuda.memory_allocated()/1024**2)


@app.local_entrypoint()
def main(probe: bool = False):
    if probe:
        print(probe_nf4.remote())
    else:
        stage_weights.remote()

# A small CPU-only gateway owns the inference credential; the team needs only its URL.
gateway_image = (modal.Image.debian_slim(python_version='3.12')
    .pip_install('fastapi==0.162.7')
    .env({'PYTHONPATH':'/app','BIRCH_NATIVE_REFINEMENT_ENABLED':'1'})
    .add_local_dir(ROOT/'decision_api','/app/decision_api',ignore=['runtime','__pycache__','*.pyc','.env','.env.*']))

@app.function(image=gateway_image, secrets=[secret], cpu=1, memory=512,
              min_containers=0, max_containers=1, scaledown_window=300, timeout=900)
@modal.concurrent(max_inputs=100)
@modal.asgi_app()
def demo():
    from decision_api.hosted import create_app
    return create_app()
