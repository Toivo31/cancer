#!/usr/bin/env python3
"""Count the reference numbers of a clinical catalogue by kind of source and by grade.

    python scripts/catalogue_stats.py catalogue/lung-primary-care

Prints, for the catalogue at the given folder:
  * counts of entries and of the numbers under `by:` levels, split into sourced (a source id from
    params/sources.yaml), assumption (chosen by us) and llm_draft (proposed by a language model, unchecked);
  * the same counts by grade (A, B, C, assumption, llm_draft, none);
  * the five numbers that matter most for the story, each with its source and grade;
  * the sources used and the warnings of the loader.

Exit code 0 when the catalogue loads, 1 when it has errors (the problems are printed).
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from patient_engine.catalogue import CatalogueError, load_catalogue  # noqa: E402

ASSUMPTION = "assumption"


def kind_of(source: str, grade: str | None) -> str:
    if grade == "llm_draft":
        return "llm_draft"
    return "assumption" if source == ASSUMPTION else "sourced"


def by_levels(by: dict | None, source: str, grade: str | None):
    """Yield (source, grade) for every number under a `by:` tree (a level inherits what it does not set)."""
    for levels in (by or {}).values():
        for ov in levels.values():
            if isinstance(ov, dict):
                s, g = ov.get("source", source), ov.get("grade", grade)
                if any(k in ov for k in ("value", "p", "values", "dist", "median", "p90", "low", "high")):
                    yield s, g
                yield from by_levels(ov.get("by"), s, g)
            else:
                yield source, grade


def count(catalogue) -> tuple[Counter, Counter, Counter, Counter]:
    entries_kind, levels_kind, entries_grade, levels_grade = Counter(), Counter(), Counter(), Counter()
    for _, leaf in catalogue.leaves():
        entries_kind[kind_of(leaf.source, leaf.grade)] += 1
        entries_grade[leaf.grade or "none"] += 1
        for s, g in by_levels(leaf.by, leaf.source, leaf.grade):
            levels_kind[kind_of(s, g)] += 1
            levels_grade[g or "none"] += 1
    return entries_kind, levels_kind, entries_grade, levels_grade


def headline(catalogue) -> list[tuple[str, str, object]]:
    """The five numbers that matter most: (label, formatted value, leaf or None)."""
    out = []

    def add(label, getter, fmt):
        try:
            leaf = getter()
        except (KeyError, AttributeError, StopIteration):
            out.append((label, "not in this catalogue", None))
            return
        out.append((label, fmt(leaf), leaf))

    v = lambda leaf: f"{next(iter(leaf.params.values())):.4g}"
    add("Lung cancer share among presenters", lambda: catalogue.conditions["lung_cancer"].prevalence, v)
    add("Pneumonia share among presenters", lambda: catalogue.conditions["pneumonia"].prevalence, v)
    add("Chest X-ray sensitivity (symptomatic)", lambda: catalogue.tests["chest_xray"].output("abnormal").sensitivity, v)
    add("Low-dose CT sensitivity (screening)", lambda: catalogue.tests["low_dose_ct"].output("suspicious_nodule").sensitivity, v)
    add("Haemoptysis frequency in lung cancer", lambda: catalogue.variables["haemoptysis"].given["lung_cancer"], v)
    return out


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] in ("-h", "--help"):
        print(__doc__)
        return 0 if len(argv) == 2 else 2
    try:
        cat = load_catalogue(argv[1])
    except CatalogueError as e:
        print(e)
        return 1
    ek, lk, eg, lg = count(cat)
    print(f"Catalogue {cat.id} v{cat.version}, status: {cat.status}, hash {cat.version_hash[:12]}")
    print(f"  {len(cat.conditions)} conditions, {len(cat.variables)} variables, {len(cat.tests)} tests, "
          f"{len(cat.cooccurrence)} co-occurrence pairs, {len(cat.background)} background fields")
    print()
    print("Reference numbers by kind of source")
    print(f"  {'':22}{'entries':>9}{'by-levels':>11}{'total':>8}")
    for k in ("sourced", "assumption", "llm_draft"):
        print(f"  {k:22}{ek[k]:>9}{lk[k]:>11}{ek[k] + lk[k]:>8}")
    print(f"  {'all':22}{sum(ek.values()):>9}{sum(lk.values()):>11}{sum(ek.values()) + sum(lk.values()):>8}")
    print()
    print("Reference numbers by grade (A, B, C = sourced; assumption; llm_draft = unchecked)")
    print(f"  {'':22}{'entries':>9}{'by-levels':>11}{'total':>8}")
    for g in ("A", "B", "C", "assumption", "llm_draft", "none"):
        if eg[g] or lg[g]:
            print(f"  {g:22}{eg[g]:>9}{lg[g]:>11}{eg[g] + lg[g]:>8}")
    print()
    print("The five numbers that matter most")
    for label, value, leaf in headline(cat):
        if leaf is None:
            print(f"  {label}: {value}")
        else:
            print(f"  {label}: {value}  (source {leaf.source}, grade {leaf.grade or '-'})")
    print()
    used = cat.sources_used()
    print(f"Sources used: {len([s for s in used if s != ASSUMPTION])} ids ({', '.join(sorted(s for s in used if s != ASSUMPTION))})")
    print(f"Loader warnings: {len(cat.problems)}")
    for p in cat.problems:
        print(f"  {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
