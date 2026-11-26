import {chromium} from "playwright";
import {fileURLToPath} from "node:url";
const [url, selector="#game"]=process.argv.slice(2);
const u=new URL(url);
if(!["http:","https:"].includes(u.protocol)||!["127.0.0.1","localhost","[::1]"].includes(u.hostname)||u.username||u.password)throw Error("local authorized URL only");
const browser=await chromium.launch({headless:true,args:["--use-angle=swiftshader","--enable-unsafe-swiftshader"]});
const failures=[];let active=false;
try{
 const context=await browser.newContext({serviceWorkers:"block",viewport:{width:844,height:390}});
 await context.route("**/*",r=>new URL(r.request().url()).origin===u.origin?r.continue():r.abort());
 const page=await context.newPage();
 page.on("pageerror",e=>failures.push(e.message));
 page.on("console",m=>{if(m.text().includes("webgl-lint running"))active=true;if(m.type()==="error")failures.push(m.text())});
 await page.addInitScript({path:fileURLToPath(new URL("../vendor/webgl-lint.js",import.meta.url))});
 // Observe contexts created by the application, never create one on its behalf.
 await page.addInitScript(()=>{window.__nexusLintContexts=[];const get=HTMLCanvasElement.prototype.getContext;HTMLCanvasElement.prototype.getContext=function(...args){const gl=get.apply(this,args);if(gl&&/^webgl|experimental-webgl$/.test(String(args[0]))){const ext=gl.getExtension("GMAN_debug_helper");window.__nexusLintContexts.push({canvas:this,active:!!ext});if(ext)ext.setConfiguration({maxDrawCalls:0,throwOnError:true});}return gl;}});
 await page.goto(u.href,{waitUntil:"domcontentloaded",timeout:30000});
 await page.locator(selector).waitFor({state:"visible",timeout:15000});
 await page.waitForTimeout(1500);
 const instrumented=await page.evaluate(s=>(window.__nexusLintContexts||[]).some(x=>x.canvas===document.querySelector(s)&&x.active),selector);
 const route=failures.map(message=>({message,skill:/shader|uniform|framebuffer|matrix/i.test(message)?"game-style-forge":/texture|sampler/i.test(message)?"sprite-stacking-grunge":/buffer|attribute|index/i.test(message)?"meta-game-fusion / blender-model-animation-enhancer":"skill-synergy-manager"}));
 console.log(JSON.stringify({active:active&&instrumented,errors:route,scope:"main-thread WebGL observation only; no FPS or visual PASS"}));
 if(!active||!instrumented||failures.length)process.exitCode=1;
}finally{await browser.close()}
