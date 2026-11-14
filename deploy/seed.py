"""Seed a running instance so a first-time visitor finds something to look at (ticket M7-5). Idempotent.

    python deploy/seed.py http://localhost:8000                       # token from $PATHWAY_ACCESS_TOKEN
    docker compose exec -T platform python /app/deploy/seed.py http://127.0.0.1:8000   # on the host, token is in the container's environment
    python deploy/seed.py URL --quick                                 # smaller cohorts (a minute instead of several)

Creates, unless a project of that name exists:
  * "Finland lung pathway (template)" and "Norway check (template)": clean copies of the two templates;
  * "Guided tour: Finland lung": the whole loop already done on one project: run today's pathway, optimise on
    training cohorts, apply the accepted changes, rerun on held-out patients, compare. Open its runs and compare them.
Synthetic data only. Needs httpx (installed with the service).
"""

from __future__ import annotations

import argparse
import os
import sys
import time

import httpx

TEMPLATE_COPIES = [("Finland lung pathway (template)", "finland_lung"), ("Norway check (template)", "norway_check")]
GUIDED = "Guided tour: Finland lung"


class Seeder:
    def __init__(self, url: str, token: str | None, quick: bool):
        h = {"Authorization": f"Bearer {token}"} if token else {}
        self.c = httpx.Client(base_url=url.rstrip("/") + "/api", headers=h, timeout=60)
        self.quick = quick

    def call(self, method: str, path: str, ok=(200, 201, 202), **kw):
        r = self.c.request(method, path, **kw)
        if r.status_code not in ok:
            raise SystemExit(f"{method} {path} -> {r.status_code}: {r.text[:400]}")
        return r.json() if r.content else None

    def wait(self, job_id: str, what: str, limit: float = 1500) -> None:
        t0 = time.time()
        while time.time() - t0 < limit:
            j = self.call("GET", f"/jobs/{job_id}")
            if j["status"] in ("succeeded", "failed", "cancelled"):
                if j["status"] != "succeeded":
                    raise SystemExit(f"{what}: job {job_id} {j['status']}: {j.get('error') or j.get('message')}")
                return
            time.sleep(1)
        raise SystemExit(f"{what}: job {job_id} still running after {limit:.0f} s")

    def project(self, name: str, template: str, existing: dict[str, dict]) -> tuple[dict, bool]:
        if name in existing:
            return existing[name], False
        return self.call("POST", "/projects", json={"name": name, "template": template}), True

    def guided_loop(self, pid: str, fid: str) -> None:
        n = 3000 if self.quick else 6000          # the world's minimum for this template is about 2700
        run = lambda label, f, seeds: self.call("POST", f"/projects/{pid}/runs", json={"flowchart": f, "n": n, "seeds": seeds, "label": label})
        r = run("today's pathway", {"id": fid}, [301, 302])
        self.wait(r["job_id"], "baseline run")
        o = self.call("POST", f"/projects/{pid}/optimisations", json={"flowchart": {"id": fid}, "n": n, "train_seeds": [101, 102],
                                                                      "heldout_seeds": [301, 302], "max_changes": 3})
        self.wait(o["job_id"], "optimisation")
        detail = self.call("GET", f"/projects/{pid}/optimisations/{o['id']}")
        accept = [c["index"] for c in detail.get("changes", [])][:2]
        if not accept:
            print("  the optimiser proposed no changes; the guided project keeps the baseline run only")
            return
        a = self.call("POST", f"/projects/{pid}/optimisations/{o['id']}/apply", json={"accept": accept})
        for key in ("baseline_run", "run"):
            if a.get(key, {}).get("job_id"):
                self.wait(a[key]["job_id"], f"apply: {key}")
        self.call("POST", f"/projects/{pid}/compare", json={"runs": [a["baseline_run_id"], a["run_id"]]})

    def seed(self) -> None:
        access = self.call("GET", "/access")
        if not access["can_write"]:
            raise SystemExit("this token cannot write here (wrong or missing token, or the instance is read-only)")
        existing = {p["name"]: p for p in self.call("GET", "/projects")}
        for name, template in TEMPLATE_COPIES:
            _, new = self.project(name, template, existing)
            print(("created  " if new else "kept     ") + name)
        p, new = self.project(GUIDED, "finland_lung", existing)
        if not new:
            print("kept     " + GUIDED)
            return
        print("created  " + GUIDED + " (running the loop; this takes a few minutes)")
        detail = self.call("GET", f"/projects/{p['id']}")
        try:
            self.guided_loop(p["id"], detail["flowcharts"][0]["id"])
        except BaseException:                     # leave nothing half done: the next run starts again
            self.c.delete(f"/projects/{p['id']}")
            raise
        print("done     " + GUIDED)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("url", nargs="?", default="http://127.0.0.1:8000")
    ap.add_argument("--token", default=os.environ.get("PATHWAY_ACCESS_TOKEN"))
    ap.add_argument("--quick", action="store_true")
    a = ap.parse_args()
    Seeder(a.url, a.token, a.quick).seed()
