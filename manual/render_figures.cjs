// Screenshot every HTML file in manual/fig_html into manual/screenshots as PNG.
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const SRC = path.join(__dirname, 'fig_html');
const OUT = path.join(__dirname, 'screenshots');

(async () => {
  const files = fs.readdirSync(SRC).filter(f => f.endsWith('.html')).sort();
  const browser = await chromium.launch({ headless: true });
  console.log(`Rendering ${files.length} figures...`);
  for (const f of files) {
    const page = await browser.newPage({ viewport: { width: 1280, height: 760 } });
    const url = 'file:///' + path.join(SRC, f).replace(/\\/g, '/');
    try {
      await page.goto(url, { waitUntil: 'load', timeout: 30000 });
      await page.waitForTimeout(2500);
      const out = f.replace(/\.html$/, '.png');
      await page.screenshot({ path: path.join(OUT, out), fullPage: false });
      console.log('  ok  ' + out);
    } catch (e) {
      console.log('  FAIL ' + f + ' :: ' + e.message);
    }
    await page.close();
  }
  await browser.close();
  console.log('Done.');
})();
