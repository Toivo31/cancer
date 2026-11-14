"""``patient_engine merge`` and ``merge_libraries``: combine libraries made for one catalogue."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys

import pytest

from patient_engine.library import MANIFEST_FILE, LibraryError, library_sources, load_library, merge_libraries, write_library
from test_pe_library_support import ROOT, build_library, make_cards, tiny_catalogue, wide_catalogue

META_A = {"generator": "llm", "model": "model-a", "prompts": {"patient": "g1@1", "results": "g2@1"},
          "error_source": "guided", "created": "2026-11-14T10:00:00Z"}
META_B = {**META_A, "model": "model-b", "prompts": {"patient": "g1@2", "results": "g2@1"}, "created": "2026-11-14T12:00:00Z"}


@pytest.fixture()
def two(tmp_path):
    a, cat = build_library(tmp_path / "a", per_condition=4, lib_name="A", meta=META_A)
    b, _ = build_library(tmp_path / "b", per_condition=3, lib_name="B", meta=META_B)
    return tmp_path, a, b, cat


def test_merge_keeps_all_cards_and_counts(two):
    tmp, a, b, _ = two
    m = merge_libraries([a.path, b.path], tmp / "m")
    lib = load_library(tmp / "m")
    assert lib.id == m.id and len(lib) == 21
    assert {c.id for c in lib.cards} == {c.id for c in a.cards} | {c.id for c in b.cards}
    assert [c.id for c in lib.cards] == sorted(c.id for c in lib.cards)
    assert lib.manifest.card_count_by_condition == {"healthy": 7, "lung_cancer": 7, "pneumonia": 7}


def test_merge_is_deterministic_in_order_and_bytes(two):
    tmp, a, b, _ = two
    m1 = merge_libraries([a.path, b.path], tmp / "m1")
    m2 = merge_libraries([b.path, a.path], tmp / "m2")
    assert m1.id == m2.id
    for name in ("cards.jsonl.gz", MANIFEST_FILE):
        assert (tmp / "m1" / name).read_bytes() == (tmp / "m2" / name).read_bytes()
    # the time of the merge is not used: created is the latest source's
    assert m1.created == "2026-11-14T12:00:00Z"


def test_manifest_records_sources_and_per_source_model_info(two):
    tmp, a, b, _ = two
    m = merge_libraries([a.path, b.path], tmp / "m")
    assert (m.generator, m.model, m.error_source) == ("llm", "model-a+model-b", "guided")
    assert m.prompts == {"patient": "g1@1+g1@2", "results": "g2@1"}
    src = library_sources(tmp / "m")
    assert [s["id"] for s in src] == sorted([a.id, b.id])
    by_id = {s["id"]: s for s in src}
    assert by_id[a.id]["model"] == "model-a" and by_id[a.id]["n_cards"] == 12
    assert by_id[b.id]["prompts"] == {"patient": "g1@2", "results": "g2@1"} and by_id[b.id]["n_cards"] == 9
    # a plain library has no sources
    assert library_sources(a.path) == []


def test_sources_are_covered_by_the_library_id(two):
    tmp, a, b, _ = two
    merge_libraries([a.path, b.path], tmp / "m")
    f = tmp / "m" / MANIFEST_FILE
    rec = json.loads(f.read_text())
    rec["sources"][0]["model"] = "someone-else"
    f.write_text(json.dumps(rec))
    with pytest.raises(LibraryError):
        load_library(tmp / "m")


def test_merging_again_returns_the_same_library(two):
    tmp, a, b, _ = two
    first = merge_libraries([a.path, b.path], tmp / "m")
    before = (tmp / "m" / MANIFEST_FILE).read_bytes()
    assert merge_libraries([a.path, b.path], tmp / "m") == first
    assert (tmp / "m" / MANIFEST_FILE).read_bytes() == before


def test_a_different_library_cannot_replace_the_output(two):
    tmp, a, b, cat = two
    c, _ = build_library(tmp / "c", per_condition=2, lib_name="C", meta=META_A)
    merge_libraries([a.path, b.path], tmp / "m")
    with pytest.raises(LibraryError, match="immutable"):
        merge_libraries([a.path, c.path], tmp / "m")


def test_duplicate_card_ids_are_refused(two):
    tmp, a, _, cat = two
    same_names, _ = build_library(tmp / "d", per_condition=2, lib_name="A", meta=META_B)   # ids A:... again
    with pytest.raises(LibraryError, match="more than one library") as e:
        merge_libraries([a.path, same_names.path], tmp / "m")
    assert len(e.value.problems) == 6
    with pytest.raises(LibraryError, match="more than one library"):       # the same library twice
        merge_libraries([a.path, a.path], tmp / "m2")
    assert not (tmp / "m").exists() and not (tmp / "m2").exists()


def test_different_catalogues_are_refused(two):
    tmp, a, _, _ = two
    wide, widen = wide_catalogue(tmp / "wide")
    cards = [widen(c) for c in make_cards(2, tiny_catalogue().version_hash, "W")]
    write_library(cards, wide, tmp / "w", {**META_A})
    with pytest.raises(LibraryError, match="different catalogues"):
        merge_libraries([a.path, tmp / "w"], tmp / "m")
    assert not (tmp / "m").exists()


def test_fewer_than_two_libraries_are_refused(two):
    tmp, a, _, _ = two
    with pytest.raises(LibraryError, match="at least two"):
        merge_libraries([a.path], tmp / "m")


def test_mixed_generators_and_error_sources(tmp_path):
    cat = tiny_catalogue()
    write_library(make_cards(2, cat.version_hash, "R"), cat, tmp_path / "r", {"created": "2026-11-14T09:00:00Z"})
    write_library(make_cards(2, cat.version_hash, "L"), cat, tmp_path / "l", {**META_A, "error_source": "free"})
    m = merge_libraries([tmp_path / "r", tmp_path / "l"], tmp_path / "m")
    assert m.generator == "llm" and m.error_source is None and m.model == "model-a"
    assert {s["generator"] for s in library_sources(tmp_path / "m")} == {"reference", "llm"}


def test_a_merged_library_can_be_merged_again(two):
    tmp, a, b, cat = two
    merge_libraries([a.path, b.path], tmp / "ab")
    c, _ = build_library(tmp / "c", per_condition=2, lib_name="C", meta=META_A)
    m = merge_libraries([tmp / "ab", c.path], tmp / "abc")
    assert m.n_cards == 27 and len(library_sources(tmp / "abc")) == 2


# ---------------------------------------------------------------- command line and consumers

def run(*args, check=True):
    p = subprocess.run([sys.executable, "-m", "patient_engine", *map(str, args)], cwd=ROOT, capture_output=True,
                       text=True, timeout=120)
    if check:
        assert p.returncode == 0, p.stderr
    return p


def test_cli_merge_then_info_cohort_show(two):
    tmp, a, b, _ = two
    out = run("merge", a.path, b.path, "--out", tmp / "m").stdout
    assert "merged 2 libraries" in out and "21 cards" in out
    info = run("library-info", tmp / "m").stdout
    assert "merged from 2 libraries" in info and a.id in info and b.id in info and "model-a+model-b" in info
    j = json.loads(run("library-info", tmp / "m", "--json").stdout)
    assert len(j["sources"]) == 2 and j["format"] == "library/1"
    assert "n=300 seed=1" in run("cohort", tmp / "m", "--n", 300).stdout
    assert "patient" in run("show", tmp / "m", "#0").stdout
    # the same merge from the command line gives the same id as the function
    assert load_library(tmp / "m").id in info


def test_cli_merge_refusal_is_exit_1_with_a_message(two):
    tmp, a, _, _ = two
    p = run("merge", a.path, a.path, "--out", tmp / "m", check=False)
    assert p.returncode == 1 and "more than one library" in p.stderr and not (tmp / "m").exists()


def test_real_gemini_libraries_merge(tmp_path):
    t, s = ROOT / "libraries" / "gemini_trial", ROOT / "libraries" / "gemini_s2_30"
    if not (t.exists() and s.exists()):
        pytest.skip("gemini libraries not present")
    m = merge_libraries([t, s], tmp_path / "m")
    assert m.n_cards == 35 and len(library_sources(tmp_path / "m")) == 2
    assert m.id == merge_libraries([s, t], tmp_path / "m2").id


def test_simulator_accepts_a_merged_library(two):
    """The encounter loop's --library takes the merged library like any other (real catalogue, real libraries)."""
    t, s = ROOT / "libraries" / "gemini_trial", ROOT / "libraries" / "gemini_s2_30"
    if not (t.exists() and s.exists()):
        pytest.skip("gemini libraries not present")
    from patient_engine.catalogue import load_catalogue
    if load_library(t).manifest.catalogue_hash != load_catalogue(ROOT / "catalogue" / "lung-primary-care").version_hash:
        pytest.skip("the committed gemini libraries were made for an earlier catalogue (D59 changed the hash)")
    tmp = two[0]
    merge_libraries([t, s], tmp / "g")
    p = subprocess.run([sys.executable, "-m", "pathway_sim", "run", "scenarios/finland_encounter.yaml", "--flowchart",
                        "encounter", "--library", str(tmp / "g"), "--n", "100"],
                       cwd=ROOT, capture_output=True, text=True, timeout=300)
    assert p.returncode == 0, p.stderr
    assert load_library(tmp / "g").id in p.stdout
