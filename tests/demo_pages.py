"""Shared checks for the offline demo pages (UI revamp, lane L0). Every page lane's test imports this.

    from demo_pages import DEMO, parse, check_page
    def test_my_page():
        check_page("patients.html", page_id="patients")

Owned by L0 / the integrator; additive changes only. The parser generalises the one in tests/test_demo_start.py:
page text is everything outside <script>, <style>, <code> and elements with class "cmd" (and their children);
HTML comments are not text.
"""
from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "demo"

PAGE_IDS = {"overview": "start.html", "simulator": "flow.html", "patients": "patients.html",
            "evidence": "evidence.html", "model": "jev.html"}

_VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}


class Page(HTMLParser):
    """Collects links (<a href>), assets (<link href>, <script src>, <img src>), page text and nav elements."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []
        self.stylesheets: list[str] = []
        self.scripts: list[str] = []
        self.images: list[str] = []
        self.text: list[str] = []
        self.navs: list[dict] = []
        self._stack: list[bool] = []  # per open element: does it hide its text?
        self._hidden = 0

    def handle_starttag(self, tag, attrs):
        a = {k: (v or "") for k, v in attrs}
        classes = a.get("class", "").split()
        if tag == "a" and a.get("href"):
            self.links.append(a["href"])
        elif tag == "link" and a.get("href"):
            self.stylesheets.append(a["href"])
        elif tag == "script" and a.get("src"):
            self.scripts.append(a["src"])
        elif tag in ("img", "source") and a.get("src"):
            self.images.append(a["src"])
        if tag == "nav":
            self.navs.append(dict(a, _classes=classes))
        if tag in _VOID:
            return
        hides = tag in ("script", "style", "code", "template") or "cmd" in classes
        self._stack.append(hides)
        self._hidden += hides

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in _VOID and self._stack:  # <x/> on a non-void element: close it again
            self._hidden -= self._stack.pop()

    def handle_endtag(self, tag):
        if tag in _VOID or not self._stack:
            return
        self._hidden -= self._stack.pop()

    def handle_data(self, data):
        if not self._hidden:
            self.text.append(data)

    @property
    def page_text(self) -> str:
        return " ".join(" ".join(self.text).split())

    @property
    def assets(self) -> list[str]:
        return self.stylesheets + self.scripts + self.images


def parse(name_or_path) -> Page:
    path = Path(name_or_path)
    if not path.is_absolute():
        path = DEMO / path
    p = Page()
    p.feed(path.read_text(encoding="utf-8"))
    p.close()
    return p


def _local(ref: str) -> str | None:
    """Path part of a local reference, or None for in-page anchors, mailto, javascript and external URLs."""
    s = urlsplit(ref)
    if s.scheme or s.netloc or ref.startswith(("#", "mailto:", "javascript:")):
        return None
    return s.path or None


# ---------- individual checks (each raises AssertionError with a readable message) ----------

def check_links_and_assets_exist(p: Page, base: Path = DEMO):
    missing = [r for r in p.links + p.assets if (path := _local(r)) and not (base / path).resolve().exists()]
    assert not missing, f"missing link or asset targets: {missing}"


def check_no_digits_in_text(p: Page):
    text = p.page_text
    hits = [text[max(0, m.start() - 25): m.end() + 25] for m in re.finditer(r"\d", text)]
    assert not hits, f"digits typed into page text (bind numbers from bundles; commands go in <code>/.cmd): {hits}"


def check_no_remote_assets(p: Page):
    remote = [r for r in p.stylesheets + p.scripts if re.match(r"(?i)^(https?:)?//", r.strip())]
    assert not remote, f"remote <link>/<script src> (the site must work offline from file://): {remote}"


def check_links_theme_and_site(p: Page):
    css = [urlsplit(s).path for s in p.stylesheets]
    js = [urlsplit(s).path for s in p.scripts]
    assert "theme.css" in css, "theme.css is not linked"
    assert "site.js" in js, "site.js is not linked"


def check_load_order(p: Page):
    """theme.css is the first stylesheet; site.js comes after every bundle (data/...) script."""
    css = [urlsplit(s).path for s in p.stylesheets]
    js = [urlsplit(s).path for s in p.scripts]
    assert css and css[0] == "theme.css", f"theme.css should be the first stylesheet, got {css}"
    i = js.index("site.js")
    late_bundles = [s for s in js[i + 1:] if s.startswith("data/")]
    assert not late_bundles, f"bundles should load before site.js: {late_bundles}"


def check_site_nav(p: Page, page_id: str | None = None):
    navs = [n for n in p.navs if "site-nav" in n["_classes"] and n.get("data-page")]
    assert navs, 'no <nav class="site-nav" data-page="..."> on the page'
    pid = navs[0]["data-page"]
    assert pid in PAGE_IDS, f"unknown data-page {pid!r}; use one of {sorted(PAGE_IDS)}"
    if page_id is not None:
        assert pid == page_id, f"data-page is {pid!r}, expected {page_id!r}"


def check_no_clinician_validated(path: Path):
    t = path.read_text(encoding="utf-8")
    assert not re.search(r"clinician[\s-]*validated", t, re.I), f"{path.name}: never claim clinical validation"


def links_site_js(name_or_path) -> bool:
    return any(urlsplit(s).path == "site.js" for s in parse(name_or_path).scripts)


def check_page(name: str, page_id: str | None = None, load_order: bool = True):
    """All shared checks for one page in demo/. page_id: the expected data-page (optional)."""
    p = parse(name)
    check_links_and_assets_exist(p)
    check_no_digits_in_text(p)
    check_no_remote_assets(p)
    check_links_theme_and_site(p)
    if load_order:
        check_load_order(p)
    check_site_nav(p, page_id)
    check_no_clinician_validated(DEMO / name)
    return p
