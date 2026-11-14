"""UI revamp lane L6: the primary-care loop page (demo/encounter.html) and the full results report (demo/index.html)
on the paper theme. Static checks only (no browser); the pages were also looked at in headless Chrome
(docs/plan/ui-revamp/handoff/l6.md)."""

import re
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "demo"
HEX = re.compile(r"#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b|rgba?\(")


class _Text(HTMLParser):
    """Visible text outside <script>, <style>, <code>, <kbd> and .cmd."""

    SKIP = {"script", "style", "code", "kbd"}

    def __init__(self):
        super().__init__()
        self.stack, self.text = [], []

    def handle_starttag(self, tag, attrs):
        cls = dict(attrs).get("class") or ""
        if tag in ("meta", "link", "br", "input", "img"):
            return
        self.stack.append(tag in self.SKIP or "cmd" in cls.split())

    def handle_endtag(self, tag):
        if self.stack and tag not in ("meta", "link", "br", "input", "img"):
            self.stack.pop()

    def handle_data(self, data):
        if not any(self.stack):
            self.text.append(data)


def page_text(html: str) -> str:
    p = _Text()
    p.feed(html)
    return " ".join(p.text)


def test_encounter_uses_the_shared_contract():
    html = (DEMO / "encounter.html").read_text()
    order = [html.index(x) for x in ('href="theme.css"', 'href="encounter.css"', 'src="data/encounter_bundle.js"',
                                     'src="site.js"', 'src="encounter.js"')]
    assert order == sorted(order), "load order: theme.css -> page CSS -> bundles -> site.js -> page JS"
    assert '<nav class="site-nav" data-page="simulator"' in html
    for cls in ('class="page ', 'class="page-top', 'class="page-title"', 'class="lede"', 'class="details"',
                'class="details-rule"', 'class="footer-strip"', 'btn--primary'):
        assert cls in html, cls
    assert html.count("btn--primary") == 1, "one primary button"
    assert "http://" not in html and "https://" not in html


def test_encounter_static_text_has_no_digits():
    text = page_text((DEMO / "encounter.html").read_text())
    assert not re.search(r"\d", text), re.findall(r".{20}\d.{20}", text)


def test_encounter_details_keep_counters_results_and_caveats():
    html = (DEMO / "encounter.html").read_text()
    top, details = html.split('class="details"', 1)
    for el in ('id="counters"', 'id="results"', 'id="note"'):
        assert el in details and el not in top, el
    # the graph, the record and the truth toggle stay above Details
    for el in ('id="gw"', 'id="side"', 'id="truth"', 'id="play"', 'id="slider"', 'id="speed"', 'id="layers"'):
        assert el in top, el
    assert "Assumed behaviour" in top and "research.html#as-primary-care-behaviour" in top
    js = (DEMO / "encounter.js").read_text()
    for caveat in ("All patients are simulated", "placeholder tables", "one illustration run", "not clinical advice"):
        assert caveat.lower() in js.lower(), caveat
    assert "CLINICIAN-VALIDATED" not in (html + js).upper().replace(" ", "-")


def test_encounter_speeds_and_url_parameters():
    js = (DEMO / "encounter.js").read_text()
    assert "const SPEEDS = [0.5, 1, 2, 4, 8]" in js
    assert re.search(r"rate: 2\b", js), "default speed is two days per second"
    for q in ("q.get('p')", "q.has('paused')", "q.get('day')", "q.get('layer')", "q.has('truth')"):
        assert q in js, q
    for key in ("'Space'", "'r'", "'t'", "'ArrowRight'", "'ArrowLeft'"):
        assert key in js, key


def test_encounter_colours_come_from_tokens():
    css = (DEMO / "encounter.css").read_text()
    assert ":root" not in css
    assert not HEX.search(css), HEX.findall(css)
    js = (DEMO / "encounter.js").read_text()
    # the only literals are the token fallbacks in the C block
    body = js.split("return o;\n})();", 1)[1]
    assert not re.search(r"#[0-9a-fA-F]{6}\b", body)
    assert "getPropertyValue" in js


def test_index_is_themed_without_touching_the_bundle():
    html = (DEMO / "index.html").read_text()
    assert html.index('href="theme.css"') < html.index("<style>") < html.index('<script id="bundle"')
    style = html[html.index("<style>"):html.index("</style>")]
    assert ":root" not in style
    assert not HEX.search(style), HEX.findall(style)
    assert "repeating-linear-gradient" not in style and "radial-gradient" not in style
    script = html[html.index("</script>", html.index('<script id="bundle"')):]
    # colours are read from the tokens; hex values appear only as fallbacks inside the C block
    c_block = script[script.index("var C=(function(){"):script.index("})();", script.index("var C=(function(){"))]
    rest = script.replace(c_block, "")
    assert "getPropertyValue" in c_block
    assert not re.search(r"#[0-9a-fA-F]{6}\b", rest), re.findall(r"#[0-9a-fA-F]{6}\b", rest)
    assert "rgba(255" not in rest
