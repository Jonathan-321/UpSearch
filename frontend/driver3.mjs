import { chromium } from 'playwright';

const browser = await chromium.launch({ headless: false, slowMo: 250 });
const page = await browser.newPage();
await page.setViewportSize({ width: 1440, height: 900 });

await page.goto('http://localhost:5180/', { waitUntil: 'networkidle' });
await page.waitForTimeout(1500);
await page.screenshot({ path: 'ss_os_01_idle.png' });
console.log('01: OS idle — CRM should show 6 companies');

// Click Anyscale from quick-add
await page.click('button:has-text("Anyscale")');
await page.waitForTimeout(300);
await page.screenshot({ path: 'ss_os_02_typed.png' });
console.log('02: company typed');

// Click Build Packet
await page.click('button:has-text("Build Packet")');
await page.waitForTimeout(2000);
await page.screenshot({ path: 'ss_os_03_running.png' });
console.log('03: pipeline running');

// Wait for profile + company stages to complete
await page.waitForTimeout(8000);
await page.screenshot({ path: 'ss_os_04_midway.png' });
console.log('04: mid-pipeline');

// Wait for full completion (up to 3 min)
console.log('Waiting for pipeline to complete...');
await page.waitForSelector('text=QA', { timeout: 180000 });
// Give it extra time after QA shows
await page.waitForTimeout(15000);
await page.screenshot({ path: 'ss_os_05_complete.png' });
console.log('05: pipeline complete');

// Click Together in the CRM table to see its packet
const togetherRow = page.locator('tr').filter({ hasText: 'Together' }).first();
if (await togetherRow.isVisible()) {
  await togetherRow.click();
  await page.waitForTimeout(1500);
  await page.screenshot({ path: 'ss_os_06_together_packet.png' });
  console.log('06: Together packet view');
}

// Switch to Technical Note tab
const noteTab = page.locator('button:has-text("Technical Note")').first();
if (await noteTab.isVisible()) {
  await noteTab.click();
  await page.waitForTimeout(500);
  await page.screenshot({ path: 'ss_os_07_note.png' });
  console.log('07: technical note tab');
}

// Switch to Drafts tab
const draftsTab = page.locator('button:has-text("Drafts")').first();
if (await draftsTab.isVisible()) {
  await draftsTab.click();
  await page.waitForTimeout(500);
  await page.screenshot({ path: 'ss_os_08_drafts.png' });
  console.log('08: drafts tab');
}

// Scroll down to approval queue
await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
await page.waitForTimeout(600);
await page.screenshot({ path: 'ss_os_09_approval.png' });
console.log('09: approval queue');

await browser.close();
console.log('ALL DONE');
