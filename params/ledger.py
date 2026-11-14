#!/usr/bin/env python3
"""Evidence ledger: how much of each scenario rests on a source and how much on an assumption.

Everything is read from the files, nothing is counted by hand:

    params/sources.yaml            the source registry (id, citation, url, how we read it: `access`)
    scenarios/*.yaml               every block that carries a `source:` tag is one ledger row
    params/*.yaml                  the wider evidence and calibration-target table shown in the dashboard

    python3 params/ledger.py                  # writes docs/ledger.md and docs/ledger.json
    python3 params/ledger.py --check          # exit 1 if the written files are out of date
    python3 params/ledger.py --print          # print the markdown only

Definitions (also written at the top of docs/ledger.md)
  * A *block* is a mapping with a `source:` key (a test, a resource, a condition, a decision mix ...), or the
    sibling mapping of a `<name>_source:` block (`arrivals` / `arrivals_source`).
  * Blocks under `finnish_targets` and `published` are calibration targets or comparators, not simulator inputs.
    They are counted separately and never as inputs.
  * *Grade* of a sourced block = how we read the cited source, from `access` in sources.yaml:
    `full_text` > `abstract` > `secondary` (news, unpublished, or seen only through another document).
    `assumption` is its own class. Study design and setting (Finnish registry, foreign cohort, survey) are not in
    sources.yaml, so no A/B quality grade is computed here.
  * A sourced block whose `note` says part of it is an assumption, a calibration or a placeholder is flagged
    `mixed`: the tag is real, but not every number in the block comes from the source. The strict count
    treats those as not sourced.
  * *Numbers* are the numeric leaves inside a block (probabilities, days, capacities, shares), not counting
    booleans or ids. For `<test>_fast` copies only the numbers that differ from the base test are counted.
"""
from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from collections import Counter, OrderedDict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = [("finland_lung", ROOT / "scenarios" / "finland_lung.yaml"),
             ("stokstad", ROOT / "scenarios" / "stokstad.yaml")]
OUT_MD = ROOT / "docs" / "ledger.md"
OUT_JSON = ROOT / "docs" / "ledger.json"

TARGET_SECTIONS = {"finnish_targets", "published"}
NOT_NUMBERS = {"note", "source", "id", "label", "description"}
MIXED = re.compile(r"assum|calibrat|placeholder|tuned|invented|our rounding|our choice|rough|chosen", re.I)
GRADE_ORDER = ["full_text", "abstract", "secondary", "not in registry"]


# ------------------------------------------------------------------------------------------ registry
def load_registry() -> dict[str, dict]:
    raw = yaml.safe_load((ROOT / "params" / "sources.yaml").read_text())
    items = raw.get("sources", raw) if isinstance(raw, dict) else raw
    return {s["id"]: s for s in items}


def access_of(src: str, reg: dict) -> str:
    if src == "assumption":
        return "assumption"
    return (reg.get(src, {}).get("access") or "not in registry").strip()


# ------------------------------------------------------------------------------------------ blocks
def numeric_leaves(node, skip_blocks: bool = True) -> list[tuple[str, float]]:
    """Numeric leaves of `node`; sub-mappings that carry their own `source` are separate blocks and skipped."""
    out: list[tuple[str, float]] = []

    def go(n, path):
        if isinstance(n, dict):
            for k, v in n.items():
                if k in NOT_NUMBERS:
                    continue
                if skip_blocks and path and isinstance(v, dict) and isinstance(v.get("source"), str):
                    continue
                go(v, path + [str(k)])
        elif isinstance(n, list):
            for i, v in enumerate(n):
                go(v, path + [str(i)])
        elif isinstance(n, (int, float)) and not isinstance(n, bool):
            out.append((".".join(path), n))

    go(node, [])
    return out


def find_blocks(raw: dict) -> list[dict]:
    """Every tagged block with its path, section, source, note and numeric leaves."""
    blocks: list[dict] = []

    def add(path: list[str], d: dict, numbers_from):
        blocks.append({"path": ".".join(path), "section": path[0], "source": d["source"],
                       "note": str(d.get("note", "")), "leaves": numeric_leaves(numbers_from), "_obj": numbers_from})

    def go(n, path):
        if isinstance(n, dict):
            if isinstance(n.get("source"), str) and path:
                add(path, n, n)
            for k, v in n.items():
                if isinstance(k, str) and k.endswith("_source") and isinstance(v, dict) and isinstance(v.get("source"), str):
                    base = k[: -len("_source")]
                    add(path + [base], v, n.get(base, {}))   # numbers live in the sibling mapping
                    continue
                go(v, path + [str(k)])
        elif isinstance(n, list):
            for i, v in enumerate(n):
                go(v, path + [str(i)])

    go(raw, [])
    return blocks


