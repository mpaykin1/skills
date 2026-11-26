// Adapter around original Modular Riffs modules, not a replacement generator.
import {validateMotifs} from './hybrid.mjs';
const PARTS=['pad','bass','melody','alt'];
const ROOTS=['C','C#','D','D#','E','F','F#','G','G#','A','A#','B'];
const clamp=(x,a,b)=>Math.min(b,Math.max(a,x));
export async function loadModular(){
 const [gen,arr,theory]=await Promise.all([import('./modular_riffs/js/generator.js'),import('./modular_riffs/js/arranger.js'),import('./modular_riffs/js/theory.js')]);
 return {...gen,...arr,...theory,STYLES:gen.STYLES};
}
function configure(s,api,style){
 if(!Object.hasOwn(api.STYLES,style))throw Error('Unknown Modular Riffs style: '+style);
 const p=api.STYLES[style]; s.style=style;s.bpm=p.bpm;s.swing=p.swing;s.bassStyle=p.bass;s.arpDir=p.arp;
 for(const [k,d] of [['pad',p.padDens],['bass',.55],['melody',p.melDens],['alt',p.leadDens]]){s.parts[k].density=d;s.parts[k].gate=p.gate[k];}
}
function setup(api,{root='C',scale='minor',seed='symphonia',style='cinematic',energy=.5,evolve=.4,blueprint='auto'}={}){
 if(!ROOTS.includes(root)||!Object.hasOwn(api.SCALES,scale)||![energy,evolve].every(x=>Number.isFinite(x)&&x>=0&&x<=1))throw Error('Invalid root, scale, or intensity');
 const s={rootPc:ROOTS.indexOf(root),scaleKey:scale,seed:String(seed),energy,evolve,blueprint,melodySalt:0,padMode:'note',blocks:[],song:[],intensity:[],parts:{},mutes:{}};
 PARTS.forEach((k,i)=>{s.parts[k]={enabled:true,channel:i,octave:0,density:.5,velocity:k==='pad'?.5:.7,gate:.7};s.mutes[k]=new Set();});configure(s,api,style);return s;
}
function event(e,start,end){if(!PARTS.includes(e.part)||!Number.isInteger(e.note)||e.note<21||e.note>108||!Number.isFinite(e.vel)||e.vel<1||e.vel>127||!Number.isFinite(start)||!Number.isFinite(end)||end<=start||start<0)throw Error('Invalid Modular Riffs event');return {pitch:e.note,velocity:e.vel/127,start,end,hand:['pad','bass'].includes(e.part)?'left':'right',part:e.part};}
function timing(e,swing){const shift=x=>x+(Math.floor(x)%2===1?swing:0);return [shift(e.startStep),Math.min(16,shift(e.startStep)+e.durSteps)];}
export class LiveRiffs{
 constructor(api,options={}){this.api=api;this.state=setup(api,options);api.generateSong(this.state);this.generator=new api.JamGenerator(this.state);this.bar=0;this.time=0;this.pending={};}
 request(change={}){const s=this.state;if(change.style!==undefined&&!Object.hasOwn(this.api.STYLES,change.style))throw Error('Unknown style');for(const k of ['energy','evolve'])if(change[k]!==undefined&&(!Number.isFinite(change[k])||change[k]<0||change[k]>1))throw Error('Invalid '+k);if(change.bpm!==undefined&&(!Number.isFinite(change.bpm)||change.bpm<30||change.bpm>220))throw Error('Invalid BPM');for(const k of ['style','energy','evolve','bpm'])if(change[k]!==undefined)this.pending[k]=change[k];}
 next(){const s=this.state,p=this.pending;this.pending={};if(p.style!==undefined)configure(s,this.api,p.style);for(const k of ['energy','evolve','bpm'])if(p[k]!==undefined)s[k]=p[k];if(this.bar+1>=s.song.length)this.api.extendSong(s,1);const info=s.song[this.bar];if(!info)throw Error('No generated harmony');const bar=this.bar++,duration=240/s.bpm,start=this.time;this.time+=duration;const events=this.generator.generateBar(bar).map(e=>{const [a,b]=timing(e,s.swing);return event(e,start+a*duration/16,start+b*duration/16);});return {bar,start,end:this.time,bpm:s.bpm,style:s.style,chord:info.chord,section:info.section,notes:events};}
}
// For existing piano pieces preserve the full chord timeline. A one-chord-per-bar
// upstream engine must never silently flatten an intra-bar chord change.
export function lockedHarmony(piece){
 if(piece?.beats!==4||(piece.beatUnit??1)!==1||!Number.isInteger(piece.totalBars)||piece.totalBars<1||piece.totalBars>200||!Array.isArray(piece.chords))throw Error('Locked mode requires a 4/4 score of 1–200 bars');
 const by=new Map();for(const c of piece.chords){if(!Number.isInteger(c.bar)||c.bar<0||c.bar>=piece.totalBars||(c.start??0)!==0||by.has(c.bar))throw Error('Locked mode needs exactly one chord per bar');const pcs=c.pcs;if(!Array.isArray(pcs)||pcs.length<3||pcs.some(x=>!Number.isInteger(x)||x<0||x>11))throw Error('Invalid chord');const rootPc=pcs[0],offsets=[...new Set(pcs.map(x=>(x-rootPc+12)%12))].sort((a,b)=>a-b);if(offsets.length<3)throw Error('Invalid chord tones');by.set(c.bar,{chord:{rootPc,offsets,label:c.chord??ROOTS[rootPc]},label:c.chord??ROOTS[rootPc],section:'A'});}
 if(by.size!==piece.totalBars)throw Error('Missing bar harmony');return Array.from({length:piece.totalBars},(_,i)=>by.get(i));
}
export function addRiffs(api,source,timeMap,{style='cinematic',energy=.4,parts=['pad'],seed=source?.piece?.seed??1}={}){
 const piece=source?.piece,perf=source?.performance;
 if(!Array.isArray(perf?.notes)||!Number.isFinite(perf.totalSeconds)||typeof timeMap?.toSeconds!=='function'||!Array.isArray(parts)||!parts.length||parts.some(k=>!['pad','bass','melody'].includes(k)))throw Error('Invalid piano performance/parts');
 if(source.backing&&parts.includes('bass'))throw Error('MMA already owns bass');
 const s=setup(api,{root:piece.root,scale:piece.mode,seed,style,energy});s.song=lockedHarmony(piece);s.intensity=s.song.map(()=>.5);for(const k of PARTS)s.parts[k].enabled=parts.includes(k);const gen=new api.JamGenerator(s),added=[];
 for(let bar=0;bar<s.song.length;bar++)for(const e of gen.generateBar(bar)){const [a,b]=timing(e,s.swing);const n=event(e,timeMap.toSeconds(bar*4+a/4),timeMap.toSeconds(bar*4+b/4));n.velocity*=.24;added.push(n);}
 return {...source,performance:{...perf,notes:[...perf.notes,...added].sort((a,b)=>a.start-b.start),totalSeconds:Math.max(perf.totalSeconds,...added.map(n=>n.end))},modularRiffs:{engine:'Modular Riffs',mode:'locked-4/4',style,parts,addedNotes:added.length,scoreUnchanged:true}};
}
// Extract upstream lead into the same six-note contour format used by NotaGen/Magenta.
export function leadMotifs(bars,previous=null){const notes=[];for(const bar of bars)for(const n of bar.notes)if(n.part==='alt')notes.push([bar.bar*4+(n.start-bar.start)*bar.bpm/60,n.pitch]);notes.sort((a,b)=>a[0]-b[0]);const m=[];for(let i=0;i+5<notes.length&&m.length<8;i+=3){const x=notes.slice(i,i+6),gaps=x.slice(1).map((n,j)=>n[0]-x[j][0]);if(gaps.some(g=>g<=0||g>4)||new Set(x.map(n=>n[1])).size<3)continue;m.push({intervals:x.slice(1).map((n,j)=>n[1]-x[j][1]),gaps});}if(!m.length)throw Error('No suitable lead motif');const old=previous?validateMotifs(previous):null;const motifs=[...new Map([...(old?.motifs??[]),...m].map(n=>[JSON.stringify(n),n])).values()];return validateMotifs({schema:'music-motif-v1',source:'modular-riffs',parentSource:old?.source??null,motifs});}
