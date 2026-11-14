/* demo/site.js: shared nav, footer, theme switch and token reader for the offline demo site (UI revamp, lane L0).
 *
 * No build, no dependencies, works from file://. Load it after theme.css, page CSS and bundles, before page JS:
 *   <script src="site.js"></script>
 * On load it applies ?theme=night and fills <nav class="site-nav" data-page="..."> if the page has one, so a page
 * needs no JS of its own for the nav. Every function is safe on a page without the elements it looks for.
 *
 *   Site.nav(pageId)     fill nav.site-nav (or create one at the top of <body>) with the five pages; mark pageId
 *   Site.footer(text)    fill .footer-strip (default: the synthetic-patients sentence)
 *   Site.tokens()        resolved token values {paper, card, ..., carbon} as hex strings, for canvas/SVG code
 *   Site.theme()         "paper" or "night"
 *   Site.pages           [{id, href, label}] in nav order
 *
 * Owned by L0 / the integrator. Page lanes do not edit it; a page joins the nav only through Site.pages.
 */
(function () {
  "use strict";

  var PAGES = [
    {id: "overview", href: "start.html", label: "Overview"},
    {id: "simulator", href: "flow.html", label: "Simulator"},
    {id: "patients", href: "patients.html", label: "Patients"},
    {id: "evidence", href: "evidence.html", label: "Evidence"},
    {id: "model", href: "jev.html", label: "Decision model"}
  ];
  var BRAND = "Equal care pathways";
  var STAMP = "Synthetic patients";
  var FOOTER = "Synthetic patients only · not clinically reviewed · numbers are read from the data bundles when the page opens";
  var TOKENS = ["paper", "card", "inset", "ink", "ink-2", "ink-3", "faint", "line", "mustard", "mustard-ink",
    "mustard-tint", "brick", "brick-tint", "brown", "carbon"];

  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) { return {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]; });
  }

  function param(name) {
    try { return new URLSearchParams(window.location.search).get(name); } catch (e) { return null; }
  }

  // ?theme=night -> data-theme="night" on <html>; anything else -> paper (attribute removed)
  function applyTheme() {
    var root = document.documentElement;
    if (param("theme") === "night") root.setAttribute("data-theme", "night");
    else if (param("theme") === "paper") root.removeAttribute("data-theme");
    cache = null;
  }

  function theme() {
    return document.documentElement.getAttribute("data-theme") === "night" ? "night" : "paper";
  }

  // Carry ?theme=night across nav links so the fallback survives navigation.
  function withTheme(href) {
    return theme() === "night" ? href + "?theme=night" : href;
  }

  function nav(pageId) {
    var el = document.querySelector("nav.site-nav");
    if (!el) {
      if (!document.body) return null;
      el = document.createElement("nav");
      el.className = "site-nav";
      document.body.insertBefore(el, document.body.firstChild);
    }
    var id = pageId || el.getAttribute("data-page") || "";
    el.setAttribute("data-page", id);
    el.setAttribute("aria-label", "Site");
    var links = PAGES.map(function (p) {
      var cur = p.id === id ? ' aria-current="page"' : "";
      return '<li><a class="site-nav__link" href="' + esc(withTheme(p.href)) + '"' + cur + ">" + esc(p.label) + "</a></li>";
    }).join("");
    el.innerHTML = '<a class="site-nav__brand" href="' + esc(withTheme(PAGES[0].href)) + '">' + esc(BRAND) + "</a>" +
      '<ul class="site-nav__links">' + links + "</ul>" +
      '<span class="stamp">' + esc(STAMP) + "</span>";
    return el;
  }

  function footer(text) {
    var el = document.querySelector(".footer-strip");
    if (!el) return null;
    el.textContent = text == null ? FOOTER : String(text);
    return el;
  }

  // Resolve a CSS colour (any syntax, incl. var() chains) to #rrggbb via a probe element.
  function toHex(value, probe) {
    probe.style.color = "";
    probe.style.color = value;
    var c = getComputedStyle(probe).color || "";
    var m = c.match(/rgba?\(\s*(\d+)[,\s]+(\d+)[,\s]+(\d+)/);
    if (!m) return value.trim();
    return "#" + [m[1], m[2], m[3]].map(function (n) { return ("0" + Number(n).toString(16)).slice(-2); }).join("").toUpperCase();
  }

  var cache = null;
  // Cached per theme; call Site.tokens(true) to re-read.
  function tokens(fresh) {
    if (cache && !fresh && cache._theme === theme()) return cache;
    var out = {};
    var cs = getComputedStyle(document.documentElement);
    var probe = document.createElement("span");
    probe.style.display = "none";
    (document.body || document.documentElement).appendChild(probe);
    try {
      TOKENS.forEach(function (k) {
        var raw = cs.getPropertyValue("--" + k).trim();
        out[k] = raw ? toHex(raw, probe) : "";
      });
    } finally {
      probe.parentNode.removeChild(probe);
    }
    out.fontSans = cs.getPropertyValue("--font-sans").trim();
    out.fontMono = cs.getPropertyValue("--font-mono").trim();
    Object.defineProperty(out, "_theme", {value: theme(), enumerable: false});
    cache = out;
    return out;
  }

  function init() {
    if (document.querySelector("nav.site-nav")) nav();
    var f = document.querySelector(".footer-strip");
    if (f && !f.textContent.trim()) footer();
  }

  applyTheme();
  window.Site = {nav: nav, footer: footer, tokens: tokens, theme: theme, pages: PAGES.slice()};
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
