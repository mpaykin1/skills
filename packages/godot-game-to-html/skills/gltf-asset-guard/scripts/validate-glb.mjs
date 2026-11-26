#!/usr/bin/env node
/** Khronos glTF-Validator official npm adapter. Build-time CPU step, no CDN. */
import fs from 'node:fs/promises';
import path from 'node:path';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url);
const validator=require('gltf-validator');
const argv=process.argv.slice(2);
const source=argv[0];
if (!source || argv.includes('--help')) {
  console.error('Usage: node validate-glb.mjs original.glb [--compare optimized.glb] [--strict-warnings] [--browser-bridge] [--offline-basis]');
  process.exit(source ? 0 : 2);
}
const compared=argv.indexOf('--compare');
const other=compared>=0?argv[compared+1]:null;
if(compared>=0&&!other) throw new Error('Missing --compare path');
const strict=argv.includes('--strict-warnings');
const browser=argv.includes('--browser-bridge');
const offlineBasis=argv.includes('--offline-basis');
if(offlineBasis&&!browser)throw new Error('--offline-basis requires --browser-bridge');
const maxBytes=1024*1024*512;
function names(arr){return (arr||[]).map((v,i)=>v.name||`__unnamed_${i}`)}
function stableShape(j){
 return {sceneCount:(j.scenes||[]).length, sceneNames:names(j.scenes), nodeNames:names(j.nodes),
   materialNames:names(j.materials), animations:names(j.animations), skinNames:names(j.skins),
   cameras:names(j.cameras), meshNames:names(j.meshes),
   textureCount:(j.textures||[]).length, imageCount:(j.images||[]).length};
}
function glbHeader(buf){
 if(buf.length<20||buf.toString('ascii',0,4)!=='glTF'||buf.readUInt32LE(4)!==2||buf.readUInt32LE(8)!==buf.length)throw new Error('Invalid GLB 2.0 header');
 const len=buf.readUInt32LE(12);
 if(buf.readUInt32LE(16)!==0x4e4f534a||len>32*1024*1024||len>buf.length-20)throw new Error('Invalid GLB JSON chunk');
 return JSON.parse(buf.subarray(20,20+len).toString('utf8'));
}
async function check(p){
 const full=path.resolve(p);const stat=await fs.stat(full);
 if(stat.size>maxBytes)throw new Error('GLB exceeds 512 MiB safety limit: '+full);
 if(path.extname(full).toLowerCase()!=='.glb')throw new Error('This stage accepts self-contained GLB only');
 const bytes=await fs.readFile(full);
 const json=glbHeader(bytes);
 for(const prop of ['images','buffers'])for(const entry of json[prop]||[]){
  if(entry.uri&&!entry.uri.startsWith('data:'))throw new Error('External resource missing from standalone GLB: '+entry.uri);
 }
 const report=await validator.validateBytes(new Uint8Array(bytes),{
  uri:path.basename(full),format:'glb',maxIssues:0,writeTimestamp:false
 });
 const errors=report.issues?.numErrors||0;
 const warnings=report.issues?.numWarnings||0;
 const issues=(report.issues?.messages||[]).slice(0,8).map(x=>`${x.code}: ${x.message}`);
 console.log(`[Khronos glTF Validator] ${path.basename(full)} errors=${errors} warnings=${warnings}`);
 if(errors||(strict&&warnings))throw new Error('glTF specification violations: '+issues.join(' | '));
 if(browser){
  const unsupported=['KHR_draco_mesh_compression','KHR_animation_pointer','KHR_interactivity','KHR_materials_variants'];
  if(!offlineBasis)unsupported.push('KHR_texture_basisu');
  const bad=unsupported.filter(e=>(json.extensionsUsed||[]).includes(e));
  if(bad.length)throw new Error('Offline Three.js bridge lacks verified decoding/interaction for: '+bad.join(', '));
 }
 return stableShape(json);
}
function lost(oldNames,newNames){
 const counts=new Map();newNames.forEach(x=>counts.set(x,(counts.get(x)||0)+1));
 return oldNames.filter(x=>{const n=counts.get(x)||0;if(n){counts.set(x,n-1);return false}return true});
}
try{
 const original=await check(source);
 if(other){
  const revised=await check(other);
  for(const key of ['sceneNames','nodeNames','materialNames','animations','skinNames','cameras']){
   const missing=lost(original[key],revised[key]);
   if(missing.length)throw new Error(`Optimized GLB lost original ${key}: ${missing.slice(0,6).join(', ')}`);
  }
  if(original.textureCount>0 && revised.textureCount===0)throw new Error('Optimized GLB lost all source textures');
  if(original.imageCount>0&&revised.imageCount===0)throw new Error('Optimized GLB lost all source images');
  console.log('[Khronos glTF Validator] preserved source scene/material/animation identities; visual parity still needs rendering');
 }
}catch(error){console.error('GLTF GUARD FAILED: '+String(error?.message||error));process.exit(1)}
