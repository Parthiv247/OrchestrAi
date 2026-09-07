import { chromium } from 'playwright'

const pages = [
  { path: '/',              name: '1-overview' },
  { path: '/pipelines',     name: '2-pipelines' },
  { path: '/approvals',     name: '3-approvals' },
  { path: '/optimizer',     name: '4-optimizer' },
  { path: '/dbt',           name: '5-dbt' },
  { path: '/analyst',       name: '6-analyst' },
  { path: '/observability', name: '7-observability' },
]

const BASE = 'http://localhost:3001'
const OUT = '/Users/parthivpatel/OrchetraAI/screenshots'

const browser = await chromium.launch()
const context = await browser.newContext({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 2,
})
const page = await context.newPage()

for (const p of pages) {
  try {
    await page.goto(BASE + p.path, { waitUntil: 'networkidle', timeout: 30000 })
  } catch {
    // networkidle can hang on polling apps — fall back to domcontentloaded
    await page.goto(BASE + p.path, { waitUntil: 'domcontentloaded', timeout: 30000 })
  }
  // give charts / framer-motion / react-query a moment to settle
  await page.waitForTimeout(3500)
  const file = `${OUT}/${p.name}.png`
  await page.screenshot({ path: file, fullPage: true })
  console.log(`captured ${p.path} -> ${file}`)
}

await browser.close()
console.log('done')
