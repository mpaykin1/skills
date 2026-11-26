import { chromium } from "playwright";
import { createRequire } from "node:module";
import { readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
const require=createRequire(import.meta.url);
const [url, selector, out]=process.argv.slice(2);
if(!url||!selector||!out) throw Error("usage: capture.mjs local-url canvas-selector output.json");
const u=new URL(url);
if(!["http:","https:"].includes(u.protocol)||!["127.0.0.1","localhost","[::1]"].includes(u.hostname)||u.username||u.password) throw Error("authorized local development URL only");
const bundle=await readFile(require.resolve("spectorjs"),"utf8");
const browser=await chromium.launch({headless:true});
try {
 const context=await browser.newContext({viewport:{width:844,height:390}});
 const page=await context.newPage();
 // Prevent accidental external network and redirects during isolated capture.
 await page.route("**/*",route=>{let v=new URL(route.request().url());return v.origin===u.origin?route.continue():route.abort()});
 await page.addInitScript({content:bundle+"\n;window.__nexusSpector=new SPECTOR.Spector();window.__nexusSpector.spyCanvases();"});
 await page.goto(u.href,{waitUntil:"domcontentloaded",timeout:30000});
 await page.locator(selector).waitFor({state:"visible",timeout:20000});
 await page.waitForTimeout(1000);
 const capture=await page.evaluate(({selector})=>new Promise((ok,fail)=>{
  const canvas=document.querySelector(selector),s=window.__nexusSpector;
  if(!(canvas instanceof HTMLCanvasElement)||!s)return fail(Error("WebGL canvas or Spector missing"));
  let timer=setTimeout(()=>fail(Error("capture timed out")),15000);
  s.onError.add(e=>{clearTimeout(timer);fail(Error(String(e)))});
  s.onCapture.add(c=>{clearTimeout(timer);ok(c)});
  s.captureNextFrame(canvas,true);
 }),{selector});
 if(!Array.isArray(capture.commands)||!capture.commands.length)throw Error("empty capture");
 await writeFile(resolve(out),JSON.stringify(capture),{flag:"wx"});
 console.log("captured commands:",capture.commands.length);
}finally{await browser.close()}
