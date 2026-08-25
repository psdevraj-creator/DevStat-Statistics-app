const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch({ headless: true, executablePath: 'C:\\Users\\dell 7390\\AppData\\Local\\ms-playwright\\chromium-1234\\chrome-win64\\chrome.exe' });
  const p = await b.newPage();
  const url = 'file:///C:/Users/dell 7390/OneDrive/Desktop/Educational webpage project/FRCR 1 page/deployment/medstat/learn-as-you-do.html';
  const errs = [];
  p.on('console', m => { if (m.type()==='error') errs.push(m.text()) });
  p.on('pageerror', e => errs.push('PAGEERR: '+e.message));
  await p.goto(url);
  const before = await p.evaluate(() => document.querySelector('.ex details').open);
  // click the actual summary
  await p.evaluate(() => document.querySelector('.ex summary').click());
  const after = await p.evaluate(() => document.querySelector('.ex details').open);
  const firstSummaryText = await p.evaluate(() => document.querySelector('.ex summary')?.textContent?.trim());
  const detailCount = await p.evaluate(() => document.querySelectorAll('.ex details').length);
  console.log('detailCount', detailCount, '| first summary text:', JSON.stringify(firstSummaryText));
  console.log('open before:', before, '| after click:', after);
  console.log('console errors:', errs);
  await b.close();
})().catch(e => { console.error('ERR', e.message); process.exit(1); });
