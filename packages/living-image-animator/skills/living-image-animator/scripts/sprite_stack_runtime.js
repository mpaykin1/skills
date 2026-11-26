/* Living Image Animator | authentic Sprite Stacking via official Three.js WebGL2 Data3DTexture.
   All body poses, slice PNGs and volume pivots come from verified author assets.
   This runtime never deforms, morphs, scales or invents character animation. */
(async function runAuthenticStacks(){
'use strict';
const error = document.getElementById('err');
const throwVisible = (e) => {error.textContent='Sprite Stacking: '+String(e && e.message||e);error.style.display='flex';};
try {
  if(typeof WebGL2RenderingContext==='undefined') throw new Error('WebGL2 is required for true volume textures');
  if(!LIA_STACK.raymarch_3d||!LIA_STACK.original_source_unchanged)throw new Error('Unverified original volume source');
  // Three ESM is bundled immediately above this runtime in the SAME module block.
  const THREE={Scene,WebGLRenderer,OrthographicCamera,BoxGeometry,Mesh,Group,ShaderMaterial,
    Vector2,Vector3,Raycaster,Data3DTexture,RGBAFormat,UnsignedByteType,NearestFilter,
    ClampToEdgeWrapping,GLSL3,DoubleSide,Color};
  const scene=new THREE.Scene();
  const renderer=new THREE.WebGLRenderer({antialias:false,alpha:true,powerPreference:'high-performance'});
  renderer.setPixelRatio(Math.min(devicePixelRatio||1,2));
  renderer.setSize(window.innerWidth,window.innerHeight);
  renderer.setClearColor(new THREE.Color('#0a1018'),0);
  document.body.style.backgroundImage=`linear-gradient(#070d17aa,#070b10cc),url('${LIA_STACK.background}')`;
  document.body.style.backgroundPosition='center';document.body.style.backgroundSize='cover';
  document.body.appendChild(renderer.domElement);
  const camera=new THREE.OrthographicCamera(-10,10,10,-10,.01,1000000);
  camera.up.set(0,0,1);
  const target=new THREE.Vector3(...LIA_STACK.camera.target);
  let yaw=LIA_STACK.camera.azimuth*Math.PI/180;
  let pitch=LIA_STACK.camera.elevation*Math.PI/180;
  let distance=LIA_STACK.camera.distance;
  const initialDistance=distance;
  const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
  function syncCamera(){
    const cp=Math.cos(pitch);
    camera.position.set(target.x+distance*cp*Math.cos(yaw),
                        target.y+distance*cp*Math.sin(yaw),target.z+distance*Math.sin(pitch));
    camera.lookAt(target);
    const aspect=Math.max(.3,innerWidth/Math.max(1,innerHeight));
    const size=distance*.38;
    camera.left=-size*aspect;camera.right=size*aspect;camera.top=size;camera.bottom=-size;
    camera.near=Math.max(.01,distance/2000);camera.far=Math.max(1000,distance*80);
    camera.updateProjectionMatrix();
  }
  syncCamera();
  addEventListener('resize',()=>{renderer.setSize(innerWidth,innerHeight);syncCamera();});
  const VERT=`
    out vec3 vLocal;
    out vec3 vEye;
    void main(){
      vLocal=position;
      vEye=(inverse(modelMatrix)*vec4(cameraPosition,1.0)).xyz;
      gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);
    }`;
  const FRAG=`
    precision highp float;
    precision highp sampler3D;
    in vec3 vLocal;
    in vec3 vEye;
    uniform sampler3D uVolume;
    uniform float uGrid;
    uniform float uDepth;
    uniform float uSampleStride;
    uniform vec3 uLight;
    uniform vec3 uFog;
    uniform float uFogStart;
    uniform float uFogEnd;
    out vec4 outColor;
    vec2 intersectBox(vec3 origin,vec3 dir){
      vec3 q=sign(dir)/max(abs(dir),vec3(.000001));
      vec3 a=(-vec3(.5)-origin)*q, b=(vec3(.5)-origin)*q;
      vec3 lo=min(a,b),hi=max(a,b);
      return vec2(max(max(lo.x,lo.y),lo.z),min(min(hi.x,hi.y),hi.z));
    }
    float occupied(vec3 uv){return texture(uVolume,uv).a;}
    void main(){
      vec3 dir=normalize(vLocal-vEye);
      vec2 hit=intersectBox(vEye,dir);
      if(hit.y<max(hit.x,0.0))discard;
      float grid=max(uGrid,uDepth);
      float stepSize=1.01*uSampleStride/grid;
      float t=max(0.0,hit.x)+stepSize*.35;
      for(int j=0;j<960;j++){
        if(t>hit.y||t>max(0.0,hit.x)+2.0)break;
        vec3 p=vEye+dir*t;
        vec3 uv=vec3(p.x+.5,.5-p.y,p.z+.5);
        if(all(greaterThanEqual(uv,vec3(0.0)))&&all(lessThanEqual(uv,vec3(1.0)))){
          vec4 c=texture(uVolume,uv);
          if(c.a>.45){
            vec3 delta=vec3(1.0/uGrid,1.0/uGrid,1.0/uDepth);
            vec3 n=vec3(occupied(uv-vec3(delta.x,0,0))-occupied(uv+vec3(delta.x,0,0)),
                        occupied(uv-vec3(0,delta.y,0))-occupied(uv+vec3(0,delta.y,0)),
                        occupied(uv-vec3(0,0,delta.z))-occupied(uv+vec3(0,0,delta.z)));
            if(length(n)<.12)n=-dir;else n=normalize(n);
            float shade=.72+.28*max(0.0,dot(normalize(uLight),n));
            vec4 clip=projectionMatrix*modelViewMatrix*vec4(p,1.0);
            gl_FragDepth=clamp((clip.z/clip.w)*.5+.5,0.0,1.0);
            float fog=clamp((distance(cameraPosition,(modelMatrix*vec4(p,1.0)).xyz)-uFogStart)/
                              max(.0001,uFogEnd-uFogStart),0.0,1.0);
            outColor=vec4(mix(c.rgb*shade,uFog,fog*.85),1.0);
            return;
          }
        }
        t+=stepSize;
      }
      discard;
    }`;
  async function decodeStack(src){
    if(!src||!Array.isArray(src.slices)||src.slices.length!==src.depth)throw new Error('Missing genuine source sprite slices');
    const N=src.size,D=src.depth;
    const buffer=new Uint8Array(N*N*D*4);
    const canvas=document.createElement('canvas');canvas.width=canvas.height=N;
    const ctx=canvas.getContext('2d',{willReadFrequently:true});if(!ctx)throw new Error('2D PNG source decoder unavailable');
    for(let z=0;z<D;z++){
      const img=new Image();img.src=src.slices[z];
      if(img.decode)await img.decode();else await new Promise((resolve,reject)=>{img.onload=resolve;img.onerror=reject;});
      if(img.width!==N||img.height!==N)throw new Error('Unregistered source slice geometry');
      ctx.clearRect(0,0,N,N);ctx.drawImage(img,0,0);
      buffer.set(ctx.getImageData(0,0,N,N).data,z*N*N*4);
    }
    const tex=new THREE.Data3DTexture(buffer,N,N,D);
    tex.format=THREE.RGBAFormat;tex.type=THREE.UnsignedByteType;
    tex.magFilter=THREE.NearestFilter;tex.minFilter=THREE.NearestFilter;
    tex.wrapS=tex.wrapT=tex.wrapR=THREE.ClampToEdgeWrapping;
    tex.unpackAlignment=1;tex.generateMipmaps=false;tex.needsUpdate=true;
    return tex;
  }
  const cache=new Map();
  async function getTexture(s){
    if(cache.has(s.sha256))return cache.get(s.sha256);
    const tex=await decodeStack(s);cache.set(s.sha256,tex);return tex;
  }
  const unitBox=new THREE.BoxGeometry(1,1,1);
  const fallbackFog=new THREE.Vector3(.035,.057,.077);
  function volumeMaterial(src,tex){
    return new THREE.ShaderMaterial({glslVersion:THREE.GLSL3,vertexShader:VERT,fragmentShader:FRAG,
      side:THREE.DoubleSide,depthTest:true,depthWrite:true,transparent:false,
      uniforms:{uVolume:{value:tex},uGrid:{value:src.size},uDepth:{value:src.depth},
        uLight:{value:new THREE.Vector3(.45,.6,.8)},uSampleStride:{value:1.0},uFog:{value:fallbackFog},
        uFogStart:{value:distance*1.3},uFogEnd:{value:distance*4.5}}});
  }
  function meshFor(src,tex){
    const mesh=new THREE.Mesh(unitBox,volumeMaterial(src,tex));
    mesh.scale.set(src.size*src.spacing[0],src.size*src.spacing[1],src.depth*src.spacing[2]);
    mesh.position.set(-src.pivot[0],-src.pivot[1],-src.pivot[2]);
    mesh.frustumCulled=true;
    return mesh;
  }
  const objects=new Map(),clickables=[];
  for(const spec of LIA_STACK.objects){
    const parent=spec.parent?objects.get(spec.parent)?.group:scene;
    if(!parent)throw new Error('Missing approved rigid parent object '+spec.parent);
    const group=new THREE.Group();group.position.set(...spec.position);group.rotation.z=spec.yaw*Math.PI/180;
    parent.add(group);
    const mesh=meshFor(spec.stack,await getTexture(spec.stack));group.add(mesh);
    const obj={spec,group,mesh,active:false,progress:0,goal:0};
    objects.set(spec.id,obj);mesh.userData.volume=obj;
    if(spec.motion)clickables.push(mesh);
    if(spec.motion?.trigger==='auto')obj.goal=1;
  }
  const actorStacks=[];
  for(const actor of LIA_STACK.actors){
    const group=new THREE.Group();group.position.set(...actor.position);group.rotation.z=actor.yaw*Math.PI/180;
    scene.add(group);
    const first=actor.frames[0];const mesh=meshFor(first,await getTexture(first));group.add(mesh);
    const textures=[];
    for(const frame of actor.frames)textures.push(await getTexture(frame));
    const clips=new Map();
    for(let i=0;i<actor.actions.length;i++){
      if(!clips.has(actor.actions[i]))clips.set(actor.actions[i],[]);
      clips.get(actor.actions[i]).push(i);
    }
    const benign=['idle','stand','rest','breathe','look','walk','run'];
    const starting=benign.find(name=>clips.has(name))||null;
    actorStacks.push({actor,group,mesh,textures,last:0,clips,current:starting,actionStart:performance.now()});
  }
  // Start only source-authored rigid motion. Never auto-attack or generate new poses.
  let clockStart=performance.now(),lastTime=performance.now();
  function draw(now){
    requestAnimationFrame(draw);
    const dt=clamp((now-lastTime)/1000,0,.05);lastTime=now;
    for(const o of objects.values()){
      const spec=o.spec,m=spec.motion;
      if(!m)continue;
      const axis=m.axis||'z';
      const duration=m.duration||1.5;
      if(m.type==='hinge'){
        o.progress+=(o.goal-o.progress)*Math.min(1,dt*5/duration);
        o.group.rotation[axis]=(axis==='z'?spec.yaw*Math.PI/180:0)+(m.degrees||90)*Math.PI/180*(o.progress*o.progress*(3-2*o.progress));
      }else if(m.type==='spin'&&m.trigger==='auto'){
        o.group.rotation[axis]+=(m.degrees||90)*Math.PI/180*dt/duration;
      }else if(m.type==='spin'&&o.active){
        o.group.rotation[axis]+=(m.degrees||90)*Math.PI/180*dt/duration;
      }
    }
    // Whole independently painted volume pose swaps; NO skinning, morph, deform or vertex motion.
    const seconds=(now-clockStart)/1000;
    for(const item of actorStacks){
      const a=item.actor;
      const frames=item.current?item.clips.get(item.current):null;
      const clipLocal=frames?Math.floor((now-item.actionStart)/1000*a.fps)%frames.length:0;
      const i=frames?frames[clipLocal]:0;
      if(item.last!==i){
        item.mesh.material.uniforms.uVolume.value=item.textures[i];
        item.last=i;
      }
      // Real source-authored walk/run path moves the whole intact 3D pose stack.
      // Clip frames and world path share the approved original 2D frame index.
      const path=a.path;
      if(Array.isArray(path)&&path.length>=2&&['walk','run','stairs_up','stairs_down'].includes(item.current)){
        let j=1;while(j<path.length-1&&path[j].frame<i)j++;
        const prev=path[j-1],next=path[j];
        const t=clamp((i-prev.frame)/Math.max(1,next.frame-prev.frame),0,1);
        const smooth=t*t*(3-2*t);
        item.group.position.set(a.position[0]+prev.dx+(next.dx-prev.dx)*smooth,
                                a.position[1]+prev.dy+(next.dy-prev.dy)*smooth,a.position[2]);
      }
    }
    syncCamera();renderer.render(scene,camera);
  }
  requestAnimationFrame(draw);
  let dragging=null,moved=false;
  const pointers=new Map();let pinch=null;
  renderer.domElement.addEventListener('pointerdown',e=>{
    renderer.domElement.setPointerCapture(e.pointerId);
    pointers.set(e.pointerId,[e.clientX,e.clientY]);
    if(pointers.size===1){dragging=[e.clientX,e.clientY];moved=false;}
    if(pointers.size===2){const points=[...pointers.values()];pinch=Math.hypot(points[0][0]-points[1][0],points[0][1]-points[1][1]);}
  });
  renderer.domElement.addEventListener('pointermove',e=>{
    if(!pointers.has(e.pointerId))return;
    const before=pointers.get(e.pointerId);pointers.set(e.pointerId,[e.clientX,e.clientY]);
    if(pointers.size===2){
      const ps=[...pointers.values()];const d=Math.hypot(ps[0][0]-ps[1][0],ps[0][1]-ps[1][1]);
      if(pinch)distance=clamp(distance*pinch/Math.max(1,d),initialDistance*.13,initialDistance*8);
      pinch=d;moved=true;
    }else{
      const dx=e.clientX-before[0],dy=e.clientY-before[1];
      yaw-=dx*.008;pitch=clamp(pitch+dy*.008,-Math.PI*.495,Math.PI*.495);
      if(dragging&&Math.hypot(e.clientX-dragging[0],e.clientY-dragging[1])>5)moved=true;
    }
  });
  renderer.domElement.addEventListener('pointerup',e=>{
    pointers.delete(e.pointerId);if(pointers.size<2)pinch=null;
    if(moved||clickables.length===0)return;
    const ndc=new THREE.Vector2(e.clientX/innerWidth*2-1,-e.clientY/innerHeight*2+1);
    const ray=new THREE.Raycaster();ray.setFromCamera(ndc,camera);
    const hits=ray.intersectObjects(clickables,false);
    if(hits.length){const o=hits[0].object.userData.volume;if(o.spec.motion.type==='hinge')o.goal=1-o.goal;else o.active=!o.active;}
  });
  renderer.domElement.addEventListener('pointercancel',e=>{pointers.delete(e.pointerId);pinch=null;});
  renderer.domElement.addEventListener('wheel',e=>{e.preventDefault();distance=clamp(distance*Math.exp(e.deltaY*.001),initialDistance*.13,initialDistance*8);},{passive:false});
  addEventListener('keydown',e=>{
    if(e.code==='ArrowLeft')yaw-=.08;if(e.code==='ArrowRight')yaw+=.08;
    if(e.code==='ArrowUp')pitch=clamp(pitch+.08,-1.56,1.56);
    if(e.code==='ArrowDown')pitch=clamp(pitch-.08,-1.56,1.56);
    if(e.code==='Equal'||e.code==='NumpadAdd')distance*=.9;
    if(e.code==='Minus'||e.code==='NumpadSubtract')distance*=1.1;
    distance=clamp(distance,initialDistance*.13,initialDistance*8);
  });
  document.addEventListener('visibilitychange',()=>{lastTime=performance.now();});
  window.__livingStack3D={engine:'Three.js Data3DTexture',objectCount:objects.size,
    actorCount:actorStacks.length,volumeTextures:cache.size,sourceOnly:true,
    setAction:(actorId,action)=>{const a=actorStacks.find(v=>v.actor.id===actorId);
      if(!a||!a.clips.has(action))return false;
      a.current=action;a.actionStart=performance.now();return true;},
    orbit:(azimuth,elevation)=>{yaw=azimuth*Math.PI/180;pitch=clamp(elevation,-89,89)*Math.PI/180;},
    toggle:(id)=>{const o=objects.get(id);if(!o||!o.spec.motion)return false;o.goal=1-o.goal;return true;}};
}catch(e){throwVisible(e);}
})();
