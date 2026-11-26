/* Real browser regression checks. Only loopback HTTP is exposed; external requests are blocked. */
import assert from 'node:assert/strict';import fs from 'node:fs/promises';import http from 'node:http';import {createHash} from 'node:crypto';
const {chromium}=await import(process.env.HERO_PLAYWRIGHT_MODULE||'playwright');
const file=process.argv[2],out=process.argv[3];if(!file||!out)throw Error('Usage: node test_controls_game.mjs GAME.html OUTPUT_DIR');
const html=await fs.readFile(file),results=[];await fs.mkdir(out,{recursive:true});
const server=http.createServer((req,res)=>{if(req.url!=='/game'){res.writeHead(404);return res.end();}res.writeHead(200,{'Content-Type':'text/html; charset=utf-8','Cache-Control':'no-store'});res.end(html);});
await new Promise(r=>server.listen(0,'127.0.0.1',r));const origin='http://127.0.0.1:'+server.address().port;
const browser=await chromium.launch({args:['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist']});
try{for(const mode of (process.env.HERO_TEST_MODES||'desktop,portrait,landscape').split(',')){
 const mobile=mode!=='desktop',viewport=mode==='desktop'?{width:960,height:600}:mode==='portrait'?{width:390,height:844}:{width:844,height:390};
 const ctx=await browser.newContext({viewport,hasTouch:mobile,isMobile:mobile});const page=await ctx.newPage(),errors=[],external=[];page.setDefaultTimeout(60000);
 await page.route('**/*',route=>{const u=route.request().url();if(u.startsWith(origin+'/'))return route.continue();external.push(u);return route.abort();});
 page.on('pageerror',e=>errors.push(e.message));await page.goto(origin+'/game');await page.waitForFunction(()=>globalThis.heroGameEvidence?.textures===(heroGameEvidence?.textureTotal||23));
 const s=()=>page.evaluate(()=>heroGameEvidence),attacks=()=>page.evaluate(()=>heroGameEvidence.events.filter(e=>e.type==='action'&&e.action==='attack').length);
 const idle=()=>page.waitForFunction(()=>heroGameEvidence.player.action==='idle');
 const restart=async()=>{if(mobile)await page.locator('[data-hero-key="restart"]').tap();else await page.keyboard.press('KeyR',{delay:35});await page.waitForFunction(()=>heroGameEvidence.time<1&&heroGameEvidence.player.hp===100&&heroGameEvidence.player.x===0&&heroGameEvidence.player.z===8);};
 const entry={mode,viewport,checks:[]};
 if(!mobile){
  assert.equal(await page.locator('button:visible').count(),0);assert.equal(await page.evaluate(()=>document.activeElement.id),'gl');
  const t=(await s()).time;await page.waitForFunction(t=>heroGameEvidence.time>t+3.2,t);assert.equal(await attacks(),0);entry.checks.push('idle: no player attacks without input');
  for(const [key,face,axis,sign] of [['ArrowLeft','left','x',-1],['ArrowRight','right','x',1],['ArrowUp','back','z',-1],['ArrowDown','front','z',1]]){
   await restart();const v=(await s()).player[axis];await page.keyboard.down(key);await page.waitForFunction(({axis,sign,v,face})=>(heroGameEvidence.player[axis]-v)*sign>.8&&heroGameEvidence.facing===face,{axis,sign,v,face});await page.keyboard.up(key);await idle();assert.equal(await attacks(),0);entry.checks.push(key+': movement + '+face+' + release');
  }
  await restart();await page.mouse.click(750,300);await page.mouse.click(200,350);await page.waitForTimeout(300);assert.equal(await attacks(),0);assert.equal(await page.evaluate(()=>document.activeElement.id),'gl');
  await page.keyboard.down('KeyJ');await page.waitForFunction(()=>heroGameEvidence.events.some(e=>e.type==='action'&&e.action==='attack'));const t2=(await s()).time;await page.waitForFunction(t=>heroGameEvidence.time>t+1.5,t2);await page.keyboard.up('KeyJ');assert.equal(await attacks(),1);entry.checks.push('one J press including repeat => exactly one attack; scene clicks => zero attacks');
  await page.keyboard.down('ArrowLeft');await page.waitForFunction(()=>heroGameEvidence.player.action==='walk');await page.evaluate(()=>window.dispatchEvent(new Event('blur')));await idle();const x=(await s()).player.x;await page.waitForTimeout(250);assert.equal((await s()).player.x,x);await page.keyboard.up('ArrowLeft');entry.checks.push('focus loss clears held keys');
  await page.setViewportSize({width:390,height:844});assert.equal(await page.locator('button:visible').count(),0);await page.setViewportSize(viewport);
  if(process.env.HERO_WORLD_TRAVEL==='1'){
   entry.travel=[];
   for(const [key,face,axis,sign,bound] of [['ArrowLeft','left','x',-1,32],['ArrowRight','right','x',1,32],['ArrowUp','back','z',-1,40],['ArrowDown','front','z',1,32]]){
    await restart();await page.keyboard.down(key);await page.waitForFunction(({axis,sign,bound,face})=>heroGameEvidence.player[axis]*sign>bound&&heroGameEvidence.facing===face,{axis,sign,bound,face},{timeout:180000});await page.keyboard.up(key);const d=await s();assert.equal(d.world.active,49);assert.equal(d.glError,0);entry.travel.push({key,position:d.player,world:d.world});
   }
   await restart();const a=await s();await page.waitForTimeout(1300);const b=await s();assert(a.enemies.some((e,i)=>e.renderFrame!==b.enemies[i].renderFrame));
  }
 }else{
  assert.equal(await page.locator('#touchActions button:visible').count(),9);
  const layout=await page.locator('#touchActions button').evaluateAll(bs=>bs.map(b=>{const r=b.getBoundingClientRect();return {key:b.dataset.heroKey,x:r.x,y:r.y,w:r.width,h:r.height,opacity:getComputedStyle(b).opacity};}));
  for(const b of layout){assert(b.x>=viewport.width*.5);assert(b.x+b.w<=viewport.width);assert(b.y+b.h<=viewport.height);assert(b.w>=44&&b.h>=44);assert.equal(b.opacity,'0.75');}entry.layout=layout;
  await page.touchscreen.tap(viewport.width*.8,viewport.height*.35);await page.waitForTimeout(250);assert.equal(await attacks(),0);entry.checks.push('right scene tap is not attack');
  const client=await ctx.newCDPSession(page),touch=(type,touchPoints)=>client.send('Input.dispatchTouchEvent',{type,touchPoints});
  const anchor={x:viewport.width*.21,y:viewport.height*.7,id:1},moved={...anchor,x:anchor.x-45};
  await touch('touchStart',[anchor]);await touch('touchMove',[moved]);await page.waitForFunction(()=>heroGameEvidence.player.x<-.6&&heroGameEvidence.facing==='left');
  const box=await page.locator('[data-hero-key="attack"]').boundingBox(),right={x:box.x+box.width/2,y:box.y+box.height/2,id:2};
  await touch('touchStart',[moved,right]);await page.waitForFunction(()=>heroGameEvidence.events.some(e=>e.type==='action'&&e.action==='attack'));await touch('touchEnd',[right]);assert.equal((await s()).controls.stick,true);await touch('touchEnd',[]);await idle();assert.equal(await attacks(),1);assert.deepEqual((await s()).controls.buttons,[]);entry.checks.push('invisible stick + independent right attack; releasing right keeps stick');
  await restart();const tb=await page.locator('[data-hero-key="attack"]').boundingBox(),held={x:tb.x+tb.width/2,y:tb.y+tb.height/2,id:3};await touch('touchStart',[held]);await page.waitForFunction(()=>heroGameEvidence.events.some(e=>e.type==='action'&&e.action==='attack'));const t3=(await s()).time;await page.waitForFunction(t=>heroGameEvidence.time>t+1.5,t3);assert.equal(await attacks(),1);await touch('touchEnd',[]);await idle();const at=await attacks();await page.waitForTimeout(300);assert.equal(await attacks(),at);entry.checks.push('holding attack does not auto-repeat; release creates no attack');
  for(const [action,type] of [['jump','jump'],['dodge','action'],['roll','action']]){await restart();await page.locator('[data-hero-key="'+action+'"]').tap();await page.waitForFunction(({action,type})=>heroGameEvidence.events.some(e=>e.type===type&&(type!=='action'||e.action===action)),{action,type});await idle();assert.equal(await attacks(),0);}
  await restart();const cb=await page.locator('[data-hero-key="crouch"]').boundingBox(),cp={x:cb.x+cb.width/2,y:cb.y+cb.height/2,id:4};await touch('touchStart',[cp]);await page.waitForFunction(()=>heroGameEvidence.player.action==='crouch');await touch('touchCancel',[]);await idle();assert.deepEqual((await s()).controls.buttons,[]);entry.checks.push('jump/dodge/roll/crouch buttons; pointercancel clears hold');
  await touch('touchStart',[anchor]);await touch('touchMove',[moved]);await page.waitForFunction(()=>heroGameEvidence.controls.stick);await touch('touchCancel',[]);await idle();assert.equal((await s()).controls.stick,false);assert.equal((await s()).controls.pointers,0);
  await page.locator('[data-hero-key="pause"]').tap();await page.waitForFunction(()=>heroGameEvidence.paused);const paused=(await s()).time;await page.waitForTimeout(250);assert.equal((await s()).time,paused);await page.locator('[data-hero-key="pause"]').tap();await page.waitForFunction(()=>!heroGameEvidence.paused);entry.checks.push('explicit pause/resume; no hidden gesture actions');
 }
 assert.equal((await s()).glError,0);assert.deepEqual(errors,[]);assert.deepEqual(external,[]);entry.errors=errors;entry.external=external;entry.final=await s();
 await page.screenshot({path:out+'/controls-'+mode+'.png'});results.push(entry);console.log(mode+' PASS');await ctx.close();
}await fs.writeFile(out+'/controls-browser-checks.json',JSON.stringify({sha256:createHash('sha256').update(html).digest('hex'),results},null,2));}
finally{await browser.close();server.close();}

