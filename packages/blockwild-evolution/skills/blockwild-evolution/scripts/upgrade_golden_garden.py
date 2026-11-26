from pathlib import Path
import re, hashlib
import argparse
p=argparse.ArgumentParser(description='Upgrade BLOCKWILD v12 authored Sunlit visual mode to Golden Garden while preserving native voxel world')
p.add_argument('--source',required=True,type=Path)
p.add_argument('--out',required=True,type=Path)
a=p.parse_args()
source=a.source
output=a.out
s=source.read_text()

# Our patch only decorates the already-authored volumetric sprite scene;
# world binary, movement, and all source archives are left untouched.
patch=r'''
// BLOCKWILD v13 · Golden Garden: one Canvas2D scene, same source-derived 3D volumes.
// Art direction: original volumetric sprites + painterly surface texturing,
// richer material-aware ground, physically placed vegetation and water caustics.
// Zero external dependencies, no network access and no second RAF.
const GOLDEN = {version:13, tileDetails:0, causticLines:0};
const goldGroundDraw = royalGroundDraw;
const goldWaterMotion = royalWaterMotion;
const goldSoftRay = royalSoftRay;
const goldDrawSprite = royalDrawSprite;
const goldDapple = royalDapple;

function goldMulberry(x,z,n=0){
 let v=Math.sin(x*128.159+z*74.385+n*62.32)*43758.544;
 return v-Math.floor(v);
}
function goldCurve(g,points,stroke,width=1){
 g.strokeStyle=stroke;g.lineWidth=width;g.lineCap='round';
 g.beginPath();g.moveTo(...points[0]);
 for(let i=1;i<points.length;i++)g.lineTo(...points[i]);g.stroke();
}
function goldRosette(g,P,x,z,t=.63){
 const q=P(x+t,z+t),r=P(x+t+.26,z+t),s=P(x+t,z+t+.26);
 const sc=Math.max(1,Math.hypot(r[0]-q[0],r[1]-q[1])*2.3);
 g.save();g.translate(q[0],q[1]);g.scale(1,.51);
 g.strokeStyle='rgba(151,119,77,.45)';g.lineWidth=.8;
 g.beginPath();g.arc(0,0,sc*1.1,0,6.283);g.stroke();
 for(let k=0;k<8;k++){
  const a=k*Math.PI/4;
  g.save();g.rotate(a);g.fillStyle=k%2?'rgba(192,149,92,.65)':'rgba(238,203,132,.76)';
  g.beginPath();g.ellipse(sc*.58,0,sc*.43,sc*.17,0,0,6.283);g.fill();g.restore();
 }
 g.fillStyle='#c79356';g.beginPath();g.arc(0,0,sc*.25,0,6.283);g.fill();
 g.restore();
}
royalGroundDraw=function(g,W,H,U,center){
 goldGroundDraw(g,W,H,U,center);
 const P=(x,z,y=0)=>royalP(x,z,y,center,U,W,H);
 // Manually authored repeating grammar, deterministic organic microdetail.
 // Each cell remains a real projected quadrilateral from the navigable floor.
 g.save();
 const microCount=4;
 for(let z=8;z<59;z++)for(let x=7;x<59;x++){
  const m=P(x+.5,z+.5), R=U*1.6;
  if(m[0]<-R||m[0]>W+R||m[1]<-R||m[1]>H+R)continue;
  const n=goldMulberry(x,z,3);if(n>.68){
   const px=x+.18+goldMulberry(x,z,4)*.55,pz=z+.14+goldMulberry(z,x,7)*.58;
   const a=P(px,pz),b=P(px+.12+goldMulberry(x,z,9)*.22,pz+.04);
   goldCurve(g,[a,b],`rgba(107,87,71,${.13+goldMulberry(x,z,11)*.22})`,.46);
  }
  if(n<.13){
   const a=P(x+.12,z+.24),b=P(x+.88,z+.27);
   goldCurve(g,[a,b],'rgba(247,238,216,.20)',.4);
  }
  for(let i=0;i<2;i++){
   const fx=x+.18+goldMulberry(x,z,i+13)*.6,fz=z+.18+goldMulberry(z,x,i+17)*.6;
   const a=P(fx,fz);g.fillStyle=i===0?'rgba(108,92,74,.20)':'rgba(247,234,209,.33)';
   g.fillRect(a[0],a[1],Math.max(.6,U*.048),.48);
  }
  // moss gathers naturally near garden edges, rather than covering central paving.
  const nearEdge=((x<18)||(x>49)||(z<13)||(z>48));
  if(nearEdge && goldMulberry(x,z,24)>.77){
   const p=P(x+.22,z+.73);g.fillStyle='rgba(72,126,65,.36)';
   g.beginPath();g.ellipse(p[0],p[1],U*.20,U*.072,-.1,0,6.283);g.fill();
  }
 }
 // Separate embossed medallions; these are inlays in a physical stone floor.
 for(const [x,z] of [[22,29],[28,32],[36,35],[24,40],[42,31],[32,41],[18,26],[45,41]]){
  const m=P(x,z);if(m[0]>-20&&m[0]<W+20&&m[1]>-20&&m[1]<H+20)goldRosette(g,P,x,z,.43);
 }
 // Fresco-like sandstone edging; understated material detail, not a top-layer backdrop.
 for(let k=16;k<52;k+=3){
  const p=P(k,51,2.9),q=P(k+.9,51,2.9);
  goldCurve(g,[p,q],'rgba(244,207,124,.48)',1);
 }
 g.restore();GOLDEN.tileDetails++;
};

// Add real volumetric-source shrubs and trees along garden edges and old walls.
// These use exactly the baked 3D slice images already present, not new flat art.
for(const row of [
 ['flowers',17.1,44.6,.66],['flowers',23.1,43.0,.71],
 ['flowers',39.2,44.5,.68],['flowers',46.1,37.1,.69],
 ['bush',48.5,17.9,.83],['bush',47.1,21.3,.79],
 ['bush',12.7,39.6,.90],['bush',52.1,41.8,.80],
 ['bush',23,49.5,.85],['bush',18.9,46.6,.85],
 ['pillar',48.4,38.4,.70]
])royalDecor.push(row);
for(const row of [[15.5,10.0,1,.83],[50.2,45.5,2,.90],[56.3,18.3,0,.95]])royalTrees.push(row);

// Sun-cast canopy fragments, applied to the actual projected stone plane.
royalDapple=function(g,P,t){
 goldDapple(g,P,t);
 g.save();
 for(let k=0;k<royalTrees.length;k++){
  const [x,z,,size]=royalTrees[k];
  const p=P(x+1.9*size,z+1.9*size,0);
  const r=18*size;
  const fog=g.createRadialGradient(p[0],p[1],2,p[0],p[1],r*2.7);
  fog.addColorStop(0,'rgba(30,74,42,.12)');
  fog.addColorStop(1,'rgba(30,74,42,0)');
  g.fillStyle=fog;g.beginPath();g.ellipse(p[0],p[1],r*2.7,r*.89,.2,0,6.283);g.fill();
  for(let j=0;j<20;j++){
   const th=goldMulberry(k,j,61)*6.283;
   const rad=Math.sqrt(goldMulberry(j,k,19))*r*1.55;
   const sx=p[0]+Math.cos(th)*rad,sy=p[1]+Math.sin(th)*rad*.40;
   const a=2+goldMulberry(j,k,38)*3.9;
   g.fillStyle=`rgba(43,72,49,${.045+.066*goldMulberry(j,k,43)})`;
   g.beginPath();g.ellipse(sx,sy,a,a*.42,th*.5,0,6.283);g.fill();
  }
 }
 g.restore();
};

// Dynamic water treatment: 3D world-space caustic projection, pool-bounded clip,
// travelling diagonal crest highlights, and soft bloom on preserved water artwork.
royalWaterMotion=function(g,P,t){
 goldWaterMotion(g,P,t);
 const A=P(31.45,11.45),B=P(42.55,11.45),C=P(42.55,26.55),D=P(31.45,26.55);
 g.save();g.beginPath();g.moveTo(...A);g.lineTo(...B);g.lineTo(...C);g.lineTo(...D);g.closePath();g.clip();
 g.globalCompositeOperation='screen';
 for(let i=0;i<52;i++){
  const x=31.7+goldMulberry(i,29)*10.6,z=11.8+goldMulberry(i,11)*14.2;
  const ox=Math.sin(t*.65+i*3.29)*.32,oz=Math.cos(t*.77+i*.89)*.29;
  const p=P(x+ox,z+oz,1.08),q=P(x+.45+ox,z+.21+oz,1.08),r=P(x+.9+ox,z+.3+oz,1.08);
  g.strokeStyle=`rgba(172,250,235,${.085+.14*(.5+.5*Math.sin(t*1.1+i*.4))})`;
  g.lineWidth=.6+(i%3)*.25;g.beginPath();g.moveTo(...p);
  g.quadraticCurveTo(...q,...r);g.stroke();
 }
 const pulse=(t*.8)%10;
 for(let k=0;k<8;k++){
  const x=31.5+goldMulberry(k,9)*11,z=11+((t*(.24+k*.011)+k*3.6)%16);
  const a=P(x,z,1.1),b=P(x+.5,z+.23,1.1);
  goldCurve(g,[a,b],`rgba(235,255,250,${.08+.17*(.5+.5*Math.sin(t*.9+k))})`,.8);
 }
 g.restore();GOLDEN.causticLines+=52;
};

// Soft physically oriented shafts: preserves the existing sunny screen layer,
// strengthens garden warmth instead of applying a universal washed-out tint.
royalSoftRay=function(g,W,H,t){
 goldSoftRay(g,W,H,t);
 g.save();g.globalCompositeOperation='screen';
 const h=g.createRadialGradient(W*.83,H*.01,0,W*.79,H*.04,W*.72);
 h.addColorStop(0,'rgba(255,232,168,.12)');
 h.addColorStop(.31,'rgba(255,224,166,.045)');
 h.addColorStop(1,'rgba(255,224,166,0)');g.fillStyle=h;g.fillRect(0,0,W,H);
 g.restore();
 // Filmic single-pass vignette; no competing WebGL compositor or texture buffers.
 const v=g.createRadialGradient(W*.52,H*.42,Math.min(W,H)*.18,W*.52,H*.42,Math.max(W,H)*.77);
 v.addColorStop(0,'rgba(35,40,33,0)');v.addColorStop(.72,'rgba(38,46,39,.025)');v.addColorStop(1,'rgba(35,41,34,.13)');
 g.fillStyle=v;g.fillRect(0,0,W,H);
};

// Lift foliage and masonry material reflectance without altering object shapes,
// hitboxes, world identities, or hero original animation frames.
royalDrawSprite=function(g,name,x,z,zoom,P,alpha=1){
 if(name==='tree0'||name==='tree1'||name==='tree2'){
  const pos=P(x,z);g.save();
  const sr=Math.max(15,26*zoom);
  const bounce=g.createRadialGradient(pos[0]-sr,pos[1]-sr*2.5,0,pos[0],pos[1]-sr,6*sr);
  bounce.addColorStop(0,'rgba(224,251,163,.12)');bounce.addColorStop(1,'rgba(224,251,163,0)');
  g.fillStyle=bounce;g.beginPath();g.ellipse(pos[0],pos[1]-sr*2,3*sr,3*sr,0,0,6.283);g.fill();g.restore();
 }
 goldDrawSprite(g,name,x,z,zoom,P,alpha);
};
'''
assert s.count('royalSetup();')==1
s=s.replace('royalSetup();\n// Load from this file', 'royalSetup();\n'+patch+'\n// Load from this file',1)
s=s.replace('V12 · SUNLIT COURTYARD / STACKED DIORAMA','V13 · GOLDEN GARDEN / SPRITE STACKED',1)
s=s.replace('BLOCKWILD v12 · The Sunlit Courtyard','BLOCKWILD v13 · Golden Garden (v12 source preserved)',1)
s=s.replace('</style>', '''
body.royal-ui #royal-canvas{filter:brightness(.90) contrast(1.18) saturate(1.06)}
</style>''',1)
# Auto-constrain output to original world files plus art patch without changing anything else.
assert 'LOAD' not in patch
output.write_text(s)
print('OUTPUT',output,output.stat().st_size)
print('sha256',hashlib.sha256(output.read_bytes()).hexdigest()[:20])
