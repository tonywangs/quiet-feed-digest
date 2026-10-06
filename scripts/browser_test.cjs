/* Local-only Chromium checks. Playwright is a development dependency, not runtime. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const {createRequire} = require('node:module');
const dependencyRoot = process.env.QUIET_FEED_BROWSER_MODULES;
const load = dependencyRoot ? createRequire(path.join(dependencyRoot, 'package.json')) : require;
const {chromium} = load('playwright');

async function main() {
  const [samplePath, hostilePath, boundedPath, evidencePath] = process.argv.slice(2);
  assert(evidencePath, 'Usage: browser_test.cjs SAMPLE HOSTILE BOUNDED EVIDENCE');
  const browser = await chromium.launch({headless: true, args: ['--no-sandbox']});
  try {
    const context = await browser.newContext({offline: true, serviceWorkers: 'block'});
    const requests = [], errors = [];
    const allowedFiles = new Set([samplePath, hostilePath, boundedPath].map(p => pathToFileURL(path.resolve(p)).href));
    await context.route('**/*', async route => {
      if (allowedFiles.has(route.request().url()) && route.request().isNavigationRequest()) {
        await route.continue();
        return;
      }
      if (/^https?:/.test(route.request().url())) requests.push(route.request().url());
      await route.abort();
    });
    const page = await context.newPage();
    page.on('pageerror', error => errors.push(error.message));
    page.on('request', request => {
      if (/^https?:/.test(request.url())) requests.push(request.url());
    });
    await page.goto(pathToFileURL(path.resolve(samplePath)).href);
    await page.waitForFunction(() => document.querySelector('#visible').textContent === '3 of 3 selected items visible');
    assert.equal(await page.locator('article').count(), 3);
    await page.locator('#source').selectOption('workshop');
    assert.equal(await page.locator('article:visible').count(), 2);
    await page.locator('#status').selectOption('revised');
    assert.equal(await page.locator('article:visible').count(), 1);
    const summary = page.locator('article:visible summary').filter({hasText: 'Before revision:'});
    await summary.focus();
    await page.keyboard.press('Enter');
    assert.equal(await summary.evaluate(el => el.parentElement.open), true);
    assert.match(await page.locator('article:visible .before').innerText(), /09:00/);
    assert.match(await page.locator('article:visible .excerpt').first().innerText(), /10:00/);
    await page.keyboard.press('Space');
    assert.equal(await summary.evaluate(el => el.parentElement.open), false);
    await page.locator('#source').focus();
    await page.keyboard.press('Tab');
    assert.equal(await page.evaluate(() => document.activeElement.id), 'status');
    const focus = await page.locator('#status').evaluate(el => ({
      style: getComputedStyle(el).outlineStyle, width: getComputedStyle(el).outlineWidth,
      visible: el.matches(':focus-visible')
    }));
    assert.equal(focus.visible, true);
    assert.equal(focus.style, 'solid');
    assert.equal(focus.width, '3px');
    await page.keyboard.press('Home');
    await page.keyboard.press('ArrowDown');
    await page.keyboard.press('Enter');
    assert.equal(await page.locator('#status').inputValue(), 'new');
    await page.locator('#source').selectOption('');
    await page.locator('#status').selectOption('');
    await page.setViewportSize({width: 320, height: 700});
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    await page.screenshot({path: path.join(path.dirname(evidencePath), 'narrow.png'), fullPage: true});
    const sampleElements = await page.locator('*').count();

    await page.goto(pathToFileURL(path.resolve(hostilePath)).href);
    await page.waitForFunction(() => document.querySelector('#visible').textContent.includes('of'));
    assert.equal(await page.locator('img, iframe, object, embed, svg, video, audio, base, form, link').count(), 0);
    assert.equal(await page.locator('script').count(), 1);
    assert.equal(await page.evaluate(() => window.PWNED), undefined);
    assert.match(await page.locator('article').first().innerText(), /<script>/);
    const urls = await page.locator('article a').evaluateAll(els => els.map(el => el.getAttribute('href')));
    assert(urls.every(url => /^https?:\/\//.test(url)));
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    const hostileElements = await page.locator('*').count();

    await page.goto(pathToFileURL(path.resolve(boundedPath)).href);
    await page.waitForFunction(() => document.querySelector('#visible').textContent === '200 of 200 selected items visible');
    assert.equal(await page.locator('article').count(), 200);
    assert.match(await page.locator('footer').innerText(), /50 comparable items omitted/);
    const boundedElements = await page.locator('*').count();
    assert(boundedElements < 11000, `DOM unexpectedly large: ${boundedElements}`);
    assert.deepEqual(errors, []);
    assert.deepEqual(requests, [], 'No automatic remote requests may be attempted');
    await context.close();
    const noScript = await browser.newContext({javaScriptEnabled: false, offline: true, serviceWorkers: 'block'});
    const plain = await noScript.newPage();
    await plain.goto(pathToFileURL(path.resolve(samplePath)).href);
    assert.equal(await plain.locator('article').count(), 3);
    assert.equal(await plain.locator('noscript').isVisible(), true);
    await noScript.close();
    fs.writeFileSync(evidencePath, JSON.stringify({
      chromium: browser.version(), node: process.version, playwright: load('playwright/package.json').version,
      external_networking: 'offline context; only named local report navigation allowed; external requests aborted; service workers blocked',
      automatic_remote_requests: requests.length, page_errors: errors.length,
      checks: ['source and status filters', 'before/after revision', 'Enter and Space disclosure keys',
               'Tab and native select keys', 'visible 3px focus', '320px viewport without overflow',
               'hostile content inert', '200-card cap', 'no-JavaScript reading'],
      elements: {sample: sampleElements, hostile: hostileElements, bounded: boundedElements},
      maximum_tested_cards: 200
    }, null, 2) + '\n');
  } finally {
    await browser.close();
  }
}
main().catch(error => {console.error(error); process.exitCode = 1;});
