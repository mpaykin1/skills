// BLOCKWILD v12 · The Sunlit Courtyard
// Original world and all source archives remain untouched. This is a separate
// authored visual style scene. Every standing prop and animation pose was baked
// from real horizontally sliced RGBA 3D voxel volumes at build time.
const ROYAL_ART={SPRITES:__ROYAL_SPRITES__, objects:[], images:{},
 base:null,baseCtx:null,baseOrigin:[31,31],baseU:0,baseW:0,baseH:0,
 readyCount:0,prevTime:0,viewVersion:0,glow:0};
let royalActive=true;
for(const [name,a] of Object.entries(ROYAL_ART.SPRITES)){
 let im=new Image();im.decoding='async';im.src=a.uri;
 im.onload=()=>{ROYAL_ART.readyCount++;};ROYAL_ART.images[name]=im;
}
const rr=(x,z,n=0)=>{
 let t=Math.sin(x*127.127+z*311.733+n*74.23)*43758.59;
 return t-Math.floor(t);
};
function royalP(x,z,y=0,center=[player.x,player.z],U=16,W=innerWidth,H=innerHeight){
 return [W*.50+(x-center[0]-(z-center[1]))*U*.91,
  H*(W<H?.525:.57)+(x-center[0]+z-center[1])*U*.455-y*U*.91];
}
function royalPoly(g,pts,fill,stroke=null,width=1){
 g.beginPath();g.moveTo(pts[0][0],pts[0][1]);
 for(let i=1;i<pts.length;i++)g.lineTo(pts[i][0],pts[i][1]);
 g.closePath();g.fillStyle=fill;g.fill();
 if(stroke){g.strokeStyle=stroke;g.lineWidth=width;g.stroke();}
}
function royalBox(g,x,z,y,width,depth,height,colors,P){
 const xa=x-width/2,xb=x+width/2,za=z-depth/2,zb=z+depth/2;
 const a=P(xa,za,y),b=P(xb,za,y),c=P(xb,zb,y),d=P(xa,zb,y),
       A=P(xa,za,y+height),B=P(xb,za,y+height),C=P(xb,zb,y+height),D=P(xa,zb,y+height);
 royalPoly(g,[a,b,B,A],colors[1]);
 royalPoly(g,[b,c,C,B],colors[2]);
 royalPoly(g,[d,c,C,D],colors[2]);
 royalPoly(g,[A,B,C,D],colors[0],'rgba(103,78,58,.14)',.55);
}
function royalGroundDraw(g,W,H,U,center){
 const P=(x,z,y=0)=>royalP(x,z,y,center,U,W,H);
 g.fillStyle='#cbb9a7';g.fillRect(0,0,W,H);
 const sh=g.createLinearGradient(0,0,0,H);sh.addColorStop(0,'rgba(102,137,104,.24)');sh.addColorStop(.55,'rgba(252,227,197,0)');sh.addColorStop(1,'rgba(116,88,69,.12)');g.fillStyle=sh;g.fillRect(0,0,W,H);
 // These physical planar floor tiles are intentionally polygonal: stacking is
 // for props, walls and actors, not a replacement for large walkable floors.
 for(let z=8;z<59;z++)for(let x=7;x<59;x++){
  const p=P(x+.5,z+.5),r=U*1.55;
  if(p[0]<-r||p[0]>W+r||p[1]<-r||p[1]>H+r)continue;
  const a=rr(x,z),b=rr(z,x,11),tone=178+Math.round(a*31);
  const colors=['#dbccba','#d5c6b4','#cbbcaf','#e6d7c2','#d2bba8','#dfd0bd','#c3b8ac'];
  const color=colors[Math.floor(a*colors.length)];
  royalPoly(g,[P(x,z),P(x+1,z),P(x+1,z+1),P(x,z+1)],color,'rgba(93,85,78,.16)',.66);
  if(a>.93){g.strokeStyle='rgba(91,72,69,.17)';g.lineWidth=.7;g.beginPath();g.moveTo(p[0]-3,p[1]-1);g.lineTo(p[0]+2,p[1]+1);g.stroke();}
  // Antique gold paving inlays from authored plan, never arbitrary repeated noise.
  if(((x===25||x===31||x===37)&&(z===29||z===41))||((x===33||x===43)&&(z===23||z===35))){
    royalPoly(g,[P(x+.16,z+.16),P(x+.84,z+.16),P(x+.84,z+.84),P(x+.16,z+.84)],'#b18c62','#f2d090',.8);
    royalPoly(g,[P(x+.34,z+.34),P(x+.66,z+.34),P(x+.66,z+.66),P(x+.34,z+.66)],'#e7cf9c');
  }
 }
 // The teal reflecting pool is physically beneath its sandstone copings.
 const x0=31,x1=43,z0=11,z1=27;
 g.save();g.shadowColor='rgba(22,89,111,.38)';g.shadowBlur=19;
 royalPoly(g,[P(x0,z0),P(x1,z0),P(x1,z1),P(x0,z1)],'#1b9ab5','#137b96',3.4);
 g.restore();
 const wg=g.createLinearGradient(...P(39,21),...P(50,29));
 wg.addColorStop(0,'#0d829b');wg.addColorStop(.42,'#079fba');wg.addColorStop(.75,'#28bfd4');wg.addColorStop(1,'#67d4d9');
 royalPoly(g,[P(x0+.3,z0+.3),P(x1-.3,z0+.3),P(x1-.3,z1-.3),P(x0+.3,z1-.3)],wg);
 g.save();g.globalAlpha=.36;
 for(let i=0;i<150;i++){
  let xx=x0+.8+rr(i,17)*(x1-x0-1.6),zz=z0+.8+rr(i,29)*(z1-z0-1.6),p=P(xx,zz);
  g.strokeStyle=i%2?'#d9fcf4':'#98e8e8';g.lineWidth=.7;g.beginPath();g.arc(p[0],p[1],1+rr(i,23)*3,0,Math.PI*1.1);g.stroke();
 }
 g.restore();
 const sand=['#e8dbc8','#ccbaa4','#ae9884'];
 for(let x=x0;x<x1;x+=1.05){royalBox(g,x+.55,z0,0,1.05,.9,1.1,sand,P);royalBox(g,x+.55,z1,0,1.05,.9,1.1,sand,P);}
 for(let z=z0+.6;z<z1;z+=1.06){royalBox(g,x0,z+.48,0,.9,1.05,1.1,sand,P);royalBox(g,x1,z+.48,0,.9,1.05,1.1,sand,P);}
 // Far walls use full dimensional stone blocks rather than painted background.
 for(let x=15;x<50;x+=1.4){
  royalBox(g,x,8.9,0,1.40,1.5,3.4,['#d9d0c2','#a99a89','#c1afa0'],P);
  if(Math.floor(x)%6===0)royalBox(g,x,8.9,3.4,1.7,1.5,.38,['#f2e0c4','#bda98e','#d3b798'],P);
 }
 for(let z=15;z<46;z+=1.4){
  royalBox(g,52,z,0,1.3,1.35,3.9,['#d9cfbf','#b6a68f','#c6b29b'],P);
 }
 // Old garden edging / flower planters in the middle plane.
 for(let x=17;x<24;x+=1){royalBox(g,x,43,0,.98,.85,.8,['#f1ddc3','#c7af99','#d8beaa'],P);}
 for(let x=29;x<38;x+=1){royalBox(g,x,44,0,.98,.84,.8,['#e8d6c1','#c8af9c','#ddbfaa'],P);}
 // Front parapet with gold-trimmed merlons, intentionally kept at bottom edge.
 for(let x=13;x<53;x+=1.5){
  royalBox(g,x,52,0,1.48,1.35,3.1,['#e5d1bd','#b59d8d','#cdb3a5'],P);
  if(Math.floor(x)%5===0)royalBox(g,x,52,3.1,1.8,1.55,.7,['#f1d5ac','#bca077','#d1ac75'],P);
 }
}
function royalShadow(g,x,z,scale,P){
 const p=P(x,z);g.save();g.fillStyle='rgba(59,46,43,.18)';g.shadowColor='rgba(70,46,28,.20)';g.shadowBlur=9;
 g.beginPath();g.ellipse(p[0]+10*scale,p[1]+8*scale,20*scale,7*scale,-.28,0,2*Math.PI);g.fill();g.restore();
}
function royalDrawSprite(g,name,x,z,zoom,P,alpha=1){
 const spec=ROYAL_ART.SPRITES[name],img=ROYAL_ART.images[name];if(!spec||!img||!img.complete||!img.naturalWidth)return;
 const p=P(x,z);let sw=spec.size[0]*zoom,sh=spec.size[1]*zoom;
 g.save();g.globalAlpha=alpha;g.drawImage(img,p[0]-spec.base[0]*zoom,p[1]-spec.base[1]*zoom,sw,sh);g.restore();
}
function royalDapple(g,P,t){
 g.save();g.fillStyle='rgba(55,77,43,.11)';
 for(let k=0;k<royalTrees.length;k++){
  const [x,z,v,m]=royalTrees[k];
  for(let j=0;j<44;j++){
    const angle=rr(j,k+27)*6.283,rad=Math.sqrt(rr(j+24,k+9))*3.7*m;
    const p=P(x+Math.cos(angle)*rad+1.1,z+Math.sin(angle)*rad+1.9);
    const sway=Math.sin(t*.5+j+9*k)*.5;
    g.beginPath();g.ellipse(p[0]+sway,p[1],1.1+rr(j,k+71)*2.9,.5+rr(k,j+8)*1.8,angle*.4,0,6.283);g.fill();
  }
 }
 g.restore();
}
const royalTrees=[
 [13.9,18.7,0,1.04],[20.2,15.0,1,1.20],[25.7,11.2,2,.91],
 [50.9,15.4,0,1.07],[54.3,32.5,2,1.12],[16.2,45.1,1,1.03],
 [23.8,52.2,0,1.04],[48.5,48.0,1,1.14],[12.2,31.2,2,1.0],
];
const royalDecor=[
 ['pillar',17,36,.84],['pillar',41,38,.88],['pillar',47,17,.78],
 ['pillar',18,21,.87],['column',27.0,21,.73],['arch',26.5,16.5,1.05],
 ['flowers',20.2,41,.87],['flowers',31,44,.94],['flowers',45.4,41,.84],
 ['bush',14,36,.85],['bush',16,34,.74],['bush',26,47,.97],
 ['bush',34,46,.84],['bush',50,34,.78],['bush',15,17,.82]
];
const royalCitizens=[
 [26.2,29.2,.0,7],[29.0,26.2,2.4,12],[37.1,28.5,.9,18],
 [26.3,37.9,1.4,22],[35.0,38.5,3.4,29],[40.5,35.2,4.1,31],
 [21.4,33.7,5.2,35]
];
function royalSoftRay(g,W,H,t){
 g.save();g.globalCompositeOperation='screen';g.translate(W*.83,-H*.10);g.rotate(.31);
 for(let i=0;i<5;i++){
  const x=(i-2)*W*.081,w=W*(.035+i*.012);
  const gr=g.createLinearGradient(0,0,0,H*1.35);
  gr.addColorStop(0,'rgba(255,252,193,.17)');gr.addColorStop(.45,'rgba(255,228,175,.05)');gr.addColorStop(1,'rgba(255,225,155,0)');g.fillStyle=gr;
  g.beginPath();g.moveTo(x,0);g.lineTo(x+w,0);g.lineTo(x+2*w,H*1.3);g.lineTo(x-1.3*w,H*1.3);g.closePath();g.fill();
 }
 g.restore();
 const halo=g.createRadialGradient(W*.87,H*.03,0,W*.86,H*.03,W*.65);
 halo.addColorStop(0,'rgba(255,247,203,.20)');halo.addColorStop(1,'rgba(255,243,198,0)');g.fillStyle=halo;g.fillRect(0,0,W,H);
}
function royalWaterMotion(g,P,t){
 g.save();
 for(let i=0;i<21;i++){
  const x=39+rr(i,37)*12,z=19+rr(i,74)*14,p=P(x,z);
  const a=.18+.18*(.5+.5*Math.sin(t*1.6+i));g.strokeStyle='rgba(222,253,249,'+a+')';g.lineWidth=1;
  g.beginPath();g.ellipse(p[0]+Math.sin(t+i)*1.5,p[1],2+rr(i,55)*5,1+rr(i,39)*2,0,0,Math.PI*.9);g.stroke();
 }
 // True top-layer lily pads and flowers positioned on the water plane.
 for(const [x,z,r] of [[33.7,13.7,0],[37.2,19.3,1],[42,16.7,2],[38.5,25,3],[32.4,23.8,4]]){
  const p=P(x,z,1.15),s=6.5;
  g.fillStyle='#4e9a67';g.beginPath();g.ellipse(p[0],p[1],s,s*.38,-.22,0,6.283);g.fill();
  g.fillStyle='#9fd5a1';g.beginPath();g.ellipse(p[0]-1.5,p[1]-1,s*.68,s*.24,0,0,6.283);g.fill();
  if(r%2===0){for(let a=0;a<5;a++){
   const ang=a*Math.PI*2/5;g.fillStyle='#fff0e6';g.beginPath();g.ellipse(p[0]+Math.cos(ang)*3,p[1]+Math.sin(ang)*2,3,1.7,ang,0,6.283);g.fill();}
   g.fillStyle='#e7ad51';g.beginPath();g.arc(p[0],p[1],1.7,0,6.283);g.fill();}
 }
 g.restore();
}
function royalOverlayUI(t){
 const c=document.getElementById('royal-mini-canvas');if(!c)return;
 const g=c.getContext('2d'),W=c.width,H=c.height;g.clearRect(0,0,W,H);
 g.fillStyle='rgba(15,36,39,.65)';g.fillRect(0,0,W,H);
 g.strokeStyle='rgba(225,217,179,.45)';g.strokeRect(8,8,W-16,H-16);
 const map=(x,z)=>[12+(x-10)/48*(W-24),12+(z-10)/48*(H-24)];
 g.fillStyle='rgba(13,151,169,.73)';let a=map(31,11),b=map(43,27);g.fillRect(a[0],a[1],b[0]-a[0],b[1]-a[1]);
 g.fillStyle='rgba(124,183,111,.8)';for(const [x,z] of royalTrees){let p=map(x,z);g.beginPath();g.arc(p[0],p[1],3,0,6.283);g.fill();}
 const p=map(player.x,player.z);g.fillStyle='#fff5d5';g.beginPath();g.moveTo(p[0],p[1]-5);g.lineTo(p[0]+4,p[1]+3);g.lineTo(p[0]-4,p[1]+3);g.fill();
}
function renderRoyal(t){
 const canvas=document.querySelector('#royal-canvas');if(!canvas)return;
 const ctx=canvas.getContext('2d',{alpha:false});
 const W=canvas.width,H=canvas.height;if(W<1||H<1)return;
 if(t-ROYAL_ART.prevTime<.028)return;ROYAL_ART.prevTime=t;
 const U=Math.max(10,Math.min(W/29,H/23,26));
 const actorScale=Math.max(.44,Math.min(W/400,H/660,1.36));
 const center=[player.x,player.z];const P=(x,z,y=0)=>royalP(x,z,y,center,U,W,H);
 const keyChanged=!ROYAL_ART.base||ROYAL_ART.baseW!==W||ROYAL_ART.baseH!==H||Math.abs(ROYAL_ART.baseU-U)>.05||Math.hypot(center[0]-ROYAL_ART.baseOrigin[0],center[1]-ROYAL_ART.baseOrigin[1])>2;
 if(keyChanged){
  if(!ROYAL_ART.base)ROYAL_ART.base=document.createElement('canvas');
  const base=ROYAL_ART.base;base.width=W;base.height=H;
  const bg=base.getContext('2d',{alpha:false});ROYAL_ART.baseCtx=bg;
  royalGroundDraw(bg,W,H,U,center);
  ROYAL_ART.baseW=W;ROYAL_ART.baseH=H;ROYAL_ART.baseU=U;ROYAL_ART.baseOrigin=center.slice();
 }
 const dx=center[0]-ROYAL_ART.baseOrigin[0],dz=center[1]-ROYAL_ART.baseOrigin[1];
 const sx=(-dx+dz)*U*.91,sy=(-dx-dz)*U*.455;
 ctx.fillStyle='#cec1b0';ctx.fillRect(0,0,W,H);ctx.drawImage(ROYAL_ART.base,sx,sy);
 royalDapple(ctx,P,t);
 royalWaterMotion(ctx,P,t);
 // Fine softened dappled shadows from the sunlit leaf canopies.
 ctx.save();for(const [x,z,style,m] of royalTrees){const p=P(x,z);
  ctx.fillStyle='rgba(63,88,47,.13)';ctx.beginPath();ctx.ellipse(p[0]+19*m*actorScale,p[1]+9*m*actorScale,47*m*actorScale,14*m*actorScale,.16,0,6.283);ctx.fill();}
 ctx.restore();
 const entities=[];
 for(const [x,z,v,m] of royalTrees)entities.push({kind:'tree',x,z,name:'tree'+v,zoom:actorScale*m*1.08,order:x+z});
 for(const [name,x,z,zm] of royalDecor)entities.push({kind:'prop',name,x,z,zoom:actorScale*zm,order:x+z});
 for(let i=0;i<royalCitizens.length;i++){
  const [x,z,phase,id]=royalCitizens[i];const wander=Math.sin(t*(.55+(i%3)*.13)+phase)*.48;
  const dx=Math.cos(phase*2.9)*wander,dz=Math.sin(phase*1.9)*wander;
  const moving=Math.abs(Math.cos(t*(.55+(i%3)*.13)+phase))>.27;
  const face=['front','left','right','back'][(i+Math.floor(t/3.8))%4];
  const sprite='citizen_'+face+'_'+(moving?(Math.floor(t*5+i)%2+1):0);
  entities.push({kind:'npc',name:sprite,x:x+dx,z:z+dz,zoom:actorScale*.65,order:x+dx+z+dz});
 }
 const moving=!!(keys.w||keys.a||keys.s||keys.d||keys.arrowup||keys.arrowdown||keys.arrowleft||keys.arrowright||Math.hypot(joy.dx,joy.dy)>.09);
 const face=keys.a||keys.arrowleft?'left':keys.d||keys.arrowright?'right':keys.s||keys.arrowdown?'front':'back';
 const frame=moving?(Math.floor(t*8)%2+1):0;
 entities.push({kind:'hero',name:'hero_'+face+'_'+frame,x:player.x,z:player.z,zoom:actorScale*.76,order:player.x+player.z+1e-5});
 entities.sort((a,b)=>a.order-b.order);
 for(const e of entities){
  if(e.kind==='npc'||e.kind==='hero')royalShadow(ctx,e.x,e.z,actorScale*.52,P);
  if(e.kind==='prop'&&(e.name==='pillar'||e.name==='arch'))royalShadow(ctx,e.x,e.z,actorScale,P);
  royalDrawSprite(ctx,e.name,e.x,e.z,e.zoom,P);
 }
 // Soft beams use screen-space postprocessing rather than replacing source volumes.
 royalSoftRay(ctx,W,H,t);
 // Floating reflected water glints and firefly atmospheric particles.
 for(let i=0;i<18;i++){
  const x=32+rr(i,33)*10,z=12+rr(i,55)*14,p=P(x,z,1.2);
  let alpha=.3+.28*(.5+.5*Math.sin(t*1.7+i*1.3));
  ctx.fillStyle=`rgba(244,255,220,${alpha})`;ctx.beginPath();ctx.arc(p[0],p[1],.5+rr(i,65)*.8,0,6.283);ctx.fill();
 }
 if(Math.floor(t*2)%4===0)royalOverlayUI(t);
}
function activateRoyal(flag,reset=false){
 royalActive=flag;
 document.body.classList.toggle('royal-ui',flag);
 const cv=document.getElementById('royal-canvas');if(cv)cv.style.display=flag?'block':'none';
 const mini=document.getElementById('royal-mini');if(mini)mini.style.display=flag?'block':'none';
 const btn=document.getElementById('royal-toggle');if(btn)btn.textContent=flag?'⌂':'✦';
 if(flag){if(reset){player.x=31.5;player.z=31.5;}if(ROYAL_ART.base){ROYAL_ART.base=null;}}
 else fallbackStaticCache.world=null;
}
function royalResize(){
 let c=document.getElementById('royal-canvas');if(!c)return;
 const dpr=Math.min(devicePixelRatio||1,1.45);
 c.width=Math.round(innerWidth*dpr);c.height=Math.round(innerHeight*dpr);
 c.style.width=innerWidth+'px';c.style.height=innerHeight+'px';ROYAL_ART.base=null;
}
function royalSetup(){
 royalResize();activateRoyal(true);
 document.getElementById('royal-toggle').addEventListener('click',()=>activateRoyal(!royalActive,true));
 window.addEventListener('resize',royalResize);
 // The original 7 regions remain available, automatically restoring the source renderer.
 document.querySelector('#location-select').addEventListener('change',()=>{if(mode!==-1)activateRoyal(false);});
}
