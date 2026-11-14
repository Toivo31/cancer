"""Every research.html#<id> link on the demo site resolves to a row of the research page (D69, ui-followups).

The research page builds one row per claim (and one card per unsupported item) from data/research_bundle.js, with the
claim id as the element id. Pages link to those rows in three ways: literal hrefs in HTML, data-claim attributes, and
ids written as string literals in page JS that build the href at load time. The static test reads all three; the
browser test opens every page (and the dashboard screens that carry claim lines), collects the rendered
a[href*="research.html#"] links, and checks each target exists on the rendered research page. The browser part is
skipped when node, Chrome or puppeteer-core is missing (as in test_demo_flow_page.py).
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "demo"
PAGES = sorted(p for p in DEMO.glob("*.html") if not p.name.startswith("_"))
SCRIPTS = sorted(DEMO.glob("*.js"))


def _register() -> dict:
    t = (DEMO / "data" / "research_bundle.js").read_text(encoding="utf-8")
    return json.loads(t[t.index("=") + 1:].strip().rstrip(";"))


REG = _register()
TARGETS = {c["id"] for c in REG["claims"]} | {u["id"] for u in REG["unsupported"]}
PREFIXES = {i.split("-")[0] for i in TARGETS}
# a string literal shaped like a claim id: a register prefix and at least three hyphenated parts
LOOKS_LIKE = re.compile(r"""["'`]((?:%s)-[a-z0-9]+(?:-[a-z0-9]+)+)["'`]""" % "|".join(sorted(PREFIXES)))


def _page_local_names() -> set[str]:
    """Class names and element ids the pages define themselves (e.g. .sim-details-btn), which are not claim ids."""
    names: set[str] = set()
    for css in DEMO.glob("*.css"):
        names |= set(re.findall(r"[.#]([a-z][a-z0-9_-]*)", css.read_text(encoding="utf-8")))
    for page in PAGES:
        names |= set(re.findall(r'\bid="([^"]+)"', page.read_text(encoding="utf-8")))
    return names - TARGETS


def _static_refs() -> dict[str, set[str]]:
    refs: dict[str, set[str]] = {}
    local = _page_local_names()
    for f in PAGES + SCRIPTS:
        if f.name == "research.js":          # the page that defines the targets
            continue
        t = f.read_text(encoding="utf-8")
        if f.name == "index.html":           # skip the frozen data block; only the page code links claims
            t = re.sub(r'<script id="bundle".*?</script>', "", t, flags=re.S)
        found = set(re.findall(r"research\.html#([A-Za-z0-9_-]+)", t))
        for attr in re.findall(r'data-claim="([^"]+)"', t):
            found |= set(attr.split())
        found |= {m for m in LOOKS_LIKE.findall(t) if m not in local}
        found -= {"id"}                      # placeholder in comments: research.html#id, data-claim="id"
        if found:
            refs[f.name] = found
    return refs


def test_register_ids_are_unique_and_html_safe():
    ids = [c["id"] for c in REG["claims"]] + [u["id"] for u in REG["unsupported"]]
    assert len(ids) == len(set(ids))
    for i in ids:
        assert re.fullmatch(r"[a-z][a-z0-9-]*", i), i


def test_every_claim_id_written_in_page_code_exists_in_the_register():
    refs = _static_refs()
    # the pages that carry claim labels since the revamp (D69), plus the dashboard's claim lines on screens 2 and 4
    for name in ("start.js", "patients.html", "evidence.js", "encounter.html", "jev.js", "flow.js", "index.html"):
        assert name in refs, f"{name}: no claim reference found (the scan or the page changed)"
    bad = {f: sorted(ids - TARGETS) for f, ids in refs.items() if ids - TARGETS}
    assert not bad, f"research.html#<id> targets missing from docs/research_claims.yaml: {bad}"


def test_dashboard_screens_two_and_four_link_their_claims():
    html = (DEMO / "index.html").read_text(encoding="utf-8")
    assert '<script src="data/research_bundle.js"></script>' in html
    assert "claimLine(sc,2)" in html and "claimLine(sc,4)" in html
    block = html[html.index("var CLAIMS=(function(){"):html.index("function claimLine")]
    for scen in ("finland_lung", "stokstad"):
        assert scen in block
    for cid in re.findall(r'\["([a-z0-9-]+)","', block):
        assert cid in TARGETS, cid


def _puppeteer():
    for d in (ROOT / "web/node_modules/puppeteer-core", Path("/home/claude/cancer/web/node_modules/puppeteer-core"),
              Path("/tmp/node_modules/puppeteer-core")):
        if (d / "package.json").exists():
            return d
    return None


COLLECT = r"""
const pp = require(process.argv[2]);
(async () => {
  const b = await pp.launch({executablePath: process.argv[3], headless: true,
    args: ['--no-sandbox', '--allow-file-access-from-files', '--host-resolver-rules=MAP * ~NOTFOUND']});
  const out = {links: {}, rows: [], errs: []};
  for (const u of JSON.parse(process.argv[5])) {
    const p = await b.newPage(); await p.setViewport({width: 1440, height: 900});
    p.on('pageerror', e => out.errs.push(u + ': ' + e.message));
    await p.goto('file://' + process.argv[4] + '/' + u, {waitUntil: 'load'});
    await new Promise(r => setTimeout(r, 700));
    out.links[u] = await p.evaluate(() => [...document.querySelectorAll('a[href*="research.html#"]')]
      .map(a => decodeURIComponent(a.getAttribute('href').split('#')[1])));
    await p.close();
  }
  const p = await b.newPage();
  await p.goto('file://' + process.argv[4] + '/research.html', {waitUntil: 'load'});
  await new Promise(r => setTimeout(r, 500));
  out.rows = await p.evaluate(() => [...document.querySelectorAll('[id]')].map(e => e.id));
  await b.close(); console.log(JSON.stringify(out));
})().catch(e => { console.error(e); process.exit(2); });
"""


def test_rendered_claim_links_resolve_on_the_research_page(tmp_path):
    pp, chrome, node = _puppeteer(), shutil.which("google-chrome") or shutil.which("chromium"), shutil.which("node")
    if not (pp and chrome and node):
        pytest.skip("needs node, Chrome and puppeteer-core")
    urls = [p.name for p in PAGES if p.name != "research.html"] + [
        "index.html#finland_lung/2", "index.html#finland_lung/4", "index.html#stokstad/2", "index.html#stokstad/4",
        "flow.html?s=norway&compare", "patients.html?truth", "encounter.html?p=1270"]
    js = tmp_path / "collect.js"
    js.write_text(COLLECT)
    res = subprocess.run([node, str(js), str(pp), chrome, str(DEMO), json.dumps(urls)],
                         capture_output=True, text=True, timeout=240)
    assert res.returncode == 0, res.stderr
    out = json.loads(res.stdout.strip().splitlines()[-1])
    assert not out["errs"], out["errs"]
    rows = set(out["rows"])
    assert TARGETS <= rows, f"research.html builds no row for {sorted(TARGETS - rows)}"
    seen = set()
    for u, ids in out["links"].items():
        missing = sorted(set(ids) - rows)
        assert not missing, f"{u}: research.html#{missing} has no row on the research page"
        seen |= set(ids)
    for u in ("start.html", "patients.html", "evidence.html", "encounter.html", "index.html#finland_lung/2",
              "index.html#stokstad/4"):
        assert out["links"][u], f"{u}: no research.html#<id> link rendered"
    assert seen, "no claim links rendered at all"
