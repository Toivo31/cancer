"""Jobs and resources: time limits, crashes, cancellation, restarts, orphans, leaks (findings F6, F7, F8, F14, F16, F17)."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

import sec_jobfuncs as jf
from sec_helpers import FINAL, make_client, new_project, wait_job, world_of
from service.jobs import JobRunner, QueueFull

HERE = Path(__file__).resolve().parent


def alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    try:                                  # a zombie is not alive for our purposes
        return Path(f"/proc/{pid}/stat").read_text().split(")")[-1].split()[0] != "Z"
    except OSError:
        return False


def wait_dead(pid, timeout=8.0):
    end = time.time() + timeout
    while time.time() < end:
        if not alive(pid):
            return True
        time.sleep(0.1)
    return False


@pytest.fixture
def runner():
    r = JobRunner(max_workers=2, max_queued=3, default_timeout=60, kill_grace=0.5)
    yield r
    r.shutdown()


# ------------------------------------------------------------------------------------------ safe: limits and isolation
def test_time_limit_is_enforced_and_the_process_is_reaped(runner, tmp_path):
    pidfile = tmp_path / "pid"
    j = runner.submit("t", jf.pid_reporter, {"path": str(pidfile)}, timeout=1.5)
    j = runner.wait(j.id, 20)
    assert j.status == "failed" and j.error["code"] == "timeout"
    assert wait_dead(int(pidfile.read_text())), "the worker survived its time limit"


def test_a_job_that_ignores_sigterm_is_killed(runner):
    j = runner.submit("t", jf.stubborn, {"seconds": 60}, timeout=1.0)
    t = time.time()
    j = runner.wait(j.id, 20)
    assert j.status == "failed" and j.error["code"] == "timeout" and time.time() - t < 10


def test_cancelling_a_running_job_stops_its_process(runner, tmp_path):
    pidfile = tmp_path / "pid"
    j = runner.submit("t", jf.pid_reporter, {"path": str(pidfile)})
    for _ in range(200):
        if pidfile.exists() and pidfile.read_text():
            break
        time.sleep(0.05)
    runner.cancel(j.id)
    assert runner.wait(j.id, 20).status == "cancelled"
    assert wait_dead(int(pidfile.read_text()))


def test_a_crashing_worker_fails_that_job_only(runner):
    ok1 = runner.submit("t", jf.quick)
    bad = runner.submit("t", jf.hard_crash)
    ok2 = runner.submit("t", jf.quick)
    assert runner.wait(bad.id, 20).error["code"] == "worker_died"
    assert runner.wait(ok1.id, 20).status == "succeeded" and runner.wait(ok2.id, 20).status == "succeeded"
    assert runner.wait(runner.submit("t", jf.quick).id, 20).status == "succeeded"       # the runner still works


def test_the_queue_is_bounded(runner):
    for _ in range(2):
        runner.submit("t", jf.sleeper, {"seconds": 30})            # both workers busy
    for _ in range(3):
        runner.submit("t", jf.sleeper, {"seconds": 30})            # queue full (3)
    with pytest.raises(QueueFull):
        runner.submit("t", jf.sleeper, {"seconds": 30})


def test_a_hostile_but_accepted_world_fails_alone_at_the_time_limit(tmp_path):
    """capacity_per_day = 1e12 passes validation and makes the job spin; the limit stops it and other projects are unaffected."""
    with make_client(tmp_path, job_seconds=4, max_jobs=2) as c:
        evil = new_project(c, "finland_lung", "evil")
        good = new_project(c, "norway_check", "good")
        w = world_of(c, evil)
        w["resources"]["nurse_appt"]["capacity_per_day"] = 10 ** 12
        w["resources"]["nurse_appt"]["min_lead_days"] = 1e15
        assert c.put(f"/api/projects/{evil}/world", json=w).status_code == 200
        bad = c.post(f"/api/projects/{evil}/runs", json={"flowchart": {"id": "baseline"}, "n": w["default_n"], "seeds": [1]}).json()
        fine = c.post(f"/api/projects/{good}/runs", json={"flowchart": {"id": "observed"}, "n": 100, "seeds": [1]}).json()
        assert wait_job(c, fine["job_id"], 30)["status"] == "succeeded"
        j = wait_job(c, bad["job_id"], 30)
        assert j["status"] == "failed" and j["error"]["code"] == "timeout"
        assert c.get(f"/api/projects/{evil}/runs/{bad['id']}").json()["status"] == "failed"


# ------------------------------------------------------------------------------------------ F6: internals in job errors
def test_failed_job_does_not_show_a_traceback_or_server_paths(client):
    rt = client.app.state.runtime
    j = rt.runner.submit("t", jf.failer)
    rt.runner.wait(j.id, 20)
    body = client.get(f"/api/jobs/{j.id}").text
    assert "Traceback" not in body and "/home/" not in body and ".py" not in body, body[:300]


def test_failed_run_does_not_show_a_traceback_or_server_paths(client, project):
    w = world_of(client, project)
    w["arrivals"] = {"rate_per_day": 0}                         # passes validation today (F15), fails in the engine
    client.put(f"/api/projects/{project}/world", json=w)
    r = client.post(f"/api/projects/{project}/runs", json={"flowchart": {"id": "observed"}, "n": 100, "seeds": [1]})
    assert r.status_code == 202, "needs a world that validates but fails: see F15"
    wait_job(client, r.json()["job_id"])
    body = client.get(f"/api/projects/{project}/runs/{r.json()['id']}").text
    assert "Traceback" not in body and "/home/" not in body, body[:300]


# ------------------------------------------------------------------------------------------ F7: delete during a run
def _delete_while_running(tmp_path):
    c = make_client(tmp_path, max_jobs=2)
    c.__enter__()
    p = new_project(c, "finland_lung")
    r = c.post(f"/api/projects/{p}/runs", json={"flowchart": {"id": "baseline"}, "n": 3000, "seeds": [1]}).json()
    for _ in range(100):
        if c.get(f"/api/jobs/{r['job_id']}").json()["status"] == "running":
            break
        time.sleep(0.1)
    time.sleep(1.0)
    assert c.delete(f"/api/projects/{p}").status_code == 204
    return c, p, r


def test_deleting_a_project_stops_its_running_jobs(tmp_path):
    c, p, r = _delete_while_running(tmp_path)
    try:
        status = c.get(f"/api/jobs/{r['job_id']}").json()["status"]
        wait_job(c, r["job_id"], 90)
        assert status in FINAL, f"the job was still {status} after its project was deleted"
    finally:
        c.__exit__(None, None, None)


def test_deleting_a_project_leaves_no_files_behind(tmp_path):
    """Safe: when the job that outlives its project finishes, the supervisor removes what it wrote (only empty directories remain)."""
    c, p, r = _delete_while_running(tmp_path)
    try:
        wait_job(c, r["job_id"], 90)
        time.sleep(0.5)
        files = [f for f in (tmp_path / "data" / "blobs" / p).rglob("*") if f.is_file()]
        assert not files, files
    finally:
        c.__exit__(None, None, None)


def test_store_recreates_blob_directory_of_a_deleted_project(tmp_path):
    """The mechanism behind F7, without a race: put_blob has no check that the project still exists."""
    from service.store import Store
    s = Store(tmp_path)
    proj = s.create_project("p", {"id": "w", "conditions": []}, [])["id"]
    s.delete_project(proj)
    s.put_blob(proj, "runlogs", "r_late", {"x": 1})
    assert (tmp_path / "blobs" / proj).exists()


# ------------------------------------------------------------------------------------------ F8: orphan after the service dies
@pytest.mark.xfail(strict=True, reason="F8 (accepted for the hackathon): a job process outlives a service that was killed (OOM, SIGKILL); the Docker container dies with PID 1. PR_SET_PDEATHSIG was tried: the parent is the forkserver, which does not die with the service")
def test_job_process_does_not_outlive_a_killed_service(tmp_path):
    out = tmp_path / "out.txt"
    with open(out, "w") as fh:        # a file, not a pipe: the orphan inherits the descriptor and would keep a pipe open until it ends
        p = subprocess.Popen([sys.executable, "-W", "ignore", str(HERE / "sec_orphan_child.py")], stdout=fh, stderr=subprocess.STDOUT,
                             cwd=HERE.parent.parent, env={**os.environ, "PYTHONPATH": str(HERE.parent.parent)})
        rc = p.wait(timeout=60)
    assert rc == -signal.SIGKILL, out.read_text()[-500:]
    pid = int(out.read_text().strip().splitlines()[0])
    try:
        assert wait_dead(pid, 6.0), f"worker {pid} is still running 6 s after its parent was killed"
    finally:
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


# ------------------------------------------------------------------------------------------ restart and races (safe)
def test_start_up_marks_leftover_work_failed(tmp_path):
    from service.runs_db import JobRows, Runs
    from service.store import Store
    with make_client(tmp_path) as c:
        p = new_project(c)
    store = Store(tmp_path / "data")                      # the "crashed" service left a queued run and a running job behind
    row, _ = Runs(store).create_or_get(p, "k1", {"patients_key": "x", "label": "", "flowchart_id": "observed", "flowchart_version": 1, "n": 60,
                                                "seeds_json": [1], "policy_json": None, "engine_version": "e", "world_rev": 1, "source_json": None})
    Runs(store).update(row["id"], status="running", job_id="j_dead")
    JobRows(store).save({"id": "j_dead", "kind": "run", "status": "running", "owner": {"project": p}, "created": time.time()})
    with make_client(tmp_path) as c2:
        got = c2.get(f"/api/projects/{p}/runs/{row['id']}").json()
        assert got["status"] == "failed" and got["error"]["code"] == "service_restarted"
        assert c2.get("/api/jobs/j_dead").json()["status"] == "failed"
        # the same request can be made again: a failed run is not a cache hit
        again = c2.post(f"/api/projects/{p}/runs", json={"flowchart": {"id": "observed"}, "n": 60, "seeds": [1]})
        assert again.status_code == 202


def test_cancel_right_after_start_never_leaves_a_run_stuck(tmp_path):
    with make_client(tmp_path, max_jobs=2) as c:
        p = new_project(c)
        runs = []
        for seed in range(10):
            r = c.post(f"/api/projects/{p}/runs", json={"flowchart": {"id": "observed"}, "n": 200, "seeds": [seed]}).json()
            c.post(f"/api/projects/{p}/runs/{r['id']}/cancel")
            c.post(f"/api/jobs/{r['job_id']}/cancel")                   # twice, through both doors
            runs.append(r)
        for r in runs:
            j = wait_job(c, r["job_id"], 60)
            row = c.get(f"/api/projects/{p}/runs/{r['id']}").json()
            assert row["status"] == j["status"] in FINAL, (row["status"], j["status"])
            if row["status"] == "succeeded":
                assert c.get(f"/api/projects/{p}/runs/{r['id']}/bundle").status_code == 200
            else:
                assert c.get(f"/api/projects/{p}/runs/{r['id']}/bundle").status_code == 409


def test_identical_requests_from_many_clients_make_one_run(tmp_path):
    with make_client(tmp_path, max_jobs=2) as c:
        p = new_project(c)
        body = {"flowchart": {"id": "observed"}, "n": 150, "seeds": [5]}
        with ThreadPoolExecutor(12) as pool:
            rs = list(pool.map(lambda _: c.post(f"/api/projects/{p}/runs", json=body), range(12)))
        assert {r.status_code for r in rs} <= {200, 202}
        assert len({r.json()["id"] for r in rs}) == 1 and sum(1 for r in rs if r.status_code == 202) == 1
        assert len(c.get(f"/api/projects/{p}/runs").json()) == 1


# ------------------------------------------------------------------------------------------ F16: heavy work in the API process
def test_flow_rebuild_is_bounded_by_the_job_limit(tmp_path, monkeypatch):
    """F16: eight parallel non-default flow requests never simulate in the API process, and never more at once than there
    are job slots; the requests the slots cannot take are answered 429 instead of being queued without bound."""
    import service.runs_core as core
    with make_client(tmp_path, max_jobs=2) as c:
        p = new_project(c)
        r = c.post(f"/api/projects/{p}/runs", json={"flowchart": {"id": "observed"}, "n": 100, "seeds": [1]}).json()
        assert wait_job(c, r["job_id"])["status"] == "succeeded"
        real, lock, state = core.simulate, threading.Lock(), {"now": 0, "peak": 0, "pids": set()}

        def slow(*a, **kw):
            with lock:
                state["now"] += 1
                state["peak"] = max(state["peak"], state["now"])
                state["pids"].add(os.getpid())
            time.sleep(0.4)
            try:
                return real(*a, **kw)
            finally:
                with lock:
                    state["now"] -= 1

        monkeypatch.setattr(core, "simulate", slow)      # would be seen if the API process simulated
        with ThreadPoolExecutor(8) as pool:
            codes = list(pool.map(lambda k: c.get(f"/api/projects/{p}/runs/{r['id']}/flow", params={"sample_seed": k + 1}).status_code, range(8)))
        assert set(codes) <= {200, 429} and 200 in codes, codes
        assert state["pids"] == set(), "the flow was re-simulated inside the API process"
        assert state["peak"] <= 2, f"{state['peak']} simulations ran at once (max_jobs is 2)"
        # the answer of a rebuild is a real flow document, and no temporary file is left behind
        ok = c.get(f"/api/projects/{p}/runs/{r['id']}/flow", params={"sample": 40, "sample_seed": 3})
        assert ok.status_code == 200 and ok.json()["meta"]["sample_seed"] == 3
        assert not list((tmp_path / "data" / "blobs" / p / "flowtmp").glob("*"))


def test_flow_rebuild_runs_as_a_job_and_the_default_flow_does_not(tmp_path):
    with make_client(tmp_path, max_jobs=2) as c:
        p = new_project(c)
        r = c.post(f"/api/projects/{p}/runs", json={"flowchart": {"id": "observed"}, "n": 100, "seeds": [1]}).json()
        assert wait_job(c, r["job_id"])["status"] == "succeeded"
        rt = c.app.state.runtime
        before = len(rt.runner.list())
        assert c.get(f"/api/projects/{p}/runs/{r['id']}/flow").status_code == 200          # the stored flow: no job
        assert len(rt.runner.list()) == before
        assert c.get(f"/api/projects/{p}/runs/{r['id']}/flow", params={"sample_seed": 9}).status_code == 200
        assert [j.kind for j in rt.runner.list()].count("flow") == 1
