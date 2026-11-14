"""WP-W4-4: JEV training export. I1 (revealed-only requests), determinism, contract validity."""

import gzip
import json
import re

import pytest

from jev.contract import DecisionRequest
from patient_engine.card import HIDDEN_FIELD_NAMES
from pathway_sim.encounter import load_world
from pathway_sim.training_export import export, split_of

WORLD = "scenarios/finland_encounter.yaml"


def read(path):
    with gzip.open(path, "rt") as f:
        return [json.loads(x) for x in f]


@pytest.fixture(scope="module")
def exported(tmp_path_factory):
    d = tmp_path_factory.mktemp("tr")
    a, b = str(d / "a.jsonl.gz"), str(d / "b.jsonl.gz")
    s = export(WORLD, 400, [1, 2], a, explore=0.3, quiet=True)
    export(WORLD, 400, [1, 2], b, explore=0.3, quiet=True)
    return a, b, s


def strings(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from strings(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from strings(v)
    elif isinstance(obj, str):
        yield obj


def test_same_seed_same_bytes(exported):
    a, b, _ = exported
    with gzip.open(a, "rb") as x, gzip.open(b, "rb") as y:
        assert x.read() == y.read()


def test_rows_shape_and_contract(exported):
    a, _, s = exported
    rows = read(a)
    assert len(rows) == s["rows"] > 500
    for r in rows:
        assert set(r) == {"request", "chosen", "policy", "behaviour_probs", "label", "outcome", "meta"}
        req = DecisionRequest.from_dict(r["request"])
        assert r["chosen"] in req.option_ids
        assert set(r["label"]) == {"primary", "coexisting", "class"}
        assert r["meta"]["split"] in ("train", "val", "test")
    assert {r["policy"].endswith("explore") for r in rows} == {True, False}


def test_i1_request_holds_no_hidden_information(exported):
    a, _, _ = exported
    world = load_world(WORLD)
    ids = set(world.catalogue.conditions)
    definitive = {t.id for t in world.catalogue.tests.values() if any(o.id.endswith("_confirmed") for o in t.outputs)}
    assert definitive
    for r in read(a):
        ctx = r["request"]["context"]
        # offered options are the same for every patient; a clinician's assessment and note are the decider's own prose
        # (they may name a diagnosis); a definitive test's result is its own answer. Everything else may not name one.
        revealed = {k: v for k, v in ctx.items() if k not in ("assessments", "notes", "observations", "history", "actions")}
        revealed["observations"] = [o for o in ctx["observations"] if o["test"] not in definitive]
        revealed["history"] = [h for h in ctx["history"] if h["test"] not in definitive]
        revealed = [r["request"]["request_id"], r["request"]["decision_point"], revealed]
        for s in strings(revealed):
            assert s not in ids, s
            assert s not in HIDDEN_FIELD_NAMES, s
            assert not re.match(r"^L_[0-9a-f]{8}", s) and not re.match(r"^c_[0-9a-f]{6}", s), s
        assert r["label"]["primary"] not in json.dumps(revealed)
        # the label and the outcome sit outside the request
        assert "label" not in r["request"] and "outcome" not in r["request"]
        assert not ({"label", "outcome", "primary"} & set(ctx))


def test_split_is_deterministic_and_roughly_80_10_10():
    xs = [split_of(f"c{i}") for i in range(5000)]
    assert xs == [split_of(f"c{i}") for i in range(5000)]
    assert 0.77 < xs.count("train") / 5000 < 0.83 and xs.count("val") > 300 and xs.count("test") > 300
