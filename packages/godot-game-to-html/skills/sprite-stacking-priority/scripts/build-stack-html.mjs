#!/usr/bin/env node
// Builds a single offline HTML from a verified sprite-stack scene payload.
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {build} from 'esbuild';
const [payloadPath,outputPath] = process.argv.slice(2);
if(!payloadPath||!outputPath)throw new Error('Usage: node build-stack-html.mjs payload.json output.html');
const here=path.dirname(fileURLToPath(import.meta.url));
const payload=JSON.parse(await fs.readFile(payloadPath,'utf8'));
if(!Array.isArray(payload.items)||!payload.items.length)throw new Error('No slice volumes');
const result=await build({entryPoints:[path.join(here,'stack-runtime.mjs')],bundle:true,write:false,
  minify:true,format:'iife',platform:'browser',target:['es2020'],logLevel:'warning',legalComments:'none'});
const js=result.outputFiles[0]?.text;
if(!js)throw new Error('Three.js renderer bundle missing');
const safe=s=>String(s).replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
const embedded=JSON.stringify(payload).replace(/</g,'\\u003c').replace(/>/g,'\\u003e');
const html=`<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><title>SPRITE STACKING · ${safe(payload.name||'Original scene')}</title><style>
:root{color-scheme:dark;font-family:system-ui,-apple-system,sans-serif}*{box-sizing:border-box}html,body{height:100%;margin:0;overflow:hidden;background:#070b10;color:#dce3e7}#scene{width:100vw;height:100dvh;touch-action:none}#scene canvas{display:block;width:100%;height:100%}header{position:absolute;top:0;left:0;right:0;pointer-events:none;padding:20px 24px;background:linear-gradient(#050a10e8,transparent);z-index:2}h1{margin:0 0 8px;font-size:13px;letter-spacing:.16em;font-weight:600}#status{font-size:11px;color:#9aaab4}#loading{position:absolute;inset:0;display:grid;place-items:center;font-size:12px;letter-spacing:.1em}#loading[hidden]{display:none}nav{position:absolute;bottom:20px;left:50%;transform:translateX(-50%);display:flex;gap:8px;z-index:3;padding:9px;background:#111e29d9;border:1px solid #70829055;border-radius:12px;backdrop-filter:blur(10px)}button{font:inherit;color:#dee8ef;font-size:12px;background:#243440;border:1px solid #72869652;border-radius:8px;padding:9px 13px;white-space:nowrap}button:active{background:#3a5564}@media(max-width:500px){header{padding:14px 16px}nav{bottom:14px}}
</style></head><body><div id="scene"></div><header><h1>SPRITE STACKING · ${safe(payload.name||'Original scene')}</h1><div id="status">Настоящие RGBA-срезы · исходные материалы</div></header><div id="loading">Загрузка объёма…</div><nav><button id="orbit" type="button">Обзор 360°</button><button id="reset" type="button">Камера</button></nav><script id="stack-payload" type="application/json">${embedded}</script><script>${js.replace(/<\/script/gi,'<\\/script')}</script></body></html>`;
await fs.mkdir(path.dirname(outputPath),{recursive:true});
await fs.writeFile(outputPath,html);
console.log('SPRITE_STACK_HTML '+outputPath+' '+Buffer.byteLength(html)+' bytes');