def dedupe_policies(blocks: list[dict]) -> list[dict]:
    """The same decision mix is repeated in every flowchart that uses it: keep one row, list the flowcharts."""
    out, seen = [], OrderedDict()
    for b in blocks:
        m = re.match(r"flowcharts\.([^.]+)\.policy\.(.+)$", b["path"])
        if not m:
            out.append(b)
            continue
        fid, name = m.groups()
        key = (name, json.dumps(b["_obj"], sort_keys=True, default=str))
        if key in seen:
            seen[key]["flowcharts"].append(fid)
        else:
            b = dict(b, flowcharts=[fid], policy=name)
            seen[key] = b
            out.append(b)
    for b in out:
        if "flowcharts" in b:
            b["path"] = f"flowcharts.{{{', '.join(b['flowcharts'])}}}.policy.{b['policy']}"
    return out


def subtract_base_numbers(blocks: list[dict]) -> None:
    """`<test>_fast` blocks copy the base test: count only the numbers that differ from it."""
    by_path = {b["path"]: b for b in blocks}
    for b in blocks:
        m = re.match(r"(tests\.)(.+)_fast$", b["path"])
        if not m:
            continue
        base = by_path.get(m.group(1) + m.group(2))
        if base:
            bl = dict(base["leaves"])
            b["leaves"] = [(k, v) for k, v in b["leaves"] if bl.get(k) != v]
            b["copy_of"] = base["path"]


# ------------------------------------------------------------------------------------------ one scenario
def sensitivity_counts(raw: dict) -> dict | None:
    """How many assumption parameters the sensitivity code can vary, and how many it varies by default."""
    sys.path.insert(0, str(ROOT))
    try:
        from pathway_sim import sensitivity as S
    except Exception:  # pragma: no cover - ledger still works without the package
        return None
    ps = S.discover(copy.deepcopy(raw))
    sel = S.select(ps, None, raw["id"], False)
    return {"discoverable_assumption_parameters": len(ps), "varied_by_default": len(sel),
            "note": "grouped parameters as defined in pathway_sim/sensitivity.py (for example p_positive[cancer] is one)"}


def ledger_for(sid: str, path: Path, reg: dict) -> dict:
    raw = yaml.safe_load(path.read_text())
    blocks = dedupe_policies(find_blocks(raw))
    subtract_base_numbers(blocks)
    rows, targets = [], []
    unknown = sorted({b["source"] for b in blocks if b["source"] != "assumption" and b["source"] not in reg})
    for b in blocks:
        acc = access_of(b["source"], reg)
        row = {"path": b["path"], "section": b["section"], "source": b["source"], "grade": acc,
               "numbers": len(b["leaves"]), "mixed": bool(b["source"] != "assumption" and MIXED.search(b["note"])),
               **({"copy_of": b["copy_of"]} if "copy_of" in b else {})}
        (targets if b["section"] in TARGET_SECTIONS else rows).append(row)

    def tally(rs):
        c = Counter(r["grade"] if r["source"] != "assumption" else "assumption" for r in rs)
        sourced = [r for r in rs if r["source"] != "assumption"]
        return {
            "blocks": len(rs),
            "sourced": len(sourced),
            "assumption": len(rs) - len(sourced),
            "sourced_by_grade": {g: c.get(g, 0) for g in GRADE_ORDER if c.get(g, 0)},
            "sourced_but_note_mentions_assumption": sum(1 for r in sourced if r["mixed"]),
            "sourced_strict": sum(1 for r in sourced if not r["mixed"]),
            "numbers": sum(r["numbers"] for r in rs),
            "numbers_in_sourced_blocks": sum(r["numbers"] for r in sourced),
            "numbers_in_assumption_blocks": sum(r["numbers"] for r in rs if r["source"] == "assumption"),
            "numbers_in_sourced_blocks_strict": sum(r["numbers"] for r in sourced if not r["mixed"]),
        }

    sections = {}
    for sec in sorted({r["section"] for r in rows}):
        sections[sec] = tally([r for r in rows if r["section"] == sec])
    # numbers outside every tagged block, in the input sections (nodes, settings): listed, not hidden
    tagged_top = {r["section"] for r in rows}
    settings = {k: v for k, v in raw.items() if isinstance(v, (int, float)) and not isinstance(v, bool)}
    cited = sorted({r["source"] for r in rows + targets if r["source"] != "assumption"})
    return {
        "id": sid, "file": str(path.relative_to(ROOT)),
        "inputs": tally(rows),
        "calibration_targets_and_comparators": tally(targets) if targets else None,
        "by_section": sections,
        "top_level_settings": settings,
        "sensitivity": sensitivity_counts(raw),
        "sources_cited_by_inputs": sorted({r["source"] for r in rows if r["source"] != "assumption"}),
        "sources_cited_only_by_targets": sorted(set(cited) - {r["source"] for r in rows}),
        "unknown_source_ids": unknown,
        "blocks": rows, "target_blocks": targets,
        "input_sections_with_tags": sorted(tagged_top),
    }


