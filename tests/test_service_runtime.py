"""service.runtime.prepare_run: what runs and optimisations call. Stored documents reproduce the YAML's numbers."""

import json

import pytest
from fastapi.testclient import TestClient

from pathway_sim import compute_metrics, generate_patients, load_scenario, simulate
from service.app import create_app
from service.config import Settings
from service.runtime import prepare_run


@pytest.mark.parametrize("template,yaml,fid,n", [("finland_lung", "finland_lung.yaml", "baseline", 300),
                                                 ("norway_check", "stokstad.yaml", "observed", 60)])
def test_stored_documents_reproduce_the_yaml_metrics(tmp_path, template, yaml, fid, n):
    with TestClient(create_app(Settings(data_dir=tmp_path / "d", web_dir=tmp_path / "w"))) as c:
        p = c.post("/api/projects", json={"name": "t", "template": template}).json()["id"]
        world = c.get(f"/api/projects/{p}/world").json()["world"]
        doc = c.get(f"/api/projects/{p}/flowcharts/{fid}/versions/latest").json()
    sc0 = load_scenario(f"scenarios/{yaml}")
    pts = generate_patients(sc0, n, 3)
    want = compute_metrics(simulate(sc0, fid, pts, seed=3), sc0)
    sc, fc, pol = prepare_run(world, doc, seed=3)
    got = compute_metrics(simulate(sc, fc, generate_patients(sc, n, 3), policy=pol, seed=3), sc)
    assert json.dumps(got, sort_keys=True, default=str) == json.dumps(want, sort_keys=True, default=str)


def test_policy_override_changes_the_run(tmp_path):
    with TestClient(create_app(Settings(data_dir=tmp_path / "d", web_dir=tmp_path / "w"))) as c:
        p = c.post("/api/projects", json={"name": "t", "template": "finland_lung"}).json()["id"]
        world = c.get(f"/api/projects/{p}/world").json()["world"]
        doc = c.get(f"/api/projects/{p}/flowcharts/baseline/versions/latest").json()
    override = json.loads(json.dumps(doc["decision_policy"]))
    override["points"]["first_contact"]["default"] = {"nurse_visit": 1.0, "gp_visit": 0.0}
    shares = []
    for dp in (None, override):
        sc, fc, pol = prepare_run(world, doc, dp, seed=1)
        run = simulate(sc, fc, generate_patients(sc, 200, 1), policy=pol, seed=1)
        picks = [c["chosen"] for pr in run.patients for c in pr.choices if c["node"] == "first_contact"]
        shares.append(picks.count("nurse_visit") / len(picks))
    assert 0.3 < shares[0] < 0.7 and shares[1] == 1.0
