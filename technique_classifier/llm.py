"""LLM classifier: one OpenAI-compatible chat call per text, checked against the original.

Works with any OpenAI-compatible endpoint (Verda inference, Hostinger AI Router, ...) through
three environment variables: ``LLM_BASE_URL``, ``LLM_API_KEY``, ``LLM_MODEL``; falls back to
``VERDA_BASE_URL`` / ``VERDA_API_KEY`` / ``VERDA_MODEL``. Standard library only.

The model returns quoted span text; offsets are computed here with ``str.find`` and every flag
is checked with :func:`validate_verdict`. Flags whose quote is not in the text are dropped and
reported, so nothing on screen can point at words the note does not contain.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request

from .schema import Evidence, Flag, Span, Verdict, load_taxonomy, validate_verdict


def _env(name: str, fallback: str, default: str | None = None) -> str | None:
    return os.environ.get(name) or os.environ.get(fallback) or default


def taxonomy_prompt(taxonomy: str) -> str:
    tx = load_taxonomy(taxonomy)
    lines = []
    for t in tx["techniques"]:
        lines.append(f"- id: {t['id']}\n  name: {t['name']}\n  definition: {' '.join(t['definition'].split())}")
        lines.append("  cues: " + "; ".join(t["cues"]))
        lines.append("  NOT this: " + "; ".join(t["not_this"]))
    return "\n".join(lines)


SYSTEM = """You review short {kind} for the techniques listed below and flag only clear cases.
Rules:
- Quote the exact words from the text as span_text (copy them character for character, shortest span that shows the problem).
- Use only the technique ids listed. Respect each technique's NOT-this list.
- confidence is 0-1. explanation: plain language, at most two sentences, for a non-expert.
- evidence: 1-2 items, type one of missing_source, contradicting_source, missing_event, repeated_visits, text_pattern.
- If the text is too short or ambiguous, return no flags and abstain=true.
- A flag means "worth a second look", not "someone made an error".
Return JSON only: {{"flags": [{{"technique_id", "span_text", "confidence", "explanation", "evidence": [{{"type", "detail"}}]}}], "summary": "<one sentence>", "abstain": false}}

Techniques:
{techniques}"""

KIND = {"clinical_notes": "clinical notes (synthetic patient records)", "misinformation": "online posts about cancer"}


def _call(messages: list[dict], timeout: float = 300.0) -> str:
    base = _env("LLM_BASE_URL", "VERDA_BASE_URL", "https://inference.verda.com/v1").rstrip("/")
    key = _env("LLM_API_KEY", "VERDA_API_KEY")
    model = _env("LLM_MODEL", "VERDA_MODEL", "kimi-k3-1-pro")
    if not key:
        raise RuntimeError("No API key: set LLM_API_KEY or VERDA_API_KEY (see .env.example)")
    body = json.dumps({"model": model, "messages": messages, "temperature": 0,
                       "max_tokens": 16000, "response_format": {"type": "json_object"}}).encode()
    req = urllib.request.Request(base + "/chat/completions", data=body, method="POST",
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"LLM API error {e.code}: {e.read()[:300]!r}") from None
    content = data["choices"][0]["message"].get("content") or ""
    if not content.strip():  # reasoning models can spend the whole budget thinking
        raise RuntimeError(f"empty answer from the model (finish_reason={data['choices'][0].get('finish_reason')})")
    return content


def _parse(raw: str) -> dict:
    raw = raw.strip()
    m = re.search(r"\{.*\}", raw, re.S)
    return json.loads(m.group(0) if m else raw)


def classify(text: str, taxonomy: str = "clinical_notes", text_id: str = "t") -> tuple[Verdict, list[str]]:
    """Return (verdict, problems). Problems lists dropped flags and validation messages."""
    tx = load_taxonomy(taxonomy)
    msgs = [{"role": "system", "content": SYSTEM.format(kind=KIND.get(taxonomy, "texts"), techniques=taxonomy_prompt(taxonomy))},
            {"role": "user", "content": text}]
    out = _parse(_call(msgs))
    flags, problems = [], []
    for f in out.get("flags", []):
        quote = (f.get("span_text") or "").strip()
        start = text.find(quote) if quote else -1
        if start < 0:  # tolerate case differences only
            start = text.lower().find(quote.lower()) if quote else -1
        if start < 0:
            problems.append(f"dropped {f.get('technique_id')}: quote not in text: {quote[:60]!r}")
            continue
        span = Span(start, start + len(quote), text[start:start + len(quote)])
        ev = [Evidence(type=e.get("type", "text_pattern"), detail=e.get("detail", ""), url=e.get("url"))
              for e in f.get("evidence", []) if isinstance(e, dict)]
        flags.append(Flag(technique_id=f.get("technique_id", ""), span=span,
                          confidence=float(f.get("confidence", 0.5)), explanation=f.get("explanation", ""), evidence=ev))
    v = Verdict(text_id=text_id, source_type=tx.get("source_type", "clinical_note"), taxonomy=taxonomy,
                flags=flags, summary=out.get("summary", ""), abstain=bool(out.get("abstain", False)))
    bad = validate_verdict(v, text)
    if bad:  # keep only flags that pass
        keep = []
        for i, fl in enumerate(v.flags):
            if any(p.startswith(f"flag {i} ") for p in bad):
                problems.append(f"dropped {fl.technique_id}: failed validation")
            else:
                keep.append(fl)
        v.flags = keep
    return v, problems
