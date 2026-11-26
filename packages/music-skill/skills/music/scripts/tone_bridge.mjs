import {samplePiano} from './salamander_bridge.mjs';
// Tone.js 14.9.17 playback adapter. All times are seconds, not transport ticks.
// One clock, bounded lookahead, no synthesis or musical generation in game frames.
const finite=Number.isFinite;
const roles=['piano','pad','bass','arp','lead','kick','snare','hat'];
const partRole={pad:'pad',bass:'bass',melody:'arp',alt:'lead'};
const freq=p=>440*2**((p-69)/12);
export function normalizePerformance(source){
 const p=source?.performance??source;
 if(!Array.isArray(p?.notes)||!finite(p.totalSeconds)||p.totalSeconds<=0||p.totalSeconds>360||p.notes.length>20000)throw Error('Invalid performance');
 const input=p.notes.map(n=>({...n,role:partRole[n.part]??'piano'}));
 const backing=source?.backing?.notes??[];
 if(!Array.isArray(backing)||backing.length>40000)throw Error('Invalid backing');
 for(const n of backing){let role=n.kind==='bass'?'bass':n.kind==='drum'?([35,36].includes(n.pitch)?'kick':[37,38,39,40].includes(n.pitch)?'snare':[42,44,46,49,51,52,55,57,59].includes(n.pitch)?'hat':null):null;
  if(role)input.push({...n,role});}
 if(backing.some(n=>n.kind==='bass')&&p.notes.some(n=>n.part==='bass'))throw Error('Duplicate MMA/Modular bass');
 const notes=input.map(n=>{if(!roles.includes(n.role)||!Number.isInteger(n.pitch)||n.pitch<0||n.pitch>127||!finite(n.start)||!finite(n.end)||n.start<0||n.end<=n.start||n.end>p.totalSeconds+2||!finite(n.velocity)||n.velocity<0||n.velocity>1)throw Error('Invalid note');return n;}).sort((a,b)=>a.start-b.start);
 return {notes,totalSeconds:notes.reduce((t,n)=>Math.max(t,n.end),p.totalSeconds)};
}
export function createToneVoices(T,{salamander=null}={}){
 const master=new T.Gain(.64),limiter=new T.Limiter(-3).toDestination();master.connect(limiter);
 const synth=(type,db,attack,decay,sustain,release)=>{const s=new T.PolySynth(T.Synth,{oscillator:{type},envelope:{attack,decay,sustain,release}});s.maxPolyphony=24;s.volume.value=db;return s.connect(master);};
 const sampled=salamander?samplePiano(T,master,salamander):null;
 const v={piano:sampled??synth('triangle',-14,.008,.36,.18,.55),pad:synth('sine',-22,.12,.25,.7,.5),bass:synth('triangle',-16,.012,.16,.6,.13),arp:synth('sine',-20,.008,.22,.18,.2),lead:synth('triangle',-15,.022,.22,.45,.22),kick:new T.MembraneSynth({volume:-13,pitchDecay:.045,octaves:4,envelope:{attack:.002,decay:.19,sustain:0,release:.12}}).connect(master),snare:new T.NoiseSynth({volume:-22,noise:{type:'white'},envelope:{attack:.002,decay:.12,sustain:0,release:.03}}).connect(master),hat:new T.NoiseSynth({volume:-30,noise:{type:'pink'},envelope:{attack:.001,decay:.045,sustain:0,release:.015}}).connect(master)};
 return {play(n,t){const d=n.end-n.start;if((n.role==='piano'||n.role==='lead')&&sampled){sampled.play(n.pitch,d,t,n.velocity);return;}if(n.role==='kick')v.kick.triggerAttackRelease('C2',Math.min(d,.2),t,n.velocity);else if(n.role==='hat'||n.role==='snare')v[n.role].triggerAttackRelease(Math.min(d,.12),t,n.velocity);else v[n.role].triggerAttackRelease(freq(n.pitch),d,t,n.velocity);},volume(x){master.gain.rampTo(x*.64,.08);},dispose(){for(const s of Object.values(v))s.dispose();master.dispose();limiter.dispose();}};
}
export class ToneMusic{
 constructor(T,{voices=createToneVoices,lookahead=.18,interval=25,onError=console.error}={}){if(!T?.start||!T?.now||!T?.getContext||lookahead<.1||lookahead>.8)throw Error('Tone.js required');Object.assign(this,{T,voices,lookahead,interval,onError});this.running=false;this.generation=0;this.level=1;}
 async start(source,{live=false}={}){this.stop();const generation=this.generation;await this.T.start();if(generation!==this.generation)return;this.source=source;this.live=live;this.queue=[];this.cursor=0;this.generatedEnd=0;this.offset=0;this.bank=this.voices(this.T);this.bank.volume(this.level);this.origin=this.T.now()+.08;this.running=true;try{if(!live){const p=normalizePerformance(source);this.queue=p.notes;this.generatedEnd=p.totalSeconds;}else if(typeof source?.next!=='function')throw Error('Live provider must implement next()');this.tick();if(this.running)this.timer=setInterval(()=>{try{this.tick()}catch(e){this.stop();this.onError(e);}},this.interval);}catch(e){this.stop();throw e;}}
 request(change){if(!this.live||!this.running||typeof this.source.request!=='function')throw Error('No live provider');this.source.request(change);}
 setVolume(x){if(!finite(x)||x<0||x>1)throw Error('Volume 0..1');this.level=x;this.bank?.volume(x);}
 tick(){if(!this.running)return;const now=this.T.now();const horizon=now+this.lookahead;
 // On suspended contexts do not generate or advance content.
 if(this.T.getContext().state!=='running')return;
 // If browser throttling misses the lookahead, re-anchor unplayed events;
 // never fire a backlog of simultaneous expired notes.
 if(this.live&&this.origin+this.generatedEnd<now&&this.cursor>=this.queue.length)this.origin=now+.05-this.generatedEnd;
 while(this.live&&this.origin+this.generatedEnd<=horizon){const b=this.source.next();if(!finite(b.start)||!finite(b.end)||b.end<=b.start||Math.abs(b.start-this.generatedEnd)>.001||!Array.isArray(b.notes))throw Error('Non-contiguous live bar (start a fresh provider)');const p=normalizePerformance({notes:b.notes.map(n=>({...n,start:n.start-b.start,end:n.end-b.start})),totalSeconds:b.end-b.start});this.queue.push(...p.notes.map(n=>({...n,start:n.start+b.start,end:n.end+b.start})));this.generatedEnd=b.end;}
 while(this.cursor<this.queue.length&&this.origin+this.queue[this.cursor].start<=horizon){const n=this.queue[this.cursor++],t=this.origin+n.start;if(t>=now-.025)this.bank.play(n,Math.max(t,now));}
 if(this.cursor){this.queue.splice(0,this.cursor);this.cursor=0;}
 if(!this.live&&!this.queue.length&&now>this.origin+this.generatedEnd+.8)this.stop();
 }
 stop(){this.generation++;this.running=false;if(this.timer!==undefined)clearInterval(this.timer);this.timer=undefined;this.bank?.dispose();this.bank=null;this.queue=[];this.cursor=0;}
}
