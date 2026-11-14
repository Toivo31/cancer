"""Start a job runner with one long job, print the job's process id, then die the way an OOM kill does (SIGKILL)."""

import os
import signal
import sys
import time

sys.path.insert(0, os.getcwd())
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import sec_jobfuncs  # noqa: E402
from service.jobs import JobRunner  # noqa: E402


def main():
    r = JobRunner(max_workers=1)
    j = r.submit("t", sec_jobfuncs.sleeper, {"seconds": 90})
    for _ in range(300):
        if r.get(j.id).status == "running":
            break
        time.sleep(0.05)
    time.sleep(0.5)
    print(r._procs[j.id].pid, flush=True)
    os.kill(os.getpid(), signal.SIGKILL)


if __name__ == "__main__":
    main()
