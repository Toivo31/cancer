"""Job functions for the job-runner tests. They live in their own importable module because a job function is pickled by name."""

import os
import signal
import time


def sleeper(ctx, seconds=60):
    time.sleep(seconds)
    return {"slept": seconds}


def stubborn(ctx, seconds=60):
    """Ignores SIGTERM, as a job stuck in native code might."""
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    time.sleep(seconds)
    return {}


def failer(ctx):
    raise RuntimeError("deliberate failure for the traceback leak test")


def hard_crash(ctx):
    os._exit(7)


def quick(ctx):
    return {"ok": True}


def pid_reporter(ctx, path):
    with open(path, "w") as f:
        f.write(str(os.getpid()))
    time.sleep(120)
    return {}
