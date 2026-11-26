/** META GAME FUSION primary visible renderer: genuine horizontal RGBA slice stacks.
 * Imported approved artwork -> immutable volume slices -> SHA-verified atlases.
 * Never approximates physics. Rapier retains rigid-body authority, Recast retains
 * navigation. Opaque alpha-cutout + depth-write keeps inter-slice occlusion.
 */
import * as THREE from 'three';
const SHA=/^[a-f0-9]{64}$/;
const NAME=/^[a-z][a-z0-9-]{1,60}\.png$/;
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));

async function verifiedBytes(path, sha256){
  if(!SHA.test(sha256))throw new Error('SpriteStack: missing valid SHA256 for '+path);
  const res=await fetch(path,{cache:'no-store'});
  if(!res.ok)throw new Error('SpriteStack: atlas unavailable '+path);
  const bytes=await res.arrayBuffer();
  if(bytes.byteLength>18_000_000)throw new Error('SpriteStack: atlas exceeds 18MB');
  if(!crypto?.subtle)throw new Error('SpriteStack: secure SHA256 runtime required');
  const digest=[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))]
     .map(x=>x.toString(16).padStart(2,'0')).join('');
  if(digest!==sha256)throw new Error('SpriteStack: atlas SHA256 mismatch '+path);
  return bytes;
}
async function verifiedTexture(name,sha256){
  if(!NAME.test(name))throw new Error('SpriteStack: unsafe atlas name');
  const bytes=await verifiedBytes('/sprite-stacks/'+name,sha256);
  const url=URL.createObjectURL(new Blob([bytes],{type:'image/png'}));
  try {
    const texture=await new THREE.TextureLoader().loadAsync(url);
    texture.colorSpace=THREE.SRGBColorSpace;
    texture.wrapS=THREE.ClampToEdgeWrapping;
    texture.wrapT=THREE.ClampToEdgeWrapping;
    texture.minFilter=THREE.LinearMipmapLinearFilter;
    texture.magFilter=THREE.LinearFilter;
    texture.anisotropy=2;
    texture.generateMipmaps=true;
    return texture;
  } finally {URL.revokeObjectURL(url);}
}

function stackGeometry(asset,frame){
  const {tile,sliceCount,dimensions,pivot}=asset;
  const {columns,rows}=frame;
  if(!Number.isInteger(tile)||tile<32||tile>512||!Number.isInteger(sliceCount)||sliceCount<12||sliceCount>128||
     !Number.isInteger(columns)||!Number.isInteger(rows)||columns*rows<sliceCount||columns*rows*tile*tile>16e6 ||
     !Array.isArray(dimensions)||dimensions.length!==3||dimensions.some(x=>!Number.isFinite(x)||x<=0||x>60)||
     !Array.isArray(pivot)||pivot.length!==3||pivot.some(x=>!Number.isFinite(x)||Math.abs(x)>60))
    throw Error('SpriteStack: invalid volume dimensions / atlas layout');
  const [width,height,depth]=dimensions;
  const uv=[],vertices=[],normals=[],indices=[];
  const eps=0.51/tile;
  const dx=width/2,dz=depth/2;
  for(let i=0;i<sliceCount;i++){
    const y=(i+.5)/sliceCount*height-pivot[1],c=i%columns,r=Math.floor(i/columns);
    const left=(c+eps)/columns,right=(c+1-eps)/columns;
    const low=1-(r+1-eps)/rows,high=1-(r+eps)/rows;
    const base=i*4;
    vertices.push(-dx-pivot[0],y,-dz-pivot[2], dx-pivot[0],y,-dz-pivot[2],
                  dx-pivot[0],y,dz-pivot[2], -dx-pivot[0],y,dz-pivot[2]);
    normals.push(0,1,0,0,1,0,0,1,0,0,1,0);
    uv.push(left,low,right,low,right,high,left,high);
    // Clockwise from above, material is DoubleSide, normal points up.
    indices.push(base,base+2,base+1,base,base+3,base+2);
  }
  const geometry=new THREE.BufferGeometry();
  geometry.setAttribute('position',new THREE.Float32BufferAttribute(vertices,3));
  geometry.setAttribute('normal',new THREE.Float32BufferAttribute(normals,3));
  geometry.setAttribute('uv',new THREE.Float32BufferAttribute(uv,2));
  geometry.setIndex(indices);
  geometry.computeBoundingSphere();
  return geometry;
}

