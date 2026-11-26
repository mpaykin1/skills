// Original RGBA slices -> genuine WebGL2 volume ray traversal, exact first-hit depth.
// The original Godot / Unity engine remains the sole authority for gameplay.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

const source=document.getElementById('stack-payload');
const data=JSON.parse(source.textContent);
const host=document.getElementById('scene');
const status=document.getElementById('status');
const loading=document.getElementById('loading');
const orbitButton=document.getElementById('orbit');
const resetButton=document.getElementById('reset');
const nav=document.querySelector('nav');
const scene=new THREE.Scene();
scene.background=new THREE.Color(0x070b10);
const camera=new THREE.PerspectiveCamera(47,1,.02,10000);
camera.up.set(0,0,1);
const volumes=new Map();
let deviceMax3D=256;
const objects=[];
let renderer,controls,home,center;
let elapsed=0,playPoses=false,autorotate=false,shading=false,slowFrames=0;
const mainLight=new THREE.Vector3(.5,-.55,.7).normalize();

const VS=`
out vec3 localPosition;
void main() {
 localPosition = position;
 gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);
}`;
const FS=`
precision highp float;
precision highp sampler3D;
uniform highp sampler3D volume;
uniform vec3 volumeSize;
uniform vec3 dimensions;
uniform vec3 cameraLocal;
uniform vec3 lightLocal;
uniform mat4 modelViewProjection;
uniform float shadingAmount;
in vec3 localPosition;
out vec4 fragColor;
void main(){
 vec3 rd=normalize(localPosition-cameraLocal);
 vec3 safeDir=vec3(abs(rd.x)<1e-8?(rd.x<0.0?-1e-8:1e-8):rd.x,
                    abs(rd.y)<1e-8?(rd.y<0.0?-1e-8:1e-8):rd.y,
                    abs(rd.z)<1e-8?(rd.z<0.0?-1e-8:1e-8):rd.z);
 vec3 inv=1.0/safeDir;
 vec3 nearT=(-volumeSize*0.5-cameraLocal)*inv;
 vec3 farT=(volumeSize*0.5-cameraLocal)*inv;
 float tEnter=max(max(min(nearT.x,farT.x),min(nearT.y,farT.y)),min(nearT.z,farT.z));
 float tExit=min(min(max(nearT.x,farT.x),max(nearT.y,farT.y)),max(nearT.z,farT.z));
 if(tExit<max(tEnter,0.0))discard;
 vec3 cellPitch=volumeSize/dimensions;
 float eps=0.00002*min(min(cellPitch.x,cellPitch.y),cellPitch.z);
 float t=max(tEnter,0.0)+eps;
 vec3 pos=cameraLocal+rd*t;
 vec3 cell=clamp(floor((pos+0.5*volumeSize)/cellPitch),vec3(0),dimensions-1.0);
 vec3 dir=sign(rd);
 vec3 nextBoundary=(cell+max(dir,vec3(0)))*cellPitch-volumeSize*0.5;
 vec3 tMax=vec3(abs(rd.x)<1e-8?1e20:(nextBoundary.x-cameraLocal.x)/rd.x,
                abs(rd.y)<1e-8?1e20:(nextBoundary.y-cameraLocal.y)/rd.y,
                abs(rd.z)<1e-8?1e20:(nextBoundary.z-cameraLocal.z)/rd.z);
 vec3 tStep=cellPitch/max(abs(rd),vec3(1e-8));
 vec3 normal=vec3(0,0,1);
 for(int i=0;i<1152;i++) {
  vec4 voxel=texelFetch(volume,ivec3(cell),0);
  if(voxel.a>=0.5) {
    // Depth must be the NEAREST FRONT face of the occupied voxel, not its center.
    vec3 hit=cameraLocal+rd*max(t-eps,0.0);
    vec4 clip=modelViewProjection*vec4(hit,1.0);
    if(clip.w<=0.0)discard;
    gl_FragDepth=clamp(0.5+0.5*clip.z/clip.w,0.0,1.0);
    float light=max(dot(normalize(normal),normalize(lightLocal)),0.0);
    float factor=mix(1.0,0.72+0.28*light,shadingAmount);
    fragColor=vec4(voxel.rgb*factor,1.0);
    return;
  }
  float stepT=min(tMax.x,min(tMax.y,tMax.z));
  if(stepT>tExit)break;
  vec3 axis=vec3(float(tMax.x<=stepT+1e-7),
                 float(tMax.y<=stepT+1e-7),float(tMax.z<=stepT+1e-7));
  cell+=axis*dir;
  tMax+=axis*tStep;
  normal=-axis*dir;
  t=stepT+eps;
  if(any(lessThan(cell,vec3(0)))||any(greaterThanEqual(cell,dimensions)))break;
 }
 discard;
}`;

