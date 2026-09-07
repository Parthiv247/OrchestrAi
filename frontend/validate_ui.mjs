import { chromium } from 'playwright'

const BASE = 'http://localhost:3001'

// Resolve a real pipeline id for the detail route
let pipelineId = ''
try {
  const r = await fetch('http://localhost:8000/api/pipelines')
  const d = await r.json()
  pipelineId = (d.pipelines && d.pipelines[0] && d.pipelines[0].id) || ''
} catch {}

const routes = [
  '/', '/pipelines', '/pipelines/new', '/analyst', '/optimizer', '/dbt',
  '/quality', '/observability', '/lineage', '/approvals', '/connectors',
  '/reports', '/settings', '/onboarding',
]
if (pipelineId) routes.push('/pipelines/' + pipelineId)

const IGNORE_URL = /favicon|_next\/static|hot-update|__nextjs|\.map(\?|$)/
// console noise we don't count as failures
const IGNORE_CONSOLE = /Download the React DevTools|Slow network|\[Fast Refresh\]|hydrat/i

const browser = await chromium.launch()
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } })

function attach(page, bucket) {
  page.on('console', m => {
    if (m.type() === 'error' && !IGNORE_CONSOLE.test(m.text()))
      bucket.console.push(m.text().slice(0, 160))
  })
  page.on('pageerror', e => bucket.pageerror.push((e.message || String(e)).slice(0, 160)))
  page.on('requestfailed', r => {
    const err = r.failure()?.errorText || 'failed'
    // ERR_ABORTED = request cancelled by our re-navigation between button clicks, not a real failure
    if (err.includes('ERR_ABORTED')) return
    if (!IGNORE_URL.test(r.url())) bucket.netfail.push(`${err} ${r.url().slice(0,90)}`)
  })
  page.on('response', r => {
    const s = r.status()
    if (s >= 400 && !IGNORE_URL.test(r.url())) bucket.http.push(`${s} ${r.url().replace('http://localhost:8000','').slice(0,80)}`)
  })
}

const report = []

for (const route of routes) {
  const page = await ctx.newPage()
  const bucket = { console: [], pageerror: [], netfail: [], http: [] }
  attach(page, bucket)
  let loadOk = true
  try {
    const resp = await page.goto(BASE + route, { waitUntil: 'domcontentloaded', timeout: 25000 })
    if (resp && resp.status() >= 400) loadOk = false
  } catch (e) { loadOk = false; bucket.pageerror.push('GOTO: ' + (e.message||'').slice(0,120)) }
  await page.waitForTimeout(1200)

  // count interactive elements
  const buttons = page.locator('button:visible')
  const nBtn = await buttons.count().catch(() => 0)
  const links = await page.locator('a[href]:visible').count().catch(() => 0)

  // click each button in isolation (re-nav between clicks to reset state)
  const clickErrors = []
  for (let i = 0; i < nBtn; i++) {
    try {
      await page.goto(BASE + route, { waitUntil: 'domcontentloaded', timeout: 20000 })
      await page.waitForTimeout(250)
      const b = page.locator('button:visible').nth(i)
      const label = (await b.innerText().catch(() => '')).replace(/\s+/g, ' ').trim().slice(0, 24) || `btn#${i}`
      const before = bucket.console.length + bucket.pageerror.length
      await b.click({ timeout: 4000, trial: false }).catch(err => {
        // not clickable / detached is not a JS error — ignore
      })
      await page.waitForTimeout(600)
      const after = bucket.console.length + bucket.pageerror.length
      if (after > before) clickErrors.push(`"${label}" -> ${(bucket.pageerror.concat(bucket.console)).slice(before).join(' | ').slice(0,120)}`)
    } catch (e) { /* ignore per-button nav races */ }
  }

  report.push({ route, loadOk, nBtn, links, ...bucket, clickErrors })
  await page.close()
}

await browser.close()

// ── Print report ────────────────────────────────────────────────────────────
let problems = 0
for (const r of report) {
  const issues = []
  if (!r.loadOk) issues.push('PAGE LOAD FAILED')
  if (r.pageerror.length) issues.push(`${r.pageerror.length} JS error(s)`)
  if (r.console.length) issues.push(`${r.console.length} console error(s)`)
  if (r.http.length) issues.push(`${r.http.length} HTTP 4xx/5xx`)
  if (r.netfail.length) issues.push(`${r.netfail.length} net fail`)
  if (r.clickErrors.length) issues.push(`${r.clickErrors.length} button error(s)`)
  const status = issues.length ? '❌' : '✅'
  if (issues.length) problems++
  console.log(`${status} ${r.route.padEnd(22)} btns=${r.nBtn} links=${r.links} ${issues.join(', ')}`)
  for (const e of r.pageerror) console.log(`      JS:   ${e}`)
  for (const e of r.console)   console.log(`      CON:  ${e}`)
  for (const e of [...new Set(r.http)]) console.log(`      HTTP: ${e}`)
  for (const e of r.netfail)   console.log(`      NET:  ${e}`)
  for (const e of r.clickErrors) console.log(`      BTN:  ${e}`)
}
console.log(`\n${problems === 0 ? '✅ ALL CLEAN' : '❌ ' + problems + ' page(s) with issues'} — ${report.length} routes checked`)
