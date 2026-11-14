"""Every parameter in params/*.yaml must trace to a registered source or be tagged `assumption`."""
from pathlib import Path

import pytest
import yaml

PARAMS = Path(__file__).resolve().parent.parent / "params"
PARAM_FILES = sorted(p for p in PARAMS.glob("*.yaml") if p.name != "sources.yaml")


def load(path):
    with open(path) as f:
        return yaml.safe_load(f)


def walk(node, prefix=""):
    """Yield (dotted_key, dict) for every mapping that carries a `value` key."""
    if isinstance(node, dict):
        if "value" in node:
            yield prefix, node
            return
        for k, v in node.items():
            yield from walk(v, f"{prefix}.{k}" if prefix else str(k))


def source_ids():
    return {s["id"] for s in load(PARAMS / "sources.yaml")}


def test_all_yaml_files_load():
    assert (PARAMS / "sources.yaml").exists()
    for p in PARAMS.glob("*.yaml"):
        assert load(p) is not None, p


def test_sources_are_well_formed():
    sources = load(PARAMS / "sources.yaml")
    assert isinstance(sources, list) and sources
    ids = [s["id"] for s in sources]
    assert len(ids) == len(set(ids)), "duplicate source ids"
    for s in sources:
        assert s.get("url", "").startswith("http"), f"{s['id']} has no url"
        assert s.get("citation"), s["id"]
        assert s.get("access") in {"full_text", "abstract", "secondary"}, s["id"]
        assert s.get("supports"), s["id"]
        assert "accessed" in s and "year" in s, s["id"]


@pytest.mark.parametrize("path", PARAM_FILES, ids=lambda p: p.name)
def test_every_parameter_has_valid_source(path):
    ids = source_ids()
    params = list(walk(load(path)))
    assert params, f"no parameters found in {path.name}"
    for key, p in params:
        src = p.get("source")
        assert src, f"{path.name}:{key} has no source"
        assert src == "assumption" or src in ids, f"{path.name}:{key} unknown source {src!r}"
        assert p.get("note"), f"{path.name}:{key} has no note"
        assert "unit" in p, f"{path.name}:{key} has no unit"


@pytest.mark.parametrize("path", PARAM_FILES, ids=lambda p: p.name)
def test_distributions_are_valid(path):
    for key, p in walk(load(path)):
        d = p.get("dist")
        if d is None:
            continue
        assert d["dist"] in {"lognormal", "uniform", "fixed", "empirical"}, key
        if d["dist"] == "lognormal":
            assert d["median"] > 0 and d["p90"] > d["median"], key
        if d["dist"] == "uniform":
            assert d["high"] > d["low"], key


def test_fractions_in_unit_interval():
    for path in PARAM_FILES:
        for key, p in walk(load(path)):
            if p.get("unit") == "fraction":
                assert 0 <= p["value"] <= 1, f"{path.name}:{key}"


def test_no_unused_sources():
    used = set()
    for path in PARAM_FILES:
        for _, p in walk(load(path)):
            used.add(p["source"])
    unused = source_ids() - used
    # Sources may support only claims in docs; just require that most are used.
    assert len(unused) <= 3, f"unused sources: {sorted(unused)}"
