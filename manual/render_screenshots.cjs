// Render each chart_outputs HTML file to a PNG screenshot using Playwright + Chromium.
// Output: manual/screenshots/<name>.png
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const SRC = path.join(ROOT, 'chart_outputs');
const OUT = path.join(ROOT, 'manual', 'screenshots');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const files = fs.readdirSync(SRC)
    .filter(f => f.endsWith('.html') && f !== 'report.html')
    .sort();

  console.log(`Rendering ${files.length} files...`);
  for (const f of files) {
    const page = await browser.newPage({ viewport: { width: 1280, height: 760 } });
    const url = 'file://' + path.join(SRC, f).replace(/\\/g, '/');
    try {
      await page.goto(url, { waitUntil: 'load', timeout: 30000 });
      // Give the CDN Plotly lib a moment to load + render the chart.
      await page.waitForTimeout(2500);
      const outName = f.replace(/\.html$/, '.png');
      await page.screenshot({ path: path.join(OUT, outName), fullPage: false });
      console.log('  ok  ' + outName);
    } catch (e) {
      console.log('  FAIL ' + f + ' :: ' + e.message);
    }
    await page.close();
  }
  await browser.close();
  console.log('Done.');
})();
