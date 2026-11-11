// Renders docs/images/it-hero.svg to it-hero.webp (1600x900) and it-hero-small.webp with the pre-installed Playwright.
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
(async () => {
  const img = path.join(__dirname, '..', '..', 'docs', 'images');
  const svg = fs.readFileSync(path.join(img, 'it-hero.svg'), 'utf8');
  const fonts = path.join(__dirname, '..', '..', 'docs', 'fonts', 'fonts.css');
  const browser = await chromium.launch();
  for (const [w, name] of [[1600, 'it-hero.webp']]) {
    const page = await browser.newPage({ viewport: { width: w, height: w * 9 / 16 }, deviceScaleFactor: 1 });
    await page.goto('file://' + fonts.replace('fonts.css', ''));
    await page.setContent(`<!doctype html><html><head><link rel="stylesheet" href="file://${fonts}"></head>` +
      `<body style="margin:0;background:#000">${svg.replace('width="1600" height="900"', `width="${w}" height="${w * 9 / 16}"`)}</body></html>`);
    await page.evaluate(() => document.fonts.ready);
    const png = await page.screenshot({ type: 'png', clip: { x: 0, y: 0, width: w, height: w * 9 / 16 } });
    fs.writeFileSync(path.join(__dirname, name + '.png'), png);
    await page.close();
  }
  await browser.close();
})();
