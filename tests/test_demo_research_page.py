"""Research behind the numbers page (demo/research.html, lane L9, D69).

The page is built entirely from window.RESEARCH_DATA (demo/data/research_bundle.js). These checks cover the static
page (shared checks from tests/demo_pages.py), that research.js reads the bundle instead of copying the register,
and that every claim id can be a row id (research.html#<claim id>). The data itself is tested in
tests/test_demo_research.py.
"""
import json
import re
from pathlib import Path

from demo_pages import DEMO, check_page, parse

PAGE = "research.html"
JS = (DEMO / "research.js").read_text(encoding="utf-8")
CSS = (DEMO / "research.css").read_text(encoding="utf-8")
HTML = (DEMO / PAGE).read_text(encoding="utf-8")


def _bundle():
    s = (DEMO / "data" / "research_bundle.js").read_text(encoding="utf-8")
    return json.loads(s[s.index("{"): s.rindex("}") + 1])


B = _bundle()


def test_shared_page_checks():
    # Not in the nav (D60: five pages); the nav marks Evidence as the current section.
    check_page(PAGE, page_id="evidence")


def test_loads_the_research_bundle_before_site_and_page_js():
    scripts = parse(PAGE).scripts
    assert scripts == ["data/research_bundle.js", "site.js", "research.js"], scripts
    assert parse(PAGE).stylesheets == ["theme.css", "research.css"]


def test_no_digits_in_page_text():
    text = parse(PAGE).page_text
    assert not re.search(r"\d", text), text


def test_js_reads_the_bundle_and_does_not_copy_the_register():
    assert "window.RESEARCH_DATA" in JS
    for c in B["claims"]:
        assert c["claim"] not in JS, f"claim text of {c['id']} is copied into research.js"
        assert c["strength"] not in JS, f"strength of {c['id']} is copied into research.js"
    assert B["framing"] not in JS and B["framing"] not in HTML, "framing sentence must come from the bundle"
    for u in B["unsupported"]:
        assert u["claim"] not in JS and u["claim"] not in HTML


def test_no_numbers_typed_in_js():
    """Numerals in research.js are limited to formatting constants; counts and shares come from the bundle."""
    code = re.sub(r"/\*.*?\*/|//[^\n]*", "", JS, flags=re.S)
    code = re.sub(r"(?<=[(,=:])\s*/(?:\\.|\[[^\]\n]*\]|[^/\n\\])+/[gimsuy]*", " RE", code)  # regex literals
    nums = set(re.findall(r"(?<![\w#.])\d+(?:\.\d+)?(?![\w])", code))
    assert nums <= {"0", "1", "8", "100"}, nums


def test_every_claim_id_is_a_valid_html_id_and_becomes_a_row_id():
    for c in B["claims"] + B["unsupported"]:
        assert re.fullmatch(r"[a-z][a-z0-9]*(-[a-z0-9]+)*", c["id"]), c["id"]
    ids = [c["id"] for c in B["claims"]] + [u["id"] for u in B["unsupported"]]
    assert len(ids) == len(set(ids)), "claim and unsupported ids collide"
    # page-own ids never collide with claim ids (they use the rs- prefix)
    page_ids = set(re.findall(r'id="([^"]+)"', HTML))
    assert not (page_ids & set(ids)), page_ids & set(ids)
    assert all(i.startswith("rs-") for i in page_ids), page_ids
    # the row is a <details> whose id is the claim id, and the unsupported card carries its id too
    assert re.search(r"""<details class="rs-claim[^']*' \+ esc\(c\.basis\) \+ '" id="' \+ esc\(c\.id\) \+ '\"""", JS)
    assert re.search(r"""class="rs-unsup" id="' \+ esc\(u\.id\)""", JS)


def test_deep_link_opens_the_row_on_load_and_on_hashchange():
    assert "location.hash" in JS
    assert 'addEventListener("hashchange", openHash)' in JS
    assert re.search(r"el\.open = true", JS)


def test_basis_chips_carry_the_word_and_a_non_colour_cue():
    # the chip text is the bundle's label, never colour alone
    assert "D.basis_labels" in JS
    for b in ("published", "simulation", "assumption"):
        assert f".rs-chip--{b}" in CSS
    assert re.search(r"\.rs-chip--assumption\{[^}]*dashed", CSS), "assumption chip needs a non-colour cue"


def test_every_bundle_section_is_rendered():
    for key in ("counts", "basis_labels", "waiting_split", "unsupported", "sources", "themes", "framing"):
        assert f"D.{key}" in JS, key
    for f in ("fi_matched_pct", "fi_assumed_pct", "no_matched_pct", "by_basis_share", "owners",
              "used_in_register", "access", "strength", "shown_on", "run", "inputs", "where", "reason", "url"):
        assert f in JS, f


def test_access_levels_are_never_upgraded():
    """Only full_text reads as 'Full text'; abstract and secondary say so."""
    m = re.search(r"var ACCESS = \{(.*?)\};", JS, re.S)
    assert m
    acc = dict(re.findall(r'(\w+): "([^"]+)"', m.group(1)))
    assert set(acc) == {"full_text", "abstract", "secondary"}
    assert "full" not in acc["abstract"].lower() and "full" not in acc["secondary"].lower()
    assert {s["access"] for s in B["sources"]} <= set(acc)


def test_wording_traps():
    for text in (HTML, JS):
        assert not re.search(r"clinician[\s-]*validated", text, re.I)
        assert not re.search(r"\bobserved\b[^.]{0,40}\b80\b", text)
    # a simulation result is never called evidence on this page's own text
    assert "not evidence" in HTML


def test_external_links_open_in_a_new_tab():
    assert 'target="_blank" rel="noopener noreferrer"' in JS
