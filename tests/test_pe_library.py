"""Library store (WP-C1-6): write, load, hash, tamper detection."""

from __future__ import annotations

import gzip
import hashlib
import json
import random
from pathlib import Path

import pytest

from patient_engine.card import card_from_json, card_to_json
from patient_engine.library import CARDS_FILE, MANIFEST_FILE, LibraryError, load_library, write_library
from test_pe_library_support import CONDITIONS, build_library, make_card, make_cards, tiny_catalogue


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    path = tmp_path_factory.mktemp("lib") / "lib"
    lib, cat = build_library(path, per_condition=30)
    return path, lib, cat


def _fresh(tmp_path, per_condition=4):
    path = tmp_path / "lib"
    build_library(path, per_condition=per_condition)
    return path


# ---------------------------------------------------------------- round trip

def test_round_trip_equal_cards_and_same_hash(built):
    path, lib, cat = built
    originals = sorted((card_from_json(d) for d in make_cards(30, cat.version_hash)), key=lambda c: c.id)
    assert list(lib.cards) == originals
    assert [card_to_json(c) for c in lib.cards] == [card_to_json(c) for c in originals]
    again = load_library(path, cat)
    assert again.manifest == lib.manifest and again.id == lib.id and again.cards == lib.cards
    assert lib.id.startswith("L_") and len(lib.id) == 18
    assert lib.manifest.card_count_by_condition == {c: 30 for c in sorted(CONDITIONS)}
    assert lib.manifest.catalogue_hash == cat.version_hash and lib.manifest.catalogue_id == "tiny"
    assert len(lib) == 90 and lib.by_condition["lung_cancer"] == tuple(i for i, c in enumerate(lib.cards) if c.primary_condition == "lung_cancer")


def test_id_does_not_depend_on_input_order_or_created_time(tmp_path):
    cat = tiny_catalogue()
    cards = make_cards(5, cat.version_hash)
    shuffled = list(cards)
    random.Random(3).shuffle(shuffled)
    a = write_library(cards, cat, tmp_path / "a", {"created": "2026-01-01T00:00:00Z"})
    b = write_library(shuffled, cat, tmp_path / "b", {"created": "2030-05-05T00:00:00Z"})
    assert a.id == b.id and a.created != b.created
    assert (tmp_path / "a" / CARDS_FILE).read_bytes() == (tmp_path / "b" / CARDS_FILE).read_bytes()


def test_id_changes_with_a_card_and_with_metadata(tmp_path):
    cat = tiny_catalogue()
    cards = make_cards(3, cat.version_hash)
    base = write_library(cards, cat, tmp_path / "a").id
    changed = [dict(c) for c in cards]
    changed[0] = make_card(0, "lung_cancer", cat.version_hash)
    changed[0]["background"] = {**changed[0]["background"], "age": 99}
    assert write_library(changed, cat, tmp_path / "b").id != base
    assert write_library(cards, cat, tmp_path / "c", {"model": "m-1"}).id != base
    assert write_library(cards, cat, tmp_path / "d", {"prompts": {"patient": "g1@2"}}).id != base


def test_manifest_defaults_come_from_card_provenance_and_meta_overrides(tmp_path):
    cat = tiny_catalogue()
    m = write_library(make_cards(2, cat.version_hash), cat, tmp_path / "a")
    assert (m.generator, m.error_source, m.model, m.prompts) == ("reference", "guided", None, {})
    m2 = write_library(make_cards(2, cat.version_hash), cat, tmp_path / "b",
                       {"generator": "llm", "model": "m", "prompts": {"patient": "g1@1"}, "error_source": "free"})
    assert (m2.generator, m2.model, m2.prompts, m2.error_source) == ("llm", "m", {"patient": "g1@1"}, "free")


def test_write_accepts_card_objects_and_dicts(tmp_path):
    cat = tiny_catalogue()
    dicts = make_cards(2, cat.version_hash)
    mixed = [card_from_json(dicts[0])] + dicts[1:]
    assert write_library(mixed, cat, tmp_path / "a").id == write_library(dicts, cat, tmp_path / "b").id


# ---------------------------------------------------------------- immutability

def test_writing_the_same_library_again_changes_nothing(tmp_path):
    cat = tiny_catalogue()
    cards = make_cards(3, cat.version_hash)
    first = write_library(cards, cat, tmp_path / "lib", {"created": "2026-01-01T00:00:00Z"})
    before = (tmp_path / "lib" / MANIFEST_FILE).read_bytes()
    second = write_library(cards, cat, tmp_path / "lib", {"created": "2031-01-01T00:00:00Z"})
    assert second == first and (tmp_path / "lib" / MANIFEST_FILE).read_bytes() == before


def test_a_different_library_cannot_replace_an_existing_one(tmp_path):
    cat = tiny_catalogue()
    write_library(make_cards(3, cat.version_hash), cat, tmp_path / "lib")
    with pytest.raises(LibraryError, match="immutable"):
        write_library(make_cards(4, cat.version_hash), cat, tmp_path / "lib")
    assert load_library(tmp_path / "lib").manifest.n_cards == 9
    assert not [p for p in tmp_path.iterdir() if ".tmp-" in p.name]


def test_load_accepts_the_manifest_path(built):
    path, lib, _ = built
    assert load_library(path / MANIFEST_FILE).id == lib.id


# ---------------------------------------------------------------- tamper

