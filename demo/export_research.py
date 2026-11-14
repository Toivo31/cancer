#!/usr/bin/env python3
"""Research claims register -> docs/research_claims.md and demo/data/research_bundle.js (window.RESEARCH_DATA).

    python demo/export_research.py            # about 15 s: reruns two simulations for the waiting-basis split
    python demo/export_research.py --check    # exit 1 if either output is stale (content apart from the timestamp)

Reads
  docs/research_claims.yaml   THE edited file: claims, their basis, framing sentence, split settings, unsupported list
  params/sources.yaml         every source (id, citation, url, year, access, supports)
  docs/pitch/fill_numbers.py  build_values(): the simulation numbers the pitch uses ({pitch.key} placeholders)
  demo/data/demo_bundle.json  wait share per scenario as the dashboard computes it
  scenarios/*.yaml            via demo/research_split.py: critical-path waiting days by the basis of their input
Simulation numbers are computed here, never typed: a {ns.key} placeholder that cannot be resolved is an error.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from research_split import decompose  # noqa: E402

REGISTER = ROOT / "docs" / "research_claims.yaml"
SOURCES = ROOT / "params" / "sources.yaml"
OUT_MD = ROOT / "docs" / "research_claims.md"
OUT_JS = HERE / "data" / "research_bundle.js"
BASES = ("published", "simulation", "assumption")
PH = re.compile(r"\{([a-z]+)\.([a-z0-9_]+)\}")
BASIS_LABEL = {"published": "Published research", "simulation": "Our simulation", "assumption": "Our assumption"}
SPLIT_LABEL = {"published": "published figure", "calibrated": "assumed input tuned to a published figure", "assumption": "assumption"}


def pitch_values() -> dict:
    spec = importlib.util.spec_from_file_location("fill_numbers", ROOT / "docs" / "pitch" / "fill_numbers.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return {k: str(v) for k, v in mod.build_values().items()}


def bundle_wait_share(sid: str) -> float:
    b = json.loads((ROOT / "demo" / "data" / "demo_bundle.json").read_text())
    sc = next(s for s in b["scenarios"] if s["id"] == sid)
    st = sc["baseline"]["metrics"]["stage_breakdown"]
    w = sum(v["wait"] for v in st.values())
    t = sum(v["service"] for v in st.values())
    return w / (w + t)


def pct(x: float) -> str:
    return str(int(x * 100 + 0.5))


def compute_split(reg: dict, known: set[str]) -> dict:
    wb = reg["waiting_basis"]
    fi, no = decompose(wb["finland"], known), decompose(wb["norway"], known)
    vals = {
        "fi_matched_pct": pct(fi["published_or_calibrated_share"]),
        "fi_assumed_pct": pct(fi["by_basis_share"]["assumption"]),
        "fi_waiting_days": f"{fi['waiting_days']:.1f}",
        "fi_booking_days": f"{fi['by_kind_days'].get('booking lead', 0):.0f}",
        "fi_queue_days": f"{fi['by_kind_days'].get('capacity queue', 0):.0f}",
        "fi_extra_days": f"{fi['by_kind_days'].get('extra wait', 0):.0f}",
        "no_matched_pct": pct(no["published_or_calibrated_share"]),
        "no_assumed_pct": pct(no["by_basis_share"]["assumption"]),
        "fi_bundle_wait_pct": pct(bundle_wait_share("finland_lung")),
        "no_bundle_wait_pct": pct(bundle_wait_share("stokstad")),
    }
    return {"finland": fi, "norway": no, "values": vals}


def resolve(text: str, ns: dict, where: str) -> str:
    def sub(m):
        space, key = m.group(1), m.group(2)
        if space not in ns or key not in ns[space]:
            raise KeyError(f"{where}: unknown placeholder {{{space}.{key}}}")
        return ns[space][key]
    return " ".join(PH.sub(sub, str(text)).split())


def build(reg: dict, sources: list[dict], split: dict, pitch: dict) -> dict:
    src = {s["id"]: s for s in sources}
    ns = {"pitch": pitch, "split": split["values"]}
    claims = []
    for c in reg["claims"]:
        if c.get("retired"):
            continue
        out = {"id": c["id"], "theme": c["theme"], "basis": c["basis"], "claim": resolve(c["claim"], ns, c["id"]),
               "strength": resolve(c.get("strength", ""), ns, c["id"]), "shown_on": c.get("shown_on", [])}
        if c["basis"] == "published":
            s = src[c["source"]]
            out.update(source=c["source"], figure=c.get("figure"), kind=c.get("kind"), access=s.get("access"),
                       url=s.get("url"), citation=s.get("citation"), year=s.get("year"))
        elif c["basis"] == "simulation":
            out.update(run=c.get("run"), inputs=c.get("inputs"))
        else:
            out.update(where=c.get("where"), reason=c.get("reason"))
        claims.append(out)
    used = {c["source"] for c in claims if c.get("source")}
    counts = {b: sum(1 for c in claims if c["basis"] == b) for b in BASES}

    def slim(d):
        return {k: v for k, v in d.items() if k != "owners"} | {"owners": [
            {k: o[k] for k in ("owner", "basis", "source", "why", "days", "share_of_waiting", "tests")} for o in d["owners"]]}

    return {
        "format": "research-bundle/1",
        "framing": " ".join(reg["framing"].split()),
        "basis_labels": BASIS_LABEL,
        "themes": reg["themes"],
        "counts": counts,
        "claims": claims,
        "waiting_split": {"finland": slim(split["finland"]), "norway": slim(split["norway"]), "values": split["values"],
                          "basis_labels": SPLIT_LABEL},
        "unsupported": reg.get("unsupported", []),
        "sources": [{"id": s["id"], "citation": s.get("citation"), "url": s.get("url"), "year": s.get("year"),
                     "access": s.get("access"), "supports": s.get("supports"), "used_in_register": s["id"] in used}
                    for s in sources],
    }


def render_md(B: dict) -> str:
    L = ["# Research behind the numbers: claims register", "",
         "Generated by `python demo/export_research.py` from `docs/research_claims.yaml` (edit that file, not this one), "
         "`params/sources.yaml`, the pitch numbers (`docs/pitch/fill_numbers.py`) and two simulation runs. "
         "Every claim our pages and pitch make has exactly one basis: **Published** (a source in the registry), "
         "**Our simulation** (synthetic patients; numbers computed, never typed) or **Our assumption** (our choice, with the reason). "
         "How we read each source (full text, abstract, secondary) comes from the registry. Claim ids are stable link targets "
         "(`research.html#<id>`).", "",
         "| Basis | Claims |", "|---|---|"]
    for b in BASES:
        L.append(f"| {BASIS_LABEL[b]} | {B['counts'][b]} |")
    L.append("")
    for th in B["themes"]:
        cs = [c for c in B["claims"] if c["theme"] == th["id"]]
        if not cs:
            continue
        L += [f"## {th['title']}", ""]
        for c in cs:
            L.append(f"### `{c['id']}` · {BASIS_LABEL[c['basis']]}")
            L += ["", c["claim"], ""]
            if c["basis"] == "published":
                L.append(f"- **Source:** {c['source']} ({c['year']}), {c['kind']}; figure: {c['figure']}; we read: **{c['access']}**. <{c['url']}>")
            elif c["basis"] == "simulation":
                L.append(f"- **Run:** {c['run']}")
                L.append(f"- **Inputs that drive it:** {c['inputs']}")
            else:
                L.append(f"- **Where:** {c['where']}")
                L.append(f"- **Why:** {c['reason']}")
            L.append(f"- **Strength:** {c['strength']}")
            if c["shown_on"]:
                L.append("- **Shown on:** " + "; ".join(c["shown_on"]))
            L.append("")
    W = B["waiting_split"]
    L += ["## The waiting-basis split (what the 'time is mostly waiting' share rests on)", "",
          "Critical-path waiting days of treated cancers, attributed to the input that sets them (`demo/research_split.py`, "
          "extending `docs/review_checks/finland_waiting_decomposition.py`). Basis: *published figure* = the input carries a "
          "registry source and its wait was set from it; *tuned to a published figure* = tagged assumption but its booking "
          "lead was calibrated to hit a published wait; *assumption* = neither. Extra waits are assumptions.", ""]
    for key, title in (("finland", "Finland (synthetic county)"), ("norway", "Norway (Stokstad et al. 2019 rebuilt)")):
        d = W[key]
        L += [f"### {title}: `{d['scenario']}`, flowchart `{d['flowchart']}`, seed {d['seed']}, {d['patients']} patients, {d['treated_cancers']} treated cancers", "",
              f"Waiting {d['waiting_days']} d and service {d['service_days']} d per treated cancer on the critical path "
              f"(waiting {pct(d['waiting_share_of_time'])}% of the time; check: critical path = time to treatment within {d['critical_path_check_days']} d).", "",
              "| Basis | Days | Share of waiting |", "|---|---|---|"]
        for b in ("published", "calibrated", "assumption"):
            L.append(f"| {SPLIT_LABEL[b]} | {d['by_basis_days'][b]} | {pct(d['by_basis_share'][b])}% |")
        L += ["", "By kind of wait (days): " + ", ".join(f"{k} {v}" for k, v in d["by_kind_days"].items()) + ".", "",
              "| Input that sets the wait | Basis | Source | Days | Share | Why |", "|---|---|---|---|---|---|"]
        for o in d["owners"]:
            L.append(f"| `{o['owner']}` ({', '.join(o['tests'])}) | {SPLIT_LABEL[o['basis']]} | {o['source'] or '-'} | {o['days']} | {pct(o['share_of_waiting'])}% | {o['why']} |")
        L.append("")
    v = W["values"]
    L += [f"The dashboard's own wait share (stage breakdown in `demo/data/demo_bundle.json`) is {v['fi_bundle_wait_pct']}% for Finland and "
          f"{v['no_bundle_wait_pct']}% for Norway; the critical-path measure above differs slightly because it counts report times as service.", ""]
    L += ["## What we could not support", "",
          "Claims made in our documents that no source in `params/sources.yaml` backs, and inputs we could not source. "
          "Do not repeat these as sourced. Weak entries above are marked in their strength line (single survey, secondary, "
          "all-cancer instead of lung-specific, one hospital).", ""]
    for u in B["unsupported"]:
        L.append(f"- **`{u['id']}`: {u['claim']}** Status: {u['status']}. {' '.join(str(u['detail']).split())}" + (" " + " ".join(f"<{x}>" for x in u["links"]) if u.get("links") else ""))
    L += ["", "## Sources", "", "| Id | Year | We read | Citation |", "|---|---|---|---|"]
    for s in B["sources"]:
        L.append(f"| {s['id']}{' (used above)' if s['used_in_register'] else ''} | {s['year']} | {s['access']} | {s['citation']} <{s['url']}> |")
    L += ["", "## What this adds up to", "", B["framing"], ""]
    return "\n".join(L)


def export() -> tuple[dict, str]:
    reg = yaml.safe_load(REGISTER.read_text())
    sources = yaml.safe_load(SOURCES.read_text())
    known = {s["id"] for s in sources}
    for c in reg["claims"]:
        if c["basis"] not in BASES:
            raise ValueError(f"{c['id']}: basis {c['basis']!r}")
        if c["basis"] == "published" and c.get("source") not in known:
            raise ValueError(f"{c['id']}: source {c.get('source')!r} not in params/sources.yaml")
    B = build(reg, sources, compute_split(reg, known), pitch_values())
    return B, render_md(B)


def js_text(B: dict, stamp: str) -> str:
    return "window.RESEARCH_DATA = " + json.dumps({**B, "generated_at": stamp}, separators=(",", ":"), ensure_ascii=False) + ";\n"


def read_bundle(path: Path = OUT_JS) -> dict:
    t = path.read_text(encoding="utf-8")
    return json.loads(t[t.index("=") + 1:].rstrip().rstrip(";"))


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    B, md = export()
    if a.check:
        old = read_bundle() if OUT_JS.exists() else {}
        old.pop("generated_at", None)
        stale = [p for p, ok in ((OUT_JS, old == json.loads(json.dumps(B))), (OUT_MD, OUT_MD.exists() and OUT_MD.read_text() == md)) if not ok]
        for p in stale:
            print("stale:", p.relative_to(ROOT))
        return 1 if stale else 0
    OUT_MD.write_text(md, encoding="utf-8")
    OUT_JS.write_text(js_text(B, datetime.now(timezone.utc).isoformat(timespec="seconds")), encoding="utf-8")
    print(f"wrote {OUT_MD.relative_to(ROOT)} and {OUT_JS.relative_to(ROOT)}: {B['counts']}; "
          f"Finland waiting matched to published {B['waiting_split']['values']['fi_matched_pct']}%, Norway {B['waiting_split']['values']['no_matched_pct']}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
