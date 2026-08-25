// Generate DevStat_Manual.pdf from DevStat_Manual.html using Playwright + Chromium.
const { chromium } = require('playwright');
const path = require('path');

(async () => {
  const root = __dirname;
  const html = 'file:///' + path.join(root, 'DevStat_Manual.html').replace(/\\/g, '/');
  const out = path.join(root, 'DevStat_Manual.pdf');

  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1024, height: 800 } });

  await page.goto(html, { waitUntil: 'load', timeout: 30000 });
  // Let all local images finish loading.
  await page.waitForTimeout(1500);

  await page.pdf({
    path: out,
    format: 'A4',
    printBackground: true,
    margin: { top: '18mm', bottom: '18mm', left: '16mm', right: '16mm' },
  });

  console.log('PDF written: ' + out);
  await browser.close();
})().catch(e => { console.error('ERR', e.message); process.exit(1); });
