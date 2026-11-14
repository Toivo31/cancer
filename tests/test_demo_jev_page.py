"""Decision model page layout (UI revamp lane L5): page template, paper theme, provenance labels, URL options.

The data and honesty checks of the page stay in tests/test_demo_jev.py; this file checks the restructure."""
import re
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "demo"
HTML = (DEMO / "jev.html").read_text(encoding="utf-8")
JS = (DEMO / "jev.js").read_text(encoding="utf-8")
CSS = (DEMO / "jev.css").read_text(encoding="utf-8")


class Tree(HTMLParser):
    """Flat list of (tag, attrs) in document order."""

    def __init__(self):
        super().__init__()
        self.tags = []

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


def tags():
    t = Tree()
    t.feed(HTML)
    return t.tags


def classes(a):
    return (a.get("class") or "").split()


def index_of(pred):
    return next(i for i, (t, a) in enumerate(tags()) if pred(t, a))


def test_load_order_theme_first_and_offline():
    order = [a.get("href") or a.get("src") for t, a in tags() if t in ("link", "script") and (a.get("href") or a.get("src"))]
    assert order.index("theme.css") < order.index("jev.css") < order.index("data/jev_bundle.js") < order.index("jev.js")
    if "site.js" in order:
        assert order.index("data/jev_bundle.js") < order.index("site.js") < order.index("jev.js")
    assert not any(re.match(r"https?://", x) for x in order), order


def test_nav_and_footer_from_the_contract():
    assert any(t == "nav" and "site-nav" in classes(a) and a.get("data-page") == "model" for t, a in tags())
    assert any("footer-strip" in classes(a) for t, a in tags())


def test_page_top_template():
    tt = tags()
    top = index_of(lambda t, a: "page-top" in classes(a))
    rule = index_of(lambda t, a: "details-rule" in classes(a))
    above = tt[top:rule]
    for cls in ("page-title", "lede", "figure", "caption"):
        assert any(cls in classes(a) for _, a in above), cls
    primaries = [a for _, a in tt if "btn--primary" in classes(a)]
    assert len(primaries) == 1, "one primary button on the page"


def test_model_card_sits_below_details():
    rule = index_of(lambda t, a: "details-rule" in classes(a))
    card = index_of(lambda t, a: a.get("id") == "model-card")
    examples = index_of(lambda t, a: a.get("id") == "examples")
    assert examples < rule < card


def test_ids_the_script_fills_exist():
    ids = {a.get("id") for _, a in tags()}
    for i in ("jev-fig", "fig-record", "fig-question", "fig-answers", "fig-person", "fig-caption", "ep-mode", "ep-url",
              "ep-status", "presets", "work", "hf", "d-enc", "arch-short", "arch-text", "facts", "honest", "footer",
              "claim-headlines"):
        assert i in ids, i
        assert f'"{i}"' in JS or i in ("jev-fig", "fig-record", "fig-question", "fig-answers", "fig-person"), i


def test_css_uses_tokens_only():
    assert ":root" not in CSS
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", CSS), "colours come from theme.css tokens"
    assert "rgba(" not in CSS and "gradient" not in CSS
    css = re.sub(r"/\*.*?\*/", "", CSS, flags=re.S)
    for sel in re.findall(r"(?:^|})\s*([^{}@]+)\{", css):
        for cls in re.findall(r"\.([a-zA-Z][\w-]*)", sel):
            assert cls.startswith("jev-") or cls in {
                "stamp", "btn", "card", "label", "details", "cmd", "best", "has", "out", "tablebars", "model", "live", "notmodel"
            }, cls


def test_provenance_labels_and_button_only_live_calls():
    for label in ("Recorded · ", "Live call · ", "scripted fixture, not the model", "mock, not the model",
                  "Placeholder decision table, not the model"):
        assert label in JS, label
    assert JS.count("fetch(") == 2          # the POST and the poll, both inside live(), which only buttons call
    assert re.search(r"live\(p\.key", JS)


def test_url_options_kept():
    assert 'param("api")' in JS
    for a in ('"hosted"', '"same"', '"recorded"', '"custom"'):
        assert a in JS
    assert "location.hash" in JS
    assert 'key: "own"' in JS


def test_scores_are_relative_statement_kept():
    assert "not probabilities" in HTML
    assert "not probabilities of disease" in JS


def test_claim_labels_link_to_research_page():
    assert '"research.html#" + id' in JS
    assert '"Our assumption", "as-jev-not-in-headlines"' in JS
    assert '"Our simulation", "sim-dm-benchmark"' in JS


def test_claim_ids_exist_in_the_research_register():
    reg = (DEMO / "data" / "research_bundle.js").read_text(encoding="utf-8")
    for cid in ("as-jev-not-in-headlines", "sim-dm-benchmark"):
        assert f'"id": "{cid}"' in reg or f'"id":"{cid}"' in reg, cid


def test_shared_page_checks():
    from tests.demo_pages import check_page
    check_page("jev.html", "model")
