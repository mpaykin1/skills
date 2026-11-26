// Synchronized lossless stems, one native AudioContext (Tone.getContext().rawContext).
// Call load before entering the scene; start from a user gesture. Do not also play
// the same composition through the live note engine.
export async function loadLoopPack(ctx, manifestUrl, destination=ctx.destination){
 const url=new URL(manifestUrl,globalThis.location?.href);const get=async u=>{const r=await fetch(u);if(!r.ok)throw Error('Loop download failed: '+r.status);return r;};
 const m=await (await get(url)).json();
 if(m.schema!=='music-loop-pack-v1'||![32000,44100,48000].includes(m.sampleRate)||![1,2].includes(m.channels)||!Number.isInteger(m.frames)||m.frames<=0||m.frames>180*m.sampleRate||!Array.isArray(m.stems)||m.stems.length<1||m.stems.length>8)throw Error('Invalid loop pack');
 const duration=m.frames/m.sampleRate;
 if(duration*ctx.sampleRate*m.channels*m.stems.length*4>64*1024*1024)throw Error('Loop pack exceeds 64 MiB decoded budget');
 const buffers=await Promise.all(m.stems.map(async s=>{if(!/^stem-\d\d\.wav$/.test(s.file)||! /^[0-9a-f]{64}$/.test(s.sha256))throw Error('Invalid stem manifest');const bytes=await(await get(new URL(s.file,url))).arrayBuffer();const digest=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),n=>n.toString(16).padStart(2,'0')).join('');if(digest!==s.sha256)throw Error('Stem integrity mismatch');const b=await ctx.decodeAudioData(bytes);if(b.numberOfChannels!==m.channels||Math.abs(b.duration-duration)>2/ctx.sampleRate)throw Error('Decoded loop alignment mismatch');return b;}));
 if(buffers.some(b=>b.length!==buffers[0].length))throw Error('Decoded stems differ in frame count');
 const master=ctx.createGain();master.gain.value=.8;master.connect(destination);const gains=buffers.map(()=>{const g=ctx.createGain();g.connect(master);return g;});let sources=[],disposed=false,epoch=0;
 const stop=()=>{for(const s of sources){try{s.stop();}catch{}s.disconnect();}sources=[];};
 return {manifest:m,async start(){if(disposed)throw Error('Disposed loop player');const id=++epoch;await ctx.resume();if(id!==epoch||disposed)return;stop();const at=ctx.currentTime+.08;sources=buffers.map((b,i)=>{const s=ctx.createBufferSource();s.buffer=b;s.loop=true;s.loopStart=0;s.loopEnd=b.duration;s.connect(gains[i]);s.start(at);return s;});},setMix(values,seconds=.15){if(disposed||values.length!==gains.length||values.some(v=>!Number.isFinite(v)||v<0||v>1)||!Number.isFinite(seconds)||seconds<.02||seconds>5)throw Error('Invalid mix');const t=ctx.currentTime;gains.forEach((g,i)=>{g.gain.cancelAndHoldAtTime(t);g.gain.linearRampToValueAtTime(values[i],t+seconds);});},stop(){epoch++;stop();},dispose(){epoch++;disposed=true;stop();gains.forEach(g=>g.disconnect());master.disconnect();}};
}
