"""How much does the result author's prompt know about whether a result is wrong? (review w8 B1)

For each positive result of a few (test, output) pairs in a library (first state), the label is the planned outcome
(false alarm vs true positive). Three feature sets, each scored by 5-fold cross-validated AUC of gradient boosting:

  reader   this attempt's own values plus age, sex and smoking: what a reader of the report has anyway
  g2@2     everything ``authors.results_user`` puts in the g2@2 prompt of that state (every test and attempt)
  g2@3     the exact g2@3 prompt of that attempt (``authors.report_user`` of its pattern): one-hot of the prompt
           text, so the score is the best any model could do from the prompt alone

g2@3's prompt is a function of the attempt's pattern only, so its AUC is at most the reader's (numbers are hidden).
Needs scikit-learn (not a project dependency):  PYTHONPATH=/path/to/sklearn python scripts/g2_blindness.py LIB

    python scripts/g2_blindness.py /tmp/fake500 --catalogue catalogue/lung-primary-care [--json out.json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

from patient_engine.authors import Authors, report_pattern, report_user, results_user  # noqa: E402
from patient_engine.catalogue import load_catalogue  # noqa: E402
from patient_engine.library import load_library  # noqa: E402
from patient_engine.pipeline import parse_results_prompt  # noqa: E402

TARGETS = [("chest_xray", "abnormal"), ("chest_ct", "suspicious_for_malignancy"), ("pet_ct", "fdg_avid"),
           ("chest_xray", "consolidation"), ("nt_probnp", "bnp_high"), ("echocardiography", "heart_failure_confirmed")]


def _enc(v):
    if v is None:
        return -1.0
    if isinstance(v, bool):
        return float(v)
    if isinstance(v, (int, float)):
        return float(v)
    return None


def _vec(items: dict, keys: list, cats: dict) -> list:
    out = []
    for k in keys:
        v = items.get(k)
        if k in cats:                                       # categorical: one-hot (absent: all zero)
            out += [float(v == c) for c in cats[k]]
        else:
            e = _enc(v)
            out.append(-1.0 if e is None else e)
    return out


def _matrix(rows: list[dict]) -> np.ndarray:
    keys = sorted({k for r in rows for k in r})
    cats = {k: sorted({str(r[k]) for r in rows if isinstance(r.get(k), str)}) for k in keys}
    cats = {k: c for k, c in cats.items() if c}
    return np.array([_vec(r, keys, cats) for r in rows])


def _auc(X, y) -> float | None:
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.model_selection import StratifiedKFold, cross_val_predict
    from sklearn.metrics import roc_auc_score
    if min(y.sum(), len(y) - y.sum()) < 5:
        return None
    p = cross_val_predict(HistGradientBoostingClassifier(max_iter=200, random_state=0), X, y,
                          cv=StratifiedKFold(5, shuffle=True, random_state=0), method="predict_proba")[:, 1]
    return float(roc_auc_score(y, p))


def measure(library_dir: str, catalogue_dir: str) -> dict:
    cat = load_catalogue(catalogue_dir)
    gp = Authors(cat).gp_tests
    lib = load_library(library_dir)
    pub = ("age", "sex", "smoking_status", "pack_years")
    rows = {t: {"y": [], "reader": [], "g2v2": [], "g2v3": []} for t in TARGETS}
    for card in lib.cards:
        st = card.states[0]
        obs = {t: [{"status": a.status, "values": dict(a.values)} for a in atts]
               for t, atts in card.observations[st].items()}
        bg = {k: card.background.get(k) for k in pub}
        prompt = None
        plan = card.hidden.error_plan[st]
        for tid, oid in TARGETS:
            test = cat.tests[tid]
            for k, a in enumerate(obs[tid]):
                if a["status"] != "ok" or a["values"].get(oid) is not True:
                    continue
                if prompt is None:
                    text = results_user(cat, card.background, card.presenting[st].reported, obs, gp)
                    parsed = parse_results_prompt(cat, text)
                    prompt = {f"{t}[{i}].{o}": v for t, atts in parsed.items() for i, at in enumerate(atts)
                              for o, v in {**at["values"], "status": at["status"]}.items()}
                    prompt.update(bg)
                    prompt.update({f"said.{v}": True for v in card.presenting[st].reported})
                    prompt["target_attempt"] = k
                rows[(tid, oid)]["y"].append(plan[tid][k].outputs.get(oid) == "false_alarm")
                rows[(tid, oid)]["reader"].append({**{o: v for o, v in a["values"].items()}, **bg})
                rows[(tid, oid)]["g2v2"].append({**prompt, "target_attempt": k})
                rows[(tid, oid)]["g2v3"].append({"prompt": report_user(test, report_pattern(test, "ok", a["values"]))})
    out = {"library": lib.manifest.id, "n_cards": len(lib.cards), "targets": []}
    for (tid, oid), r in rows.items():
        y = np.array(r["y"], dtype=int)
        res = {"target": f"{tid}.{oid}", "n": int(len(y)), "n_false_alarm": int(y.sum())}
        for name in ("reader", "g2v2", "g2v3"):
            a = _auc(_matrix(r[name]), y) if len(y) else None
            res[name] = None if a is None else round(a, 3)
        res["g2v3_distinct_prompts"] = len({x["prompt"] for x in r["g2v3"]})
        out["targets"].append(res)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("library")
    ap.add_argument("--catalogue", default=str(ROOT / "catalogue" / "lung-primary-care"))
    ap.add_argument("--json")
    a = ap.parse_args(argv)
    res = measure(a.library, a.catalogue)
    print(f"library {res['library']} ({res['n_cards']} cards), first state; 5-fold AUC false alarm vs true positive")
    print(f"{'positive result':42} {'n (FA)':>10} {'reader':>7} {'g2@2':>6} {'g2@3':>6} {'g2@3 prompts':>13}")
    for t in res["targets"]:
        print(f"{t['target']:42} {t['n']:>5} ({t['n_false_alarm']:>3}) {t['reader']!s:>7} {t['g2v2']!s:>6} "
              f"{t['g2v3']!s:>6} {t['g2v3_distinct_prompts']:>13}")
    if a.json:
        Path(a.json).write_text(json.dumps(res, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
