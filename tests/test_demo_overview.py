"""Overview page (demo/start.html, UI revamp lane L2): structure of the top, claim labels, links kept.

The older rules (no digits in page text, numeral whitelist in start.js, link targets) stay in test_demo_start.py."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "demo"
HTML = (DEMO / "start.html").read_text(encoding="utf-8")
JS = (DEMO / "start.js").read_text(encoding="utf-8")


def _top():
    return HTML[HTML.index('<header class="page-top'):HTML.index('class="details"')]


def test_nav_and_load_order():
    assert '<nav class="site-nav" data-page="overview">' in HTML
    links = re.findall(r'<link rel="stylesheet" href="([^"]+)"', HTML)
    assert links[:2] == ["theme.css", "start.css"]
    scripts = re.findall(r'<script src="([^"]+)"', HTML)
    assert scripts[-1] == "start.js"
    assert ":root" not in (DEMO / "start.css").read_text(encoding="utf-8")


def test_top_has_three_cards_and_one_primary_button():
    top = _top()
    assert top.count('class="card ov-card"') == 3
    assert HTML.count("btn--primary") == 1
    assert re.search(r'<a class="btn btn--primary" href="flow\.html">Open the simulator</a>', top)
    assert 'class="details-rule"' in HTML and 'class="footer-strip"' in HTML


def test_top_is_short():
    text = re.sub(r"<svg.*?</svg>", " ", _top(), flags=re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    words = [w for w in text.split() if re.search(r"[A-Za-z]", w) and w != "pending"]
    assert len(words) <= 120, len(words)  # plan: about 80; the cards carry labels and claim tags


def test_no_clinician_validated_claim():
    for t in (HTML, JS):
        assert "clinician-validated" not in t.lower() and "clinically validated" not in t.lower()


def test_claim_labels_name_real_claims():
    t = (DEMO / "data" / "research_bundle.js").read_text(encoding="utf-8")
    ids = {c["id"] for c in json.loads(t[t.index("=") + 1:].rstrip().rstrip(";"))["claims"]}
    used = set()
    for attr in re.findall(r'data-claim="([^"]+)"', HTML):
        used |= set(attr.split())
    for group in re.findall(r"claimList\(box, \[([^\]]+)\]\)", JS):
        used |= set(re.findall(r'"([\w-]+)"', group))
    assert len(used) >= 10
    assert used <= ids, used - ids


def test_norway_headline_carries_its_range():
    """D68 / numbers sheet: the optimiser's best fit is never shown without the range over the fitting settings."""
    assert "optimiser_no_equipment" in JS and 't-chk-range' in HTML
    assert re.search(r'set\("t-chk-range", "No new equipment, best fit\. "', JS)
    assert "faster_pet" not in _top()


def test_old_entry_points_still_linked():
    for href in ("jev.html", "encounter.html", "index.html#finland_lung/2", "index.html#stokstad/5",
                 "flow.html?s=finland&amp;compare", "../docs/validation.md", "../docs/ledger.md"):
        assert f'href="{href}"' in HTML, href
    assert "flow.html?s=norway&compare&left=observed&right=suggested" in JS
    assert "patients.html" in JS and "research.html#" in JS
