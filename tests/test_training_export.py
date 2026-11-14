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


# ---------------------------------------------------------------------------------------------- libraries (D52)

@pytest.fixture(scope="module")
def two_libs(tmp_path_factory):
    from patient_engine.reference import reference_cards
    from patient_engine.library import write_library
    from patient_engine.skeleton import Design
    world = load_world(WORLD)
    paths = []
    for seed, gen, extra in ((5, "reference", {}), (6, "llm", {"model": "test-model"})):
        d = tmp_path_factory.mktemp(f"lib{seed}")
        design = Design(mode="stratified", n=3 * len(world.catalogue.conditions), counts=tuple((c, 3) for c in world.catalogue.conditions))
        cards = list(reference_cards(world.catalogue, design, seed))
        meta = {"created": "1970-01-01T00:00:00Z", "generator": gen, **extra}
        try:
            write_library(cards, world.catalogue, d, meta=meta)
        except Exception as e:                                   # an llm library needs llm provenance on its cards
            pytest.skip(f"cannot write a {gen} test library from reference cards: {e}")
        paths.append(str(d))
    return paths


def test_libraries_holdout_and_meta(two_libs, tmp_path):
    out = str(tmp_path / "l.jsonl.gz")
    s = export(WORLD, 150, [1], out, libraries=[two_libs[0]], holdout_libraries=[two_libs[1]], quiet=True)
    rows = read(out)
    gens = {(r["meta"]["generator"], r["meta"]["library"]) for r in rows}
    assert len(gens) == 2 and {g for g, _ in gens} == {"reference", "llm:test-model"}
    assert {r["meta"]["split"] for r in rows if r["meta"]["generator"].startswith("llm")} == {"test"}
    assert {r["meta"]["split"] for r in rows if r["meta"]["generator"] == "reference"} >= {"train"}
    assert [x["holdout"] for x in s["libraries"]] == [False, True]


def test_library_for_another_catalogue_is_refused(tmp_path):
    with pytest.raises(SystemExit):
        export(WORLD, 10, [1], str(tmp_path / "x.jsonl.gz"), libraries=[str(tmp_path)], quiet=True)


# ---------------------------------------------------------------------------------------------- the HTTP JEV (D51)

def test_jev_over_http_against_the_stub_server(tmp_path, monkeypatch):
    from jev.stub import StubBackend
    from jev.stub_server import serve_in_thread
    srv, url = serve_in_thread(StubBackend({}))
    try:
        monkeypatch.setenv("JEV_ALLOWED_HOSTS", url.split("//", 1)[1])
        out = str(tmp_path / "j.jsonl.gz")
        s = export(WORLD, 60, [1], out, jev=url, quiet=True)
        rows = read(out)
        assert rows and s["jev_calls"][0]["calls"] == len(rows) and s["jev_calls"][0]["failures"] == 0
        assert s["jev_calls"][0]["network_calls"] >= 1 and s["jev_calls"][0]["p95_ms"] is not None
        assert {r["policy"] for r in rows} == {"stub@1"}
        for r in rows:
            DecisionRequest.from_dict(r["request"])
    finally:
        srv.shutdown()


def test_jev_not_allowed_or_unreachable_is_a_clear_error(tmp_path, monkeypatch):
    monkeypatch.setenv("JEV_ALLOWED_HOSTS", "")
    monkeypatch.delenv("JEV_DEFAULT_URL", raising=False)
    with pytest.raises(SystemExit, match="JEV_ALLOWED_HOSTS"):
        export(WORLD, 10, [1], str(tmp_path / "a.jsonl.gz"), jev="http://127.0.0.1:9", quiet=True)
    monkeypatch.setenv("JEV_ALLOWED_HOSTS", "127.0.0.1:9")
    with pytest.raises(SystemExit, match="not usable"):
        export(WORLD, 10, [1], str(tmp_path / "b.jsonl.gz"), jev="http://127.0.0.1:9", quiet=True)


def test_jev_accepts_a_factory_kind(tmp_path):
    out = str(tmp_path / "k.jsonl.gz")
    s = export(WORLD, 40, [1], out, jev="stub", quiet=True)
    assert s["rows"] > 0 and s["jev_calls"][0]["failures"] == 0
    with pytest.raises(SystemExit, match="not usable"):
        export(WORLD, 10, [1], str(tmp_path / "u.jsonl.gz"), jev="no_such_backend", quiet=True)


def _assessment_authors(rows):
    return [a["author"] for r in rows for a in r["request"]["context"].get("assessments", [])]


def test_table_assessments_are_stripped_by_default_and_kept_on_request(tmp_path):
    kept, dflt = str(tmp_path / "k.jsonl.gz"), str(tmp_path / "d.jsonl.gz")
    sk = export(WORLD, 150, [1], kept, explore=0.3, quiet=True, keep_table_notes=True)
    sd = export(WORLD, 150, [1], dflt, explore=0.3, quiet=True)
    rk, rd = read(kept), read(dflt)
    ak = _assessment_authors(rk)
    assert ak and all(a.endswith("/table") for a in ak)          # the placeholder tables wrote them
    assert any("Table rule" in a.get("note", "") for r in rk for a in r["request"]["context"]["assessments"])
    assert _assessment_authors(rd) == []
    assert not any("Table rule" in json.dumps(r["request"]) for r in rd)
    assert sd["rows"] == sk["rows"] and sd["rows_with_table_assessments_removed"] > 0
    assert sk["rows_with_table_assessments_removed"] == 0
    # nothing else changes: same rows, same choices, same labels
    assert [(r["chosen"], r["label"], r["meta"]) for r in rd] == [(r["chosen"], r["label"], r["meta"]) for r in rk]


def test_real_decider_assessments_stay():
    from pathway_sim.training_export import strip_placeholder_assessments
    req = {"context": {"assessments": [{"author": "gp_encounter/table", "note": "Table rule: x."},
                                       {"author": "gp_encounter/birch", "note": "model says"},
                                       {"author": "nurse_encounter/stub-model", "note": "y"}]}}
    assert strip_placeholder_assessments(req) == 1
    assert [a["author"] for a in req["context"]["assessments"]] == ["gp_encounter/birch", "nurse_encounter/stub-model"]


def test_with_text_writes_the_birch_adapters_own_rendering(tmp_path):
    out = str(tmp_path / "t.jsonl.gz")
    export(WORLD, 60, [1], out, quiet=True, with_text=True)
    rows = read(out)
    assert rows and all(set(r) == {"request", "request_text", "chosen", "policy", "behaviour_probs", "label", "outcome", "meta"} for r in rows)
    assert all(r["request_text"]["context"].startswith("Patient in Finnish primary care") for r in rows)
    assert any(r["request_text"]["evidence"] for r in rows)
    assert not any("Table rule" in json.dumps(r["request_text"]) for r in rows)