def _flip(path: Path, pos: int) -> None:
    b = bytearray(path.read_bytes())
    b[pos] ^= 0x01
    path.write_bytes(bytes(b))


def test_editing_one_byte_of_the_cards_file_raises(tmp_path):
    path = _fresh(tmp_path)
    f = path / CARDS_FILE
    original = f.read_bytes()
    n = len(original)
    positions = set(range(0, 14)) | set(range(n - 12, n)) | set(range(0, n, max(n // 150, 1)))
    for pos in sorted(positions):
        f.write_bytes(original)
        _flip(f, pos)
        with pytest.raises(LibraryError):
            load_library(path)
    f.write_bytes(original)
    assert load_library(path).manifest.n_cards == 12            # untouched file still loads


def test_truncated_or_missing_files_raise(tmp_path):
    path = _fresh(tmp_path)
    f = path / CARDS_FILE
    original = f.read_bytes()
    f.write_bytes(original[:-5])
    with pytest.raises(LibraryError):
        load_library(path)
    f.unlink()
    with pytest.raises(LibraryError):
        load_library(path)
    f.write_bytes(original)
    (path / MANIFEST_FILE).unlink()
    with pytest.raises(LibraryError):
        load_library(path)


def test_editing_the_manifest_raises(tmp_path):
    path = _fresh(tmp_path)
    m = path / MANIFEST_FILE
    original = json.loads(m.read_text())
    edits = {
        "id": "L_0000000000000000",
        "model": "someone-else",
        "generator": "llm",
        "catalogue_hash": "0" * 64,
        "catalogue_id": "other",
        "prompts": {"patient": "x"},
        "error_source": "free",
        "card_count_by_condition": {"healthy": 4, "lung_cancer": 4, "pneumonia": 3},
    }
    for key, value in edits.items():
        m.write_text(json.dumps({**original, key: value}))
        with pytest.raises(LibraryError):
            load_library(path)
    m.write_text(json.dumps(original))
    assert load_library(path).manifest.n_cards == 12


def test_edited_cards_with_a_recomputed_file_hash_still_fail_the_content_hash(tmp_path):
    """An attacker who also fixes the file hash in the manifest is caught by the library id."""
    path = _fresh(tmp_path)
    f, m = path / CARDS_FILE, path / MANIFEST_FILE
    lines = gzip.decompress(f.read_bytes()).split(b"\n")
    first = json.loads(lines[0])
    first["background"]["age"] += 1
    lines[0] = json.dumps(first, sort_keys=True, separators=(",", ":")).encode()
    payload = gzip.compress(b"\n".join(lines), compresslevel=6, mtime=0)
    f.write_bytes(payload)
    rec = json.loads(m.read_text())
    rec["file"].update(bytes=len(payload), sha256=hashlib.sha256(payload).hexdigest())
    m.write_text(json.dumps(rec))
    with pytest.raises(LibraryError, match="hash"):
        load_library(path)


def test_wrong_catalogue_is_refused(built, tmp_path):
    path, _, cat = built
    other = tiny_catalogue()
    object.__setattr__(other, "version_hash", "f" * 64)
    with pytest.raises(LibraryError, match="catalogue"):
        load_library(path, other)
    assert load_library(path, cat).catalogue is cat


# ---------------------------------------------------------------- what write refuses

def test_write_refuses_bad_cards(tmp_path):
    cat = tiny_catalogue()
    good = make_cards(2, cat.version_hash)

    with pytest.raises(LibraryError, match="at least one"):
        write_library([], cat, tmp_path / "e")
    with pytest.raises(LibraryError, match="duplicate"):
        write_library(good + [good[0]], cat, tmp_path / "d")

    other_cat = json.loads(json.dumps(good[0]))
    other_cat["id"] = "x:1"
    other_cat["provenance"]["catalogue_id"] = "not_tiny"
    with pytest.raises(LibraryError, match="catalogue 'not_tiny'"):
        write_library(good + [other_cat], cat, tmp_path / "c")

    stale = json.loads(json.dumps(good[0]))
    stale["id"] = "x:2"
    stale["provenance"]["catalogue_hash"] = "0" * 64
    with pytest.raises(LibraryError, match="catalogue hash"):
        write_library(good + [stale], cat, tmp_path / "h")
    write_library(good + [stale], cat, tmp_path / "h2", check_catalogue_hash=False)

    broken = json.loads(json.dumps(good[0]))
    broken["id"] = "x:3"
    del broken["observations"]["all_active"]["chest_xray"]
    with pytest.raises(LibraryError) as e:
        write_library(good + [broken], cat, tmp_path / "s")
    assert e.value.problems
    write_library(good + [broken], cat, tmp_path / "s2", validate=False)

    with pytest.raises(LibraryError, match="generator"):
        write_library(good, cat, tmp_path / "g", {"generator": "magic"})
    assert not (tmp_path / "e").exists() and not (tmp_path / "d").exists()


def test_cards_file_is_gzip_json_lines_one_card_per_line(built):
    path, lib, _ = built
    lines = gzip.decompress((path / CARDS_FILE).read_bytes()).decode().splitlines()
    assert len(lines) == 90
    ids = [json.loads(line)["id"] for line in lines]
    assert ids == sorted(ids) == [c.id for c in lib.cards]
    assert all(json.loads(line)["provenance"]["library"] is None for line in lines)
