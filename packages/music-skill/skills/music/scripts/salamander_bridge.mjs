// Original Salamander recordings, played through the same Tone master as other parts.
// No network or decoding in the real-time scheduler.
const ROOTS=Array.from({length:30},(_,i)=>21+3*i);
const UPPER=[26,34,36,43,46,50,56,64,72,80,88,96,104,112,120,127];
export function selectSample(pitch,velocity,layers){
 if(!Number.isInteger(pitch)||pitch<21||pitch>108||!Number.isFinite(velocity)||velocity<0||velocity>1||!Array.isArray(layers)||!layers.length||layers.some(l=>!Number.isInteger(l)||l<1||l>16))throw Error('Invalid piano event or layers');
 const v=Math.max(1,Math.round(velocity*127));const exact=UPPER.findIndex(x=>v<=x)+1;
 const layer=layers.reduce((a,b)=>Math.abs(b-exact)<Math.abs(a-exact)?b:a);
 const midi=ROOTS.reduce((a,b)=>Math.abs(b-pitch)<Math.abs(a-pitch)?b:a);
 return {midi,layer,rate:2**((pitch-midi)/12)};
}
export async function loadSalamander(T,url=new URL('./salamander/manifest.json',import.meta.url),{onProgress=()=>{},maxDecodedMB=160,signal}={}){
 const base=new URL(url,globalThis.location?.href??import.meta.url),res=await fetch(base,{signal});if(!res.ok)throw Error('Salamander manifest unavailable');const m=await res.json();
 if(m.schema!=='salamander-bank-v1'||m.source!=='https://github.com/sfzinstruments/SalamanderGrandPiano'||m.license!=='CC-BY-3.0'||!Array.isArray(m.layers)||!m.layers.length||new Set(m.layers).size!==m.layers.length||m.layers.some(x=>!Number.isInteger(x)||x<1||x>16)||!Array.isArray(m.samples)||m.samples.length!==m.layers.length*30||typeof m.credit!=='string')throw Error('Invalid Salamander bank');
 const ctx=T.getContext(),buffers=new Map(),files=new Set();let used=0,done=0;
 for(const s of m.samples){const key=`${s.midi}-v${s.layer}`;if(!ROOTS.includes(s.midi)||!m.layers.includes(s.layer)||s.file!==key+'.mp3'||files.has(key))throw Error('Invalid sample mapping');files.add(key);}
 if(!Number.isFinite(m.maxSampleSeconds)||m.maxSampleSeconds<=0||m.maxSampleSeconds>18||m.samples.length*m.maxSampleSeconds*ctx.sampleRate*4>maxDecodedMB*1024*1024)throw Error('Bank exceeds memory budget; select mobile preset or raise budget on desktop');
 // Sequential decoding keeps transient memory bounded on phones.
 for(const s of m.samples){const r=await fetch(new URL(s.file,base),{signal});if(!r.ok)throw Error('Missing Salamander sample '+s.file);const buffer=await ctx.decodeAudioData(await r.arrayBuffer());if(!buffer.length||buffer.duration>m.maxSampleSeconds+.2)throw Error('Invalid audio sample');used+=buffer.length*buffer.numberOfChannels*4;if(used>maxDecodedMB*1024*1024)throw Error('Decoded sample budget exceeded');buffers.set(`${s.midi}-v${s.layer}`,buffer);onProgress(++done,m.samples.length);}
 return {layers:m.layers.slice().sort((a,b)=>a-b),buffers,credit:m.credit,decodedBytes:used,context:ctx};
}
export function samplePiano(T,master,bank,{maxVoices=32}={}){
 if(bank.context!==T.getContext())throw Error('Sample bank must share Tone audio context');
 const ctx=bank.context,active=new Set();let disposed=false;
 function drop(v){try{v.src.stop()}catch{}v.src.disconnect();v.gain.disconnect();active.delete(v);}
 return {play(pitch,duration,t,velocity){if(disposed)return;const sel=selectSample(pitch,velocity,bank.layers);const buffer=bank.buffers.get(`${sel.midi}-v${sel.layer}`);if(!buffer)throw Error('Missing preloaded piano sample');
  while(active.size>=maxVoices)drop(active.values().next().value);
  const src=ctx.createBufferSource(),gain=ctx.createGain(),v={src,gain};src.buffer=buffer;src.playbackRate.value=sel.rate;src.connect(gain);gain.connect(master.input);active.add(v);src.onended=()=>{src.disconnect();gain.disconnect();active.delete(v);};
  const start=Math.max(t,ctx.currentTime),length=buffer.duration/sel.rate;const release=Math.min(.45,Math.max(.035,length*.1));const held=Math.max(.003,Math.min(duration,length-release));const end=Math.min(start+length,start+held+release);const level=.22*(.25+.75*velocity);gain.gain.setValueAtTime(0,start);gain.gain.linearRampToValueAtTime(level,start+Math.min(.004,held));gain.gain.setValueAtTime(level,start+held);gain.gain.linearRampToValueAtTime(0,end);src.start(start);src.stop(end);
 },dispose(){disposed=true;for(const v of [...active])drop(v);}};
}
