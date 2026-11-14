"""The Evidence page (demo/evidence.html, UI lane L4): static checks of the page, its script, and the additive
`evidence` field of demo/data/start_bundle.js against the review files it is read from.

Numbers are bound at load time by demo/evidence.js; here the static page is checked, and every bundle value the
page shows is compared with its source in docs/review_checks/ (the way test_demo_start.py checks the optimiser band).
"""
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "demo"
PAGE = DEMO / "evidence.html"
JS = DEMO / "evidence.js"
CSS = DEMO / "evidence.css"
RC = ROOT / "docs" / "review_checks"


class P(HTMLParser):
    """Collects links, assets, visible text (outside <script>, <code>, <pre class=cmd>, .cmd) and the nav."""

    def __init__(self):
        super().__init__()
        self.links, self.assets, self.text, self.navs = [], [], [], []
        self._skip = 0
        self._stack = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = (a.get("class") or "").split()
        if tag == "a" and a.get("href"):
            self.links.append(a["href"])
        if tag == "script" and a.get("src"):
            self.assets.append(a["src"])
        if tag == "link" and a.get("href"):
            self.assets.append(a["href"])
        if tag == "nav":
            self.navs.append(a)
        hidden = tag in ("script", "style", "code") or "cmd" in cls
        self._stack.append(hidden)
        if hidden:
            self._skip += 1

    def handle_endtag(self, tag):
        if self._stack and self._stack.pop():
            self._skip -= 1

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_data(self, d):
        if not self._skip:
            self.text.append(d)


VOID = {"meta", "link", "br", "img", "input", "hr", "source", "circle", "line"}


def parsed():
    p = P()
    html = PAGE.read_text(encoding="utf-8")
    # void elements have no end tag: close them so the hidden-stack stays balanced
    html = re.sub(r"<(%s)\b([^>]*?)/?>" % "|".join(VOID), r"<\1\2></\1>", html)
    p.feed(html)
    return p


def bundle():
    t = (DEMO / "data" / "start_bundle.js").read_text(encoding="utf-8")
    return json.loads(re.match(r"window\.START_DATA = (.*);\s*$", t, re.S).group(1))


def rc(name):
    return json.loads((RC / name).read_text(encoding="utf-8"))


# ---------- the page ----------

def test_links_and_assets_exist_and_are_local():
    p = parsed()
    for ref in p.links + p.assets:
        if ref.startswith("#"):
            continue
        assert not re.match(r"https?://", ref) or ref in p.links, f"remote asset: {ref}"
        path = urlsplit(ref).path
        assert path and (DEMO / path).resolve().exists(), f"missing target: {ref}"
    for ref in p.assets:
        assert not re.match(r"(https?:)?//", ref), f"asset from the network: {ref}"


def test_contract_load_order_and_nav():
    p = parsed()
    assert p.assets[:2] == ["theme.css", "evidence.css"]
    scripts = [a for a in p.assets if a.endswith(".js")]
    assert scripts == ["data/start_bundle.js", "data/research_bundle.js", "site.js", "evidence.js"]
    assert any(n.get("class") == "site-nav" and n.get("data-page") == "evidence" for n in p.navs)
    html = PAGE.read_text(encoding="utf-8")
    for cls in ("page-top", "page-title", "lede", "figure", "caption", "details", "details-rule", "finding",
                "footer-strip", "btn--primary"):
        assert f'class="{cls}' in html or f" {cls}" in html, cls
    assert html.count("btn--primary") == 1, "one primary action per view"


def test_no_number_typed_into_page_text():
    text = " ".join(parsed().text)
    assert not re.search(r"\d", text), re.findall(r".{20}\d.{20}", text)


def test_details_rule_comes_after_the_figure_and_caveats_sit_below_it():
    html = PAGE.read_text(encoding="utf-8")
    rule = html.index('class="details-rule"')
    assert html.index('id="ev-chart"') < rule < html.index('id="ev-multiples"') < html.index('id="ev-limits"')


def test_script_has_no_hand_typed_results():
    js = JS.read_text(encoding="utf-8")
    code = re.sub(r"^\s*//.*$", "", re.sub(r"/\*.*?\*/", "", js, flags=re.S), flags=re.M)
    code = re.sub(r'"(?:[^"\\]|\\.)*"', '""', code)
    nums = set(re.findall(r"(?<![\w.$#])\d+(?:\.\d+)?(?![\w])", code))
    assert nums <= {"0", "1", "2", "10", "100"}, nums


