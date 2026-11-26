import {createRigSync} from '../../rigify-hybrid/runtime/rig-sync.mjs';
export function createLayeredRigSync(motion,volumes,applyPose,applySword,resolveWorld){
 const hash=motion.layer_recipe_sha256;
 if(typeof hash!=='string'||!/^[a-f0-9]{64}$/.test(hash))throw Error('missing layer recipe digest');
 for(const name of Object.keys(motion.clips))if(volumes[name]?.layer_recipe_sha256!==hash)throw Error('volume baked from different layers: '+name);
 return createRigSync(motion,volumes,applyPose,applySword,resolveWorld);
}
