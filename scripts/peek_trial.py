"""Print a few cards' texts and some report wordings from a generated library, for a human read.
    python scripts/peek_trial.py libraries/gemini_v2_trial30 [--cards 4] [--wordings 14]
Prints the hidden condition next to each patient account on purpose (so you can judge whether the account is
consistent with it); that is for the reader, not for any decider. Wordings come from runs/gen_cache/g2_bank/*.json."""
import argparse, gzip, json, random
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("lib")
ap.add_argument("--cards", type=int, default=4)
ap.add_argument("--wordings", type=int, default=14)
a = ap.parse_args()
rows = [json.loads(l) for l in gzip.open(Path(a.lib) / "cards.jsonl.gz", "rt")]
rnd = random.Random(1)
for c in rnd.sample(rows, min(a.cards, len(rows))):
    cond = ", ".join(f"{x['role']}={x['id']}" for x in c["hidden"]["conditions"])
    print("=" * 100)
    print(c["id"], "| condition:", cond, "| age", c["background"].get("age"), c["background"].get("sex"), c["background"].get("smoking_status"))
    for st, p in c["presenting"].items():
        print(f"  [{st}] complaint: {p.get('text')}")
    for n in c["notes"][:2]:
        print(f"  [{n['state']}] {n['kind']}: {n['text']}")
    obs = c["observations"][c["states"][0]]
    for t, atts in list(obs.items())[:4]:
        print(f"  report {t}: {atts[0].get('report')}")
print("=" * 100)
bank = sorted(Path("runs/gen_cache/g2_bank").glob("*.json"))
print(f"{len(bank)} cached wordings; showing {min(a.wordings, len(bank))}")
for f in rnd.sample(bank, min(a.wordings, len(bank))):
    s = json.dumps(json.loads(f.read_text()), ensure_ascii=False)
    print("-", s[:420])
