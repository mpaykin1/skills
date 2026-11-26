// Authored adapter. Native Effekseer context is externally initialized; no second loop.
export const CUES=Object.freeze({light_hit:'light_slash',heavy_hit:'heavy_slash',air_hit:'air_slash',takeoff:'jump_burst',land:'landing_dust',impact:'hit_sparks'});
export function createCombatVFX({native=null,assets,spawnBaked,now,max=24,onError=console.warn}){
 if(typeof spawnBaked!=='function'||typeof now!=='function'||!Number.isInteger(max)||max<1)throw Error('invalid VFX configuration');
 const active=[],seen=new Map();let ctx=native;
 function fail(e){onError(e);ctx=null;for(const item of active){if(item.handle){try{item.handle.stop();}catch{}item.handle=null;try{item.baked=spawnBaked(item.asset,item.pos,Math.max(0,now()-item.start));}catch(e){onError(e)}}}}
 function emit(ev){const name=CUES[ev.cue],asset=assets[name],p=ev.position,t=now();if(!name||!asset||!ev.id||!Array.isArray(p)||p.length!==3||!p.every(Number.isFinite))return false;
 if(seen.has(ev.id))return false;seen.set(ev.id,t);while(seen.size>2048)seen.delete(seen.keys().next().value);
 if(active.length>=max)return false;let item={asset,pos:[...p],start:t,handle:null,baked:null};
 if(ctx&&asset.effect){try{item.handle=ctx.play(asset.effect,...p);if(!item.handle)throw Error('Effekseer play failed');}catch(e){fail(e);}}
 if(!item.handle){try{item.baked=spawnBaked(asset,p,0);}catch(e){onError(e);return false;}}active.push(item);return true;}
 function tick(dt){if(!Number.isFinite(dt)||dt<0)return;try{ctx?.update(Math.min(dt,.1)*60);}catch(e){fail(e)}const t=now();for(let i=active.length-1;i>=0;i--){const a=active[i],age=t-a.start;if(age>=a.asset.duration){try{a.handle?.stop();a.baked?.dispose();}catch(e){onError(e)}active.splice(i,1);}else a.baked?.update(age);}}
 function draw(renderer,camera){if(!ctx)return;try{ctx.setProjectionMatrix(Float32Array.from(camera.projectionMatrix.elements));ctx.setCameraMatrix(Float32Array.from(camera.matrixWorldInverse.elements));ctx.draw();}catch(e){fail(e)}finally{renderer.resetState();}}
 function dispose(){for(const a of active){a.handle?.stop();a.baked?.dispose();}active.length=0;seen.clear();ctx=null;}
 return {emit,tick,draw,contextLost:()=>fail(Error('Effekseer context lost')),dispose};
}
export async function verifyAtlas(bytes,meta){if(meta.schema!=='effekseer-combat-v1'||!Number.isInteger(meta.count)||meta.count<2||!(meta.fps>0)||!(meta.duration>0)||Math.abs(meta.duration-meta.count/meta.fps)>1e-6)throw Error('invalid atlas metadata');const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),x=>x.toString(16).padStart(2,'0')).join('');if(hash!==meta.sha256)throw Error('atlas hash mismatch');}
export function atlasFrame(meta,age){const i=Math.min(meta.count-1,Math.max(0,Math.floor(age*meta.fps)));return {x:(i%meta.columns)*meta.width,y:Math.floor(i/meta.columns)*meta.height,w:meta.width,h:meta.height};}
export function drawCombat2D(ctx,image,meta,age,x,y,w,h){if(age<0||age>=meta.duration)return;const r=atlasFrame(meta,age);ctx.drawImage(image,r.x,r.y,r.w,r.h,x,y,w,h);}
// Three.js fallback uses same baked frames. Each effect owns its UV transform; no shared texture mutation.
export function bakedThree(THREE,scene,texture,meta,pos,scale=1){if(texture.image.width!==meta.columns*meta.width||texture.image.height!==meta.rows*meta.height)throw Error('atlas dimensions');const tex=texture.clone();tex.needsUpdate=true;tex.repeat.set(1/meta.columns,1/meta.rows);const mat=new THREE.SpriteMaterial({map:tex,transparent:true,depthWrite:false,depthTest:true});const sprite=new THREE.Sprite(mat);sprite.position.set(...pos);sprite.scale.set(scale*meta.width/meta.height,scale,1);scene.add(sprite);return {update(age){const r=atlasFrame(meta,age);tex.offset.set(r.x/(meta.columns*meta.width),1-(r.y+meta.height)/(meta.rows*meta.height));},dispose(){scene.remove(sprite);mat.dispose();tex.dispose();}};}
