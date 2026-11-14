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
const slug = u => u.replace(/\.html/, "").replace(/[^A-Za-z0-9]+/g, "_").replace(/^_|_$/g, "") || "page";

(async () => {
  const browser = await puppeteer.launch({
    executablePath: chrome, headless: true,
    args: ["--no-sandbox", "--hide-scrollbars", "--allow-file-access-from-files", "--host-resolver-rules=MAP * ~NOTFOUND"],
  });
  const lines = [];
  let errors = 0;
  for (const u of urls) {
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
        await page.screenshot({path: path.join(outDir, `${slug(u)}_${w}x${h}.png`)});
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
