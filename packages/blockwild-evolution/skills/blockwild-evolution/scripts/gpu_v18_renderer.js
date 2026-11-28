// BLOCKWILD v18: genuine source-occupancy RGBA volume slices in WebGL2.
// Each occupied cell, color & world-space normal is baked from the SAME original
// author-created 48x48x64 3D volume. Canvas2D is a preserved fallback, not a replacement.
const BW18 = {
  version:18,volumeData:__BW18_GPU_VOLUME_DATA__, active:false,ready:false,
  gl:null,canvas:null,frames:0,draws:0,visible:0,textureTypes:0,
  resources:new Map(),placements:[],vbo:null,vao:null,sceneTexture:null,post:null,stack:null,
  offContext:false,failReason:'',gpuMS:0,lastTime:0
};
// 160 animated view names map to 20 physical full-body pose volumes.
const BW18_FACES=['front','front_right','right','back_right','back','back_left','left','front_left'];
function BW18_key(name){
 const m=/^(hero|citizen[012])_(front_right|back_right|back_left|front_left|front|back|left|right)_([0-4])$/.exec(name);
 return m?'gpu_'+m[1]+'_'+m[3]:name;
}
function BW18_angle(name){
 const m=/^(?:hero|citizen[012])_(front_right|back_right|back_left|front_left|front|back|left|right)_([0-4])$/.exec(name);
 if(!m)return 0;
 const face=name.slice(name.indexOf('_')+1,name.lastIndexOf('_'));
 return BW18_FACES.indexOf(face)*Math.PI/4;
}
const BW18_OLD_DRAW=royalDrawSprite;
royalDrawSprite=function(g,name,x,z,zoom,P,alpha=1){
  // While GPU is active, paint the original image only for props without a
  // ready source-volume atlas. Actor appearance/animation remains untouched.
  if(BW18.active&&BW18.ready&&BW18.resources.has(BW18_key(name))&&BW18.painterPass){
    const s=ROYAL_ART.SPRITES[name];
    if(s){BW18.placements.push({name,key:BW18_key(name),angle:BW18_angle(name),x,z,zoom,alpha,w:s.size[0],h:s.size[1]});
      royalShadow(g,x,z,zoom*.8,P);}
    return;
  }
  return BW18_OLD_DRAW(g,name,x,z,zoom,P,alpha);
};
const BW18_OLD_RENDER=renderRoyal;
renderRoyal=function(t){
  BW18.placements.length=0;
  BW18.painterPass=true;
  BW18_OLD_RENDER(t);
  BW18.painterPass=false;
  if(BW18.active&&BW18.ready)try{BW18_render(t)}catch(e){BW18_disable('Ошибка WebGL2: '+e.message);}
};
const BW18_OLD_SWITCH=activateRoyal;
activateRoyal=function(flag,reset=false){
  BW18_OLD_SWITCH(flag,reset);
  if(BW18.canvas)BW18.canvas.style.display=flag&&BW18.active?'block':'none';
  const cv=document.getElementById('royal-canvas');
  if(cv)cv.style.opacity=flag&&BW18.active?'0':'1';
};
const BW18_OLD_RESIZE=royalResize;
royalResize=function(){BW18_OLD_RESIZE();BW18_resize();};
function BW18_disable(reason){
  BW18.active=false;BW18.ready=false;BW18.failReason=reason;
  if(BW18.canvas)BW18.canvas.style.display='none';
  const cv=document.getElementById('royal-canvas');if(cv)cv.style.opacity='1';
  console.warn('[BLOCKWILD v18] 2.5D reserve mode:',reason);
}
function BW18_shader(gl,kind,source){
  const sh=gl.createShader(kind);gl.shaderSource(sh,source);gl.compileShader(sh);
  if(!gl.getShaderParameter(sh,gl.COMPILE_STATUS))throw Error(gl.getShaderInfoLog(sh));
  return sh;
}
function BW18_program(gl,vs,fs){
  const p=gl.createProgram();gl.attachShader(p,BW18_shader(gl,gl.VERTEX_SHADER,vs));
  gl.attachShader(p,BW18_shader(gl,gl.FRAGMENT_SHADER,fs));
  gl.linkProgram(p);if(!gl.getProgramParameter(p,gl.LINK_STATUS))throw Error(gl.getProgramInfoLog(p));
  return p;
}
const BW18_POST_VS=`#version 300 es
precision highp float;
out vec2 vUV;
void main(){
 vec2 p=vec2(float((gl_VertexID<<1)&2),float(gl_VertexID&2));
 vUV=p;gl_Position=vec4(p*2.0-1.0,0.999,1.0);
}`;
const BW18_POST_FS=`#version 300 es
precision highp float;
in vec2 vUV;out vec4 outColor;
uniform sampler2D uScene;uniform vec2 uRes;uniform float uTime;
vec3 filmic(vec3 v){return (v*(2.51*v+.03))/(v*(2.43*v+.59)+.14);}
void main(){
 vec2 uv=vUV;vec3 src=texture(uScene,uv).rgb;
 vec2 sun=vec2(.83,.93),ray=uv-sun;
 float beam=pow(max(0.,1.-abs(ray.x+ray.y*.28)*2.0),2.5);
 beam*=1.0-smoothstep(.10,1.1,length(ray));
 float grain=fract(sin(dot(floor(uv*uRes*.55),vec2(12.9898,78.233)))*43758.5453)-.5;
 // Material-sensitive luminance and shadow: no smoothing of sprite edges.
 float luma=dot(src,vec3(.23,.67,.10));
 vec3 glow=vec3(1.0,.79,.44)*beam*(.024+.013*sin(uTime*.23));
 vec3 col=src+glow;
 col=mix(col,col*vec3(.945,.975,1.035),.045*(1.0-luma));
 col+=(grain*.006);
 float vig=1.-.15*pow(length((uv-.5)*vec2(.80,1.10)),1.8);
 col=clamp(col*vig,0.,1.);
 outColor=vec4(col,1.);
}`;
// Geometry actually covers 64 discrete horizontal XY planes in world X/Z, one per
// occupied height slice, and uses independently baked occupancy normals.
const BW18_STACK_VS=`#version 300 es
precision highp float;
out vec2 vUV;out vec3 vWorld;out float vLayer;
uniform vec2 uCanvas;uniform vec2 uCenter;uniform vec3 uAnchor;uniform vec3 uSize;
uniform float uU;uniform float uAngle;
void main(){
  vec2 p;
  int k=gl_VertexID%6;
  if(k==0)p=vec2(0.,0.); else if(k==1||k==4)p=vec2(1.,0.);
  else if(k==2||k==3)p=vec2(0.,1.);else p=vec2(1.,1.);
  float layer=float(gl_InstanceID);
  vec2 local=(p-.5)*uSize.xz;
  float cs=cos(uAngle),sn=sin(uAngle);
  float wx=uAnchor.x+local.x*cs-local.y*sn;
  float wz=uAnchor.z+local.x*sn+local.y*cs;
  float wy=uAnchor.y+layer/63.*uSize.y;
  float sx=uCanvas.x*.5+(wx-uCenter.x-wz+uCenter.y)*uU*.91;
  float sy=uCanvas.y*(uCanvas.x<uCanvas.y?.525:.57)+(wx-uCenter.x+wz-uCenter.y)*uU*.455-wy*uU*.91;
  vec2 ndc=vec2(sx/uCanvas.x*2.-1.,1.-sy/uCanvas.y*2.);
  // 3D depth in the same authored isometric camera coordinate system.
  float depth=clamp(-(.13*(wx-uCenter.x+wz-uCenter.y)+.15*wy)/65.,-.92,.92);
  gl_Position=vec4(ndc,depth,1.);
  vec2 tile=vec2(mod(layer,8.),floor(layer/8.));
  vUV=(tile+p)/8.0;
  vWorld=vec3(wx,wy,wz);vLayer=layer;
}`;
const BW18_STACK_FS=`#version 300 es
precision highp float;
in vec2 vUV;in vec3 vWorld;in float vLayer;out vec4 outColor;
uniform sampler2D uAlbedo;uniform sampler2D uNormal;uniform vec3 uSun;uniform float uAngle;
uniform float uTime;
void main(){
  vec4 c=texture(uAlbedo,vUV);
  if(c.a<.78)discard;
  vec3 n0=normalize(texture(uNormal,vUV).rgb*2.-1.);
  float ca=cos(uAngle),sa=sin(uAngle);
  vec3 n=normalize(vec3(n0.x*ca-n0.z*sa,n0.y,n0.x*sa+n0.z*ca));
  float diffuse=max(dot(n,normalize(uSun)),0.);
  float back=clamp(dot(n,normalize(vec3(-.4,.52,-.6))),0.,1.);
  float ao=mix(.7,1.,smoothstep(0.,64.,vLayer));
  vec3 sunHue=vec3(1.08,.99,.84),skyHue=vec3(.69,.82,1.02);
  vec3 col=c.rgb*(sunHue*(.46+.47*diffuse)+skyHue*(.11+.17*back))*ao;
  float high=pow(max(0.,dot(normalize(n+uSun),normalize(vec3(.34,.8,.35)))),18.);
  col+=high*vec3(.22,.16,.075)*.12;
  // Deep volume gap illumination, slight soft daylight, no generic cube texture.
  outColor=vec4(clamp(col,0.,1.),1.0);
}`;
function BW18_newTex(gl,filter=gl.LINEAR){
 const t=gl.createTexture();gl.bindTexture(gl.TEXTURE_2D,t);
 gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,filter);
 gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,filter);
 gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE);
 gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE);
 return t;
}
async function BW18_init(){
  if(BW18.canvas)return;
  const canvas=document.createElement('canvas');canvas.id='royal-gpu';
  canvas.setAttribute('aria-label','WebGL2: 3D sprite stacking сцена с нормалями');
  canvas.style.cssText='position:absolute;inset:0;z-index:2;display:none;width:100%;height:100%;pointer-events:none;';
  document.body.appendChild(canvas);BW18.canvas=canvas;
  // Explicit requirement: keep Canvas fallback if no WebGL2 instead of black screen.
  const gl=canvas.getContext('webgl2',{antialias:true,alpha:false,depth:true,stencil:false,premultipliedAlpha:false,desynchronized:true,failIfMajorPerformanceCaveat:true});
  if(!gl){BW18_disable('WebGL2 отсутствует');return;}
  BW18.gl=gl;BW18.vao=gl.createVertexArray();gl.bindVertexArray(BW18.vao);
  try{
   BW18.post=BW18_program(gl,BW18_POST_VS,BW18_POST_FS);
   BW18.stack=BW18_program(gl,BW18_STACK_VS,BW18_STACK_FS);
   BW18.sceneTexture=BW18_newTex(gl);
   gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL,true);
   const makeImage=(uri)=>new Promise((resolve,reject)=>{
     const im=new Image();im.onload=()=>resolve(im);im.onerror=()=>reject(new Error('atlas decode'));
     im.src=uri;
   });
   for(const [name,source] of Object.entries(BW18.volumeData)){
     const [image,normal]=await Promise.all([makeImage(source.albedo),makeImage(source.normal)]);
     if(image.width!==384||normal.width!==384||image.height!==384||normal.height!==384)throw Error('Atlas size '+name);
     const a=BW18_newTex(gl,gl.NEAREST);gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,image.width,image.height,0,gl.RGBA,gl.UNSIGNED_BYTE,image);
     const n=BW18_newTex(gl,gl.NEAREST);gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,normal.width,normal.height,0,gl.RGBA,gl.UNSIGNED_BYTE,normal);
     BW18.resources.set(name,{a,n,...source});
   }
   BW18.volumeData=null; // Release base64 strings after the GPU has its textures.
   BW18.textureTypes=BW18.resources.size;
   BW18_resize();BW18.ready=true;BW18.active=true;
   canvas.style.display=royalActive?'block':'none';
   const legacy=document.getElementById('royal-canvas');if(legacy)legacy.style.opacity='0';
   canvas.addEventListener('webglcontextlost',e=>{e.preventDefault();BW18_disable('WebGL2 context lost');});
   console.info('[BLOCKWILD v18] genuine GPU volume stacks',BW18.textureTypes);
  }catch(e){BW18_disable(e.message)}
}
function BW18_resize(){
 const c=BW18.canvas;if(!c||!BW18.gl)return;
 const src=document.getElementById('royal-canvas');if(!src)return;
 if(c.width!==src.width||c.height!==src.height){
  c.width=src.width;c.height=src.height;
  const gl=BW18.gl;gl.bindTexture(gl.TEXTURE_2D,BW18.sceneTexture);
  gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,c.width,c.height,0,gl.RGBA,gl.UNSIGNED_BYTE,null);
 }
}
function BW18_render(t){
 const gl=BW18.gl,src=document.getElementById('royal-canvas');
 if(!gl||!src||gl.isContextLost())throw Error('context unavailable');
 BW18_resize();const W=BW18.canvas.width,H=BW18.canvas.height;
 const begin=performance.now();
 gl.viewport(0,0,W,H);gl.disable(gl.DEPTH_TEST);gl.disable(gl.BLEND);
 gl.bindTexture(gl.TEXTURE_2D,BW18.sceneTexture);
 gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL,true);
 gl.texSubImage2D(gl.TEXTURE_2D,0,0,0,gl.RGBA,gl.UNSIGNED_BYTE,src);
 gl.useProgram(BW18.post);gl.activeTexture(gl.TEXTURE0);gl.bindTexture(gl.TEXTURE_2D,BW18.sceneTexture);
 gl.uniform1i(gl.getUniformLocation(BW18.post,'uScene'),0);
 gl.uniform2f(gl.getUniformLocation(BW18.post,'uRes'),W,H);
 gl.uniform1f(gl.getUniformLocation(BW18.post,'uTime'),t);
 gl.drawArrays(gl.TRIANGLES,0,3);
 // Draw genuine source-volume cross sections as one instanced call per object,
 // with hardware depth test and occupancy-derived normal mapping.
 gl.enable(gl.DEPTH_TEST);gl.depthFunc(gl.LESS);gl.clearDepth(1);gl.clear(gl.DEPTH_BUFFER_BIT);
 gl.useProgram(BW18.stack);
 gl.uniform2f(gl.getUniformLocation(BW18.stack,'uCanvas'),W,H);
 gl.uniform2f(gl.getUniformLocation(BW18.stack,'uCenter'),player.x,player.z);
 gl.uniform1f(gl.getUniformLocation(BW18.stack,'uU'),Math.max(8,Math.min(W/38,H/29,24)));
 gl.uniform3f(gl.getUniformLocation(BW18.stack,'uSun'),.63,.83,.42);
 gl.uniform1f(gl.getUniformLocation(BW18.stack,'uTime'),t);
 gl.uniform1i(gl.getUniformLocation(BW18.stack,'uAlbedo'),0);
 gl.uniform1i(gl.getUniformLocation(BW18.stack,'uNormal'),1);
 let visible=0;
 const uAnchor=gl.getUniformLocation(BW18.stack,'uAnchor'),uSize=gl.getUniformLocation(BW18.stack,'uSize'),uAngle=gl.getUniformLocation(BW18.stack,'uAngle');
 for(const obj of BW18.placements){
  const data=BW18.resources.get(obj.key);if(!data||!obj.alpha)continue;
  const U=Math.max(8,Math.min(W/38,H/29,24));
  const span=Math.min(9,Math.max(2.2,obj.w*obj.zoom/(1.82*U)));
  gl.uniform3f(uAnchor,obj.x,0,obj.z);
  gl.uniform1f(uAngle,obj.angle);
  gl.uniform3f(uSize,span,span*(64/48),span);
  gl.activeTexture(gl.TEXTURE0);gl.bindTexture(gl.TEXTURE_2D,data.a);
  gl.activeTexture(gl.TEXTURE1);gl.bindTexture(gl.TEXTURE_2D,data.n);
  gl.drawArraysInstanced(gl.TRIANGLES,0,6,64);visible++;
 }
 BW18.visible=visible;BW18.frames++;BW18.draws+=visible;
 BW18.gpuMS=BW18.gpuMS*.90+(performance.now()-begin)*.10;
 if(BW18.frames%270===0 && BW18.gpuMS>47)console.warn('[BW18] expensive GPU frame',BW18.gpuMS.toFixed(1));
}
BW18_init();
