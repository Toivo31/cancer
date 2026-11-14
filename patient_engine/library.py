"""Library store (``library/1``): an immutable, stored set of cards with a content-hash id.

A library is a directory::

    <path>/manifest.json     library/1 manifest (``LibraryManifest.to_json()``) plus {"file": {name, bytes, sha256}}
    <path>/cards.jsonl.gz    one ``card_to_json`` dict per line, sorted by card id, gzip with a fixed header

The library id is ``"L_" + first 16 hex of SHA-256`` over the catalogue id and hash, generator, model, prompt
versions, error source and every card line (canonical JSON: sorted keys, no spaces). ``created`` and the card
counts are not hashed (the counts are checked against the cards). ``load_library`` recomputes the id, checks
the file hash recorded in the manifest, and raises ``LibraryError`` for any difference, so changing a byte of
either file is caught.

Cards keep ``provenance.library = None`` inside the file (the id is computed from the cards, so it cannot be
inside them). The library object knows its id.

Standard library only. Cards are hidden-side objects; the simulation reaches them through
``patient_engine.reveal.RevealHandle`` only.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import shutil
import tempfile
import zlib
from dataclasses import dataclass, field
from functools import cached_property
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from .card import (
    ERROR_SOURCES,
    GENERATORS,
    INITIAL_STATE,
    LIBRARY_FORMAT,
    Card,
    LibraryManifest,
    card_from_json,
    card_schema_problems,
    card_to_json,
)

__all__ = ["Library", "LibraryError", "write_library", "load_library", "CARDS_FILE", "MANIFEST_FILE"]

CARDS_FILE = "cards.jsonl.gz"
MANIFEST_FILE = "manifest.json"
_ID_HEX = 16
_GZIP_LEVEL = 6


class LibraryError(ValueError):
    """A library cannot be written or read: bad cards, a mismatch with the catalogue, or a file that does
    not match its recorded hash. ``problems`` carries detail when there is any."""

    def __init__(self, message: str, problems: list | None = None):
        super().__init__(message)
        self.problems = problems or []


# ============================================================================ the object

@dataclass(frozen=True)
class Library:
    """A loaded library. ``cards`` is sorted by card id; ``by_condition`` maps a primary condition id to the
    positions of its cards in ``cards`` (in that order)."""
    manifest: LibraryManifest
    cards: tuple[Card, ...]
    path: Path | None = field(default=None, compare=False)
    catalogue: Any = field(default=None, compare=False, repr=False)

    @property
    def id(self) -> str:
        return self.manifest.id

    def __len__(self) -> int:
        return len(self.cards)

    @cached_property
    def by_condition(self) -> dict[str, tuple[int, ...]]:
        out: dict[str, list[int]] = {}
        for i, c in enumerate(self.cards):
            out.setdefault(c.primary_condition, []).append(i)
        return {k: tuple(v) for k, v in out.items()}

    def card(self, card_id: str) -> Card:
        for c in self.cards:
            if c.id == card_id:
                return c
        raise KeyError(card_id)


# ============================================================================ hashing

def _canonical(d: Any) -> bytes:
    return json.dumps(d, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def _library_id(header: Mapping[str, Any], lines: Iterable[bytes]) -> str:
    h = hashlib.sha256()
    h.update(_canonical({"format": LIBRARY_FORMAT, **header}))
    for line in lines:
        h.update(b"\n")
        h.update(line)
    return "L_" + h.hexdigest()[:_ID_HEX]


def _header(manifest_like: Mapping[str, Any]) -> dict[str, Any]:
    h = {k: manifest_like.get(k) for k in ("catalogue_id", "catalogue_hash", "generator", "model", "error_source")}
    h["prompts"] = dict(manifest_like.get("prompts") or {})
    return h


def _gzip_header() -> bytes:
    """The 10 header bytes our writer produces (fixed mtime, so the file is reproducible); anything else is
    a modified or foreign file."""
    return gzip.compress(b"", compresslevel=_GZIP_LEVEL, mtime=0)[:10]


# ============================================================================ write

def _as_card(c: Card | Mapping[str, Any]) -> Card:
    return c if isinstance(c, Card) else card_from_json(c)


def write_library(cards: Iterable[Card | Mapping[str, Any]], catalogue, path: str | os.PathLike,
                  meta: Mapping[str, Any] | None = None, *, validate: bool = True,
                  check_catalogue_hash: bool = True) -> LibraryManifest:
    """Write ``cards`` as a library under directory ``path`` and return its manifest.

    ``catalogue`` is a loaded ``Catalogue`` (its id and ``version_hash`` go into the manifest). ``meta`` may
    set ``generator``, ``model``, ``prompts``, ``error_source`` (default: taken from the cards' provenance
    when they all agree) and ``created`` (ISO 8601 UTC; default now).

    Checks: every card has a unique id, ``states[0] == all_active``, ``provenance.catalogue_id`` equals the
    catalogue's, and (``check_catalogue_hash``) so does ``provenance.catalogue_hash``; with ``validate`` each
    card passes ``card_schema_problems``. Semantic validation is ``patient_engine.validate`` (WP-C1-4) and
    runs before cards reach a library.

    A library is immutable: if ``path`` already holds a library with the same id the existing manifest is
    returned untouched; a different library there raises ``LibraryError``."""
    meta = dict(meta or {})
    objs = sorted((_as_card(c) for c in cards), key=lambda c: c.id)
    if not objs:
        raise LibraryError("a library needs at least one card")
    problems: list = []
    seen: set[str] = set()
    for c in objs:
        if c.id in seen:
            problems.append(f"duplicate card id {c.id!r}")
        seen.add(c.id)
        if c.states[0] != INITIAL_STATE:
            problems.append(f"{c.id}: first state is {c.states[0]!r}, not {INITIAL_STATE!r}")
        if c.provenance.catalogue_id != catalogue.id:
            problems.append(f"{c.id}: made for catalogue {c.provenance.catalogue_id!r}, library is for {catalogue.id!r}")
        elif check_catalogue_hash and c.provenance.catalogue_hash != catalogue.version_hash:
            problems.append(f"{c.id}: catalogue hash {c.provenance.catalogue_hash[:12]} differs from {catalogue.version_hash[:12]}")
        if validate:
            for p in card_schema_problems(card_to_json(c), catalogue):
                problems.append(f"{c.id}: {getattr(p, 'message', p)} ({getattr(p, 'path', '')})")
    if problems:
        raise LibraryError(f"{len(problems)} problem(s) in the cards, first: {problems[0]}", problems)

    def agreed(attr: str, default: Any) -> Any:
        values = {json.dumps(getattr(c.provenance, attr), sort_keys=True) for c in objs}
        return json.loads(values.pop()) if len(values) == 1 else default

    generator = meta.get("generator", agreed("generator", None))
    if generator not in GENERATORS:
        raise LibraryError(f"generator must be one of {GENERATORS}, got {generator!r} (give meta['generator'])")
    error_source = meta.get("error_source", agreed("error_source", None))
    if error_source is not None and error_source not in ERROR_SOURCES:
        raise LibraryError(f"error_source must be one of {ERROR_SOURCES} or None, got {error_source!r}")
    header = {"catalogue_id": catalogue.id, "catalogue_hash": catalogue.version_hash, "generator": generator,
              "model": meta.get("model", agreed("model", None)),
              "prompts": dict(meta.get("prompts", agreed("prompts", {})) or {}), "error_source": error_source}
    lines = [_canonical(card_to_json(c)) for c in objs]
    counts: dict[str, int] = {}
    for c in objs:
        counts[c.primary_condition] = counts.get(c.primary_condition, 0) + 1
    manifest = LibraryManifest(
        id=_library_id(header, lines), card_count_by_condition=dict(sorted(counts.items())),
        created=str(meta.get("created") or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")), **header)

    root = Path(path)
    existing = root / MANIFEST_FILE
    if existing.exists():
        try:
            old = LibraryManifest.from_json(json.loads(existing.read_text()))
        except (ValueError, KeyError) as e:
            raise LibraryError(f"{root} holds something that is not a library: {e}") from None
        if old.id == manifest.id:
            return old
        raise LibraryError(f"{root} already holds library {old.id}; libraries are immutable (new id would be {manifest.id})")

    payload = gzip.compress(b"\n".join(lines) + b"\n", compresslevel=_GZIP_LEVEL, mtime=0)
    record = manifest.to_json() | {"file": {"name": CARDS_FILE, "bytes": len(payload),
                                            "sha256": hashlib.sha256(payload).hexdigest()}}
    root.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix=root.name + ".tmp-", dir=root.parent))
    try:
        (tmp / CARDS_FILE).write_bytes(payload)
        (tmp / MANIFEST_FILE).write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
        if root.exists():
            root.rmdir()                      # an empty directory is fine; a non-empty one raises
        os.replace(tmp, root)
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    return manifest


# ============================================================================ load

def load_library(path: str | os.PathLike, catalogue=None) -> Library:
    """Read and verify a library. ``path`` is the directory (or its ``manifest.json``). Raises
    ``LibraryError`` when a file is missing, is not what the manifest records, or when the cards do not
    hash to the manifest id. With ``catalogue`` the library must have been made for it (same hash)."""
    root = Path(path)
    if root.is_file() and root.name == MANIFEST_FILE:
        root = root.parent
    try:
        record = json.loads((root / MANIFEST_FILE).read_text())
        manifest = LibraryManifest.from_json(record)
        file_info = record["file"]
        payload = (root / file_info["name"]).read_bytes()
    except (OSError, ValueError, KeyError, TypeError) as e:
        raise LibraryError(f"cannot read library at {root}: {e}") from None
    if file_info["name"] != CARDS_FILE:
        raise LibraryError(f"unexpected card file name {file_info['name']!r}")
    if len(payload) != file_info.get("bytes") or hashlib.sha256(payload).hexdigest() != file_info.get("sha256"):
        raise LibraryError(f"{CARDS_FILE} does not match the hash recorded in the manifest (file changed)")
    # Byte 9 is the gzip "OS" byte: Python writes 0xff on Linux but a platform code on macOS, so
    # a library written on a Mac would be rejected here. Compare everything else.
    if payload[:9] != _gzip_header()[:9]:
        raise LibraryError(f"{CARDS_FILE} has an unexpected gzip header")
    try:
        raw = gzip.decompress(payload)
        lines = raw.split(b"\n")
        if lines and lines[-1] == b"":
            lines.pop()
        cards = tuple(card_from_json(json.loads(line)) for line in lines)
    except (OSError, EOFError, zlib.error, ValueError, KeyError, TypeError) as e:
        raise LibraryError(f"cannot read cards of library {manifest.id}: {e}") from None
    if _library_id(_header(record), lines) != manifest.id:
        raise LibraryError(f"cards do not hash to library id {manifest.id} (content or metadata changed)")
    counts: dict[str, int] = {}
    for c in cards:
        counts[c.primary_condition] = counts.get(c.primary_condition, 0) + 1
    if counts != manifest.card_count_by_condition:
        raise LibraryError("card counts in the manifest do not match the cards")
    if catalogue is not None and catalogue.version_hash != manifest.catalogue_hash:
        raise LibraryError(f"library {manifest.id} was made for catalogue hash {manifest.catalogue_hash[:12]}, "
                           f"got {catalogue.version_hash[:12]}")
    return Library(manifest=manifest, cards=cards, path=root, catalogue=catalogue)