function decode(b64) {
 const output=new Uint8Array(Math.floor(b64.length*3/4)+3);
 let offset=0;
 for(let i=0;i<b64.length;i+=4*16384){
   const chunk=atob(b64.slice(i,i+4*16384));
   for(let j=0;j<chunk.length;j++)output[offset++]=chunk.charCodeAt(j);
 }
 return output.subarray(0,offset);
}
function volumeTexture(index){
 if(volumes.has(index))return volumes.get(index);
 const s=data.volumes[index];
 if(!s)throw new Error('Не найден реальный стек '+index);
 const [w,h,z]=s.dims;
 if(w<1||h<1||z<1||w>512||h>512||z>256 || Math.max(w,h,z)>deviceMax3D)throw new Error('RGBA объём превышает лимит 3D-текстур GPU');
 const bytes=decode(s.rgba);
 if(bytes.length!==w*h*z*4)throw new Error('Corrupt RGBA slice data: '+s.name);
 const texture=new THREE.Data3DTexture(bytes,w,h,z);
 texture.format=THREE.RGBAFormat;
 texture.type=THREE.UnsignedByteType;
 texture.minFilter=THREE.NearestFilter;
 texture.magFilter=THREE.NearestFilter;
 texture.unpackAlignment=1;
 texture.generateMipmaps=false;
 texture.colorSpace=THREE.SRGBColorSpace;
 texture.needsUpdate=true;
 volumes.set(index,texture);
 return texture;
}
function addStack(item){
 const v=data.volumes[item.volume];
 if(!v)throw new Error('Stack asset unavailable: '+item.volume);
 const frames=item.frames?.length?item.frames:[item.volume];
 for(const frame of frames){
   const next=data.volumes[frame];
   if(!next||next.dims.some((n,j)=>n!==v.dims[j])||
      next.spacing.some((n,j)=>Math.abs(n-v.spacing[j])>1e-7)||
      next.pivot.some((n,j)=>Math.abs(n-v.pivot[j])>1e-6)){
     throw new Error('Full-body pose volume frame has different dimensions, spacing or pivot');
   }
   volumeTexture(frame);
 }
 const [nx,ny,nz]=v.dims;
 const size=new THREE.Vector3(nx*v.spacing[0],ny*v.spacing[1],nz*v.spacing[2]);
 const mat=new THREE.ShaderMaterial({
   glslVersion:THREE.GLSL3,vertexShader:VS,fragmentShader:FS,
   transparent:false,depthTest:true,depthWrite:true,side:THREE.DoubleSide,
   uniforms:{volume:{value:volumeTexture(item.volume)},
     volumeSize:{value:size},dimensions:{value:new THREE.Vector3(nx,ny,nz)},
     cameraLocal:{value:new THREE.Vector3()},lightLocal:{value:mainLight.clone()},
     modelViewProjection:{value:new THREE.Matrix4()},shadingAmount:{value:0}}
 });
 const mesh=new THREE.Mesh(new THREE.BoxGeometry(size.x,size.y,size.z),mat);
 mesh.position.fromArray(item.position);
 mesh.rotation.set(...item.rotation,'XYZ');
 mesh.scale.fromArray(item.scale);
 scene.add(mesh);
 objects.push({mesh,mat,frames,fps:Math.max(1,Math.min(30,item.fps||12)),frame:-1});
}
function addButton(label,click){
 const b=document.createElement('button');b.type='button';b.textContent=label;
 b.addEventListener('click',click);nav?.appendChild(b);return b;
}
function resize(){
 const w=Math.max(1,host.clientWidth),h=Math.max(1,host.clientHeight);
 renderer.setSize(w,h,false);camera.aspect=w/h;camera.updateProjectionMatrix();
}
try {
 renderer=new THREE.WebGLRenderer({antialias:true,powerPreference:'high-performance'});
 const gl=renderer.getContext();
 if(!(gl instanceof WebGL2RenderingContext))throw new Error('Объёмная текстура требует WebGL2');
 deviceMax3D=gl.getParameter(gl.MAX_3D_TEXTURE_SIZE)||256;
 renderer.outputColorSpace=THREE.SRGBColorSpace;
 renderer.toneMapping=THREE.NoToneMapping;
 renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,2));
 host.appendChild(renderer.domElement);
 for(const item of data.items)addStack(item);
 if(!objects.length)throw new Error('Нет исходных RGBA 3D-стеков');
 const bounds=new THREE.Box3();objects.forEach(o=>bounds.expandByObject(o.mesh));
 center=bounds.getCenter(new THREE.Vector3());
 const diameter=Math.max(.5,bounds.getSize(new THREE.Vector3()).length()*.55);
 home=center.clone().add(new THREE.Vector3(diameter*1.4,-diameter*1.6,diameter));
 camera.position.copy(home);
 camera.near=Math.max(.001,diameter*.001);
 camera.far=Math.max(100,diameter*80);
 camera.updateProjectionMatrix();
 controls=new OrbitControls(camera,renderer.domElement);
 controls.target.copy(center);controls.enableDamping=true;controls.dampingFactor=.065;
 controls.minDistance=Math.max(.02,diameter*.1);
 controls.maxDistance=diameter*25;
 controls.autoRotate=false;controls.update();
 resize();window.addEventListener('resize',resize);
 const obs=new ResizeObserver(resize);obs.observe(host);
 orbitButton?.addEventListener('click',()=>{
   autorotate=!autorotate;controls.autoRotate=autorotate;
   orbitButton.textContent=autorotate?'Стоп 360°':'Обзор 360°';
 });
 resetButton?.addEventListener('click',()=>{
   camera.position.copy(home);controls.target.copy(center);controls.update();
 });
 if(objects.some(o=>o.frames.length>1)){
   const pose=addButton('▶ Позы',()=>{
     playPoses=!playPoses;pose.textContent=playPoses?'❚❚ Позы':'▶ Позы';
   });
 }
 const shadeButton=addButton('Свет: исходный',()=>{
   shading=!shading;
   shadeButton.textContent=shading?'Свет: рельеф':'Свет: исходный';
   for(const obj of objects)obj.mat.uniforms.shadingAmount.value=shading?1:0;
 });
 status.textContent=`${objects.length} независимых объёмов · ${data.layerCount} RGBA-срезов · WebGL2`;
 loading.hidden=true;
 const clock=new THREE.Clock();
 const q=new THREE.Quaternion();const light=mainLight.clone();
 function frame(){
   requestAnimationFrame(frame);
   if(document.hidden){clock.getDelta();return;}
   const delta=Math.min(.1,clock.getDelta());
   if(playPoses)elapsed+=delta;
   controls.update();
   scene.updateMatrixWorld(true);camera.updateMatrixWorld(true);
   for(const obj of objects){
     const {mesh,mat}=obj;
     if(obj.frames.length>1){
       const next=playPoses?Math.floor(elapsed*obj.fps)%obj.frames.length:0;
       if(next!==obj.frame){mat.uniforms.volume.value=volumeTexture(obj.frames[next]);obj.frame=next;}
     }
     mat.uniforms.cameraLocal.value.copy(mesh.worldToLocal(camera.position.clone()));
     mesh.getWorldQuaternion(q);
     mat.uniforms.lightLocal.value.copy(light).applyQuaternion(q.invert()).normalize();
     mat.uniforms.modelViewProjection.value.multiplyMatrices(camera.projectionMatrix,camera.matrixWorldInverse).multiply(mesh.matrixWorld);
   }
   renderer.render(scene,camera);
   if(delta>1/28)slowFrames++;else slowFrames=Math.max(0,slowFrames-2);
   if(slowFrames>24 && renderer.getPixelRatio()>1){renderer.setPixelRatio(1);resize();slowFrames=0;}
 }
 frame();
}catch(error){
 status.textContent='Оригинальный стек не может быть показан: '+String(error?.message||error);
 loading.textContent='WebGL2 недоступен или данные повреждены';loading.hidden=false;
}
