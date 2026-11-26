import fs from 'node:fs';import path from 'node:path';
import {loadModular,LiveRiffs,leadMotifs,addRiffs} from './modular_bridge.mjs';
const [mode,output,...args]=process.argv.slice(2);const api=await loadModular();
if(mode==='styles'){console.log(Object.keys(api.STYLES).join('\n'));process.exit(0);}
if(!output)throw Error('Usage: modular_cli.mjs live output.json [style] [bars] [seed] | locked output.json input.json [style] | motifs output.json live.json [previous.json]');
let result;
if(mode==='live'){const [style='cinematic',count='32',seed='symphonia']=args;const n=Number(count);if(!Number.isInteger(n)||n<1||n>128)throw Error('Bars 1–128');const live=new LiveRiffs(api,{style,seed}),bars=Array.from({length:n},()=>live.next());result={bars,performance:{notes:bars.flatMap(b=>b.notes),totalSeconds:live.time},engine:'Modular Riffs'};}
else if(mode==='locked'){const [input,style='cinematic']=args;const source=JSON.parse(fs.readFileSync(input,'utf8'));const {makeTimeMap}=await import('./vendor/composer.js');result=addRiffs(api,source,makeTimeMap(source.piece),{style});}
else if(mode==='motifs'){const [input,previous]=args;result=leadMotifs(JSON.parse(fs.readFileSync(input,'utf8')).bars,previous?JSON.parse(fs.readFileSync(previous,'utf8')):null);}
else throw Error('Unknown command');fs.mkdirSync(path.dirname(output),{recursive:true});fs.writeFileSync(output,JSON.stringify(result,null,2));
