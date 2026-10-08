/* Corpus-derived report checks; all external requests blocked. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const {createRequire} = require('node:module');
const load = process.env.QUIET_FEED_BROWSER_MODULES ? createRequire(path.join(process.env.QUIET_FEED_BROWSER_MODULES,'package.json')) : require;
const {chromium}=load('playwright');
async function main() {
  const [reportPath,jsonPath,evidencePath]=process.argv.slice(2);
  const report=JSON.parse(fs.readFileSync(jsonPath));
  const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
  try {
    const context=await browser.newContext({offline:true,serviceWorkers:'block'});
    const url=pathToFileURL(path.resolve(reportPath)).href;
    const requests=[],errors=[];
    await context.route('**/*',async route=>{
      if(route.request().url()===url && route.request().isNavigationRequest()) return route.continue();
      await route.abort();
    });
    context.on('request',r=>{if(/^https?:/.test(r.url())) requests.push(r.url());});
    const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
    await page.goto(url);
    await page.waitForFunction(()=>document.querySelector('#visible').textContent==='4 of 4 selected items visible');
    assert.equal(await page.locator('article').count(),4);
    await page.locator('#source').selectOption('rss');assert.equal(await page.locator('article:visible').count(),2);
    await page.locator('#status').selectOption('revised');assert.equal(await page.locator('article:visible').count(),1);
    const summary=page.locator('article:visible summary').filter({hasText:'Before revision:'});
    await summary.focus();await page.keyboard.press('Enter');assert.equal(await summary.evaluate(e=>e.parentElement.open),true);
    assert.match(await page.locator('article:visible .before').innerText(),/<p>Example description<\/p>/);
    assert.match(await page.locator('article:visible .excerpt').first().innerText(),/Revised locally/);
    await page.keyboard.press('Space');assert.equal(await summary.evaluate(e=>e.parentElement.open),false);
    await page.locator('#source').focus();await page.keyboard.press('Tab');assert.equal(await page.evaluate(()=>document.activeElement.id),'status');
    await page.locator('#source').selectOption('');await page.locator('#status').selectOption('');
    assert.equal(await page.locator('img,iframe,object,embed,svg,base,form').count(),0);
    assert.equal(await page.evaluate(()=>window.PWNED),undefined);
    assert.match(await page.locator('body').innerText(),/<script>window.PWNED/);
    const selection=new Set(report.digest.selection.map(s=>s.feed_id+'|'+s.identity));
    const expected=report.items.filter(i=>selection.has(i.feed_id+'|'+i.identity)).flatMap(i=>[i.after,...(i.status==='revised'?[i.before]:[])]).map(r=>r.article_url).filter(Boolean).sort();
    const hrefs=await page.locator('article a').evaluateAll(els=>els.map(e=>e.getAttribute('href')).sort());
    assert.deepEqual(hrefs,expected);assert(hrefs.includes('https://example.org/corpus/story'));
    assert(hrefs.every(u=>/^https?:\/\//.test(u)));
    await page.setViewportSize({width:320,height:700});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
    assert.deepEqual(requests,[]);assert.deepEqual(errors,[]);
    // Exercise navigation only after asserting zero automatic requests. Routing
    // and the offline context still prevent any actual remote connection.
    const article=page.locator('article a[href="https://example.org/corpus/story"]');
    await article.click();
    assert(requests.includes('https://example.org/corpus/story'));
    fs.writeFileSync(evidencePath,JSON.stringify({chromium:browser.version(),playwright:load('playwright/package.json').version,node:process.version,
      automatic_remote_requests:0,blocked_user_navigation:requests,article_hrefs:hrefs,page_errors:errors,
      checks:['source filtering','revision filtering','before/after text','Enter and Space disclosure','Tab navigation','hostile markup inert','validated resolved article links','blocked article navigation','320px viewport'],external_networking:'offline context; service workers blocked; route permits only report file'},null,2)+'\n');
  } finally {await browser.close();}
}
main().catch(e=>{console.error(e);process.exitCode=1;});
