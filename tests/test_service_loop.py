"""The whole loop through the API: template -> run -> optimise -> apply -> rerun on the same patients -> compare (M2-9)."""

import copy
import json
import time

import pytest
from fastapi.testclient import TestClient

from service.app import create_app
from service.config import Settings

N = 150
OPT = {"flowchart": {"id": "observed"}, "n": N, "train_seeds": [101, 102], "heldout_seeds": [301], "max_changes": 3,
       "allow": ["detach", "relax", "standardise"]}


@pytest.fixture(scope="module")
def loop(tmp_path_factory):
    app = create_app(Settings(data_dir=tmp_path_factory.mktemp("loop"), web_dir=tmp_path_factory.mktemp("noweb"), max_jobs=2))
    with TestClient(app) as c:
        p = c.post("/api/projects", json={"name": "loop", "template": "norway_check"}).json()["id"]
        yield c, p


def wait(c, job_id, timeout=120):
    end = time.time() + timeout
    while time.time() < end:
        j = c.get(f"/api/jobs/{job_id}").json()
        if j["status"] in ("succeeded", "failed", "cancelled"):
            return j
        time.sleep(0.1)
    raise AssertionError("timeout")


@pytest.fixture(scope="module")
def optimised(loop):
    c, p = loop
    r = c.post(f"/api/projects/{p}/optimisations", json=OPT)
    assert r.status_code == 202, r.text
    o = r.json()
    j = wait(c, o["job_id"])
    assert j["status"] == "succeeded", j
    return o["id"]


def test_optimisation_result_has_labels_evidence_and_unseen_numbers(loop, optimised):
    c, p = loop
    o = c.get(f"/api/projects/{p}/optimisations/{optimised}").json()
    assert o["status"] == "succeeded" and o["progress"] == 1.0 and o["flowchart"] == {"id": "observed", "version": 1}
    assert len(o["changes"]) >= 2
    ch = o["changes"][0]
    assert ch["index"] == 0 and ch["label"] and ch["records_reading"] and ch["train"]["on_time_after"] > ch["train"]["on_time_before"]
    assert ch["heldout_after_this_change"]["on_time"] is not None
    assert o["heldout"]["after"]["share_within_target"] > o["heldout"]["before"]["share_within_target"]
    assert "never saw" in o["honesty"] and "selection_optimism_pp" in o and isinstance(o["blocked"], list)
    assert o["proposed_flowchart"]["nodes"] and o["proposed_flowchart"]["edges"]
    assert any(x["id"] == optimised for x in c.get(f"/api/projects/{p}/optimisations").json())
    assert "changes" not in c.get(f"/api/projects/{p}/optimisations").json()[0]      # the list stays light


def _shape(doc):
    return ({n["id"]: {k: v for k, v in n.items() if k != "ui"} for n in doc["nodes"]},
            sorted(((e["from"], e["to"], e["type"], e.get("index", 0)) for e in doc["edges"])))


def test_apply_all_equals_the_optimisers_own_output(loop, optimised):
    c, p = loop
    o = c.get(f"/api/projects/{p}/optimisations/{optimised}").json()
    r = c.post(f"/api/projects/{p}/optimisations/{optimised}/apply", json={"rerun": False})
    assert r.status_code == 200, r.text
    out = r.json()
    new = c.get(f"/api/projects/{p}/flowcharts/observed/versions/{out['flowchart']['version']}").json()
    assert _shape(new) == _shape(o["proposed_flowchart"])
    assert [e["index"] for e in new["edits_from_parent"]] == list(range(len(o["changes"])))
    assert new["parent_version"] == out["based_on"]["version"] and "run_id" not in out


def test_apply_a_subset_then_rerun_on_the_same_patients_and_compare(loop, optimised):
    c, p = loop
    r = c.post(f"/api/projects/{p}/optimisations/{optimised}/apply", json={"accept": [0], "label": "first change only"})
    assert r.status_code == 200, r.text
    out = r.json()
    new = c.get(f"/api/projects/{p}/flowcharts/observed/versions/{out['flowchart']['version']}").json()
    assert [e["index"] for e in new["edits_from_parent"]] == [0] and out["accepted"] == [0]
    for run_id in (out["run_id"], out["baseline_run_id"]):
        run = c.get(f"/api/projects/{p}/runs/{run_id}").json()
        assert wait(c, run["job_id"])["status"] == "succeeded"
    new_run = c.get(f"/api/projects/{p}/runs/{out['run_id']}").json()
    base_run = c.get(f"/api/projects/{p}/runs/{out['baseline_run_id']}").json()
    assert new_run["patients_key"] == base_run["patients_key"] and new_run["seeds"] == base_run["seeds"] == [301]
    assert new_run["flowchart"]["version"] == out["flowchart"]["version"] and base_run["flowchart"]["version"] == 1
    assert new_run["label"] == "first change only" and new_run["source"]["optimisation"] == optimised
    cmp = c.post(f"/api/projects/{p}/compare", json={"runs": [base_run["id"], new_run["id"]]})
    assert cmp.status_code == 200 and cmp.json()["same_patients"]
    assert cmp.json()["headline"]["share_within_target"]["b"] > cmp.json()["headline"]["share_within_target"]["a"]
    # the same patients were put through both: the patient logs have identical ids and arrival days
    a = c.get(f"/api/projects/{p}/runs/{base_run['id']}/patients", params={"limit": 50}).json()["patients"]
    b = c.get(f"/api/projects/{p}/runs/{new_run['id']}/patients", params={"limit": 50}).json()["patients"]
    assert [(x["id"], x["arrival"], x["cancer"]) for x in a] == [(x["id"], x["arrival"], x["cancer"]) for x in b]
    # applying twice reruns from the cache: same run ids
    again = c.post(f"/api/projects/{p}/optimisations/{optimised}/apply", json={"accept": [0], "rerun": True}).json()
    assert again["baseline_run_id"] == base_run["id"] and again["flowchart"]["version"] != out["flowchart"]["version"]