def test_css_uses_tokens_not_colour_literals():
    css = re.sub(r"/\*.*?\*/", "", CSS.read_text(encoding="utf-8"), flags=re.S)
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b|rgba?\(|hsla?\(", css)
    assert ":root" not in css


def test_wording_traps_absent():
    text = (PAGE.read_text(encoding="utf-8") + JS.read_text(encoding="utf-8")).lower()
    for bad in ("matches", "predicted exactly", "78 to 86", "78–86", "beats the authors", "beat the authors",
                "improves on the authors", "clinician-validated", "clinically validated", "ahead in", "optimiser is ahead"):
        assert bad not in text, bad


def test_claim_links_name_real_research_claims():
    """D69: the labels link research.html#<claim id>; every id used must exist in the research register."""
    js = JS.read_text(encoding="utf-8")
    ids = set(re.findall(r'claimLink\("([a-z0-9-]+)"', js)) | set(re.findall(r'"((?:pub|sim|as|in)-[a-z0-9-]+)"', js))
    t = (DEMO / "data" / "research_bundle.js").read_text(encoding="utf-8")
    reg = json.loads(t[t.index("=") + 1:].rstrip().rstrip(";"))
    known = {c["id"] for c in reg["claims"]}
    assert ids and ids <= known, ids - known


# ---------- the bundle field ----------

def test_evidence_rows_match_the_review_files():
    E = bundle()["evidence"]
    summ, best, val = rc("norway_opt_summary.json"), rc("norway_opt_bestfit.json"), json.loads(
        (ROOT / "docs/validation_results.json").read_text())
    assert E["n_settings"] == summ["n_settings"] == 184
    assert E["target_days"] == 42
    rows = {r["key"]: r for r in E["rows"]}
    assert list(rows) == ["observed", "faster_pet", "authors", "optimiser_no_equipment"]
    for key, rk, pk in (("observed", "observed", "observed"), ("faster_pet", "faster_pet", "faster_pet"),
                        ("authors", "optimal", "optimal"), ("optimiser_no_equipment", "full_nofast", None)):
        r = rows[key]
        assert r["best_fit"] == best["shipped_best_fit"][rk]["share_within_target"]
        assert abs(r["best_fit"] * 100 - summ["best_fit_shipped_percent"][rk]) < 0.05
        for q in ("min", "median", "max"):
            assert abs(r["band"][q] - summ["bands_percent"][rk][q] / 100) < 1e-9
        if pk:
            assert r["published"] == val["published"][pk]["share_within_target"]
        else:
            assert r["published"] is None
    # numbers sheet B1: about 67% at the best fit, 48 to 77% across the settings
    o = rows["optimiser_no_equipment"]
    assert round(o["best_fit"] * 100) == 67 and round(o["band"]["min"] * 100) == 48 and round(o["band"]["max"] * 100) == 77


def test_evidence_robustness_fields_match_the_review_files():
    E = bundle()["evidence"]
    rank, ext, loo, noise, mech, struct, summ = (rc("norway_ranking.json"), rc("norway_grid_extension.json"),
                                                 rc("norway_leave_one_out.json"), rc("norway_noise.json"),
                                                 rc("norway_mechanisms.json"), rc("norway_opt_structure.json"),
                                                 rc("norway_opt_summary.json"))
    assert E["ranking"]["holds_in"] == rank["optimal>faster_pet>observed_in"] == E["ranking"]["settings"]
    assert E["ranking"]["holds_at_grid_points"] == rank["ranking_holds_at_grid_points"]
    assert E["grid"]["first_accepted"] == ext["accepted_original_subset"]
    assert E["grid"]["extended_accepted"] == ext["accepted_extended"]
    assert abs(E["grid"]["extended_authors"]["min"] - ext["pred_extended"]["optimal"]["min"]) < 1e-9
    assert E["grid"]["authors_in_published_ci"] == loo["both_targets"]["optimal_in_published_ci_72_87"]
    on = {c["on"]: c for c in E["targets_as_one"]["calibrated_on"]}
    for k in ("both_targets", "share_only", "median_only"):
        assert on[k]["accepted"] == loo[k]["accepted"]
        assert on[k]["authors"]["median"] == loo[k]["pred"]["optimal"]["median"]
    t = noise["tolerance_as_shipped_0.04_2.5"]["pred_of_accepted_mean_across_resamples"]
    assert E["noise"]["authors"]["p5"] == t["optimal"]["p5"] and E["noise"]["scanner"]["p95"] == t["faster_pet"]["p95"]
    assert [r["rho"] for r in E["scanner_miss"]["runs"]] == [r["rho"] for r in mech["runs"] if r["scenario"] == "base"]
    assert E["scanner_miss"]["published"] == 0.48
    op = E["optimiser"]
    assert op["beats_observed"] == summ["counts"]["opt_nofast_beats_observed"]
    assert op["beats_scanner_alone"] == summ["counts"]["opt_nofast_beats_fasterpet"] == 128
    abl = {a["change"]: a for a in op["ablation"]}
    assert abl["b"]["loss_median_pts"] == summ["differences_pts"]["full_nofast - no_b_nofast"]["median"]
    assert abs(abl["b"]["loss_best_fit_pts"] - (summ["best_fit_shipped_percent"]["full_nofast"]
                                                - summ["best_fit_shipped_percent"]["no_b_nofast"])) < 1e-6
    assert max(abl.values(), key=lambda a: a["loss_median_pts"])["change"] == "b"
    st = E["structure"]
    assert st["stricter"]["in_published_ci"] == struct["grid_bands"]["optimal_petvisit_nogate"]["in_published_CI_72_87"] == 139
    assert st["shipped"]["in_published_ci"] == struct["grid_bands"]["optimal"]["in_published_CI_72_87"]
    assert abs(st["stricter"]["band"]["median"] - 0.79) < 1e-9


def test_evidence_field_carries_nothing_from_the_with_scanner_optimiser_run():
    """D68: the run from the faster-scanner pathway stays an internal check; no field of it reaches the page."""
    s = json.dumps(bundle()["evidence"])
    for bad in ("full_fast", "_fast\"", "no_d_fast", "opt_fast", "with_scanner", "optimiser_scanner"):
        assert bad not in s, bad


def test_existing_bundle_fields_are_unchanged_in_shape():
    d = bundle()
    assert d["format"] == "start-bundle/1"
    for k in ("validation", "norway_robustness", "encounter_results", "encounter_consistency", "norway", "ledger",
              "catalogue", "evidence"):
        assert k in d
