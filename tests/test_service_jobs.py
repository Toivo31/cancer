"""Job runner: progress, cancel, time limit, crash isolation, queueing, engine progress hook."""

import os
import time

import pytest

from pathway_sim import generate_patients, load_scenario, simulate
from service.jobs import JobRunner, QueueFull


# job functions must live at module level (they are pickled by name)
def _ok(ctx, n=3):
    for i in range(n):
        ctx.progress(i + 1, n, f"step {i + 1}", force=True)
        ctx.log(f"did {i + 1}")
    return {"n": n}


def _sleepy(ctx, seconds=30):
    ctx.progress(1, 10, "started", force=True)
    time.sleep(seconds)
    return {}


def _raises(ctx):
    raise ValueError("bad input")


def _dies(ctx):
    os._exit(7)   # simulates a segfault or the out-of-memory killer


def _cooperative(ctx):
    for _ in range(500):
        ctx.check_cancel()
        time.sleep(0.01)
    return {}


def _engine_progress(ctx, n=400):
    sc = load_scenario("scenarios/stokstad.yaml")
    pts = generate_patients(sc, n, 1)
    simulate(sc, "observed", pts, seed=1, progress=lambda d, t: ctx.progress(d, t, force=True), progress_every=100)
    return {"done": True}


@pytest.fixture
def runner():
    r = JobRunner(max_workers=2, max_queued=3, default_timeout=60)
    yield r
    r.shutdown()


def test_success_progress_log_result(runner):
    j = runner.submit("t", _ok, {"n": 4}, label="demo")
    j = runner.wait(j.id, 30)
    assert j.status == "succeeded" and j.result == {"n": 4} and j.progress == 1.0
    assert j.log and j.log[-1] == "did 4" and j.started and j.finished and j.error is None


def test_exception_fails_only_that_job(runner):
    bad = runner.submit("t", _raises)
    good = runner.submit("t", _ok)
    assert runner.wait(bad.id, 30).status == "failed"
    assert runner.get(bad.id).error["code"] == "ValueError" and "bad input" in runner.get(bad.id).error["message"]
    assert runner.wait(good.id, 30).status == "succeeded"


def test_crashing_worker_fails_alone(runner):
    dead = runner.submit("t", _dies)
    other = runner.submit("t", _ok)
    assert runner.wait(dead.id, 30).status == "failed"
    assert runner.get(dead.id).error["code"] == "worker_died" and "7" in runner.get(dead.id).error["message"]
    assert runner.wait(other.id, 30).status == "succeeded"
    again = runner.submit("t", _ok)   # the runner still works afterwards
    assert runner.wait(again.id, 30).status == "succeeded"


def test_cancel_running_job(runner):
    j = runner.submit("t", _sleepy)
    t0 = time.time()
    while runner.get(j.id).status != "running" and time.time() - t0 < 20:
        time.sleep(0.02)
    runner.cancel(j.id)
    j = runner.wait(j.id, 20)
    assert j.status == "cancelled" and j.finished
    assert runner.cancel(j.id).status == "cancelled"   # idempotent


def test_cancel_queued_job_and_queue_limit():
    r = JobRunner(max_workers=1, max_queued=2, default_timeout=60)
    try:
        a = r.submit("t", _sleepy)
        t0 = time.time()
        while r.get(a.id).status != "running" and time.time() - t0 < 20:
            time.sleep(0.02)
        b = r.submit("t", _ok)
        c = r.submit("t", _ok)
        assert r.get(b.id).status == "queued"
        with pytest.raises(QueueFull):
            r.submit("t", _ok)
        r.cancel(b.id)
        assert r.get(b.id).status == "cancelled"
        r.cancel(a.id)
        assert r.wait(a.id, 20).status == "cancelled"
        assert r.wait(c.id, 30).status == "succeeded"   # the queue moves on
    finally:
        r.shutdown()


def test_time_limit(runner):
    j = runner.submit("t", _sleepy, timeout=0.8)
    j = runner.wait(j.id, 20)
    assert j.status == "failed" and j.error["code"] == "timeout"


def test_cooperative_cancel_flag(runner):
    j = runner.submit("t", _cooperative)
    time.sleep(0.5)
    runner.cancel(j.id)
    assert runner.wait(j.id, 20).status == "cancelled"


def test_max_workers_respected():
    r = JobRunner(max_workers=1, default_timeout=60)
    try:
        a = r.submit("t", _sleepy, {"seconds": 5})
        b = r.submit("t", _ok)
        time.sleep(0.6)
        assert r.get(a.id).status == "running" and r.get(b.id).status == "queued"
        r.cancel(a.id)
        assert r.wait(b.id, 30).status == "succeeded"
    finally:
        r.shutdown()


def test_hooks_called():
    seen, saved = [], []
    r = JobRunner(max_workers=1, persist=lambda d: saved.append(d["status"]), on_finish=lambda j: seen.append(j.status))
    try:
        j = r.submit("t", _ok)
        r.wait(j.id, 30)
        time.sleep(0.1)
        assert seen == ["succeeded"] and saved[0] == "queued" and "running" in saved and saved[-1] == "succeeded"
    finally:
        r.shutdown()


def test_engine_progress_hook_through_a_job(runner):
    j = runner.submit("t", _engine_progress, {"n": 400})
    j = runner.wait(j.id, 60)
    assert j.status == "succeeded" and j.progress == 1.0


def test_engine_progress_callback_counts_and_does_not_change_result():
    sc = load_scenario("scenarios/stokstad.yaml")
    pts = generate_patients(sc, 250, 3)
    calls = []
    a = simulate(sc, "observed", pts, seed=3, progress=lambda d, t: calls.append((d, t)), progress_every=100)
    b = simulate(sc, "observed", pts, seed=3)
    assert calls[0] == (100, 250) and calls[-1] == (250, 250) and [c[0] for c in calls] == sorted(c[0] for c in calls)
    assert a.to_dict() == b.to_dict()


def test_engine_progress_can_abort():
    sc = load_scenario("scenarios/stokstad.yaml")
    pts = generate_patients(sc, 250, 3)

    class Stop(Exception):
        pass

    def cb(d, t):
        raise Stop()
    with pytest.raises(Stop):
        simulate(sc, "observed", pts, seed=3, progress=cb, progress_every=50)
