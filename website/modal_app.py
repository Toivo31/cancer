"""CPU-only website hosting. Reuses the existing public decision gateway."""
from pathlib import Path
import modal

app = modal.App("equal-care-pathways")
image = (modal.Image.debian_slim(python_version="3.12")
         .pip_install("fastapi==0.115.12")
         .add_local_dir(Path(__file__).parent / "public", "/site"))

@app.function(image=image, cpu=0.25, memory=256, min_containers=0,
              max_containers=2, scaledown_window=300)
@modal.concurrent(max_inputs=100)
@modal.asgi_app()
def web():
    from fastapi import FastAPI
    from fastapi.staticfiles import StaticFiles
    site = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    site.mount("/", StaticFiles(directory="/site", html=True), name="website")
    return site
