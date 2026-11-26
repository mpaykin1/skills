import {loadTonal,selectHarmonicVariation} from './tonal_bridge.mjs';
import {chooseVariation} from './hybrid.mjs';
import fs from 'node:fs';
import path from 'node:path';
import {compose,performance,STYLES} from './engine.mjs';
import {pieceToMidi} from './vendor/midi.js';
import {pieceToMusicXml} from './vendor/musicxml.js';
const args=process.argv.slice(2); if(args.includes('--styles')){console.log(Object.keys(STYLES).join('\n'));process.exit(0);}
const o={};for(let i=0;i<args.length;i+=2){let k=args[i].slice(2),v=args[i+1];if(!['style','root','mode','seed','tempo','melodySeed','leftSeed','out','motif','harmony'].includes(k)||v===undefined)throw new Error('Invalid arguments');o[k]=['seed','tempo','melodySeed','leftSeed'].includes(k)?Number(v):v;}
const {out='music',motif,harmony,...opts}=o; if(harmony!==undefined&&harmony!=='tonal')throw Error('Use --harmony tonal'); const bank=motif?JSON.parse(fs.readFileSync(motif,'utf8')):null; const hybrid=harmony==='tonal'?selectHarmonicVariation(await loadTonal(),compose,opts,bank):bank?chooseVariation(compose,opts,bank):null; const piece=hybrid?hybrid.piece:compose(opts);fs.mkdirSync(path.dirname(out),{recursive:true});fs.writeFileSync(out+'.mid',Buffer.from(pieceToMidi(piece)));fs.writeFileSync(out+'.musicxml',pieceToMusicXml(piece));fs.writeFileSync(out+'.json',JSON.stringify({piece,performance:performance(piece),motifDistance:hybrid?.distance??null,motifSource:hybrid?.motifSource??null,...(hybrid?.harmony?{harmony:hybrid.harmony}:{})},null,2));
