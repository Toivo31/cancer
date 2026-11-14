"""The start page (demo/start.html): link targets exist and no number is typed into the page text.

Numbers are bound at load time from the bundles (see demo/start.js); here the static page is checked."""
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "demo"
PAGE = DEMO / "start.html"


class P(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links, self.scripts, self.text, self._skip, self._code = [], [], [], 0, 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "a" and a.get("href"):
            self.links.append(a["href"])
        if tag == "script":
            self._skip += 1
            if a.get("src"):
                self.scripts.append(a["src"])
        if tag == "link" and a.get("href"):
            self.scripts.append(a["href"])
        if tag == "code" or (tag == "span" and "cmd" in (a.get("class") or "")):
            self._code += 1

    def handle_endtag(self, tag):
        if tag == "script":
            self._skip -= 1
        if tag in ("code", "span") and self._code:
            self._code -= 1 if tag == "code" or self._code else 0

    def handle_data(self, d):
        if not self._skip and not self._code:
            self.text.append(d)


def parsed():
    p = P()
    p.feed(PAGE.read_text(encoding="utf-8"))
    return p


def test_every_link_and_asset_exists():
    p = parsed()
    assert len(p.links) >= 10
    for ref in p.links + p.scripts:
        path = urlsplit(ref).path
        assert path and (DEMO / path).resolve().exists(), f"missing target: {ref}"


def test_no_number_typed_into_page_text():
    text = " ".join(parsed().text)
    # commands and URLs (inside <code> or .cmd) are exempt; everything else is bound from data at load time
    assert not re.search(r"\d", text), re.findall(r".{20}\d.{20}", text)


def test_script_has_no_hand_typed_results():
    js = (DEMO / "start.js").read_text(encoding="utf-8")
    code = re.sub(r"^\s*//.*$", "", re.sub(r"/\*.*?\*/", "", js, flags=re.S), flags=re.M)
    nums = set(re.findall(r"(?<![\w.$#])\d+(?:\.\d+)?(?![\w])", re.sub(r'"[^"]*"', '""', code)))
    assert nums <= {"0", "1", "2", "16", "100"}, nums


def test_start_bundle_parses():
    import json
    t = (DEMO / "data" / "start_bundle.js").read_text(encoding="utf-8")
    d = json.loads(re.match(r"window\.START_DATA = (.*);\s*$", t, re.S).group(1))
    assert d["format"] == "start-bundle/1"


def test_norway_links_built_in_script_name_real_variants():
    """The two Norway buttons are added by start.js; their left/right keys must be variants in the flow bundle."""
    import json
    js = (DEMO / "start.js").read_text(encoding="utf-8")
    t = (DEMO / "data" / "flow_bundle.js").read_text(encoding="utf-8")
    d = json.loads(t[t.index("=") + 1:].rstrip().rstrip(";"))
    keys = {v["key"] for s in d["scenarios"] if s["id"] == "norway" for v in s["variants"]}
    pairs = re.findall(r"flow\.html\?s=norway&compare&left=(\w+)&right=(\w+)", js)
    assert len(pairs) >= 1
    for a, b in pairs:
        assert a in keys and b in keys
    nor = next(s for s in d["scenarios"] if s["id"] == "norway")
    assert set(nor["default_pair"]) <= keys


def test_start_bundle_norway_ranges_match_the_review_files():
    """The Norway optimiser bands on the pages are read from docs/review_checks, not typed."""
    import json
    t = (DEMO / "data" / "start_bundle.js").read_text(encoding="utf-8")
    d = json.loads(re.match(r"window\.START_DATA = (.*);\s*$", t, re.S).group(1))
    O = d["norway"]["optimiser"]
    summ = json.loads((ROOT / "docs/review_checks/norway_opt_summary.json").read_text())
    assert O["n_settings"] == summ["n_settings"] == 184
    assert abs(O["bands"]["optimiser_no_equipment"]["median"] - summ["bands_percent"]["full_nofast"]["median"] / 100) < 1e-9
    assert O["counts"]["noeq_beats_scanner_alone"] == summ["counts"]["opt_nofast_beats_fasterpet"]
    assert O["structure"]["literal_in_published_ci"] == 139


def test_pages_do_not_claim_the_optimiser_beats_the_authors():
    for name in ("start.js", "flow.js", "index.html"):
        text = (DEMO / name).read_text(encoding="utf-8").lower()
        for bad in ("ahead in", "most of the lead", "optimiser is ahead", "ours is ahead"):
            assert bad not in text, (name, bad)
