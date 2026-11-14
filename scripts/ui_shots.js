// Screenshots and console-error capture for the demo pages. Called by scripts/ui_shots.sh; not meant to run alone.
// Usage: node scripts/ui_shots.js <puppeteer-core dir> <chrome> <out-dir> <demo-dir> <url>...
// Each url is relative to demo/ (e.g. "flow.html?s=finland&compare"). Writes <slug>_<w>x<h>.png and console.txt.
// Exit code 1 if any page logs a console error, throws, or fails to load a local file.
"use strict";
const path = require("path");
const fs = require("fs");
const [, , ppDir, chrome, outDir, demoDir, ...urls] = process.argv;
const puppeteer = require(ppDir);
const SIZES = [[1440, 900], [1920, 1080]];
// File name: page and query as before ("flow.html?s=finland" -> flow_s_finland); a hash adds "_h_<hash>"
// ("jev.html#gp_visit" -> jev_h_gp_visit), so hash URLs of one page get their own files. Repeats get _2, _3 ...
const clean = s => s.replace(/[^A-Za-z0-9]+/g, "_").replace(/^_|_$/g, "");
const seen = {};
const slug = u => {
  const i = u.indexOf("#"), base = i < 0 ? u : u.slice(0, i), hash = i < 0 ? "" : u.slice(i + 1);
  let s = clean(base.replace(/\.html/, "")) || "page";
  if (hash) s += "_h_" + (clean(hash) || "top");
  seen[s] = (seen[s] || 0) + 1;
  return seen[s] > 1 ? `${s}_${seen[s]}` : s;
};

(async () => {
  const browser = await puppeteer.launch({
    executablePath: chrome, headless: true,
    args: ["--no-sandbox", "--hide-scrollbars", "--allow-file-access-from-files", "--host-resolver-rules=MAP * ~NOTFOUND"],
  });
  const lines = [];
  let errors = 0;
  for (const u of urls) {
    const name = slug(u);
    for (const [w, h] of SIZES) {
      const page = await browser.newPage();
      await page.setViewport({width: w, height: h});
      const tag = `${u} @${w}x${h}`;
      page.on("console", m => { if (m.type() === "error") { errors++; lines.push(`ERROR ${tag}: console: ${m.text()}`); } });
      page.on("pageerror", e => { errors++; lines.push(`ERROR ${tag}: pageerror: ${e.message}`); });
      page.on("requestfailed", r => { errors++; lines.push(`ERROR ${tag}: request failed: ${r.url()} ${r.failure() && r.failure().errorText}`); });
      const url = "file://" + path.resolve(demoDir, u.split(/[?#]/)[0]) + u.slice(u.split(/[?#]/)[0].length);
      try {
        await page.goto(url, {waitUntil: "load", timeout: 20000});
        await new Promise(r => setTimeout(r, 1500));
        await page.screenshot({path: path.join(outDir, `${name}_${w}x${h}.png`)});
        lines.push(`ok    ${tag}`);
      } catch (e) {
        errors++;
        lines.push(`ERROR ${tag}: ${e.message}`);
      }
      await page.close();
    }
  }
  await browser.close();
  fs.writeFileSync(path.join(outDir, "console.txt"), lines.join("\n") + "\n");
  console.log(lines.join("\n"));
  process.exit(errors ? 1 : 0);
})().catch(e => { console.error(e); process.exit(2); });
