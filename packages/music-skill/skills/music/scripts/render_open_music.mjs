// The notes and performance timings originate in Piano Music Generator;
// the optional motif selection originates in the NotaGen bridge.
import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {Studio,midiToFreq} from './open_music/src/synth.js';
export function renderPerformance(performance,{seed=7,sampleRate=22050,orchestra=false,backing=null}={}){
 const {notes,totalSeconds}=performance??{};
 if(!Array.isArray(notes)||!notes.length||notes.length>20000||!Number.isFinite(totalSeconds)||totalSeconds<=0||totalSeconds>360)throw new Error('Invalid or oversized performance; render one phrase/piece at a time');
 if(![22050,32000,44100,48000].includes(sampleRate))throw new Error('Unsupported sample rate');
 if(!Number.isInteger(seed)||seed<0||seed>0xffffffff)throw new Error('Invalid seed');
 for(const n of notes)if(!Number.isInteger(n.pitch)||n.pitch<21||n.pitch>108||!Number.isFinite(n.start)||!Number.isFinite(n.end)||n.start<0||n.end<=n.start||n.end>totalSeconds+0.001||!Number.isFinite(n.velocity)||n.velocity<0||n.velocity>1||!['left','right'].includes(n.hand))throw new Error('Invalid piano event');
 const extra=backing?.notes??[];
 if(backing && (backing.engine!=='MMA'||!Array.isArray(extra)||extra.length>40000))throw new Error('Invalid MMA backing');
 for(const n of extra)if(!['bass','drum'].includes(n.kind)||!Number.isInteger(n.pitch)||n.pitch<0||n.pitch>127||!Number.isFinite(n.start)||!Number.isFinite(n.end)||n.start<0||n.end<=n.start||n.end>totalSeconds+2||!Number.isFinite(n.velocity)||n.velocity<0||n.velocity>1)throw new Error('Invalid MMA note');
 const studio=new Studio({sampleRate,seconds:Math.max(totalSeconds,...extra.map(n=>n.end))+2.5,seed,expressive:true});
 for(const n of notes){
  const duration=n.end-n.start;
  studio.piano(n.start,duration,n.pitch,{gain:0.12,velocity:n.velocity,pan:n.hand==='left'?-0.14:0.14,delay:0.01,reverb:0.25});
  // Conservative doubling: same pitches and timing, no competing new harmony.
  // Longer bass notes support strings; sustained treble notes can colour the melody.
  if(orchestra&&duration>=0.45&&n.hand==='left'&&n.pitch>=36&&n.pitch<=60)
   studio.strings(n.start,duration,[n.pitch],{gain:0.025,velocity:n.velocity,pan:-0.2,attack:0.12,release:0.3,delay:0});
  if(orchestra&&duration>=0.8&&n.hand==='right'&&n.pitch>=60&&n.pitch<=84)
   studio.flute(n.start,duration,n.pitch,{gain:0.012,velocity:n.velocity,pan:0.25,delay:0});
 }
 for(const n of extra){
  const v=n.velocity;
  if(n.kind==='bass'){studio.bass(n.start,n.end-n.start,midiToFreq(n.pitch),{gain:0.09*v,midi:n.pitch});continue;}
  // GM drum reduction: supported synth voices only; the MIDI retains all original drums.
  if([35,36].includes(n.pitch))studio.kick(n.start,{gain:0.17*v});
  else if([37,38,40].includes(n.pitch))studio.snare(n.start,{gain:0.11*v});
  else if(n.pitch===39)studio.clap(n.start,{gain:0.075*v});
  else if([42,44,46,49,51,52,55,57,59].includes(n.pitch))studio.hat(n.start,{gain:0.035*v,open:[46,49,51,52,55,57,59].includes(n.pitch)});
 }
 return studio.finish({targetLufs:-16,fadeIn:0.02,fadeOut:0.7});
}
if(process.argv[1]&&import.meta.url===pathToFileURL(path.resolve(process.argv[1])).href){
 const [input,output,...flags]=process.argv.slice(2);
 if(!input||!output||!output.endsWith('.wav')||flags.some(x=>x!=='--orchestra'))throw new Error('Usage: node render_open_music.mjs piece.json output.wav [--orchestra]');
 const source=JSON.parse(fs.readFileSync(input,'utf8'));
 fs.mkdirSync(path.dirname(output),{recursive:true});
 renderPerformance(source.performance,{seed:source.piece?.seed??7,orchestra:flags.includes('--orchestra'),backing:source.backing}).writeWav(output);
}
