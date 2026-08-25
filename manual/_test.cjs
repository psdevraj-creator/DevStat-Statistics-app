const { chromium } = require('playwright');
const path = require('path');
(async () => {
  const b = await chromium.launch({ headless: true });
  const p = await b.newPage({ viewport: { width: 1280, height: 760 } });
  const url = 'file:///' + path.resolve('..','chart_outputs','01_histogram.html').replace(/\\/g,'/');
  await p.goto(url, { waitUntil: 'load', timeout: 30000 });
  await p.waitForTimeout(2500);
  const plots = await p.evaluate(() => typeof window.Plotly !== 'undefined');
  await p.screenshot({ path: 'screenshots/_test.png' });
  console.log('Plotly loaded:', plots, '| shot saved');
  await b.close();
})().catch(e => { console.error('ERR', e.message); process.exit(1); });
