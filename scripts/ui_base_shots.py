#!/usr/bin/env python3
"""Offline screenshot harness for the demo site (before/after UI revamp).
Usage: python3 /tmp/ui_base_shots.py [--out DIR] [--repo /home/claude/cancer] [--settle-ms 5000] [--real-clock]
Opens every page from file://, one page at a time, at 1440x900 and 1920x1080.
Animation settling: Playwright's fake clock is installed before load and advanced a fixed
--settle-ms (default 5000) of virtual time, so animated pages (rAF/setTimeout driven) reach the
same state on every run. Pages given ?paused&day=N are static anyway. --real-clock waits real time instead.
Exit code 1 if any page fails to load (or is blank); console errors are reported only."""
import argparse, json, re, sys, time, hashlib
from pathlib import Path
from playwright.sync_api import sync_playwright

ap = argparse.ArgumentParser()
ap.add_argument("--out", default="/tmp/ui_shots_trial")
ap.add_argument("--repo", default="/home/claude/cancer")
ap.add_argument("--settle-ms", type=int, default=5000)
ap.add_argument("--real-clock", action="store_true")
ap.add_argument("--only", default="", help="substring filter on shot name")
a = ap.parse_args()
repo = Path(a.repo).resolve(); demo = repo / "demo"; out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
SIZES = [(1440, 900), (1920, 1080)]

def enc_ids():
    """Valid patient ids from the encounter bundle (first listed example, else first patient)."""
    txt = (demo / "data/encounter_bundle.js").read_text()
    m = re.search(r"window\.ENC_DATA\s*=\s*", txt)
    try:
        d, _ = json.JSONDecoder().raw_decode(txt[m.end():])
        ex = d.get("examples") or []
        pid = ex[0]["id"] if ex else d["patients"][0]["id"]
        return pid, ex[0].get("key") if ex else "first_patient"
    except Exception as e:
        print("could not parse encounter bundle:", e); return None, None

def index_routes():
    b = json.loads((demo / "data/demo_bundle.json").read_text())
    ids = [s["id"] for s in b["scenarios"]]
    tabs = len(re.findall(r'\["\d","', re.search(r"var TABS=\[.*?\];", (demo / "index.html").read_text()).group(0)))
    return [(f"index_{sid}_{t}", f"index.html#{sid}/{t}", True) for sid in ids for t in range(1, tabs + 1)]

pages = [("start", "start.html", True)]  # third field: also save full-page when taller than viewport
for name, qs in [("flow_default", ""), ("flow_finland", "?s=finland"), ("flow_finland_compare", "?s=finland&compare"),
                 ("flow_norway_compare", "?s=norway&compare"),
                 ("flow_norway_compare_authors_vs_pet", "?s=norway&compare&left=authors&right=suggested_faster_pet"),
                 ("flow_paused_day60", "?paused&day=60"), ("flow_layer_time", "?layer=time"), ("flow_theme_night", "?theme=night")]:
    pages.append((name, "flow.html" + qs, True))
pages.append(("encounter_default", "encounter.html", True))
pid, pkey = enc_ids()
missing = []
if pid is not None:
    pages += [(f"encounter_p{pid}", f"encounter.html?p={pid}", True), (f"encounter_p{pid}_truth", f"encounter.html?p={pid}&truth", True)]
else:
    missing.append("encounter ?p=<id>: could not read an id from encounter_bundle.js")
pages.append(("jev", "jev.html", True))
pages += index_routes()
if a.only: pages = [p for p in pages if a.only in p[0]]

manifest = {"started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "repo": str(repo), "settle": "real-clock %dms" % a.settle_ms if a.real_clock else "fake clock advanced %dms virtual" % a.settle_ms,
            "encounter_id": pid, "encounter_id_key": pkey, "not_covered": missing, "shots": []}
failures = 0; t_all = time.time()