def test_unknown_change_and_unfinished_optimisation_are_refused(loop, optimised):
    c, p = loop
    r = c.post(f"/api/projects/{p}/optimisations/{optimised}/apply", json={"accept": [42], "rerun": False})
    assert r.status_code == 409 and r.json()["error"]["code"] == "unknown_change"
    assert c.post(f"/api/projects/{p}/optimisations/o_nope/apply", json={}).status_code == 404


def test_linked_changes_must_be_accepted_together(loop, optimised):
    c, p = loop
    rt = c.app.state.runtime
    saved = rt.store.get_blob(p, "optimisations", optimised)
    linked = copy.deepcopy(saved)
    linked["steps"][0]["evidence"]["accepted_together_with"] = [linked["steps"][1]["plain"]]
    linked["steps"][1]["evidence"]["accepted_together_with"] = [linked["steps"][0]["plain"]]
    rt.store.put_blob(p, "optimisations", optimised, linked)
    try:
        r = c.post(f"/api/projects/{p}/optimisations/{optimised}/apply", json={"accept": [0], "rerun": False})
        e = r.json()["error"]
        assert r.status_code == 409 and e["code"] == "linked_change" and e["problems"][0]["needs"] == [1]
        ok = c.post(f"/api/projects/{p}/optimisations/{optimised}/apply", json={"accept": [0, 1], "rerun": False})
        assert ok.status_code == 200
    finally:
        rt.store.put_blob(p, "optimisations", optimised, saved)


def test_optimisation_input_checks(loop):
    c, p = loop
    bad = dict(OPT, allow=["teleport"])
    assert c.post(f"/api/projects/{p}/optimisations", json=bad).status_code == 422
    same = dict(OPT, heldout_seeds=[101])
    assert c.post(f"/api/projects/{p}/optimisations", json=same).status_code == 422
    assert c.post(f"/api/projects/{p}/optimisations", json=dict(OPT, n=10 ** 7)).status_code == 429
    assert c.post(f"/api/projects/{p}/optimisations", json=dict(OPT, flowchart={"id": "zzz"})).status_code == 404


def test_cancel_an_optimisation(loop):
    c, p = loop
    o = c.post(f"/api/projects/{p}/optimisations", json=dict(OPT, n=2000, max_changes=8)).json()
    end = time.time() + 20
    while c.get(f"/api/jobs/{o['job_id']}").json()["status"] != "running" and time.time() < end:
        time.sleep(0.05)
    r = c.post(f"/api/projects/{p}/optimisations/{o['id']}/cancel").json()
    assert r["status"] == "cancelled"
    assert c.post(f"/api/projects/{p}/optimisations/{o['id']}/apply", json={}).status_code == 409


def test_finnish_template_loop_with_a_short_warm_up(tmp_path):
    """The Finnish template end to end at small n (its 60-day warm-up is shortened so few patients are enough)."""
    app = create_app(Settings(data_dir=tmp_path / "d", web_dir=tmp_path / "x", max_jobs=2))
    with TestClient(app) as c:
        p = c.post("/api/projects", json={"name": "fi", "template": "finland_lung"}).json()["id"]
        w = c.get(f"/api/projects/{p}/world").json()["world"]
        w["warmup_days"] = 5
        assert c.put(f"/api/projects/{p}/world", json=w).status_code == 200
        r = c.post(f"/api/projects/{p}/runs", json={"flowchart": {"id": "baseline"}, "n": 500, "seeds": [301]})
        assert r.status_code == 202, r.text
        assert wait(c, r.json()["job_id"])["status"] == "succeeded"
        o = c.post(f"/api/projects/{p}/optimisations", json={"flowchart": {"id": "baseline"}, "n": 500, "train_seeds": [101],
                                                             "heldout_seeds": [301], "max_changes": 2, "allow": ["detach", "relax"]}).json()
        assert wait(c, o["job_id"])["status"] == "succeeded"
        res = c.get(f"/api/projects/{p}/optimisations/{o['id']}").json()
        assert res["changes"] and res["heldout"]["after"]["share_within_target"] is not None
        a = c.post(f"/api/projects/{p}/optimisations/{o['id']}/apply", json={}).json()
        assert a["baseline_run_id"] == r.json()["id"]            # the parent's run on the held-out patients is the one already made
        assert wait(c, c.get(f"/api/projects/{p}/runs/{a['run_id']}").json()["job_id"])["status"] == "succeeded"
        assert c.post(f"/api/projects/{p}/compare", json={"runs": [a["baseline_run_id"], a["run_id"]]}).status_code == 200
        flow = c.get(f"/api/projects/{p}/runs/{a['run_id']}/flow").json()
        assert flow["format"] == "flow/1" and flow["totals"]["n"] > 0
        m = c.get(f"/api/projects/{p}/runs/{a['run_id']}").json()["metrics"]       # flow totals equal the run's metrics
        assert flow["metrics"]["share_within_target"] == pytest.approx(m["share_within_target"], abs=1e-3)
        assert flow["metrics"]["median_days_to_treatment"] == pytest.approx(m["median_days_to_treatment"], abs=0.02)
        assert flow["totals"]["n"] == m["n"]


