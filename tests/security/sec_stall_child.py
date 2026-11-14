"""Hang 48 /decide calls on a silent local JEV and print how long /api/health takes meanwhile. Runs in its own process so a stall cannot wedge the test run."""
import os
import socket
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, os.getcwd())
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sec_helpers import make_client, new_project  # noqa: E402


def main():
    silent = socket.socket()
    silent.bind(("127.0.0.1", 0))
    silent.listen(128)
    url = f"http://127.0.0.1:{silent.getsockname()[1]}"
    pol = {"backend": "http", "url": url, "model": "m", "timeout": 2.0}
    body = {"flowchart": {"id": "observed"}, "decision_point": "sample_plan", "decision_policy": pol}
    c = make_client(Path(tempfile.mkdtemp()))
    c.__enter__()
    p = new_project(c)
    pool = ThreadPoolExecutor(max_workers=50)
    for _ in range(48):
        pool.submit(c.post, f"/api/projects/{p}/decide", json=body)
    time.sleep(1.0)
    t = time.time()
    c.get("/api/health")
    print(f"{time.time() - t:.2f}", flush=True)
    os._exit(0)


if __name__ == "__main__":
    main()
