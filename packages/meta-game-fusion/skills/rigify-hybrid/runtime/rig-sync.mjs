// Same authored timeline for complete volume poses and sword attachment; no synthetic pose interpolation.
export function createRigSync(motion,clipVolumes,applyPose,applySword,resolveWorld){
 if(motion.schema!=='rigify-motion-v1'||typeof applyPose!=='function'||typeof applySword!=='function'||typeof resolveWorld!=='function')throw Error('invalid rig bridge');
 return {sample(name,seconds){const c=motion.clips[name],v=clipVolumes[name];if(!c||!v||v.hero_id!==motion.hero_id||v.source_sha256!==motion.source_sha256||v.fps!==c.fps||v.poses.length!==c.frames.length||!v.poses.every((p,i)=>p.frame===c.frames[i].frame))throw Error('unsynchronized volume poses');if(!Number.isFinite(seconds))throw Error('invalid time');const i=Math.max(0,Math.min(c.frames.length-1,Math.floor(seconds*c.fps+1e-7)));const frame=c.frames[i];applyPose(v.poses[i]);applySword(frame);return frame;},
 cue(name,frameNumber,cue,id){const c=motion.clips[name];const e=c?.events.find(e=>e.frame===frameNumber&&e.cue===cue);if(!e||!id)return null;const f=c.frames.find(f=>f.frame===frameNumber);return {id,cue,position:resolveWorld(f.local[e.bone])};}};
}
