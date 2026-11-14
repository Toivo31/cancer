"""A record-based JEV request (WP-C8-4) against the stub server: the envelope is unchanged, the extra
context keys are ignored by the stub, and the example file in jev/examples is a valid request."""

import json
from pathlib import Path

import pytest

from jev import StubBackend
from jev.contract import DecisionRequest
from jev.record_context import context_from_record
from jev.stub_server import serve_in_thread
from patient_engine.catalogue import load_catalogue
from patient_engine.record import Entry, Observation, Record
from test_jev_contract import _post

ROOT = Path(__file__).resolve().parent.parent.parent
OPTIONS = [{"id": "order_chest_xray", "label": "Chest X-ray", "test": "chest_xray",
            "features": {"invasive": False, "lead_days": 3.0}},
           {"id": "treat_antibiotics", "label": "Antibiotics"},
           {"id": "refer_urgent", "label": "Urgent referral"}]


def make_record():
    rec = Record("C1a2b3c4d5", {"age": 67, "sex": "f", "smoking_status": "former"})
    rec.append(Entry(0.0, 1, "encounter", encounter=1, role="nurse", reported=("cough_3wk", "fever"),
                     found={"cough_3wk": True, "fever": True}, action="book_gp_routine",
                     note="Cough, fever. GP booked."))
    rec.append(Entry(9.0, 1, "encounter", encounter=2, role="gp", reported=("cough_3wk", "fever"),
                     found={"weight_loss": False}, action="order_chest_xray", note="Chest X-ray ordered."))
    rec.append(Entry(11.5, 1, "result", observations=(
        Observation("chest_xray", 1, "ok", {"abnormal": False, "consolidation": True},
                    "Right lower lobe consolidation."),)))
    return rec


@pytest.fixture(scope="module")
def url():
    table = {"gp_encounter": {"default": {"order_chest_xray": 0.5, "treat_antibiotics": 0.3, "refer_urgent": 0.2}}}
    srv, u = serve_in_thread(StubBackend(table))
    yield u.rstrip("/")
    srv.shutdown()
    srv.server_close()


def request(ctx):
    return {"request_id": "C1a2b3c4d5:gp_encounter:3", "decision_point": "gp_encounter",
            "question_type": "next_step", "context": ctx, "options": OPTIONS}


def test_record_request_is_answered_by_the_stub(url):
    ctx = context_from_record(make_record(), role="gp", now_days=11.5,
                              catalogue=load_catalogue(ROOT / "catalogue" / "_examples" / "tiny"))
    status, body = _post(url, {"model": "stub@1", "requests": [request(ctx)]})
    assert status == 200, body
    r = body["responses"][0]
    assert r["request_id"] == "C1a2b3c4d5:gp_encounter:3"
    assert set(r["probs"]) == {o["id"] for o in OPTIONS}
    assert abs(sum(r["probs"].values()) - 1) < 1e-6


def test_example_file_is_a_valid_request_and_matches_the_builder():
    doc = json.loads((ROOT / "jev" / "examples" / "decide_request_record.json").read_text())
    for q in doc["requests"]:
        DecisionRequest.from_dict(q)
    built = context_from_record(make_record(), role="gp", now_days=11.5,
                                catalogue=load_catalogue(ROOT / "catalogue" / "_examples" / "tiny"))
    assert doc["requests"][0]["context"] == built
