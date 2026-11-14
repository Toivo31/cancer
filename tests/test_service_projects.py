"""Service skeleton, projects, world, flowchart versions, validate (M2-3, M2-4)."""

import copy
import json

import pytest
from fastapi.testclient import TestClient

from service.app import create_app
from service.config import Settings


@pytest.fixture()
def client(tmp_path):
    app = create_app(Settings(data_dir=tmp_path / "data", web_dir=tmp_path / "noweb"))
    with TestClient(app) as c:
        c.app_state = app
        yield c


def make(client, template="norway_check", name="Test"):
    r = client.post("/api/projects", json={"name": name, "template": template})
    assert r.status_code == 201, r.text
    return r.json()


def err(r, status, code):
    assert r.status_code == status, r.text
    e = r.json()["error"]
    assert e["code"] == code, e
    return e


def test_docs_and_health(client):
    assert client.get("/docs").status_code == 200
    spec = client.get("/openapi.json").json()
    assert "/api/templates" in spec["paths"] and "/api/projects/{p}/validate" in spec["paths"]
    assert client.get("/api/health").json()["ok"] is True


def test_templates(client):
    ts = client.get("/api/templates").json()
    assert [t["id"] for t in ts] == ["finland_lung", "norway_check"]
    fi = ts[0]
    assert {f["id"] for f in fi["flowcharts"]} >= {"baseline", "direct_ct"} and all(f["nodes"] > 5 for f in fi["flowcharts"])
    full = client.get("/api/templates/finland_lung").json()
    assert full["world"]["id"] == "finland_lung" and full["flowchart_documents"][0]["nodes"]
    assert client.get("/api/templates/nope").status_code == 404


def test_create_project_from_template(client):
    p = make(client, "finland_lung", "Finland")
    assert p["name"] == "Finland" and p["world_id"] == "finland_lung" and p["world_rev"] == 1
    ids = {f["id"] for f in p["flowcharts"]}
    assert "baseline" in ids and all(f["latest_version"] == 1 and not f["versions"][0]["locked"] for f in p["flowcharts"])
    assert client.get(f"/api/projects/{p['id']}").json()["id"] == p["id"]
    assert [x["id"] for x in client.get("/api/projects").json()] == [p["id"]]
    e = err(client.post("/api/projects", json={"name": "x", "template": "nope"}), 404, "not_found")
    err(client.post("/api/projects", json={"name": "   ", "template": "norway_check"}), 422, "invalid_request")
    err(client.post("/api/projects", json={"name": "x"}), 422, "template_required")


def test_duplicate_project_names_get_suffix(client):
    a, b, c = (make(client, name="Same") for _ in range(3))
    assert [a["name"], b["name"], c["name"]] == ["Same", "Same (2)", "Same (3)"]


def test_unknown_project_is_404_everywhere(client):
    for method, path in [("get", ""), ("delete", ""), ("get", "/world"), ("get", "/flowcharts"), ("get", "/flowcharts/x/versions/1")]:
        err(getattr(client, method)(f"/api/projects/p_nope{path}"), 404, "not_found")


def test_delete_project(client):
    p = make(client)
    assert client.delete(f"/api/projects/{p['id']}").status_code == 204
    assert client.get(f"/api/projects/{p['id']}").status_code == 404
    assert client.get("/api/projects").json() == []


def test_world_get_put(client):
    p = make(client, "finland_lung")
    w = client.get(f"/api/projects/{p['id']}/world").json()
    assert w["rev"] == 1 and w["world"]["resources"]["ct_scanner"] if "ct_scanner" in w["world"]["resources"] else True
    world = w["world"]
    # preserves what the client sent, including keys the models do not know
    assert "arrivals_source" in world and "finnish_targets" in world
    res = next(iter(world["resources"]))
    world["resources"][res]["capacity_per_day"] = 77
    r = client.put(f"/api/projects/{p['id']}/world", json=world)
    assert r.status_code == 200, r.text
    assert r.json()["rev"] == 2 and r.json()["world"]["resources"][res]["capacity_per_day"] == 77
    assert client.get(f"/api/projects/{p['id']}/world").json()["world"]["resources"][res]["capacity_per_day"] == 77
    # stale revision
    err(client.put(f"/api/projects/{p['id']}/world", params={"if_rev": 1}, json=world), 409, "stale_revision")
    assert client.put(f"/api/projects/{p['id']}/world", params={"if_rev": 2}, json=world).status_code == 200


