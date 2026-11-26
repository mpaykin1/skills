// Requires Playwright installed in the test environment; HERO_PLAYWRIGHT_MODULE may point to it.
import {pathToFileURL} from 'node:url';import path from 'node:path';import fs from 'node:fs/promises';import assert from 'node:assert/strict';
const {chromium}=await import(process.env.HERO_PLAYWRIGHT_MODULE||'playwright');
const file=path.resolve(process.argv[2]),out=path.resolve(process.argv[3]||path.dirname(file));
const args=process.env.HERO_SOFTWARE_GL==='1'?['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist']:[];
const browser=await chromium.launch({args});const results=[];
function overlaps(a,b){return Math.min(a.x+a.width,b.x+b.width)-Math.max(a.x,b.x)>2&&Math.min(a.y+a.height,b.y+b.height)-Math.max(a.y,b.y)>2;}
try{
 for(const [name,width,height,mobile]of [['desktop',960,600,false],['portrait',390,844,true],['landscape',844,390,true]]){
  const ctx=await browser.newContext({viewport:{width,height},isMobile:mobile,hasTouch:mobile,offline:true}),page=await ctx.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(pathToFileURL(file).href);await page.waitForFunction(()=>globalThis.heroGameEvidence?.textures===Object.keys(window.ASSETS).length);await page.click('#startGame');
  await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
  const hint=await page.locator('#portalHint').boundingBox(),buttons=await page.locator('#topButtons').boundingBox(),seal=await page.locator('#meters strong').boundingBox();
  assert(!overlaps(hint,buttons),name+': objective overlaps sound/pause controls');assert(!overlaps(hint,seal),name+': objective overlaps seal count');assert.deepEqual(errors,[]);
  if(mobile)for(const k of ['attack','grab','jump','dodge','roll','crouch','run','interact'])assert(await page.locator(`[data-hero-key="${k}"]`).isVisible());
  await page.screenshot({path:path.join(out,'ash-verified-layout-'+name+'.png')});results.push({name,viewport:{width,height},hint,buttons,seal,overlap:false,errors});await ctx.close();
 }
 await fs.writeFile(path.join(out,'ash-verified-layout-checks.json'),JSON.stringify(results,null,2));console.log(JSON.stringify({layoutPassed:results.map(x=>x.name)}));
}finally{await browser.close();}
