// Magenta.js 1.23.1 adapter. The model performs real inference; no fake fallback.
// Quarter-note grid is shared with the source composition and MMA.
import {analyzePiece} from './tonal_bridge.mjs';
import {validateMotifs} from './hybrid.mjs';
export const CHECKPOINT='https://storage.googleapis.com/magentadata/js/checkpoints/music_rnn/chord_pitches_improv';
const SPQ=4, NAMES=['C','C#','D','Eb','E','F','F#','G','Ab','A','Bb','B'];
const TYPES=[['',[0,4,7]],['m',[0,3,7]],['dim',[0,3,6]],['7',[0,4,7,10]],['m7',[0,3,7,10]]];
export function chordSymbol(pcs){
 if(!Array.isArray(pcs)||pcs.length<3||pcs.some(p=>!Number.isInteger(p)||p<0||p>11))throw Error('Invalid chord pitch classes');
 const set=new Set(pcs); // Upstream orders root first; preserve it, including symmetric chords.
 for(const root of [pcs[0],...pcs.slice(1)])for(const [suffix,intervals] of TYPES)
  if(set.size===intervals.length&&intervals.every(i=>set.has((root+i)%12)))return NAMES[root]+suffix;
 throw Error('Unsupported chord; do not guess harmony');
}
export function prepare(piece,{bar=0,bars=2,tonal=null}={}){
 if(!piece||!Array.isArray(piece.notes)||!Array.isArray(piece.chords)||![3,4].includes(piece.beats)||(piece.beatUnit??1)!==1)throw Error('Magenta bridge supports simple 3/4 and 4/4 only');
 if(!Number.isInteger(bar)||bar<0||!Number.isInteger(bars)||bars<1||bars>4||bar+1+bars>piece.totalBars)throw Error('Select one primer bar plus 1–4 continuation bars within the score');
 if(!Number.isFinite(piece.tempo)||piece.tempo<=0)throw Error('Invalid tempo');
 if(tonal)analyzePiece(tonal,piece);
 const primer=piece.beats*SPQ,steps=bars*primer,origin=bar*piece.beats;
 const top=new Map();
 for(const n of piece.notes){if(n.hand!=='right'||n.ornament||n.time<origin||n.time>=origin+piece.beats||!Number.isInteger(n.pitch)||!Number.isFinite(n.duration)||n.duration<=0)continue;
  const start=Math.round((n.time-origin)*SPQ);if(start>=primer)continue;
  const old=top.get(start);if(!old||old.pitch<n.pitch)top.set(start,n);
 }
 const entries=[...top].sort((a,b)=>a[0]-b[0]);if(entries.length<2)throw Error('Primer needs two melody attacks');
 // Model is a 36-note monophonic encoder: fit the whole phrase by octave only.
 const low=Math.min(...entries.map(x=>x[1].pitch)),high=Math.max(...entries.map(x=>x[1].pitch));
 const shifts=[0,-12,12,-24,24,-36,36];const shift=shifts.find(d=>low+d>=48&&high+d<=83);if(shift===undefined)throw Error('Primer outside model range');
 const notes=entries.map(([start,n],i)=>({pitch:n.pitch+shift,quantizedStartStep:start,quantizedEndStep:Math.min(primer,entries[i+1]?.[0]??primer,start+Math.max(1,Math.round(n.duration*SPQ))),velocity:Math.max(1,Math.min(127,Math.round((n.velocity??.7)*127))),instrument:0,program:0,isDrum:false}));
 const timeline=piece.chords.map(c=>({time:c.bar*piece.beats+(c.start??0),pcs:c.pcs})).sort((a,b)=>a.time-b.time);
 // One symbol per grid step: encodeProgression distributes evenly across primer+continuation.
 const progression=[];let pos=-1;for(let i=0;i<primer+steps;i++){const time=origin+i/SPQ;while(pos+1<timeline.length&&timeline[pos+1].time<=time+1e-8)pos++;if(pos<0)throw Error('Missing chord at primer onset');progression.push(chordSymbol(timeline[pos].pcs));}
 return {sequence:{notes,quantizationInfo:{stepsPerQuarter:SPQ},totalQuantizedSteps:primer,tempos:[{time:0,qpm:piece.tempo}],timeSignatures:[{time:0,numerator:piece.beats,denominator:4}]},steps,progression,shift,bar,bars};
}
export function extractBank(sequence,previous=null){
 const top=new Map();for(const n of sequence?.notes??[]){const t=n.quantizedStartStep;if(!Number.isInteger(t)||!Number.isInteger(n.pitch)||n.pitch<21||n.pitch>108)continue;top.set(t,Math.max(n.pitch,top.get(t)??0));}
 const seq=[...top].sort((a,b)=>a[0]-b[0]);const motifs=[];
 for(let i=0;i+5<seq.length&&motifs.length<8;i+=3){const chunk=seq.slice(i,i+6);const pitches=chunk.map(x=>x[1]);const gaps=chunk.slice(1).map((x,j)=>(x[0]-chunk[j][0])/SPQ);if(new Set(pitches).size<3||gaps.some(x=>x<=0||x>4))continue;motifs.push({intervals:pitches.slice(1).map((p,j)=>p-pitches[j]),gaps});}
 if(!motifs.length)throw Error('No usable six-note continuation; keep existing music');
 const old=previous?validateMotifs(previous):null;const existing=old?.motifs??[];const unique=new Map();for(const m of [...existing,...motifs])unique.set(JSON.stringify([m.intervals,m.gaps]),m);
 // Keep all existing motifs; do not silently evict a bank. Reserve space in advance.
 if(unique.size>32)throw Error('Motif bank full; supply a smaller previous bank');
 const result={schema:'music-motif-v1',source:'magenta-js-chord-pitches-improv',parentSource:old?.source??null,parentSha256:old?.sha256??null,motifs:[...unique.values()]};return validateMotifs(result);
}
export class MagentaMotifs{
 constructor(mm,tonal=null){this.tonal=tonal;if(typeof mm?.MusicRNN!=='function')throw Error('Load @magenta/music 1.23.1');this.model=new mm.MusicRNN(CHECKPOINT);this.ready=false;this.busy=false;}
 async generate(piece,{bar=0,bars=2,temperature=.85,previous=null}={}){
  if(this.busy)throw Error('Inference already running');if(!Number.isFinite(temperature)||temperature<0||temperature>1.5)throw Error('Temperature 0–1.5');
  const {sequence,steps,progression}=prepare(piece,{bar,bars,tonal:this.tonal});this.busy=true;
  try{if(!this.ready){await this.model.initialize();this.ready=true;}
   const result=await this.model.continueSequence(sequence,steps,temperature||undefined,progression);
   return {bank:extractBank(result,previous),continuation:result,checkpoint:CHECKPOINT,bar,bars,temperature};
  }finally{this.busy=false;}
 }
 dispose(){if(this.busy)throw Error('Inference running');this.model.dispose();this.ready=false;}
}