function proxyGeometry(asset){
  const [width,height,depth]=asset.dimensions;
  const g=new THREE.PlaneGeometry(Math.max(width,depth),height);
  g.translate(0,height/2-asset.pivot[1],0);
  return g;
}
function setViewUV(geometry,idx){
  if(geometry.userData.spriteView===idx)return;
  geometry.userData.spriteView=idx;
  const uv=geometry.attributes.uv;
  const original=geometry.userData.originalUV??new Float32Array(uv.array);
  geometry.userData.originalUV=original;
  for(let i=0;i<uv.count;i++){
    uv.setXY(i,original[i*2]*.25+idx*.25,original[i*2+1]);
  }
  uv.needsUpdate=true;
}
function cutoutMaterial(tex){return new THREE.MeshStandardMaterial({
    map:tex,side:THREE.DoubleSide,transparent:false,alphaTest:.45,
    depthTest:true,depthWrite:true,roughness:.94,metalness:.08,
    polygonOffset:false,
  });}

export class FusionSpriteStacks {
  constructor(scene,world,assets){
    this.scene=scene;this.world=world;this.assets=new Map(assets.map(v=>[v.id,v]));
    this.textures=new Map();this.materials=new Map();this.geometries=new Map();
    this.instances=[];this.animators=[];this.batches=[];
    this.ready=true;this.time=0;this.stats={assets:this.assets.size,instances:0,batches:0,animated:0,loadedFrames:0,visible:true};
  }
  static async create({scene,world}){
    const cfg=world?.sprite_stacking;
    if(!cfg?.primary_renderer)return null;
    if(cfg.manifest!=='/sprite-stacks/manifest.json')throw Error('SpriteStack: unsupported manifest URL');
    const buf=await verifiedBytes(cfg.manifest,cfg.sha256);
    const manifest=JSON.parse(new TextDecoder().decode(buf));
    if(manifest.schema!=='meta-game-fusion.sprite-stacking.v1'||manifest.mode!=='horizontal-physical-slices'||
       !Array.isArray(manifest.assets)||manifest.assets.length<1||manifest.assets.length>60)
      throw Error('SpriteStack: invalid manifest');
    const ids=new Set();
    for(const a of manifest.assets){
      if(!/^[a-z][a-z0-9-]{1,42}$/.test(a.id)||ids.has(a.id)||!a.actions?.idle?.length)
        throw Error('SpriteStack: invalid asset id / idle action');
      ids.add(a.id);
      for(const arr of Object.values(a.actions)){
        if(!Array.isArray(arr)||arr.length>24)throw Error('SpriteStack: invalid animation frames');
        for(const fr of arr)if(!NAME.test(fr.atlas)||!SHA.test(fr.sha256)||
          !NAME.test(fr.views)||!SHA.test(fr.viewsSha256))throw Error('SpriteStack: unverified frame');
      }
    }
    const engine=new FusionSpriteStacks(scene,world,manifest.assets);
    // Fully validated; only visual, decorative atlas textures need loading.
    await Promise.all(manifest.assets.map(a=>engine._frame(a,'idle',0)));
    return engine;
  }
  async _frame(asset,action,index){
    const a=asset.actions[action];if(!a||!a[index])throw Error('SpriteStack: missing approved pose '+asset.id+':'+action+'/'+index);
    const f=a[index];const key=f.atlas;
    if(this.materials.has(key))return this.materials.get(key);
    if(this.textures.has(key))return this.textures.get(key); // in-flight Promise
    const promise=(async()=>{
      const [texture,viewTexture]=await Promise.all([
        verifiedTexture(f.atlas,f.sha256), verifiedTexture(f.views,f.viewsSha256)]);
      const mat=cutoutMaterial(texture);
      const proxyMat=new THREE.MeshBasicMaterial({map:viewTexture,side:THREE.DoubleSide,
        alphaTest:.45,transparent:false,depthWrite:true,depthTest:true});
      const value={geometry:stackGeometry(asset,f),material:mat,
        proxyGeometry:proxyGeometry(asset),proxyMaterial:proxyMat};
      this.materials.set(key,value);this.stats.loadedFrames++;
      this.textures.delete(key);
      return value;
    })().catch(e=>{this.textures.delete(key);throw e});
    this.textures.set(key,promise);
    return promise;
  }
  _createFrame(meshData,asset){
    const mesh=new THREE.Mesh(meshData.geometry,meshData.material);
    mesh.name='SpriteStack: '+asset.id;
    mesh.frustumCulled=true;mesh.userData.mgfSpriteStack=true;
    mesh.userData.mgfBVHExclude=true; // Color-mask quads are not solid collision geometry.
    const proxy=new THREE.Mesh(meshData.proxyGeometry.clone(),meshData.proxyMaterial);
    proxy.userData.mgfBVHExclude=true;
    proxy.visible=false;
    return {mesh,proxy};
  }
  async make(id,{position=[0,0,0],scale=1,rotationY=0,action='idle',fps=9}={}){
    const a=this.assets.get(id);if(!a)throw Error('SpriteStack: unknown asset '+id);
    if(!Number.isFinite(scale)||scale<=0||scale>20)throw Error('SpriteStack scale invalid');
    const actionFrames=a.actions[action];if(!actionFrames)throw Error('SpriteStack: approved action missing '+id+':'+action);
    const all=await Promise.all(actionFrames.map((_,i)=>this._frame(a,action,i)));
    const initial=all[0];
    const g=new THREE.Group();g.name='SpriteStack volume: '+id;
    g.position.fromArray(position);g.scale.setScalar(scale);g.rotation.y=rotationY;
    const {mesh,proxy}=this._createFrame(initial,a);g.add(mesh,proxy);
    this.scene.add(g);
    const inst={id,asset:a,root:g,mesh,proxy,action,frame:0,fps:clamp(fps,1,30),elapsed:0,
      transitioning:false,animated:actionFrames.length>1,rotationY,dispose:()=>this.scene.remove(g)};
    inst.setAction=(next)=>this.setAction(inst,next);
    this.instances.push(inst);this.stats.instances++;this.stats.animated=this.instances.filter(x=>x.animated).length;
    return inst;
  }
  async setAction(inst,action){
    if(!inst||inst.transitioning||inst.action===action)return;
    const asset=inst.asset,frames=asset.actions[action];
    if(!frames)throw Error('SpriteStack: missing approved complete action '+asset.id+':'+action);
    inst.transitioning=true;
    try {
      const data=await Promise.all(frames.map((_,i)=>this._frame(asset,action,i)));
      const first=data[0];
      inst.mesh.geometry=first.geometry;inst.mesh.material=first.material;
      inst.proxy.material=first.proxyMaterial;
      inst.action=action;inst.frame=0;inst.elapsed=0;
      inst.animated=frames.length>1;
      this.stats.animated=this.instances.filter(x=>x.animated).length;
    }finally{inst.transitioning=false;}
  }
  batch(id,placements){
    const asset=this.assets.get(id);if(!asset||!Array.isArray(placements)||!placements.length)return null;
    const first=this.materials.get(asset.actions.idle[0].atlas);
    if(!first)throw Error('SpriteStack: preload required '+id);
    const count=Math.min(placements.length,600);
    const mesh=new THREE.InstancedMesh(first.geometry,first.material,count);
    mesh.name='SpriteStack instanced: '+id;
    mesh.userData.mgfBVHExclude=true;
    mesh.userData.mgfSpriteStack=true;
    const obj=new THREE.Object3D();
    for(let i=0;i<count;i++){
      const p=placements[i],scale=p.scale??1;
      obj.position.set(...(p.position||[0,0,0]));obj.rotation.set(0,p.rotationY??0,0);
      obj.scale.setScalar(scale);obj.updateMatrix();mesh.setMatrixAt(i,obj.matrix);
    }
    mesh.instanceMatrix.needsUpdate=true;this.scene.add(mesh);
    const proxies=[];
    for(let view=0;view<4;view++){
      const geo=first.proxyGeometry.clone();setViewUV(geo,view);
      const batch=new THREE.InstancedMesh(geo,first.proxyMaterial,count);
      batch.count=0;batch.visible=false;batch.frustumCulled=false;
      batch.userData.mgfBVHExclude=true;this.scene.add(batch);proxies.push(batch);
    }
    const entry={id,mesh,placements:placements.slice(0,count),asset,proxies};
    this.batches.push(entry);this.stats.batches++;
    return entry;
  }
  setPoseFrame(inst,frame){
    const f=inst.asset.actions[inst.action];if(!f?.length)return;
    frame%=f.length;if(frame===inst.frame)return;
    const data=this.materials.get(f[frame].atlas);
    if(!data)return; // Only fully loaded complete pose actions may animate.
    inst.mesh.geometry=data.geometry;inst.mesh.material=data.material;
    inst.proxy.material=data.proxyMaterial;
    inst.frame=frame;
  }
  update(dt,camera){
    this.time+=Math.min(.1,Math.max(0,dt));
    if(!camera)return;
    // Keep exact 3D slices for normal views. At a *strictly tangential* camera
    // angle show a four-direction orthographic projection derived from the SAME
    // slices. Never fabricate an unknown rear texture.
    for(const inst of this.instances){
      if(!inst.root.parent)continue;
      const world=new THREE.Vector3();inst.root.getWorldPosition(world);
      const dx=camera.position.x-world.x,dz=camera.position.z-world.z,
        dy=camera.position.y-world.y-inst.asset.dimensions[1]*.5;
      const planeAngle=Math.abs(Math.atan2(dy,Math.hypot(dx,dz)));
      const edge=planeAngle<.095;
      inst.mesh.visible=!edge;inst.proxy.visible=edge;
      if(edge){
        const az=Math.atan2(dx,dz)-inst.root.rotation.y;
        const dir=((Math.round(az/(Math.PI/2))%4)+4)%4;
        setViewUV(inst.proxy.geometry,dir);
        inst.proxy.rotation.y=Math.atan2(dx,dz)-inst.root.rotation.y;
      }
      const n=inst.asset.actions[inst.action]?.length||1;
      if(n>1&&!inst.transitioning){
        inst.elapsed+=Math.min(.1,Math.max(0,dt));
        const next=Math.floor(inst.elapsed*inst.fps)%n;
        if(next!==inst.frame)this.setPoseFrame(inst,next);
      }
    }
    // One InstancedMesh per prop type for normal camera elevation. At extreme
    // horizon angles, draw a *same-stack-derived* 4-way projection per batch.
    for(const batch of this.batches){
      const a=batch.asset,first=batch.placements[0];
      const fp=first.position||[0,0,0],dx=camera.position.x-fp[0],
        dz=camera.position.z-fp[2],dy=camera.position.y-fp[1]-a.dimensions[1]*.5;
      const edge=Math.abs(Math.atan2(dy,Math.hypot(dx,dz)))<.095;
      batch.mesh.visible=!edge;
      for(const b of batch.proxies){b.visible=false;b.count=0;}
      if(!edge)continue;
      const obj=new THREE.Object3D(),counts=[0,0,0,0];
      for(const p of batch.placements){
        const pos=p.position||[0,0,0],vx=camera.position.x-pos[0],vz=camera.position.z-pos[2],
            az=Math.atan2(vx,vz),local=az-(p.rotationY||0);
        const dir=((Math.round(local/(Math.PI/2))%4)+4)%4;
        obj.position.set(...pos);obj.rotation.set(0,az,0);
        obj.scale.setScalar(p.scale??1);obj.updateMatrix();
        batch.proxies[dir].setMatrixAt(counts[dir]++,obj.matrix);
      }
      for(let i=0;i<4;i++){const pr=batch.proxies[i];pr.count=counts[i];
        if(pr.count){pr.visible=true;pr.instanceMatrix.needsUpdate=true;}}
    }
  }
  attachModelTo(parent,instance,{hideMeshes=[]}={}){
    if(!parent||!instance)return;
    if(parent!==instance.root.parent){instance.root.removeFromParent();parent.add(instance.root);instance.root.position.set(0,0,0);}
    for(const m of hideMeshes)if(m)m.visible=false;
  }
  destroy(){
    for(const i of this.instances)i.root.removeFromParent();
    for(const b of this.batches){b.mesh.removeFromParent();for(const pr of b.proxies){pr.removeFromParent();pr.geometry.dispose();}}
    for(const v of this.materials.values()){
      v.geometry.dispose();v.material.map.dispose();v.material.dispose();
      v.proxyGeometry.dispose();v.proxyMaterial.map.dispose();v.proxyMaterial.dispose();
    }
    this.materials.clear();this.textures.clear();this.instances=[];this.batches=[];
  }
}
