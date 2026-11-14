"""The Patients page (demo/patients.html, UI lane L3).

Static checks: the shared page checks (tests/demo_pages.py, when present), link targets, no digits in the page text,
offline assets, the load order, and that the sealed truth is not in the static page (the truth container is empty and
hidden; patients.js fills it only after the reader lifts the seal). Numbers are bound from bundles by patients.js."""
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

import pytest

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "demo"
PAGE = DEMO / "patients.html"
JS = DEMO / "patients.js"
CSS = DEMO / "patients.css"


class P(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links, self.assets, self.scripts, self.text = [], [], [], []
        self.ids, self.stack = {}, []
        self._skip = 0
        self._code = 0
        self.truth_text = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = a.get("class") or ""
        if a.get("id"):
            self.ids[a["id"]] = (tag, a)
        if tag == "a" and a.get("href"):
            self.links.append(a["href"])
        if tag == "script":
            self._skip += 1
            if a.get("src"):
                self.scripts.append(a["src"])
                self.assets.append(a["src"])
        if tag == "link" and a.get("href"):
            self.assets.append(a["href"])
        if tag == "style":
            self._skip += 1
        code = tag == "code" or "cmd" in cls.split()
        self._code += code
        self.stack.append((tag, code, a.get("id")))

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._skip -= 1
        while self.stack:
            t, code, _ = self.stack.pop()
            self._code -= code
            if t == tag:
                break

    def handle_data(self, d):
        if any(i == "pt-truth" for _, _, i in self.stack):
            self.truth_text.append(d)
        if not self._skip and not self._code:
            self.text.append(d)


@pytest.fixture(scope="module")
def page():
    p = P()
    p.feed(PAGE.read_text(encoding="utf-8"))
    return p


def _local(href):
    u = urlsplit(href)
    return not u.scheme and not u.netloc and u.path


def test_shared_page_checks():
    helper = pytest.importorskip("demo_pages", reason="tests/demo_pages.py (L0-B) not merged yet")
    for name in ("check_page", "check_all", "run_checks"):
        fn = getattr(helper, name, None)
        if callable(fn):
            fn(PAGE)
            return
    pytest.skip("tests/demo_pages.py has no page-level entry point this test knows")


def test_links_and_assets_exist(page):
    missing = []
    for href in page.links + page.assets:
        if not _local(href):
            continue
        target = (DEMO / urlsplit(href).path).resolve()
        if not target.exists():
            missing.append(href)
    # research.html comes from lane L9; until it is merged its links are allowed to dangle here.
    missing = [m for m in missing if not m.startswith("research.html")]
    assert not missing, missing


def test_offline(page):
    for src in page.assets:
        assert not re.match(r"(?i)https?:|//", src), src
    for f in (JS, CSS):
        assert not re.search(r"(?i)(src|href|url)\s*[=(]\s*['\"]?(https?:)?//", f.read_text(encoding="utf-8")), f.name


def test_no_digits_in_page_text(page):
    text = " ".join(page.text)
    assert not re.search(r"\d", text), re.findall(r".{0,30}\d.{0,30}", text)


def test_theme_site_and_load_order(page):
    a = page.assets
    assert a[0] == "theme.css" and a[1] == "patients.css", a
    assert "site.js" in a and "patients.js" in a
    bundles = [x for x in a if x.startswith("data/")]
    assert bundles, "page reads no bundle"
    assert max(a.index(b) for b in bundles) < a.index("site.js") < a.index("patients.js")
    nav = page.ids  # nav has no id; check the raw markup instead
    assert re.search(r'<nav class="site-nav" data-page="patients">', PAGE.read_text(encoding="utf-8"))
    assert "pt-footer" in nav and "footer-strip" in nav["pt-footer"][1].get("class", "")


def test_truth_is_sealed_in_static_page(page):
    tag, attrs = page.ids["pt-truth"]
    assert "hidden" in attrs, "the truth container must be hidden until the reader asks"
    assert not "".join(page.truth_text).strip(), "the truth container must be empty in the static page"
    btn = page.ids["pt-reveal"][1]
    assert btn.get("aria-pressed") == "false" and btn.get("aria-controls") == "pt-truth"
    js = JS.read_text(encoding="utf-8")
    # truth is read only in renderTruth after the S.open check, and in renderRecord only when S.open
    assert "if (!S.open) { box.hidden = true; return; }" in js
    assert "S.open && ENC.truth" in js


def test_url_parameters_supported():
    js = JS.read_text(encoding="utf-8")
    assert 'Q.has("truth")' in js and 'Q.get("p")' in js


def test_no_typed_numbers_in_js():
    """Numerals in patients.js are limited to formatting constants; results come from the bundles."""
    js = JS.read_text(encoding="utf-8")
    js = re.sub(r"/\*.*?\*/", "", js, flags=re.S)
    js = re.sub(r"//[^\n]*", "", js)
    js = re.sub(r'"(?:[^"\\]|\\.)*"', '""', js)   # string literals (ids, prompt names like g2@3) are not numbers
    nums = {int(n) for n in re.findall(r"(?<![\w.])(\d+)(?![\w.])", js)}
    assert nums <= {0, 1, 2, 3, 6, 16, 100}, sorted(nums)


def test_no_clinical_approval_claim(page):
    raw = (PAGE.read_text(encoding="utf-8") + JS.read_text(encoding="utf-8")).lower()
    assert "clinician-validated" not in raw and "clinically validated" not in raw


def test_bundle_fields_the_page_reads_exist():
    import json

    def load(name):
        s = (DEMO / "data" / name).read_text(encoding="utf-8")
        return json.loads(s[s.index("{"): s.rstrip().rstrip(";").rindex("}") + 1])

    enc = load("encounter_bundle.js")
    ids = {str(p["id"]) for p in enc["patients"]}
    assert any(str(e["id"]) in ids for e in enc["examples"])
    assert any(e["key"] == "cancer_as_infection" for e in enc["examples"])
    for e in enc["examples"]:
        if str(e["id"]) in ids:
            assert str(e["id"]) in enc["truth"]
    flow = load("flow_bundle.js")
    no = [s for s in flow["scenarios"] if s["id"] == "norway"][0]
    keys = {v["key"] for v in no["variants"]}
    assert {"observed", "suggested"} <= keys
    st = load("start_bundle.js")
    assert "optimiser_no_equipment" in st["norway"]["optimiser"]["bands"]
    cards = load("cards_bundle.js")
    assert cards["example"]["hidden"]["conditions"]