# ------------------------------------------------------------------------------------------ params table
def params_table(reg: dict) -> dict:
    """The wider table the dashboard shows (params/*.yaml): evidence and calibration targets, not only inputs."""
    rows = []
    for f in sorted((ROOT / "params").glob("*.yaml")):
        if f.name == "sources.yaml":
            continue
        data = yaml.safe_load(f.read_text()) or {}
        for section, params in data.items():
            if not isinstance(params, dict):
                continue
            for name, p in params.items():
                if isinstance(p, dict) and "source" in p:
                    rows.append({"file": f.name, "section": section, "name": name, "source": p["source"],
                                 "grade": access_of(p["source"], reg)})
    c = Counter((r["grade"] if r["source"] != "assumption" else "assumption") for r in rows)
    per_file = {}
    for r in rows:
        d = per_file.setdefault(r["file"], Counter())
        d["rows"] += 1
        d["assumption" if r["source"] == "assumption" else "sourced"] += 1
    return {"rows": len(rows), "sourced": sum(1 for r in rows if r["source"] != "assumption"),
            "assumption": sum(1 for r in rows if r["source"] == "assumption"),
            "sourced_by_grade": {g: c.get(g, 0) for g in GRADE_ORDER if c.get(g, 0)},
            "per_file": {k: dict(v) for k, v in per_file.items()},
            "unknown_source_ids": sorted({r["source"] for r in rows if r["source"] != "assumption" and r["source"] not in reg})}


def registry_summary(reg: dict, scenarios: list[dict]) -> dict:
    used_inputs = {s for sc in scenarios for s in sc["sources_cited_by_inputs"]}
    used_targets = {s for sc in scenarios for s in sc["sources_cited_only_by_targets"]}
    c = Counter((s.get("access") or "unspecified").strip() for s in reg.values())
    return {"sources": len(reg), "by_access": dict(c),
            "cited_by_a_scenario_input": len(used_inputs), "cited_only_by_targets": sorted(used_targets - used_inputs),
            "not_cited_by_any_scenario": sorted(set(reg) - used_inputs - used_targets)}


# ------------------------------------------------------------------------------------------ output
def build() -> dict:
    reg = load_registry()
    scs = [ledger_for(sid, p, reg) for sid, p in SCENARIOS]
    out_scs = []
    for s in scs:
        out_scs.append(s)
    return {"definitions": __doc__.split("Definitions")[1].split('"""')[0].strip() if "Definitions" in __doc__ else "",
            "scenarios": out_scs, "params_table": params_table(reg), "registry": registry_summary(reg, scs)}


def pct(a, b):
    return f"{100 * a / b:.0f}%" if b else "n/a"


