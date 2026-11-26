#!/usr/bin/env node
/** Pixelmatch 8.0.0: deterministic, pixel-level comparison of paired PNG screenshots.
 * Only aligned screenshots of original and derivative art are comparable.
 * Exit code 0: pass; 1: visual regression; 2: invalid input.
 * No output files by default. Originals are read-only.
 */
import fs from 'node:fs/promises';
import path from 'node:path';
import pixelmatch from 'pixelmatch';
import {PNG} from 'pngjs';

function fail(message, code=2) {
  console.error(`VISUAL PARITY: ${message}`);
  process.exit(code);
}
const argv=process.argv.slice(2);
if(argv.includes('--help')) {
  console.log('Usage: node compare-screenshots.mjs --baseline original.png|folder --candidate derivative.png|folder [--max-ratio 0.03] [--threshold 0.1] [--include-aa] [--diff-dir separate-dir]');
  process.exit(0);
}
function option(name, fallback=null) {
  const index=argv.indexOf(name);
  if(index===-1) return fallback;
  if(index===argv.length-1 || argv[index+1].startsWith('--')) fail(`Missing argument for ${name}`);
  return argv[index+1];
}
const baseline=option('--baseline');
const candidate=option('--candidate');
if(!baseline || !candidate) fail('Both --baseline and --candidate are required; never estimate preservation without screenshot pairs');
const maxRatio=Number(option('--max-ratio','0.03'));
const threshold=Number(option('--threshold','0.10'));
const includeAA=argv.includes('--include-aa');
const diffDir=option('--diff-dir');
if(!Number.isFinite(maxRatio) || maxRatio<0 || maxRatio>1)fail('--max-ratio must be between 0 and 1');
if(!Number.isFinite(threshold) || threshold<0 || threshold>1)fail('--threshold must be between 0 and 1');

async function safeStat(filename) {
  try {return await fs.stat(filename);} catch {fail(`File/directory missing: ${filename}`);}
}
async function pairs() {
  const left=path.resolve(baseline),right=path.resolve(candidate);
  const lstat=await safeStat(left),rstat=await safeStat(right);
  if(lstat.isFile() && rstat.isFile()) {
    if(path.extname(left).toLowerCase()!=='.png' || path.extname(right).toLowerCase()!=='.png') fail('Only PNG screenshots are accepted');
    return [[left,right,path.basename(right)]];
  }
  if(lstat.isDirectory() && rstat.isDirectory()) {
    const leftFiles=(await fs.readdir(left)).filter(f=>f.toLowerCase().endsWith('.png')).sort();
    const rightFiles=(await fs.readdir(right)).filter(f=>f.toLowerCase().endsWith('.png')).sort();
    if(!leftFiles.length)fail('No baseline PNG frames present');
    if(leftFiles.length!==rightFiles.length || leftFiles.some((f,i)=>f!==rightFiles[i]))fail('PNG frame names/count differ: every original frame must match an optimized frame');
    return leftFiles.map(f=>[path.join(left,f),path.join(right,f),f]);
  }
  fail('Baseline and candidate must both be PNG files or both be directories');
}
const screens=await pairs();
if(diffDir) {
  const resolved=path.resolve(diffDir);
  for(const source of [baseline,candidate]) {
    const input=path.resolve(source);
    if(resolved===input || (await safeStat(input)).isDirectory() && (resolved.startsWith(input+path.sep)||input.startsWith(resolved+path.sep)))fail('Diff directory must be separate from source screenshot directories');
  }
  const check=await fs.stat(resolved).catch(()=>null);
  if(check && !check.isDirectory())fail('Diff path exists and is not a directory');
}
let rejected=0,worstRatio=0,totalPixels=0,totalDifferent=0;
for(const [original,optimized,name] of screens) {
  const [oldBytes,newBytes]=await Promise.all([fs.readFile(original),fs.readFile(optimized)]);
  let first,second;
  try {
    first=PNG.sync.read(oldBytes);
    second=PNG.sync.read(newBytes);
  } catch(error) {fail(`Cannot decode PNG ${name}: ${error.message}`);}
  if(first.width!==second.width||first.height!==second.height)fail(`Viewport mismatch at ${name}: ${first.width}x${first.height} vs ${second.width}x${second.height}`);
  if(first.width===0||first.height===0||first.width*first.height>4096*4096)fail(`Unreasonable screenshot resolution: ${name}`);
  const diff=diffDir?new PNG({width:first.width,height:first.height}):null;
  const count=pixelmatch(first.data,second.data,diff?.data??null,first.width,first.height,{threshold,includeAA,alpha:0.6});
  const pixels=first.width*first.height;
  const ratio=count/pixels;
  totalPixels+=pixels;
  totalDifferent+=count;
  worstRatio=Math.max(worstRatio,ratio);
  if(ratio>maxRatio)rejected++;
  if(diffDir) {
    await fs.mkdir(diffDir,{recursive:true});
    await fs.writeFile(path.join(diffDir,path.basename(name)),PNG.sync.write(diff));
  }
  console.log(`${name}: ${count}/${pixels} changed pixels (${(ratio*100).toFixed(3)}%); ${ratio<=maxRatio?'PASS':'BLOCK'}`);
}
console.log(`PIXELMATCH 8.0.0: ${screens.length} aligned frame pairs; worst=${(worstRatio*100).toFixed(3)}%; total=${(100*totalDifferent/totalPixels).toFixed(3)}%; gate=${(maxRatio*100).toFixed(3)}%; ${rejected?'BLOCK':'PASS'}`);
if(rejected)process.exit(1);
