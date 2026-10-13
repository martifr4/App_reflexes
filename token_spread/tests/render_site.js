// Renders site/index.html in headless Chromium (desktop light/dark, phone) and reports
// console errors, horizontal overflow and the page's own verification badge.
// Usage (from token_spread/): node tests/render_site.js [outdir]   -> screenshots in outdir
const path = require('path');
let chromium;
try { ({ chromium } = require('playwright')); } catch { ({ chromium } = require('/opt/node-tools/node_modules/playwright')); }
(async () => {
  const file = path.resolve(__dirname, '../site/index.html'), out = process.argv[2];
  const browser = await chromium.launch({ proxy: process.env.HTTPS_PROXY ? { server: process.env.HTTPS_PROXY } : undefined });
  let failed = false;
  for (const [name, vp, scheme] of [['desktop-light', { width: 1280, height: 900 }, 'light'], ['desktop-dark', { width: 1280, height: 900 }, 'dark'], ['phone', { width: 390, height: 844 }, 'light']]) {
    const page = await (await browser.newContext({ viewport: vp, colorScheme: scheme, ignoreHTTPSErrors: true })).newPage();
    const errs = [];
    page.on('pageerror', e => errs.push(e.message));
    page.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });
    await page.goto('file://' + file, { waitUntil: 'networkidle', timeout: 60000 }).catch(e => errs.push(e.message));
    await page.waitForTimeout(600);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    const verify = await page.evaluate(() => (document.getElementById('verify') || {}).textContent || '');
    const fonts = errs.filter(e => /fonts\.g/.test(e)); const real = errs.filter(e => !/fonts\.g/.test(e));
    console.log(`${name}: overflow ${overflow}px | ${verify.trim()} | errors: ${JSON.stringify(real)}`);
    if (overflow > 0 || real.length || !/verified/.test(verify)) failed = true;
    if (out) await page.screenshot({ path: path.join(out, `${name}.png`), fullPage: true });
  }
  await browser.close();
  process.exit(failed ? 1 : 0);
})();
