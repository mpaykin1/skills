// Shared harmony adapter; actual theory operations delegated to Tonal 6.9.0.
// This module works in Node or browser with injected Tonal; no hidden fallback.
import {motifDistance,validateMotifs} from './hybrid.mjs';
const NAMES=['C','C#','D','Eb','E','F','F#','G','Ab','A','Bb','B'];
const SUFFIXES=['','m','dim','7','m7','maj7','m7b5','dim7','aug','sus2','sus4','6','m6','add9','9','maj9','m9','mMaj7'];
const pc=n=>((n%12)+12)%12;
const equal=(a,b)=>a.size===b.size&&[...a].every(n=>b.has(n));
export async function loadTonal(){return await import('tonal');}
export function harmonyAPI(T){
 if(!T?.Chord?.get||!T?.Note?.chroma||!T?.Scale?.get)throw Error('Tonal 6.9.0 required');
 const pitchSet=notes=>new Set(notes.map(n=>T.Note.chroma(n)));
 const chord=(pcs)=>{
  if(!Array.isArray(pcs)||pcs.length<3||pcs.some(x=>!Number.isInteger(x)||x<0||x>11))throw Error('Invalid pitch classes');
  const set=new Set(pcs),root=pcs[0];
  // The upstream root is significant (particularly diminished chords). Never re-root.
  for(const suffix of SUFFIXES){const symbol=NAMES[root]+suffix, c=T.Chord.get(symbol);if(!c.empty&&equal(set,pitchSet(c.notes)))return {symbol,rootPc:root,pcs:[...set],quality:c.quality,scales:T.Chord.chordScales(symbol)};}
  throw Error('Unrecognized exact chord at root '+NAMES[root]+': '+pcs.join(','));
 };
 const scale=(root,mode)=>{const name=({harmonicMinor:'harmonic minor',melodicMinor:'melodic minor',minorPentatonic:'minor pentatonic',majorPentatonic:'major pentatonic'})[mode]??mode;const s=T.Scale.get(root+' '+name);if(s.empty||!s.notes.length)throw Error('Unsupported scale: '+root+' '+mode);return {name:s.name,pcs:[...pitchSet(s.notes)]};};
 return {chord,scale};
}
export function analyzePiece(T,piece){
 if(!piece||!Array.isArray(piece.chords)||!piece.chords.length||!Array.isArray(piece.notes)||!Number.isFinite(piece.beats)||piece.beats<=0||!Number.isFinite(piece.totalBeats)||piece.totalBeats<=0)throw Error('Invalid score');
 const api=harmonyAPI(T),home=api.scale(piece.root,piece.mode),unit=piece.beatUnit??1;
 if(!Number.isFinite(unit)||unit<=0)throw Error('Invalid beat unit');
 const spans=piece.chords.map(c=>{if(!Number.isInteger(c.bar)||c.bar<0||!Number.isFinite(c.start??0)||(c.start??0)<0||(c.start??0)>=piece.beats)throw Error('Invalid chord position');return {at:c.bar*piece.beats+(c.start??0),...api.chord(c.pcs),source:c.chord??null};}).sort((a,b)=>a.at-b.at);
 if(spans[0].at!==0||spans.some((s,i)=>s.at>=piece.totalBeats||(i>0&&s.at<=spans[i-1].at)))throw Error('Incomplete or overlapping harmony');
 const timeline=spans.map((s,i)=>({...s,end:spans[i+1]?.at??piece.totalBeats,quarterStart:s.at*unit,quarterEnd:(spans[i+1]?.at??piece.totalBeats)*unit,borrowed:s.pcs.some(p=>!home.pcs.includes(p))}));
 const top=new Map();for(const n of piece.notes){if(n.hand!=='right'||n.ornament)continue;if(!Number.isFinite(n.time)||!Number.isInteger(n.pitch)||n.pitch<21||n.pitch>108)throw Error('Invalid melody event');if(n.time<0||n.time>=piece.totalBeats)continue;const old=top.get(n.time);if(old===undefined||n.pitch>old)top.set(n.time,n.pitch);}
 let idx=0,attacks=0,strong=0,stable=0,chromatic=0;
 for(const [at,pitch] of [...top].sort((a,b)=>a[0]-b[0])){while(idx+1<timeline.length&&timeline[idx+1].at<=at+1e-7)idx++;const c=timeline[idx];attacks++;if(!home.pcs.includes(pc(pitch))&&!c.pcs.includes(pc(pitch)))chromatic++;const beat=at%piece.beats;if(Math.abs(beat)<1e-6||(piece.beats===4&&Math.abs(beat-2)<1e-6)){strong++;if(c.pcs.includes(pc(pitch)))stable++;}}
 // Chromatic/borrowed notes and suspensions are legitimate; diagnostic, not a hard ban.
 return {schema:'music-harmony-v1',engine:'tonal',scale:home,timeline,metrics:{attacks,strong,stable,chromatic,strongChordRatio:strong?stable/strong:null,chromaticRatio:attacks?chromatic/attacks:null}};
}
export function selectHarmonicVariation(T,compose,options,bank=null,count=8){
 if(bank)validateMotifs(bank);if(!Number.isInteger(count)||count<1||count>16)throw Error('Candidates 1–16');
 let best=null;const seed=options.seed??1;
 for(let i=0;i<count;i++){const piece=compose({...options,seed:(seed+i)>>>0}),harmony=analyzePiece(T,piece),d=bank?motifDistance(piece,bank):0;if(!Number.isFinite(d))continue;const m=harmony.metrics;const cost=d+.15*(1-(m.strongChordRatio??.5))+.05*(m.chromaticRatio??0);if(!best||cost<best.cost)best={piece,harmony,distance:bank?d:null,cost,candidates:count,motifSource:bank?.sha256??null};}
 if(!best)throw Error('No comparable candidate');return best;
}
export function analyzeLiveBars(T,bars){const api=harmonyAPI(T);if(!Array.isArray(bars)||!bars.length)throw Error('No live bars');return bars.map(b=>{const c=b.chord;if(!c||!Number.isInteger(c.rootPc)||!Array.isArray(c.offsets))throw Error('Invalid live chord');return {bar:b.bar,start:b.start,end:b.end,...api.chord(c.offsets.map(x=>pc(c.rootPc+x)))};});}