with sync_playwright() as p:
    br = p.chromium.launch(channel="chrome", args=["--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=1"])
    for (w, h) in SIZES:
        for name, rel, full in pages:
            url = (demo / rel.split("#")[0].split("?")[0]).as_uri() + rel[len(rel.split("#")[0].split("?")[0]):]
            fname = f"{name}_{w}x{h}.png"
            rec = {"file": fname, "name": name, "url": url, "size": f"{w}x{h}", "console_errors": [], "console_warnings": [],
                   "page_errors": [], "failed_requests": [], "non_file_requests": [], "load_ms": None, "ok": False}
            ctx = br.new_context(viewport={"width": w, "height": h}, device_scale_factor=1)
            ctx.route(re.compile(r"^(https?|wss?|ftp)://"), lambda r: r.abort())  # offline enforced
            pg = ctx.new_page()
            def on_console(m, rec=rec):
                if m.type == "error": rec["console_errors"].append(m.text)
                elif m.type == "warning": rec["console_warnings"].append(m.text)
            pg.on("console", on_console)
            pg.on("pageerror", lambda e, rec=rec: rec["page_errors"].append(str(e)))
            pg.on("requestfailed", lambda r, rec=rec: rec["failed_requests"].append(f"{r.url} ({r.failure})"))
            pg.on("request", lambda r, rec=rec: rec["non_file_requests"].append(r.url) if not r.url.startswith(("file:", "data:", "blob:")) else None)
            try:
                if not a.real_clock: pg.clock.install()
                t0 = time.time()
                pg.goto(url, wait_until="load", timeout=30000)
                rec["load_ms"] = round((time.time() - t0) * 1000)
                pg.evaluate("document.fonts.ready.then(()=>1)")
                if a.real_clock: pg.wait_for_timeout(a.settle_ms)
                else:
                    # freeze the clock, rewind the simulator to its start, then advance a fixed virtual time
                    pg.clock.pause_at(int(time.time() * 1000) + 3_600_000)
                    pg.evaluate("""()=>{try{if(typeof S!=='undefined'&&S&&typeof S.t==='number'&&S.playing){S.t=0;if(typeof last!=='undefined')last=performance.now();}}catch(e){}}""")
                    pg.clock.run_for(a.settle_ms)
                pg.wait_for_timeout(300)
                info = pg.evaluate("""()=>({title:document.title,text:(document.body.innerText||'').trim().length,
                    sh:document.documentElement.scrollHeight,canvas:document.querySelectorAll('canvas').length,
                    svg:document.querySelectorAll('svg').length})""")
                rec.update(info)
                pg.screenshot(path=str(out / fname), full_page=False)
                if full and info["sh"] > h + 20:
                    fn2 = f"{name}_{w}x{h}_full.png"; pg.screenshot(path=str(out / fn2), full_page=True); rec["full_page_file"] = fn2
                rec["sha1"] = hashlib.sha1((out / fname).read_bytes()).hexdigest()[:12]
                rec["png_bytes"] = (out / fname).stat().st_size
                rec["ok"] = info["text"] > 50 and rec["png_bytes"] > 8000
                if not rec["ok"]: rec["problem"] = "looks blank (little text or tiny PNG)"
            except Exception as e:
                rec["problem"] = f"load failed: {e}"
            if rec["non_file_requests"]: rec["problem"] = (rec.get("problem", "") + " non-file request(s)").strip()
            ctx.close()
            if not rec["ok"]: failures += 1
            manifest["shots"].append(rec)
            print(f"{'OK  ' if rec['ok'] else 'FAIL'} {fname:70s} {rec['load_ms']}ms err={len(rec['console_errors'])+len(rec['page_errors'])}", flush=True)
    br.close()

manifest["runtime_s"] = round(time.time() - t_all, 1); manifest["failures"] = failures
(out / "manifest.json").write_text(json.dumps(manifest, indent=1))
S = manifest["shots"]
errs = [s for s in S if s["console_errors"] or s["page_errors"]]
L = [f"# UI shots summary", "", f"- shots: {len(S)} ({len(pages)} pages x {len(SIZES)} sizes), runtime {manifest['runtime_s']}s, failures {failures}",
     f"- settle: {manifest['settle']}", f"- encounter patient id: {pid} ({pkey})",
     f"- non-file requests: {sum(len(s['non_file_requests']) for s in S)}", f"- shots with console/page errors: {len(errs)}"]
if missing: L += ["- not covered: " + "; ".join(missing)]
seen = {}
for s in errs:
    for m in s["console_errors"] + s["page_errors"]: seen.setdefault(m, []).append(s["name"])
if seen:
    L += ["", "## Errors (message: pages)"]
    for m, ns in seen.items(): L.append(f"- `{m[:200]}`: {', '.join(sorted(set(ns)))}")
bad = [s for s in S if not s["ok"]]
if bad:
    L += ["", "## Failed"] + [f"- {s['file']}: {s.get('problem')}" for s in bad]
(out / "summary.md").write_text("\n".join(L) + "\n")
print("\n".join(L))
sys.exit(1 if failures else 0)