def markdown(L: dict) -> str:
    out = ["# Evidence ledger", "",
           "Generated by `python3 params/ledger.py` from `params/sources.yaml`, `scenarios/*.yaml` and `params/*.yaml`. Nothing here is counted by hand; "
           "rerun the script after any change to those files (`--check` fails when this file is stale). Machine-readable copy: `docs/ledger.json`.",
           "",
           "## What is counted", "",
           "- **Block**: a mapping with a `source:` key (a test, a resource, a condition, a group, a decision mix, the arrival stream) in a scenario file. "
           "One block is one row of the ledger. The same decision mix repeated in several flowcharts is one row.",
           "- **Input vs target**: blocks under `finnish_targets` and `published` are calibration targets or published comparators the engine does not read as inputs; they are reported separately.",
           "- **Grade** of a sourced block is how we read the cited source (`access` in `params/sources.yaml`): `full_text`, `abstract`, or `secondary` (news, unpublished, or seen only through another document). "
           "Study design and setting are not recorded there, so no A/B quality grade is computed.",
           "- **Mixed**: a sourced block whose own note says part of it is an assumption, a calibration or a placeholder (for example the GP clinic is sourced for its booking lead, while its capacity is an assumption). "
           "The *strict* sourced count leaves these out.",
           "- **Numbers** are the numeric values inside the blocks (probabilities, days, capacities, shares); this is a finer count than blocks.", ""]
    for s in L["scenarios"]:
        i, t = s["inputs"], s["calibration_targets_and_comparators"]
        out += [f"## {s['id']} (`{s['file']}`)", "",
                "| | Blocks | Sourced | of which strict (no assumption wording in the note) | Assumption | Numbers in sourced blocks | Numbers in assumption blocks |",
                "|---|---|---|---|---|---|---|",
                f"| **Simulator inputs** | {i['blocks']} | {i['sourced']} ({pct(i['sourced'], i['blocks'])}) | {i['sourced_strict']} ({pct(i['sourced_strict'], i['blocks'])}) | "
                f"{i['assumption']} ({pct(i['assumption'], i['blocks'])}) | {i['numbers_in_sourced_blocks']} (strict {i['numbers_in_sourced_blocks_strict']}) | {i['numbers_in_assumption_blocks']} |"]
        if t:
            out.append(f"| Calibration targets, comparators (not inputs) | {t['blocks']} | {t['sourced']} | {t['sourced_strict']} | {t['assumption']} | {t['numbers_in_sourced_blocks']} | {t['numbers_in_assumption_blocks']} |")
        out += ["", f"Sourced inputs by how we read the source: " + ", ".join(f"{g} {n}" for g, n in i["sourced_by_grade"].items()) + ".", ""]
        if s["sensitivity"]:
            sn = s["sensitivity"]
            out += [f"Sensitivity coverage: the sensitivity code finds {sn['discoverable_assumption_parameters']} assumption parameters (grouped, see `pathway_sim/sensitivity.py`) and varies {sn['varied_by_default']} of them by default.", ""]
        out += ["By section:", "", "| Section | Blocks | Sourced | Assumption | Numbers (sourced / assumption) |", "|---|---|---|---|---|"]
        for sec, v in s["by_section"].items():
            out.append(f"| `{sec}` | {v['blocks']} | {v['sourced']} | {v['assumption']} | {v['numbers_in_sourced_blocks']} / {v['numbers_in_assumption_blocks']} |")
        out += ["", "Every input block:", "", "| Block | Source | Grade | Numbers | Flag |", "|---|---|---|---|---|"]
        for r in s["blocks"]:
            flag = "mixed" if r["mixed"] else ""
            out.append(f"| `{r['path']}` | {r['source']} | {r['grade']} | {r['numbers']} | {flag} |")
        if s["target_blocks"]:
            out += ["", "Targets and comparators (not inputs):", "", "| Block | Source | Grade | Numbers |", "|---|---|---|---|"]
            for r in s["target_blocks"]:
                out.append(f"| `{r['path']}` | {r['source']} | {r['grade']} | {r['numbers']} |")
        if s["unknown_source_ids"]:
            out += ["", f"**Source ids not in the registry:** {', '.join(s['unknown_source_ids'])}"]
        out.append("")
    p = L["params_table"]
    out += ["## The wider parameter table (`params/*.yaml`, shown on the dashboard's sources screen)", "",
            f"{p['rows']} rows: {p['sourced']} sourced, {p['assumption']} assumption. Most rows are published intervals, survival and incidence figures "
            "used as calibration targets or background, not simulator inputs, so this is evidence, not input coverage.", "",
            "| File | Rows | Sourced | Assumption |", "|---|---|---|---|"]
    for f, v in p["per_file"].items():
        out.append(f"| `params/{f}` | {v.get('rows', 0)} | {v.get('sourced', 0)} | {v.get('assumption', 0)} |")
    r = L["registry"]
    out += ["", "## Source registry", "",
            f"{r['sources']} sources in `params/sources.yaml`: " + ", ".join(f"{k} {v}" for k, v in sorted(r["by_access"].items())) + ". "
            f"{r['cited_by_a_scenario_input']} are cited by at least one scenario input.", ""]
    if r["cited_only_by_targets"]:
        out.append(f"Cited only as a calibration target or comparator: {', '.join(r['cited_only_by_targets'])}.")
    if r["not_cited_by_any_scenario"]:
        out.append(f"Registered but not cited by either scenario file (background in `params/*.yaml`): {', '.join(r['not_cited_by_any_scenario'])}.")
    out.append("")
    return "\n".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="exit 1 if docs/ledger.md or docs/ledger.json are stale")
    ap.add_argument("--print", action="store_true", help="print the markdown and write nothing")
    a = ap.parse_args(argv)
    L = build()
    for s in L["scenarios"]:  # drop internals before writing
        pass
    md = markdown(L)
    js = json.dumps(L, indent=1, default=str) + "\n"
    if a.print:
        print(md)
        return 0
    if a.check:
        stale = [p.name for p, new in ((OUT_MD, md), (OUT_JSON, js)) if not p.exists() or p.read_text() != new]
        if stale:
            print("stale:", ", ".join(stale))
            return 1
        print("ledger up to date")
        return 0
    OUT_MD.write_text(md)
    OUT_JSON.write_text(js)
    for s in L["scenarios"]:
        i = s["inputs"]
        print(f"{s['id']}: {i['blocks']} input blocks, {i['sourced']} sourced ({i['sourced_strict']} strict), {i['assumption']} assumption; "
              f"targets {s['calibration_targets_and_comparators']['blocks'] if s['calibration_targets_and_comparators'] else 0}")
    print("wrote", OUT_MD.relative_to(ROOT), "and", OUT_JSON.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
