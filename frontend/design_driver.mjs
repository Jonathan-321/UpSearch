import { chromium } from 'playwright';
const b = await chromium.launch({ headless: true });
const p = await b.newPage();
await p.setViewportSize({ width: 1440, height: 900 });
await p.goto('http://localhost:5180/', { waitUntil: 'networkidle' });
await p.waitForTimeout(2500);
await p.screenshot({ path: 'design_01_main.png' });
console.log('01: main OS view');

// Click Together to show packet
const row = p.locator('div').filter({ hasText: /^Together/ }).first();
if (await row.isVisible()) {
  await row.click();
  await p.waitForTimeout(1500);
}
await p.screenshot({ path: 'design_02_packet.png' });
console.log('02: packet selected');

// Click Technical Note tab
const noteBtn = p.locator('button:has-text("Technical Note")').first();
if (await noteBtn.isVisible()) { await noteBtn.click(); await p.waitForTimeout(400); }
await p.screenshot({ path: 'design_03_note.png' });
console.log('03: note tab');

// Drafts tab
const draftsBtn = p.locator('button:has-text("Drafts")').first();
if (await draftsBtn.isVisible()) { await draftsBtn.click(); await p.waitForTimeout(400); }
await p.screenshot({ path: 'design_04_drafts.png' });
console.log('04: drafts tab');

// Scroll to approval queue
await p.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
await p.waitForTimeout(600);
await p.screenshot({ path: 'design_05_approval.png' });
console.log('05: approval queue');

// Toggle Quick Search
await p.click('button:has-text("Quick Search")');
await p.waitForTimeout(800);
await p.screenshot({ path: 'design_06_search.png' });
console.log('06: quick search mode');

await b.close();
console.log('DONE');
