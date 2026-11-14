// Scripted browser pass: opens a template, waits for its first run, takes a screenshot of each layer, edits one
// probability, saves a version and runs it, and screenshots each screen into web/shots/ (git-ignored).
//   npm run build && npm run shots -- http://localhost:8000/ [norway_check|finland_lung]
// Needs Chrome (CHROME_PATH, default /usr/bin/google-chrome) and a running service (or add ?mock=1 for demo data).
import puppeteer from 'puppeteer-core'
import { mkdirSync } from 'node:fs'

const url = process.argv[2] ?? 'http://localhost:8000/'
const template = process.argv[3] ?? 'norway_check'
const out = new URL('../shots/', import.meta.url).pathname
mkdirSync(out, { recursive: true })
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

const browser = await puppeteer.launch({ executablePath: process.env.CHROME_PATH ?? '/usr/bin/google-chrome', headless: 'new', args: ['--no-sandbox'] })
const page = await browser.newPage()
await page.setViewport({ width: 1920, height: 1080 })
const problems = []
page.on('pageerror', (e) => problems.push(e.message))
page.on('console', (m) => { if (m.type() === 'error') problems.push(m.text()) })
const shot = async (name) => { await page.screenshot({ path: `${out}${name}.png` }); console.log('saved', name) }
const clickText = (sel, text) => page.evaluate((sel, text) => { const b = [...document.querySelectorAll(sel)].find((x) => x.textContent.trim().startsWith(text)); if (!b) throw new Error(`no ${sel} "${text}"`); b.click() }, sel, text)

await page.goto(url, { waitUntil: 'networkidle0' })
await shot('01-projects')
await page.click(`[data-testid="template-${template}"] button`)
await page.waitForSelector('.react-flow__node')
await sleep(1500)
await shot('02-opened-with-run-starting')
await page.waitForSelector('[data-testid="playback-bar"]', { timeout: 120000 })
await sleep(8000)
for (const l of ['Flow', 'Time', 'Queues', 'Decisions', 'Structure']) {
  await clickText('.toolbar .tab', l)
  await sleep(700)
  await shot(`03-layer-${l.toLowerCase()}`)
}
await clickText('.toolbar .tab', 'Flow')
await clickText('.side .tab', 'Where time is lost')
await sleep(400)
await shot('04-where-time-is-lost')
// decisions: change the first option of the first decision by one point, rebalance the second
await clickText('.subbar .tab', 'Decisions')
await page.waitForSelector('[data-testid="decisions-table"]')
const card = (await page.$$('[data-testid^="decision-"]'))[0]
const inputs = await card.$$('input.num-in')
const a = Number(await inputs[0].evaluate((e) => e.value)), b = Number(await inputs[1].evaluate((e) => e.value))
await inputs[0].evaluate((e) => e.select()); await inputs[0].type(String(Math.round((a - 10) * 10) / 10))
await inputs[1].evaluate((e) => e.select()); await inputs[1].type(String(Math.round((b + 10) * 10) / 10))
await sleep(300)
await shot('05-decisions-edited')
await page.click('[data-testid="save-version"]')
await sleep(1500)
await shot('06-saved-new-version')
await clickText('.subbar .tab', 'Flowchart')
await sleep(500)
await page.evaluate(() => { const b = [...document.querySelectorAll('.side .tab')].find((x) => x.textContent.trim() === 'Run'); if (b) b.click() })
await page.waitForSelector('[data-testid="start-run"]')
await page.evaluate(() => { const e = document.querySelector('#run-n'); e.focus(); e.select() })
await page.keyboard.type(template === 'norway_check' ? '500' : '3000')
await page.click('[data-testid="start-run"]')
await sleep(2500)
await shot('07-second-run-started')
await page.waitForFunction(() => document.querySelectorAll('[data-testid="run-history"] .runrow').length >= 2 && !document.querySelector('[data-testid="run-progress"]'), { timeout: 180000 })
await sleep(6000)
await shot('08-second-run-finished')
await browser.close()
console.log(problems.length ? `console problems:\n${problems.join('\n')}` : 'no console errors')
