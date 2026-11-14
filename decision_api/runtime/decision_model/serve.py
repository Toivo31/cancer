"""Run one immutable checkpoint behind the demo API; fixture mode is explicit."""
import argparse
import hmac
import os
from pathlib import Path
from fastapi import FastAPI, Depends, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from .inference_schema import ScoreRequest, PathwayRequest, Review, DecisionResponse


def create_app(service, *, api_key=None, origins=()):
    app = FastAPI(title='Birch decision inference', version='1.0.0',
                  description='Candidate scores and reviewable workflow proposals. Scores are not calibrated clinical risks.')
    root = Path(__file__).resolve().parents[1]

    def authorize(authorization: str | None = Header(default=None)):
        if api_key and (authorization is None or not hmac.compare_digest(authorization, 'Bearer '+api_key)):
            raise HTTPException(401, 'A valid bearer token is required')

    @app.get('/demo/examples/{name}', include_in_schema=False)
    def demo_example(name: str):
        examples = {'pathway': 'demo-pathway.json', 'score': 'demo-score.json'}
        if name not in examples:
            raise HTTPException(404, 'Unknown demo example')
        return FileResponse(root/'examples'/examples[name], media_type='application/json')

    @app.get('/demo', include_in_schema=False)
    def demo():
        return FileResponse(root/'decision_model/demo_web/index.html')

    @app.post('/demo/samples/{sample_id}/prepare', dependencies=[Depends(authorize)], include_in_schema=False)
    def prepare_sample(sample_id: str):
        import json
        sample_root = root/'decision_model/demo_web/samples'
        catalog = json.loads((sample_root/'catalog.json').read_text())
        sample = next((item for item in catalog['examples'] if item['id'] == sample_id), None)
        if sample is None:
            raise HTTPException(404, 'Unknown demo sample')
        # Only bundled allowlisted files can enter the image store. No upload,
        # caller-supplied path, diagnosis or ground-truth label enters this input.
        asset = invoke(service.images.save, (sample_root/(sample_id+'.png')).read_bytes())
        return dict(**asset, context=sample['context'])

    app.mount('/demo', StaticFiles(directory=root/'decision_model/demo_web', html=True), name='demo')
    if origins:
        app.add_middleware(CORSMiddleware, allow_origins=list(origins),
                           allow_methods=['GET', 'POST'], allow_headers=['Authorization', 'Content-Type'])

    def invoke(function, *args):
        try:
            return function(*args)
        except KeyError:
            raise HTTPException(404, 'Unknown decision ID') from None
        except ValueError as error:
            raise HTTPException(422, str(error)) from None
        except RuntimeError:
            raise HTTPException(503, 'Inference failed; no substitute scores were generated') from None

    @app.get('/healthz')
    def health():
        return dict(ready=True, backend=service.predictor.metadata, capabilities=dict(context_refinement=hasattr(getattr(service.predictor, 'model', None), 'base_generator')))

    @app.post('/v1/images', dependencies=[Depends(authorize)])
    async def image(request: Request):
        data = bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data) > service.images.max_bytes:
                raise HTTPException(413, 'Image exceeds 10 MiB')
        return invoke(service.images.save, bytes(data))

    @app.post('/v1/score', dependencies=[Depends(authorize)], response_model=DecisionResponse, response_model_exclude_none=True)
    def score(request: ScoreRequest):
        return invoke(service.score, request)

    @app.post('/v1/pathway/propose', dependencies=[Depends(authorize)], response_model=DecisionResponse, response_model_exclude_none=True)
    def propose(request: PathwayRequest):
        return invoke(service.propose, request)

    @app.get('/v1/decisions/{identifier}', dependencies=[Depends(authorize)])
    def decision(identifier: str):
        return invoke(service.store.get, identifier)

    @app.post('/v1/decisions/{identifier}/review', dependencies=[Depends(authorize)])
    def review(identifier: str, request: Review):
        return invoke(service.store.review, identifier, request)

    from decision_api.native_refinement import install_refinement_route
    install_refinement_route(app, service, authorize)
    return app


def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--checkpoint', type=Path)
    mode.add_argument('--fixture', type=Path)
    parser.add_argument('--database', type=Path, default=Path('outputs/demo/decisions.sqlite'))
    parser.add_argument('--images', type=Path, default=Path('outputs/demo/images'))
    parser.add_argument('--layout', choices=['8x48gb', '8x96gb'])
    parser.add_argument('--cache-mib', type=int, default=64)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--allow-origin', action='append', default=[])
    args = parser.parse_args()
    if args.cache_mib < 0:
        parser.error('--cache-mib cannot be negative')
    from .inference_backend import FixturePredictor, checkpoint_predictor
    from .inference_service import DecisionService, DecisionStore, ImageStore
    predictor = (FixturePredictor(args.fixture) if args.fixture else
                 checkpoint_predictor(args.checkpoint, layout=args.layout, cache_bytes=args.cache_mib*1024**2))
    store = DecisionStore(args.database)
    service = DecisionService(predictor, store, ImageStore(args.images))
    import uvicorn
    try:
        uvicorn.run(create_app(service, api_key=os.environ.get('BIRCH_API_KEY'), origins=args.allow_origin),
                    host=args.host, port=args.port, workers=1)
    finally:
        store.close()


if __name__ == '__main__':
    main()
