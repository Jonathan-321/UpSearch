import { chromium } from 'playwright';

const browser = await chromium.launch({ headless: false, slowMo: 200 });
const context = await browser.newContext();
const page = await context.newPage();
await page.setViewportSize({ width: 1280, height: 900 });

page.on('console', msg => { if (msg.type() === 'error') console.error('PAGE ERR:', msg.text()); });

await page.goto('http://localhost:5180/', { waitUntil: 'networkidle' });
await page.waitForTimeout(2000);
await page.screenshot({ path: 'ss_01_idle.png' });
console.log('01: idle loaded');

await page.fill('input[type=text]', 'LLM inference optimization');
await page.waitForTimeout(400);
await page.click('button[type=submit]');
await page.waitForTimeout(2000);
await page.screenshot({ path: 'ss_02_scouting.png' });
console.log('02: scouting (real API call in progress)');

console.log('Waiting for API results (up to 2 min)...');
await page.waitForSelector('text=opportunities ranked by fit', { timeout: 120000 });
await page.waitForTimeout(1000);
await page.screenshot({ path: 'ss_03_results.png' });
console.log('03: results + supervisor scores');

const leadBtn = page.locator('button:has-text("Use this lead")').first();
await leadBtn.scrollIntoViewIfNeeded();
await leadBtn.click();
await page.waitForTimeout(2000);
await page.screenshot({ path: 'ss_04_strategizing.png' });
console.log('04: strategist + writer running');

await page.waitForSelector('text=Outreach ready', { timeout: 120000 });
await page.waitForTimeout(1000);
await page.screenshot({ path: 'ss_05_draft.png' });
console.log('05: draft + strategy rendered');

await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
await page.waitForTimeout(800);
await page.screenshot({ path: 'ss_06_supervisor_wandb.png' });
console.log('06: supervisor panel + W&B tracker');

await browser.close();
console.log('ALL DONE');
