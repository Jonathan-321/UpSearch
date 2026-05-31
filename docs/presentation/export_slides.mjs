import { createRequire } from 'node:module'
import path from 'node:path'
import { pathToFileURL } from 'node:url'

const require = createRequire(import.meta.url)
const { chromium } = require('../../frontend/node_modules/playwright')
const browser = await chromium.launch({ headless: true })
const page = await browser.newPage({ viewport: { width: 1600, height: 900 } })
const deck = pathToFileURL(path.resolve('upsearch-pitch-deck.html')).href

await page.goto(deck, { waitUntil: 'networkidle' })
const slides = page.locator('.slide')
for (let index = 0; index < await slides.count(); index += 1) {
  await slides.nth(index).screenshot({
    path: `slide-${String(index + 1).padStart(2, '0')}.png`,
  })
}
await page.pdf({
  path: 'upsearch-pitch-deck.pdf',
  printBackground: true,
  preferCSSPageSize: true,
})

await browser.close()
