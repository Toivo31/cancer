"""The Simulator page (demo/flow.html, UI revamp lane L1).

Static checks always run; the browser smoke check runs when Chrome and puppeteer-core are available (as for
scripts/ui_shots.sh) and is skipped otherwise.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from demo_pages import DEMO, ROOT, check_page

FLOW_JS = (DEMO / "flow.js").read_text(encoding="utf-8")


def _flow_bundle():
    t = (DEMO / "data" / "flow_bundle.js").read_text(encoding="utf-8")
    return json.loads(t[t.index("=") + 1:].rstrip().rstrip(";"))


def test_shared_page_checks():
    """theme.css first, site.js linked after the bundles, nav data-page=simulator, no digits in page text, offline."""
    check_page("flow.html", page_id="simulator")


def test_no_colour_literals_in_flow_js():
    """Canvas and SVG colours come from the theme tokens (Site.tokens()), not hex literals."""
    hits = re.findall(r"['\"`]#[0-9a-fA-F]{3,8}\b", FLOW_JS) + re.findall(r"rgba?\(\s*\d", FLOW_JS)
    assert not hits, hits


def test_flow_css_has_no_root_and_no_grid():
    css = (DEMO / "flow.css").read_text(encoding="utf-8")
    assert not re.search(r":root\s*\{", css)
    assert "linear-gradient(rgba" not in css  # the old background grid
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", css), "colours come from theme.css tokens"


def test_every_pair_linked_from_the_site_exists_in_the_bundle():
    keys = {s["id"]: {v["key"] for v in s["variants"]} for s in _flow_bundle()["scenarios"]}
    for name in ("start.js", "start.html", "evidence.js", "evidence.html", "index.html"):
        path = DEMO / name
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8").replace("&amp;", "&")
        for m in re.finditer(r"flow\.html\?([^\"'\s<>`]*)", text):
            q = dict(kv.split("=", 1) if "=" in kv else (kv, "") for kv in m.group(1).split("&") if kv)
            sid = q.get("s", "norway")
            assert sid in keys, (name, m.group(0))
            for side in ("left", "right"):
                if q.get(side):
                    assert q[side] in keys[sid], (name, m.group(0))
    for s in _flow_bundle()["scenarios"]:
        assert set(s["default_pair"]) <= keys[s["id"]]


def test_url_parameters_are_still_read():
    for p in ("s", "compare", "left", "right", "view", "layer", "paused", "day", "large", "speed"):
        assert re.search(r"q\.(get|has)\('%s'\)" % p, FLOW_JS), p


def test_no_optimiser_with_scanner_pair_offered():
    """D68: Norway offers no optimiser-with-faster-scanner variant; the page names none."""
    nor = next(s for s in _flow_bundle()["scenarios"] if s["id"] == "norway")
    assert {v["key"] for v in nor["variants"]} == {"observed", "suggested", "faster_pet", "authors"}
    assert "optimiser_fast" not in FLOW_JS and "suggested_fast" not in FLOW_JS


def test_honesty_text_kept():
    """Caveats moved into Details drawers, not deleted."""
    for s in ("not like for like", "needs a clinical check", "Trust the ranking of reorderings, not their exact size",
              "not clinical advice", "h += waitBasisNote();", "does not search live"):
        assert s in FLOW_JS, s
    assert not re.search(r"clinician[\s-]*validated", FLOW_JS, re.I)


def _puppeteer():
    for d in (ROOT / "web/node_modules/puppeteer-core", Path("/home/claude/cancer/web/node_modules/puppeteer-core"),
              Path("/tmp/node_modules/puppeteer-core")):
        if (d / "package.json").exists():
            return d
    return None


SMOKE = r"""
const pp = require(process.argv[2]);
(async () => {
  const b = await pp.launch({executablePath: process.argv[3], headless: true,
    args: ['--no-sandbox', '--allow-file-access-from-files', '--host-resolver-rules=MAP * ~NOTFOUND']});
  const out = [];
  for (const u of JSON.parse(process.argv[5])) {
    const p = await b.newPage(); await p.setViewport({width: 1440, height: 900});
    const errs = [];
    p.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });
    p.on('pageerror', e => errs.push(e.message));
    p.on('requestfailed', r => errs.push('failed ' + r.url()));
    await p.goto('file://' + process.argv[4] + '/' + u, {waitUntil: 'load'});
    await new Promise(r => setTimeout(r, 600));
    const r = await p.evaluate(() => ({head: [...document.querySelectorAll('#head .sim-head__v')].map(e => e.textContent),
      flip: !document.querySelector('#flip').hidden, keys: window.__flow.keys, opt: window.__flow.opt, side: window.__flow.side,
      split: window.__flow.split, layer: window.__flow.layer, speed: window.__flow.speed, t: window.__flow.t, H: window.__flow.H}));
    out.push({u, errs, ...r}); await p.close();
  }
  await b.close(); console.log(JSON.stringify(out));
})().catch(e => { console.error(e); process.exit(2); });
"""


def test_browser_smoke_headline_numbers_and_url_parameters(tmp_path):
    pp, chrome, node = _puppeteer(), shutil.which("google-chrome") or shutil.which("chromium"), shutil.which("node")
    if not (pp and chrome and node):
        pytest.skip("needs node, Chrome and puppeteer-core")
    urls = ["flow.html", "flow.html?s=finland&compare&paused&day=999", "flow.html?s=norway&compare",
            "flow.html?s=norway&compare&left=authors&right=suggested", "flow.html?s=norway&compare&left=observed&right=faster_pet",
            "flow.html?s=finland&view=both", "flow.html?s=finland&view=left&layer=time&speed=0.5", "flow.html?theme=night"]
    js = tmp_path / "smoke.js"
    js.write_text(SMOKE)
    res = subprocess.run([node, str(js), str(pp), chrome, str(DEMO), json.dumps(urls)], capture_output=True, text=True, timeout=180)
    assert res.returncode == 0, res.stderr
    rows = {r["u"]: r for r in json.loads(res.stdout.strip().splitlines()[-1])}
    for u, r in rows.items():
        assert not r["errs"], (u, r["errs"])
    sc = {s["id"]: s for s in _flow_bundle()["scenarios"]}
    var = lambda sid, k: next(v for v in sc[sid]["variants"] if v["key"] == k)["flow"]["metrics"]

    # default: Norway, Today only, no flip, one value per row
    r = rows["flow.html"]
    assert not r["opt"] and not r["flip"] and r["side"] == 0 and r["speed"] == 2
    m = var("norway", "observed")
    assert r["head"][:2] == [f"{100 * m['share_within_target']:.1f}%", f"{m['median_days_to_treatment']:.1f}"]

    # Finland after Optimise, at the end of the clock: today -> after equals flow.metrics of both variants
    r = rows["flow.html?s=finland&compare&paused&day=999"]
    assert r["opt"] and r["flip"] and r["side"] == 1 and abs(r["t"] - r["H"]) < 1e-6
    a, b = var("finland", "baseline"), var("finland", "suggested")
    want = [f"{100 * a['share_within_target']:.1f}%", f"{100 * b['share_within_target']:.1f}%",
            f"{a['median_days_to_treatment']:.1f}", f"{b['median_days_to_treatment']:.1f}",
            f"{a['missed_cancers']:.1f}", f"{b['missed_cancers']:.1f}"]
    assert r["head"] == want

    assert rows["flow.html?s=norway&compare"]["keys"] == sc["norway"]["default_pair"]
    assert rows["flow.html?s=norway&compare&left=authors&right=suggested"]["keys"] == ["authors", "suggested"]
    assert rows["flow.html?s=norway&compare&left=observed&right=faster_pet"]["keys"] == ["observed", "faster_pet"]
    assert rows["flow.html?s=finland&view=both"]["split"]
    r = rows["flow.html?s=finland&view=left&layer=time&speed=0.5"]
    assert r["side"] == 0 and r["layer"] == "time" and r["speed"] == 0.5 and r["opt"]
