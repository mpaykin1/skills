// BLOCKWILD v17: real 3D-occupied volume additions plus light transport approximation.
// No CDN, no extra renderer/RAF, no changed original-world source or player identity.
const BW17={version:17,volumes:4,shadowObjects:0,causticGlints:0,frameCount:0};
for(const [name,asset] of Object.entries(BW17_SPRITES)){
 if(ROYAL_ART.SPRITES[name])throw Error('v17 would overwrite '+name);
 ROYAL_ART.SPRITES[name]=asset;
 const img=new Image();img.decoding='async';img.src=asset.uri;
 img.onload=()=>{ROYAL_ART.readyCount++;ROYAL_ART.base=null;};
 ROYAL_ART.images[name]=img;
}
// Deliberately few additions; protect open hero routes and courtyard negative space.
royalDecor.push(
 ['v17_wisteria_pergola',12.6,23.8,.78],
 ['v17_ivy_pillar',54.1,19.5,.52],
 ['v17_ivy_pillar',16.7,51.0,.52],
 ['v17_royal_pedestal',47.7,44.5,.54],
 ['v17_lily_well',52.0,39.5,.61]
);
// Shape-accurate sunlight occlusion: use the silhouette alpha of the *actual*
// authored volume-slice PNG, reproject onto the ground and soft-filter it once.
const BW17ShadowMasks=new Map();
function bw17ShadowMask(name,img){
 if(BW17ShadowMasks.has(name))return BW17ShadowMasks.get(name);
 const sw=img.naturalWidth,sh=img.naturalHeight;
 if(!sw||!sh)return null;
 const c=document.createElement('canvas');c.width=sw+10;c.height=sh+10;
 const k=c.getContext('2d');k.filter='blur(2.2px)';k.drawImage(img,5,5);
 k.filter='none';k.globalCompositeOperation='source-in';
 k.fillStyle='#233b2b';k.fillRect(0,0,c.width,c.height);
 BW17ShadowMasks.set(name,c);return c;
}
const BW17OldDraw=royalDrawSprite;
royalDrawSprite=function(g,name,x,z,zoom,P,alpha=1){
 const s=ROYAL_ART.SPRITES[name],img=ROYAL_ART.images[name];
 if(s&&img?.complete&&img.naturalWidth&&alpha>.05){
  const contact=P(x,z,0),sz=Math.min(1.3,Math.max(.3,zoom));
  const mask=bw17ShadowMask(name,img);
  if(mask&&contact[0]>-190&&contact[0]<g.canvas.width+190&&contact[1]>-190&&contact[1]<g.canvas.height+190){
   // Distinct contact + projected alpha silhouette, softly lit from upper right.
   g.save();
   g.globalAlpha=alpha*((name.startsWith('hero_')||name.startsWith('citizen'))?.38:.29);
   g.translate(contact[0]-sz*7,contact[1]+sz*4);
   g.transform(.81,.11,.42,-.17,0,0);
   g.drawImage(mask,-s.base[0]*zoom-5*zoom,-s.base[1]*zoom-5*zoom,
               (s.size[0]+10)*zoom,(s.size[1]+10)*zoom);
   g.restore();
   BW17.shadowObjects++;
  }
 }
 BW17OldDraw(g,name,x,z,zoom,P,alpha);
};
// Natural close-range microrelief: corner gold tesserae only where floor is walkable.
const BW17OldGround=royalGroundDraw;
royalGroundDraw=function(g,W,H,U,center){
 BW17OldGround(g,W,H,U,center);
 const P=(x,z,y=0)=>royalP(x,z,y,center,U,W,H);
 g.save();
 for(let n=0;n<140;n++){
  const x=13+rr(n,336)*38,z=17+rr(n,424)*37;
  if((x>31&&x<45&&z>10&&z<29)||(x>39&&x<49&&z>56))continue;
  const q=P(x,z,.03);
  if(q[0]<-8||q[0]>W+8||q[1]<-8||q[1]>H+8)continue;
  const size=.55+rr(n,914)*1.5;
  g.strokeStyle=n%6===0?'rgba(255,230,169,.42)':'rgba(112,85,63,.20)';
  g.lineWidth=.55;g.beginPath();g.moveTo(q[0]-size,q[1]-.3);
  g.lineTo(q[0]+size*.7,q[1]+size*.34);g.stroke();
 }
 // Physically aligned bevels along every polished stone tile: top-left sunny
 // edges and recessed bottom-right grout. Drawn on the actual floor plane.
 for(let z=10;z<58;z++)for(let x=10;x<58;x++){
  if((x>=31&&x<=44&&z>=10&&z<=28)||(x>=40&&x<=49&&z>=56))continue;
  const m=P(x+.5,z+.5,.035),dist=U*1.5;
  if(m[0]<-dist||m[0]>W+dist||m[1]<-dist||m[1]>H+dist)continue;
  const a=P(x+.08,z+.08,.03),b=P(x+.92,z+.08,.03),
        c=P(x+.92,z+.92,.03),d=P(x+.08,z+.92,.03);
  g.lineWidth=Math.max(.38,Math.min(1,U*.051));
  g.strokeStyle='rgba(255,243,219,.37)';g.beginPath();g.moveTo(...d);g.lineTo(...a);g.lineTo(...b);g.stroke();
  g.strokeStyle='rgba(103,81,71,.23)';g.beginPath();g.moveTo(...b);g.lineTo(...c);g.lineTo(...d);g.stroke();
 }
 // Hand-placed gold inlay filigree follows the real courtyard edge, not UI pixels.
 for(const [x,z,dir] of [[17,36,0],[47,34,0],[34,18,1],[34,50,1]]){
  for(let j=0;j<16;j++){
   const xx=x+(dir===0?0:j*.31), zz=z+(dir===1?0:j*.31);
   const pt=P(xx,zz,.04);
   if(pt[0]<-5||pt[0]>W+5||pt[1]<-5||pt[1]>H+5)continue;
   g.fillStyle='rgba(193,146,80,.52)';g.beginPath();g.arc(pt[0],pt[1],.55,0,Math.PI*2);g.fill();
  }
 }
 g.restore();
};
const BW17OldWater=royalWaterMotion;
royalWaterMotion=function(g,P,t){
 BW17OldWater(g,P,t);
 // Slightly dispersive caustics clipped to actual 3D water planes.
 g.save();g.beginPath();const qs=[P(31.8,12,1.16),P(42.3,12,1.16),P(42.3,26.3,1.16),P(31.8,26.3,1.16)];
 g.moveTo(...qs[0]);for(let i=1;i<4;i++)g.lineTo(...qs[i]);g.closePath();g.clip();
 g.globalCompositeOperation='screen';
 for(let k=0;k<74;k++){
  const wx=32.1+rr(k,301)*10.2,wz=12.2+rr(k,601)*13.7;
  const p=P(wx,wz,1.18);const pulse=.5+.5*Math.sin(t*1.8+k*.58);
  g.strokeStyle='rgba(221,255,245,'+(.10+.27*pulse).toFixed(2)+')';
  g.lineWidth=.45+.5*pulse;
  g.beginPath();g.ellipse(p[0]+2*Math.sin(t*.6+k),p[1]+1.5*Math.cos(t*.65+k),
                        1.5+rr(k,801)*3.5,.8+rr(k,921),rr(k,313),0,Math.PI*1.45);g.stroke();
  BW17.causticGlints++;
 }
 g.restore();
};
const BW17OldLighting=royalSoftRay;
royalSoftRay=function(g,W,H,t){
 BW17OldLighting(g,W,H,t);
 // Glancing warm sun and localized air bloom at architectural edges.
 g.save();g.globalCompositeOperation='soft-light';
 const sun=g.createRadialGradient(W*.83,H*.01,0,W*.80,H*.01,Math.max(W,H)*.84);
 sun.addColorStop(0,'rgba(255,229,172,.21)');sun.addColorStop(.53,'rgba(255,213,167,.08)');
 sun.addColorStop(1,'rgba(72,96,83,.03)');g.fillStyle=sun;g.fillRect(0,0,W,H);
 g.restore();
 const U=Math.max(8,Math.min(W/38,H/29,24)),center=[player.x,player.z];
 const P=(x,z,y=0)=>royalP(x,z,y,center,U,W,H);
 // Two swarms of animated source-derived three-dimensional butterfly projections.
 const butterflies=Object.keys(ROYAL_ART.SPRITES).filter(k=>k.startsWith('butterfly'));
 if(butterflies.length){
  for(let i=0;i<7;i++){
   const theta=t*(.41+i*.045)+i*2.7;
   const x=(i%2?18:44)+4.5*Math.cos(theta),z=(i%3?24:43)+3.6*Math.sin(theta*.81);
   const name=butterflies[Math.floor(t*5.8+i)%butterflies.length];
   const pos=P(x,z,3.0+Math.sin(theta*2)*.7);
   const s=ROYAL_ART.SPRITES[name],img=ROYAL_ART.images[name];
   if(s&&img?.complete&&img.naturalWidth&&pos[0]>-20&&pos[0]<W+20&&pos[1]>-20&&pos[1]<H+20){
    const scale=Math.max(.17,Math.min(.37,W/1250));
    g.save();g.globalAlpha=.78;
    g.drawImage(img,pos[0]-s.base[0]*scale,pos[1]-s.base[1]*scale,s.size[0]*scale,s.size[1]*scale);
    g.restore();
   }
  }
 }
 BW17.frameCount++;
};