def test_world_put_rejections(client):
    p = make(client, "finland_lung")
    world = client.get(f"/api/projects/{p['id']}/world").json()["world"]
    bad = copy.deepcopy(world)
    bad["conditions"][0]["prevalence"] = 0.5
    e = err(client.put(f"/api/projects/{p['id']}/world", json=bad), 422, "invalid_document")
    assert e["problems"]
    renamed = {**world, "id": "other"}
    err(client.put(f"/api/projects/{p['id']}/world", json=renamed), 422, "invalid_document")
    err(client.put(f"/api/projects/{p['id']}/world", json={"id": "x"}), 422, "invalid_request")


def test_world_edit_that_breaks_a_flowchart_is_reported_not_blocked(client):
    p = make(client, "finland_lung")
    world = client.get(f"/api/projects/{p['id']}/world").json()["world"]
    victim = next(n["test"] for n in client.get(f"/api/projects/{p['id']}/flowcharts/baseline").json()["latest"]["nodes"] if n.get("test"))
    del world["tests"][victim]
    r = client.put(f"/api/projects/{p['id']}/world", json=world)
    assert r.status_code == 200
    assert any(x["code"] == "unknown_test" and x["flowchart_id"] == "baseline" for x in r.json()["problems"])


def test_flowchart_versions(client):
    p = make(client)
    pid = p["id"]
    fcs = client.get(f"/api/projects/{pid}/flowcharts").json()
    obs = next(f for f in fcs if f["id"] == "observed")
    assert obs["latest"]["version"] == 1 and obs["latest"]["parent_version"] is None
    doc = obs["latest"]
    doc["name"] = "Edited"
    r = client.post(f"/api/projects/{pid}/flowcharts/observed/versions", json=doc)
    assert r.status_code == 201, r.text
    assert r.json()["version"] == 2 and r.json()["parent_version"] == 1 and r.json()["name"] == "Edited"
    assert client.get(f"/api/projects/{pid}/flowcharts/observed/versions/latest").json()["version"] == 2
    assert client.get(f"/api/projects/{pid}/flowcharts/observed/versions/1").json()["name"] != "Edited"
    err(client.get(f"/api/projects/{pid}/flowcharts/observed/versions/9"), 404, "not_found")
    err(client.get(f"/api/projects/{pid}/flowcharts/observed/versions/abc"), 422, "invalid_version")
    vs = client.get(f"/api/projects/{pid}/flowcharts/observed/versions").json()
    assert [v["version"] for v in vs] == [1, 2]
    # the client cannot pick the version number or the parent
    doc2 = {**doc, "version": 99, "parent_version": 50}
    assert client.post(f"/api/projects/{pid}/flowcharts/observed/versions", json=doc2).json()["version"] == 3


def test_new_flowchart_and_duplicate_id(client):
    p = make(client)
    pid = p["id"]
    doc = client.get(f"/api/projects/{pid}/flowcharts/observed").json()["latest"]
    doc["id"] = "mine"
    r = client.post(f"/api/projects/{pid}/flowcharts", json=doc)
    assert r.status_code == 201 and r.json()["version"] == 1
    err(client.post(f"/api/projects/{pid}/flowcharts", json=doc), 409, "duplicate_flowchart")
    # path id and document id must agree
    err(client.post(f"/api/projects/{pid}/flowcharts/observed/versions", json=doc), 422, "invalid_document")


def test_save_rejects_invalid_documents_with_codes(client):
    p = make(client, "finland_lung")
    pid = p["id"]
    base = client.get(f"/api/projects/{pid}/flowcharts/baseline").json()["latest"]

    def post(mutate):
        d = copy.deepcopy(base)
        mutate(d)
        r = client.post(f"/api/projects/{pid}/flowcharts/baseline/versions", json=d)
        assert r.status_code == 422, r.text
        return {x["code"] for x in r.json()["error"]["problems"]}

    assert "duplicate_id" in post(lambda d: d["nodes"].append(dict(d["nodes"][0])))
    assert "unknown_reference" in post(lambda d: d["edges"].append({"from": "ghost", "to": "ct", "type": "required"}))
    assert "unknown_test" in post(lambda d: d["nodes"][1].update(test="no_such_test"))
    assert "cycle" in post(lambda d: d["edges"].append({"from": "treat", "to": "first_contact", "type": "required"}))
    exits = {n["id"] for n in base["nodes"] if n["kind"] == "exit"}
    assert "no_exit" in post(lambda d: d.update(nodes=[n for n in d["nodes"] if n["id"] not in exits],
                                                 edges=[e for e in d["edges"] if e["to"] not in exits and e["from"] not in exits]))
    assert "guard_syntax" in post(lambda d: next(n for n in d["nodes"] if n.get("when")).update(when="ct and ("))
    assert "decision_needs_two_options" in post(lambda d: d["edges"].__setitem__(
        slice(None), [e for e in d["edges"] if not (e["type"] == "option" and e["from"] == "sample_choice" and e["to"] == "ttnb")]))
    # nothing was stored by the failures
    assert client.get(f"/api/projects/{pid}/flowcharts/baseline").json()["latest_version"] == 1


