"""Output format for the technique classifier.

One classifier, two taxonomies:
  * ``misinformation``  - online cancer content (Hostinger "Decode the Noise")
  * ``clinical_notes``  - synthetic patient records (AstraZeneca "Equal Care Across Finland")

The classifier (an LLM or rules) returns a :class:`Verdict` per text. The same
structure is used for hand-made labels, so predictions and labels can be compared
directly when measuring precision and recall.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

import yaml

TAXONOMY_DIR = Path(__file__).parent / "taxonomies"

SourceType = Literal["online_post", "clinical_note"]
EvidenceType = Literal[
    "missing_source",        # no verifiable source for a claim
    "contradicting_source",  # a reliable source says otherwise (url required)
    "missing_event",         # expected test/referral absent from the pathway
    "repeated_visits",       # same symptom over several visits
    "text_pattern",          # the wording itself (weakest evidence)
]


@dataclass
class Span:
    start: int  # character offset in the original text, inclusive
    end: int    # exclusive
    text: str   # must equal original_text[start:end]


@dataclass
class Evidence:
    type: EvidenceType
    detail: str              # one sentence, plain language
    url: str | None = None   # required for contradicting_source


@dataclass
class Flag:
    technique_id: str         # an id from the taxonomy
    span: Span
    confidence: float         # 0.0-1.0
    explanation: str          # plain language, max two sentences, for a lay reader
    evidence: list[Evidence] = field(default_factory=list)


@dataclass
class Coordination:
    """Network-level signals (online posts only): copy-paste campaigns, bots."""
    near_duplicates: int = 0                 # posts with near-identical text
    accounts: int = 0                        # distinct accounts posting them
    burst: bool = False                      # many posts in a short window
    shared_domains: list[str] = field(default_factory=list)


@dataclass
class Verdict:
    text_id: str
    source_type: SourceType
    taxonomy: str                     # "misinformation" or "clinical_notes"
    flags: list[Flag] = field(default_factory=list)
    summary: str = ""                 # one plain-language sentence for the reader
    abstain: bool = False             # True when the text is too ambiguous to judge
    coordination: Coordination | None = None

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Taxonomy loading and validation
# ---------------------------------------------------------------------------

REQUIRED_TECHNIQUE_KEYS = {
    "id", "name", "definition", "cues", "example", "explanation", "evidence", "not_this",
}


def load_taxonomy(name: str) -> dict:
    """Load ``taxonomies/<name>.yaml`` and check every technique has all fields."""
    path = TAXONOMY_DIR / f"{name}.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    ids = set()
    for tech in data["techniques"]:
        missing = REQUIRED_TECHNIQUE_KEYS - tech.keys()
        if missing:
            raise ValueError(f"{path.name}: technique {tech.get('id')!r} lacks {sorted(missing)}")
        if tech["id"] in ids:
            raise ValueError(f"{path.name}: duplicate technique id {tech['id']!r}")
        ids.add(tech["id"])
    return data


def technique_ids(name: str) -> set[str]:
    return {t["id"] for t in load_taxonomy(name)["techniques"]}


def validate_verdict(verdict: Verdict, original_text: str) -> list[str]:
    """Return a list of problems (empty list = valid). Use on every LLM output."""
    problems: list[str] = []
    valid_ids = technique_ids(verdict.taxonomy)
    for i, flag in enumerate(verdict.flags):
        where = f"flag {i} ({flag.technique_id})"
        if flag.technique_id not in valid_ids:
            problems.append(f"{where}: unknown technique id")
        s = flag.span
        if not (0 <= s.start < s.end <= len(original_text)):
            problems.append(f"{where}: span offsets out of range")
        elif original_text[s.start:s.end] != s.text:
            problems.append(f"{where}: span text does not match the original")
        if not 0.0 <= flag.confidence <= 1.0:
            problems.append(f"{where}: confidence must be 0-1")
        if not flag.explanation.strip():
            problems.append(f"{where}: explanation is empty")
        for ev in flag.evidence:
            if ev.type == "contradicting_source" and not ev.url:
                problems.append(f"{where}: contradicting_source needs a url")
    if verdict.coordination is not None and verdict.source_type != "online_post":
        problems.append("coordination signals only apply to online posts")
    return problems


# JSON Schema for structured LLM output (Gemini / Nemotron / OpenAI-compatible APIs).
VERDICT_JSON_SCHEMA: dict = {
    "type": "object",
    "required": ["flags", "summary", "abstain"],
    "properties": {
        "flags": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["technique_id", "span_text", "confidence", "explanation", "evidence"],
                "properties": {
                    "technique_id": {"type": "string"},
                    # The model returns the quoted text only; offsets are computed in code
                    # with original_text.find(span_text) to avoid off-by-one errors.
                    "span_text": {"type": "string"},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "explanation": {"type": "string"},
                    "evidence": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["type", "detail"],
                            "properties": {
                                "type": {"type": "string", "enum": list(EvidenceType.__args__)},
                                "detail": {"type": "string"},
                                "url": {"type": "string"},
                            },
                        },
                    },
                },
            },
        },
        "summary": {"type": "string"},
        "abstain": {"type": "boolean"},
    },
}
