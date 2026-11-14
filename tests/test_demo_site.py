"""The shared demo-site contract (UI revamp, lane L0): theme.css, fonts, site.js, and the shared checks on every page
that links site.js. Pages that do not link site.js yet are skipped, so old pages do not fail before their lane
reaches them."""
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from demo_pages import DEMO, PAGE_IDS, check_page, links_site_js, parse

THEME = DEMO / "theme.css"
SITE = DEMO / "site.js"

TOKENS = ["--paper", "--card", "--inset", "--ink", "--ink-2", "--ink-3", "--faint", "--line", "--mustard",
          "--mustard-ink", "--mustard-tint", "--brick", "--brick-tint", "--brown", "--carbon",
          "--s1", "--s2", "--s3", "--s4", "--s5", "--s6", "--s7", "--s8", "--s9", "--font-sans", "--font-mono"]
ALIASES = ["--night", "--p1", "--p2", "--text", "--muted", "--dim", "--mint", "--amber", "--coral", "--blue",
           "--red", "--violet", "--line", "--mono", "--sans"]
CLASSES = ["page", "page-top", "page-title", "lede", "figure", "caption", "details", "details-rule", "finding",
           "card", "inset", "stamp", "stamp--brick", "chip", "btn", "btn--primary", "btn--secondary", "num",
           "num--big", "label", "cmd", "footer-strip", "drawer", "drawer--open", "site-nav"]

SITE_PAGES = sorted(p.name for p in DEMO.glob("*.html") if links_site_js(p))


def _root_block(css: str, selector: str) -> str:
    m = re.search(re.escape(selector) + r"\s*\{(.*?)\n\}", css, re.S)
    assert m, f"no {selector} block in theme.css"
    return m.group(1)


def test_theme_tokens_and_aliases_defined():
    css = THEME.read_text(encoding="utf-8")
    root = _root_block(css, ":root")
    for name in TOKENS + ALIASES:
        assert re.search(re.escape(name) + r"\s*:", root), f"{name} missing from :root"
    night = _root_block(css, 'html[data-theme="night"]')
    for name in ALIASES:
        if name != "--line":
            assert re.search(re.escape(name) + r"\s*:", night), f"{name} missing from the night block"


def test_theme_shared_classes_defined():
    css = THEME.read_text(encoding="utf-8")
    for c in CLASSES:
        assert re.search(r"\." + re.escape(c) + r"(?![\w-])", css), f".{c} missing from theme.css"


def test_theme_is_offline_and_fonts_exist():
    css = THEME.read_text(encoding="utf-8")
    assert not re.search(r"(?i)(https?:)?//[\w.-]+\.\w+/", re.sub(r"/\*.*?\*/", "", css, flags=re.S)), "remote URL in theme.css"
    assert "@import" not in css
    fonts = re.findall(r'url\("?([^")]+)"?\)', css)
    assert fonts, "no font files referenced (if fonts are dropped, remove @font-face too)"
    for f in fonts:
        assert (DEMO / f).exists(), f"font file missing: {f}"
    assert (DEMO / "fonts" / "OFL.txt").exists()


def test_never_clinician_validated():
    for p in [THEME, SITE, DEMO / "_skeleton.html"] + [DEMO / n for n in SITE_PAGES]:
        assert not re.search(r"clinician[\s-]*validated", p.read_text(encoding="utf-8"), re.I), p.name


def test_site_js_pages_match_contract():
    js = SITE.read_text(encoding="utf-8")
    for pid, href in PAGE_IDS.items():
        assert re.search(r'id:\s*"%s",\s*href:\s*"%s"' % (pid, re.escape(href)), js), (pid, href)
    for label in ["Overview", "Simulator", "Patients", "Evidence", "Decision model"]:
        assert f'"{label}"' in js
    for fn in ["nav:", "footer:", "tokens:", "theme:"]:
        assert fn in js
    assert "http://" not in js and "https://" not in js


def test_skeleton_follows_the_template():
    p = check_page("_skeleton.html")
    css = [s for s in p.stylesheets]
    assert css[0] == "theme.css"


def test_nav_targets_exist():
    for href in PAGE_IDS.values():
        assert (DEMO / href).exists(), href


@pytest.mark.parametrize("name", SITE_PAGES)
def test_site_page_passes_shared_checks(name):
    check_page(name)


def test_parser_hides_code_and_cmd_text():
    from demo_pages import Page
    p = Page()
    p.feed('<p>a <code>x1</code> b <span class="cmd">run <b>2</b></span> c<br>d<script>var n=3</script></p>')
    assert p.page_text == "a b c d"


@pytest.mark.skipif(not shutil.which("node"), reason="node not installed")
def test_site_js_parses():
    subprocess.run(["node", "--check", str(SITE)], check=True)