def test_validate_endpoint_never_stores(client):
    p = make(client)
    pid = p["id"]
    doc = client.get(f"/api/projects/{pid}/flowcharts/observed").json()["latest"]
    r = client.post(f"/api/projects/{pid}/validate", json={"flowchart": doc})
    assert r.status_code == 200 and r.json() == {"ok": True, "problems": []}
    doc["nodes"].append(dict(doc["nodes"][0]))
    bad = client.post(f"/api/projects/{pid}/validate", json={"flowchart": doc}).json()
    assert bad["ok"] is False and bad["problems"][0]["code"] == "duplicate_id" and bad["problems"][0]["node"] == doc["nodes"][0]["id"]
    assert client.get(f"/api/projects/{pid}/flowcharts/observed").json()["latest_version"] == 1
    # an optional world is checked too
    world = client.get(f"/api/projects/{pid}/world").json()["world"]
    world["conditions"][0]["prevalence"] = 0.3
    doc["nodes"].pop()
    w = client.post(f"/api/projects/{pid}/validate", json={"world": world, "flowchart": doc}).json()
    assert w["ok"] is False


def test_locked_versions_are_immutable(client):
    p = make(client)
    pid, store = p["id"], client.app.state.services.store
    doc, v = store.get_version_for_run(pid, "observed")      # what a run does
    assert v == 1
    assert client.get(f"/api/projects/{pid}/flowcharts/observed/versions/1").headers["X-Version-Locked"] == "true"
    assert client.get(f"/api/projects/{pid}/flowcharts/observed").json()["versions"][0]["locked"] is True
    doc["name"] = "tampered"
    err(client.put(f"/api/projects/{pid}/flowcharts/observed/versions/1", json=doc), 409, "version_locked")
    err(client.delete(f"/api/projects/{pid}/flowcharts/observed"), 409, "version_locked")
    # a new version is still allowed, and while unlocked it can be overwritten
    v2 = client.post(f"/api/projects/{pid}/flowcharts/observed/versions", json=doc).json()
    assert v2["version"] == 2
    v2["name"] = "draft"
    r = client.put(f"/api/projects/{pid}/flowcharts/observed/versions/2", json=v2)
    assert r.status_code == 200 and r.json()["name"] == "draft" and r.json()["parent_version"] == 1
    # unlocked flowchart can be deleted
    assert client.delete(f"/api/projects/{pid}/flowcharts/faster_pet").status_code == 204
    assert client.get(f"/api/projects/{pid}/flowcharts/faster_pet").status_code == 404


def test_giant_payload_refused(tmp_path):
    app = create_app(Settings(data_dir=tmp_path / "d", web_dir=tmp_path / "w", max_document_bytes=2000))
    with TestClient(app) as c:
        r = c.post("/api/projects", json={"name": "x" * 5000, "template": "norway_check"})
        assert r.status_code == 413 and r.json()["error"]["code"] == "payload_too_large"
        # chunked body without Content-Length is counted as it is read
        def gen():
            yield b'{"name": "'
            yield b"x" * 3000
            yield b'", "template": "norway_check"}'
        r = c.post("/api/projects", content=gen(), headers={"content-type": "application/json"})
        assert r.status_code == 413, r.text


def test_blob_store_round_trip_and_cleanup(client):
    p = make(client)
    store = client.app.state.services.store
    path = store.put_blob(p["id"], "runs", "r_1", {"a": [1, 2, 3]})
    assert path.endswith("r_1.json.gz") and store.has_blob(p["id"], "runs", "r_1")
    assert store.get_blob(p["id"], "runs", "r_1") == {"a": [1, 2, 3]}
    with pytest.raises(ValueError):
        store.put_blob(p["id"], "../x", "k", {})
    client.delete(f"/api/projects/{p['id']}")
    assert not store.has_blob(p["id"], "runs", "r_1")


def test_extra_tables_cascade_with_project(client):
    p = make(client)
    store = client.app.state.services.store
    store.ensure_schema("CREATE TABLE IF NOT EXISTS thing (id TEXT PRIMARY KEY, project_id TEXT REFERENCES projects(id) ON DELETE CASCADE)")
    store.execute("INSERT INTO thing VALUES ('t1', ?)", (p["id"],))
    client.delete(f"/api/projects/{p['id']}")
    assert store.query("SELECT * FROM thing") == []
