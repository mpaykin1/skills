/* Inspect real rendered environment props through a least-privilege loopback origin. */
import fs from 'node:fs/promises';import http from 'node:http';import assert from 'node:assert/strict';import {createHash} from 'node:crypto';
const {chromium}=await import(process.env.HERO_PLAYWRIGHT_MODULE||'playwright');
const file=process.argv[2],out=process.argv[3];if(!file||!out)throw Error('Usage: node test_environment_game.mjs GAME.html OUTPUT_DIR');
const html=await fs.readFile(file),results=[];await fs.mkdir(out,{recursive:true});
const server=http.createServer((req,res)=>{if(req.url!=='/game'){res.writeHead(404);return res.end();}res.setHeader('Content-Type','text/html; charset=utf-8');res.end(html);});await new Promise(r=>server.listen(0,'127.0.0.1',r));const origin='http://127.0.0.1:'+server.address().port;
const browser=await chromium.launch({args:['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
try{for(const viewport of [{width:1366,height:768},{width:390,height:844},{width:844,height:390}]){
 const mobile=viewport.width!==1366,ctx=await browser.newContext({viewport,hasTouch:mobile,isMobile:mobile}),page=await ctx.newPage(),errors=[],external=[];
 await page.route('**/*',r=>{if(r.request().url().startsWith(origin+'/'))return r.continue();external.push(r.request().url());return r.abort();});page.on('pageerror',e=>errors.push(e.message));
 await page.goto(origin+'/game');await page.waitForFunction(()=>globalThis.heroGameEvidence?.textureTotal===26&&heroGameEvidence.textures===26);
 const s=()=>page.evaluate(()=>heroGameEvidence),assets=await page.evaluate(()=>Object.fromEntries(Object.entries(HERO_PROP_PACK.assets).map(([k,a])=>[k,{width:a.width,height:a.height,pivot:a.pivot,role:a.role,gate:a.gate,review:a.review}])));
 assert.equal(Object.keys(assets).length,3);const initial=await s();assert(initial.environment.visible.length>10);assert(initial.environment.completeProps);assert.equal(initial.glError,0);
 for(const p of initial.environment.visible){assert(assets[p.id]);assert(!['old_oak','dead_forest','distant_ruins'].includes(p.id));assert(Math.abs(p.width/p.height-assets[p.id].width/assets[p.id].height)<1e-9);assert(p.opacity>0&&p.opacity<=1);}
 assert.equal(await page.locator('button:visible').count(),mobile?9:0);await page.screenshot({path:out+'/trees-'+viewport.width+'-initial.png'});
 if(!mobile){
  await page.mouse.move(800,280);await page.mouse.down();await page.mouse.move(930,280,{steps:10});await page.mouse.up();await page.waitForFunction(()=>heroGameEvidence.cameraYaw>.5);await page.screenshot({path:out+'/trees-camera-turn.png'});
  assert.equal((await s()).events.filter(e=>e.type==='action'&&e.action==='attack').length,0);
  await page.keyboard.press('KeyR');await page.waitForFunction(()=>heroGameEvidence.time<1); // yaw stays camera-relative deliberately.
  await page.keyboard.down('ArrowLeft');await page.waitForFunction(()=>Math.hypot(heroGameEvidence.player.x,heroGameEvidence.player.z-8)>27,null,{timeout:120000});await page.keyboard.up('ArrowLeft');
  const walked=await s();assert.equal(walked.world.active,49);assert(walked.environment.visible.every(p=>assets[p.id]));await page.screenshot({path:out+'/trees-after-chunk-travel.png'});
 }
 assert.deepEqual(errors,[]);assert.deepEqual(external,[]);assert.equal((await s()).glError,0);results.push({viewport,assets,initial,final:await s(),errors,external});console.log(viewport.width+'x'+viewport.height+' complete props PASS');await ctx.close();
}await fs.writeFile(out+'/environment-browser-checks.json',JSON.stringify({sha256:createHash('sha256').update(html).digest('hex'),results},null,2));}finally{await browser.close();server.close();}