def test_optimiser_under_a_stub_backend(tmp_path):
    """Hardcoded stub tables are legitimate for 'standardise' (spec 05); a model backend (http, local) is not
    overridden unless asked (F7). Decision probabilities come from the flowchart's table in every run."""
    app = create_app(Settings(data_dir=tmp_path / "d", web_dir=tmp_path / "x", max_jobs=2))
    with TestClient(app) as c:
        p = c.post("/api/projects", json={"name": "s", "template": "norway_check"}).json()["id"]
        base = {"flowchart": {"id": "observed"}, "n": 120, "train_seeds": [101], "heldout_seeds": [301], "max_changes": 1}
        o = c.post(f"/api/projects/{p}/optimisations", json=base)
        assert o.status_code == 202 and o.json()["settings"]["allow"] == ["detach", "relax", "standardise"]
        assert wait(c, o.json()["job_id"])["status"] == "succeeded"
        # a version that points at a model backend: standardise is refused by default, allowed on request
        doc = c.get(f"/api/projects/{p}/flowcharts/observed/versions/latest").json()
        doc["decision_policy"] = {"backend": "http", "url": "http://127.0.0.1:9", "mode": "sample", "points": {}}
        saved = c.post(f"/api/projects/{p}/flowcharts/observed/versions", json=doc)
        assert saved.status_code == 201, saved.text
        model = {**base, "flowchart": {"id": "observed", "version": saved.json()["version"]}}
        e = c.post(f"/api/projects/{p}/optimisations", json={**model, "allow": ["standardise"]})
        assert e.status_code == 422 and e.json()["error"]["code"] == "standardise_under_jev"
        d = c.post(f"/api/projects/{p}/optimisations", json=model)       # default allow leaves it out (then the unreachable model is reported)
        assert d.status_code == 422 and d.json()["error"]["code"] == "invalid_decision_policy"


def test_standardise_under_stub_changes_the_table_and_the_rerun_reflects_it(tmp_path):
    """An accepted 'standardise' must change what the stub does, in the new version and in the rerun."""
    app = create_app(Settings(data_dir=tmp_path / "d", web_dir=tmp_path / "x", max_jobs=2))
    with TestClient(app) as c:
        p = c.post("/api/projects", json={"name": "s", "template": "norway_check"}).json()["id"]
        o = c.post(f"/api/projects/{p}/optimisations", json={"flowchart": {"id": "observed"}, "n": 150, "train_seeds": [101, 102],
                                                             "heldout_seeds": [301], "max_changes": 3,
                                                             "allow": ["standardise"]}).json()
        assert wait(c, o["job_id"])["status"] == "succeeded"
        res = c.get(f"/api/projects/{p}/optimisations/{o['id']}").json()
        std = [ch for ch in res["changes"] if ch["kind"] == "standardise"]
        assert std, "the Norway template has standardise changes the optimiser accepts"
        a = c.post(f"/api/projects/{p}/optimisations/{o['id']}/apply", json={"accept": [std[0]["index"]]}).json()
        new = c.get(f"/api/projects/{p}/flowcharts/observed/versions/{a['flowchart']['version']}").json()
        row = new["decision_policy"]["points"][std[0]["target"]]["default"]
        assert row == {opt: (1.0 if opt == std[0]["other"] else 0.0) for opt in row}
        for r in (a["run_id"], a["baseline_run_id"]):
            assert wait(c, c.get(f"/api/projects/{p}/runs/{r}").json()["job_id"])["status"] == "succeeded"
        rows = [json.loads(x) for x in c.get(f"/api/projects/{p}/runs/{a['run_id']}/decisions",
                                              params={"point": std[0]["target"]}).text.splitlines()]
        assert rows and {x["chosen"] for x in rows} == {std[0]["other"]}
