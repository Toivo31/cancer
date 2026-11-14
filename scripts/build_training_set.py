#!/usr/bin/env python
"""Build the JEV training file and the held-out test file with one command.

    python scripts/build_training_set.py                    # realistic mix, libraries found in libraries/
    python scripts/build_training_set.py --mix balanced     # every condition equally often (for rare conditions)
    python scripts/build_training_set.py --dry-run          # show the plan and stop

Writes (default folder runs/training/, git-ignored):
    train.jsonl.gz         rows from ref500 and every model-written library except the held-out one
                           (split: train / val / test by card; use train and val; the "test" rows of this
                           file are the same-generator check)
    test.jsonl.gz          rows from ONE model-written library that is not in training (all split = test)
    build_summary.json     what went in, row counts, label balance, sizes, checks
With --mix balanced the files are train_balanced.jsonl.gz / test_balanced.jsonl.gz.

Which libraries: ref500, and every `gemini_*` library for the world's catalogue. The held-out library is the
`gemini_s<seed>_<n>` with the highest seed (ties: more cards). With only the small libraries present that is
gemini_s2_30. `--holdout DIR` chooses another. New libraries (gemini_s3_500 ...) are picked up when they appear.

Everything is rebuilt from the libraries and the scenario on every run (nothing is cached), so when the
behaviour tables change, running this again gives rows that match them. Same inputs, same bytes.

Patients per library and seed: `--n` (default 2000), but small libraries get fewer, 20 per card with a floor of
200, so a 5-card library is not copied 400 times. Synthetic data only; no model is called.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402

from patient_engine.card import HIDDEN_FIELD_NAMES  # noqa: E402
from patient_engine.library import LibraryError, load_library  # noqa: E402

PER_CARD = 20          # patients per card for a small library
MIN_PATIENTS = 200
GEMINI_NAME = re.compile(r"^gemini_s(\d+)_(\d+)$")
ROW_KEYS = {"request", "chosen", "policy", "behaviour_probs", "label", "outcome", "meta"}


# ------------------------------------------------------------------------------------------ libraries

def discover(libs_dir: Path, catalogue_hash: str):
    """(training candidates, holdout candidates, skipped) as lists of (name, Library)."""
    found, skipped = [], []
    for d in sorted(libs_dir.iterdir()):
        if not (d / "manifest.json").exists() or not (d.name == "ref500" or d.name.startswith("gemini_")):
            continue
        try:
            lib = load_library(d)
        except LibraryError as e:
            skipped.append((d.name, f"unreadable: {e}"))
            continue
        if lib.manifest.catalogue_hash != catalogue_hash:
            skipped.append((d.name, f"made for another catalogue ({lib.manifest.catalogue_hash[:12]})"))
            continue
        found.append((d.name, lib))
    return found, skipped


def pick_holdout(found, forced: str | None):
    if forced:
        want = Path(forced).name
        for name, lib in found:
            if name == want or str(Path(forced).resolve()) == str(lib.path.resolve()):
                return name
        raise SystemExit(f"error: --holdout {forced} is not one of the libraries found: {[n for n, _ in found]}")
    cands = []
    for name, lib in found:
        m = GEMINI_NAME.match(name)
        if m:
            cands.append((int(m.group(1)), lib.manifest.n_cards, name))
    if not cands:
        raise SystemExit("error: no gemini_s<seed>_<n> library found to hold out; give --holdout DIR")
    return max(cands)[2]


def backgrounds_check(lib) -> str:
    """The pack-years fix: never-smokers must have 0 pack-years. Counts the cards that break it."""
    never = [c for c in lib.cards if c.background.get("smoking_status") == "never"]
    bad = sum(1 for c in never if (c.background.get("pack_years") or 0) > 0)
    return f"never-smokers with pack-years > 0: {bad} of {len(never)}" + ("   <- made before the pack-years fix" if bad else "")


def parse_seeds(s: str) -> list[int]:
    if "-" in s:
        a, b = s.split("-")
        return list(range(int(a), int(b) + 1))
    return [int(x) for x in s.split(",")]


def patients_for(n: int, lib) -> int:
    return min(n, max(MIN_PATIENTS, PER_CARD * lib.manifest.n_cards))


# ------------------------------------------------------------------------------------------ scenario

def balanced_world(world_path: Path, out_dir: Path, conditions) -> Path:
    """A copy of the scenario with the same prevalence for every condition. Paths in the file are relative to
    its folder, so they are made absolute in the copy."""
    raw = yaml.safe_load(world_path.read_text())
    base = world_path.parent
    for key in ("catalogue", "care", "care_fallback", "policy", "resources_file"):
        if raw.get(key):
            raw[key] = str((base / raw[key]).resolve())
    if (raw.get("hospital") or {}).get("scenario"):
        raw["hospital"]["scenario"] = str((base / raw["hospital"]["scenario"]).resolve())
    raw["prevalence"] = {c: 1.0 / len(conditions) for c in conditions}
    raw["description"] = "BALANCED copy for training: every condition equally likely. " + str(raw.get("description", ""))
    out = out_dir / "finland_encounter_balanced.yaml"
    out.write_text(yaml.safe_dump(raw, sort_keys=False))
    return out


# ------------------------------------------------------------------------------------------ the information boundary

def _strings(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from _strings(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from _strings(v)
    elif isinstance(obj, str):
        yield obj


class Boundary:
    """The check of tests/test_training_export.py, run on every row written. The request may hold only what
    the decider could see when it chose. Clinician prose (notes, assessments), earlier action ids and a
    definitive test's own result may name a diagnosis; nothing else may name a condition, a hidden field or a
    library or card id; and label and outcome are never inside the request."""

    def __init__(self, world):
        self.conditions = set(world.catalogue.conditions)
        self.definitive = {t.id for t in world.catalogue.tests.values()
                           if any(o.id.endswith("_confirmed") for o in t.outputs)}
        self.violations: list[str] = []
        self.checked = 0

    def check(self, r: dict) -> None:
        self.checked += 1
        problems = []
        if set(r) != ROW_KEYS:
            problems.append(f"row keys {sorted(r)}")
        req, ctx = r["request"], r["request"]["context"]
        if {"label", "outcome", "chosen", "primary"} & set(req) | ({"label", "outcome", "primary"} & set(ctx)):
            problems.append("label or outcome inside the request")
        revealed = {k: v for k, v in ctx.items() if k not in ("assessments", "notes", "observations", "history", "actions")}
        revealed["observations"] = [o for o in ctx.get("observations", []) if o["test"] not in self.definitive]
        revealed["history"] = [h for h in ctx.get("history", []) if h["test"] not in self.definitive]
        for s in _strings([req["request_id"], req["decision_point"], revealed]):
            if s in self.conditions or s in HIDDEN_FIELD_NAMES or re.match(r"^L_[0-9a-f]{8}", s) or re.match(r"^c_[0-9a-f]{6}", s) \
                    or re.match(r"^[a-z_]+\.s\d+:\d+", s):
                problems.append(f"hidden-side string {s!r}")
                break
        if r["chosen"] not in {o["id"] for o in req["options"]}:
            problems.append("chosen is not among the offered options")
        if problems and len(self.violations) < 10:
            self.violations.append(f"{r['meta'].get('library')}/{r['meta'].get('patient')}: " + "; ".join(problems))
        elif problems:
            self.violations.append("...")


# ------------------------------------------------------------------------------------------ main

def human(nbytes: int) -> str:
    return f"{nbytes / 1e6:.1f} MB" if nbytes >= 1e6 else f"{nbytes / 1e3:.0f} kB"


def table(title: str, counts: Counter, total: int) -> list[str]:
    out = [f"  {title}"]
    for k, v in sorted(counts.items(), key=lambda kv: -kv[1]):
        out.append(f"    {k:<30}{v:>9}  {100 * v / total:5.1f}%")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--world", default="scenarios/finland_encounter.yaml")
    ap.add_argument("--libraries-dir", default="libraries")
    ap.add_argument("--out", default="runs/training", help="output folder (default runs/training, git-ignored)")
    ap.add_argument("--mix", choices=["realistic", "balanced"], default="realistic",
                    help="realistic: the catalogue's prevalence (lung cancer 1.3%%). balanced: all 11 conditions equally often")
    ap.add_argument("--n", type=int, default=2000, help="patients per library and seed (small libraries get fewer, see above)")
    ap.add_argument("--seeds", default="1", help="e.g. 1 or 1,2 or 1-3")
    ap.add_argument("--explore", type=float, default=0.3, help="share of decisions drawn at random among the offered options")
    ap.add_argument("--holdout", metavar="DIR", help="library to hold out for the test file (default: highest-seed gemini_s*_N)")
    ap.add_argument("--exclude", action="append", default=[], metavar="NAME", help="library folder name to leave out; repeatable")
    ap.add_argument("--dry-run", action="store_true", help="show which libraries and sizes would be used, then stop")
    ap.add_argument("--keep-work", action="store_true", help="keep the per-library files under <out>/_work")
    args = ap.parse_args(argv)

    from pathway_sim.encounter import load_world
    from pathway_sim.training_export import export

    t_start = time.time()
    world_path = (ROOT / args.world) if not Path(args.world).is_absolute() else Path(args.world)
    world = load_world(world_path)
    conditions = sorted(world.catalogue.conditions)
    found, skipped = discover(ROOT / args.libraries_dir, world.catalogue.version_hash)
    found = [(n, lb) for n, lb in found if n not in args.exclude]
    hold_name = pick_holdout(found, args.holdout)
    train = [(n, lb) for n, lb in found if n != hold_name]
    hold_lib = dict(found)[hold_name]
    if not train:
        raise SystemExit("error: no training library left")
    seeds = parse_seeds(args.seeds)
    suffix = "" if args.mix == "realistic" else "_balanced"
    out = ROOT / args.out if not Path(args.out).is_absolute() else Path(args.out)
    work = out / "_work"

    print(f"world {args.world}  catalogue {world.catalogue.version_hash[:12]}  mix {args.mix}  seeds {seeds}  explore {args.explore}")
    plan = [(n, lb, False) for n, lb in train] + [(hold_name, hold_lib, True)]
    print(f"{'library':<22}{'id':<20}{'cards':>6}{'patients':>10}  role      {'generator':<24}")
    for n, lb, is_hold in plan:
        m = lb.manifest
        print(f"{n:<22}{lb.id:<20}{m.n_cards:>6}{patients_for(args.n, lb):>10}  {'TEST' if is_hold else 'train':<9} "
              f"{m.generator + ':' + str(m.model):<24}")
        print(f"{'':<22}{backgrounds_check(lb)}")
    for n, why in skipped:
        print(f"skipped {n}: {why}")
    ids = Counter(c.id for _, lb, _ in plan for c in lb.cards)
    clash_hold = {c.id for c in hold_lib.cards} & {c.id for _, lb in train for c in lb.cards}
    if clash_hold:
        print(f"WARNING: {len(clash_hold)} card ids of the held-out library also occur in a training library")
    dup = sum(1 for v in ids.values() if v > 1)
    if dup:
        print(f"note: {dup} card ids occur in two libraries (different libraries, same naming: ref500 and gemini_trial both use "
              f"seed 1). Rows are identified by (meta.library, meta.seed, meta.patient), never by card id alone.")
    if args.dry_run:
        return 0

    out.mkdir(parents=True, exist_ok=True)
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    scenario = str(world_path)
    if args.mix == "balanced":
        scenario = str(balanced_world(world_path, work, conditions))

    # one export per library, then stream the rows into the two files
    parts = []
    for n, lb, is_hold in plan:
        t0 = time.time()
        f = work / f"{n}.jsonl.gz"
        k = patients_for(args.n, lb)
        # The held-out library is exported like any other and its rows are marked split=test below. (Passing it
        # only as --holdout-library would also export the world's default library, which is not wanted here.)
        s = export(scenario, k, seeds, str(f), explore=args.explore, quiet=True, libraries=[str(lb.path)])
        parts.append((n, lb, is_hold, f))
        print(f"  exported {n:<20}{s['rows']:>8} rows from {k} patients x {len(seeds)} seed(s)  {time.time() - t0:5.1f} s")

    bound = Boundary(world)
    files = {"train": out / f"train{suffix}.jsonl.gz", "test": out / f"test{suffix}.jsonl.gz"}
    stats = {k: {"rows": 0, "node": Counter(), "primary": Counter(), "class": Counter(), "split": Counter(),
                 "policy": Counter(), "library": Counter(), "chosen": defaultdict(Counter), "patients": set()} for k in files}
    handles = {}
    for k, p in files.items():
        raw = open(str(p) + ".tmp", "wb")
        handles[k] = (raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0, compresslevel=6))
    try:
        for n, lb, is_hold, f in parts:
            kind = "test" if is_hold else "train"
            with gzip.open(f, "rb") as src:
                for line in src:
                    r = json.loads(line)
                    if is_hold:
                        r["meta"]["split"] = "test"
                        line = json.dumps(r, ensure_ascii=False, separators=(",", ":")).encode() + b"\n"
                    bound.check(r)
                    handles[kind][1].write(line if line.endswith(b"\n") else line + b"\n")
                    st = stats[kind]
                    st["rows"] += 1
                    node = r["request"]["decision_point"]
                    st["node"][node] += 1
                    st["primary"][r["label"]["primary"]] += 1
                    st["class"][r["label"]["class"]] += 1
                    st["split"][r["meta"]["split"]] += 1
                    st["policy"]["explore" if r["policy"].endswith("explore") else "table"] += 1
                    st["library"][r["meta"]["library"]] += 1
                    st["chosen"][node][r["chosen"]] += 1
                    st["patients"].add((r["meta"]["library"], r["meta"]["seed"], r["meta"]["patient"]))
    finally:
        for raw_, gz in handles.values():
            gz.close()
            raw_.close()
    for k, p in files.items():
        Path(str(p) + ".tmp").replace(p)
    if not args.keep_work:
        shutil.rmtree(work, ignore_errors=True)

    # ---- report
    print()
    for kind in ("train", "test"):
        st = stats[kind]
        p = files[kind]
        total = st["rows"]
        print(f"{p.relative_to(ROOT) if p.is_relative_to(ROOT) else p}: {total} rows, {len(st['patients'])} patients, {human(p.stat().st_size)}")
        print(f"  rows by decision node: " + ", ".join(f"{k} {v}" for k, v in sorted(st["node"].items())))
        print(f"  rows by split: " + ", ".join(f"{k} {v}" for k, v in sorted(st["split"].items())) +
              "   policy: " + ", ".join(f"{k} {v}" for k, v in sorted(st["policy"].items())))
        for line in table("label.primary (what the patient had)", st["primary"], total):
            print(line)
        print("  label.class: " + ", ".join(f"{k} {100 * v / total:.1f}%" for k, v in sorted(st["class"].items())))
        for node, c in sorted(st["chosen"].items()):
            top = ", ".join(f"{a} {100 * v / sum(c.values()):.0f}%" for a, v in c.most_common(4))
            print(f"  chosen at {node}: {top} ...")
    print(f"information boundary: {bound.checked} rows checked, {len([v for v in bound.violations if v != '...'])} with a problem")
    for v in bound.violations[:10]:
        print("   ", v)
    leak = set(stats["train"]["library"]) & set(stats["test"]["library"])
    print(f"libraries in both files: {sorted(leak) or 'none'}")

    summary = {
        "format": "jev_training_build/1", "mix": args.mix, "world": args.world, "catalogue_hash": world.catalogue.version_hash,
        "seeds": seeds, "explore": args.explore, "n": args.n,
        "libraries": [{"name": n, "id": lb.id, "cards": lb.manifest.n_cards, "model": lb.manifest.model,
                       "generator": lb.manifest.generator, "role": "test" if h else "train",
                       "patients_per_seed": patients_for(args.n, lb), "backgrounds": backgrounds_check(lb)} for n, lb, h in plan],
        "skipped": skipped,
        "files": {k: {"path": str(files[k]), "rows": stats[k]["rows"], "patients": len(stats[k]["patients"]),
                      "bytes": files[k].stat().st_size,
                      "sha256": hashlib.sha256(files[k].read_bytes()).hexdigest(),
                      "rows_by_node": dict(stats[k]["node"]), "rows_by_split": dict(stats[k]["split"]),
                      "rows_by_primary": dict(stats[k]["primary"]), "rows_by_class": dict(stats[k]["class"]),
                      "rows_by_policy": dict(stats[k]["policy"])} for k in files},
        "boundary_rows_checked": bound.checked, "boundary_violations": bound.violations,
        "git": subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip(),
        "seconds": round(time.time() - t_start, 1),
    }
    sp = out / f"build_summary{suffix}.json"
    sp.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(f"summary: {sp.relative_to(ROOT) if sp.is_relative_to(ROOT) else sp}   total {summary['seconds']} s")
    return 1 if bound.violations else 0


if __name__ == "__main__":
    sys.exit(main())
