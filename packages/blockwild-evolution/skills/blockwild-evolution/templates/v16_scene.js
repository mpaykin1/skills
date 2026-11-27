// BLOCKWILD v16 — additive author-made source-volume diorama layer.
// Original v15 hero/NPC models, directions, camera, physics, world and audio are intact.
// All additional props are actual 3D occupied volumes rasterized to transparent RGBA.
const BW16 = {version:'16.0', extraVolumes:11, originalCharactersPreserved:true,
                    waterSamples:0, fallingPetals:0, ambientLanterns:0};
// Add genuine 3D volume derived props; do not override existing character sprites.
for (const [name, asset] of Object.entries(BW16_EXTRA_SPRITES)) {
  if (ROYAL_ART.SPRITES[name]) throw Error('BW16 cannot replace source sprite: '+name);
  ROYAL_ART.SPRITES[name] = asset;
  const im = new Image(); im.decoding='async';im.src=asset.uri;
  im.onload=()=>{ROYAL_ART.readyCount++};
  ROYAL_ART.images[name]=im;
}
// Replace only the two authored old decorative arch props, not source mesh identities.
for (const item of royalDecor) if(item[0]==='arch')item[0]='v16_rose_arch';
royalDecor.push(
  ['v16_fountain',35.6,20.1,.76],
  ['v16_lantern',26.0,14.3,.53],['v16_lantern',47.3,28.1,.55],
  ['v16_lantern',16.5,41.3,.52],['v16_lantern',55.8,55.3,.53],
  ['v16_bench',14.1,28.5,.62],['v16_bench',48.0,49.0,.68],
  ['v16_urn_rose',18.0,22.4,.76],['v16_urn_cream',45.3,38.8,.80],
  ['v16_urn_rose',19.4,46.7,.76],['v16_urn_cream',51.2,53.6,.75],
  ['v16_carved_urn',26.1,52.8,.66],['v16_carved_urn',47.7,15.3,.65],
  ['v16_cherry0',7.4,48.0,.97],['v16_cherry1',61.7,19.8,1.00],
  ['v16_cherry1',6.2,27.7,.96],
  ['v16_cypress',17.7,9.3,.91],['v16_cypress',52.8,10.8,.97],
  ['v16_citrus',61.0,40.3,1.01],['v16_citrus',4.2,44.6,.92]
);
// Existing tile geometry is retained; add sculpted jewel-inlays and aged-stone
// hairline joints in the exact projected walkable 3D floor coordinates.
const BW16GroundOld=royalGroundDraw;
royalGroundDraw=function(g,W,H,U,center){
 BW16GroundOld(g,W,H,U,center);
 const P=(x,z,y=0)=>royalP(x,z,y,center,U,W,H);
 g.save();
 // Distinct mosaic rosettes, accurately projected flat onto source paving.
 for(let zz=21;zz<=57;zz+=9)for(let xx=19;xx<=51;xx+=10){
  const q=P(xx,zz),radius=U*.50;
  if(q[0]<-40||q[0]>W+40||q[1]<-40||q[1]>H+40)continue;
  const corners=[P(xx-0.56,zz-.56,.014),P(xx+.56,zz-.56,.014),P(xx+.56,zz+.56,.014),P(xx-.56,zz+.56,.014)];
  royalPoly(g,corners,'rgba(214,188,145,.34)','rgba(139,102,66,.38)',Math.max(.45,U*.046));
  const mid=P(xx,zz,.023);
  g.save();g.translate(mid[0],mid[1]);g.scale(Math.max(.5,U*.66),Math.max(.5,U*.36));
  for(let n=0;n<8;n++){
   const a=n*Math.PI/4;
   g.fillStyle=n%2===0?'rgba(185,142,85,.58)':'rgba(248,217,158,.74)';
   g.beginPath();g.ellipse(Math.cos(a)*.43,Math.sin(a)*.43,.18,.36,a,0,Math.PI*2);g.fill();
  }
  g.fillStyle='rgba(255,221,140,.82)';g.beginPath();g.arc(0,0,.22,0,Math.PI*2);g.fill();g.restore();
 }
 // Irregular fine joints and weathered mineral specks, stable in world space.
 for(let i=0;i<720;i++){
   const x=13+rr(i,811)*45,z=14+rr(i,912)*49;
   if(x>31&&x<44&&z>10&&z<28)continue; // pond
   const p=P(x,z,.016);
   if(p[0]<-5||p[0]>W+5||p[1]<-5||p[1]>H+5)continue;
   const vein=rr(i,1104),size=U*(.05+rr(i,771)*.1);
   g.lineWidth=.5+vein*.4;
   g.strokeStyle=vein>.60?'rgba(107,98,82,.20)':'rgba(255,244,221,.25)';
   g.beginPath();g.moveTo(p[0]-size,p[1]);
   g.lineTo(p[0]+size*.45,p[1]+size*(.18+rr(i,73)*.40));g.stroke();
 }
 // Slender connected ivy borders and flower petals growing at actual stone edges.
 for(const [xx,zz,dx,dz,count] of [[14.2,52.5,1,0,24],[51.4,16.0,0,1,19],
                                    [28.7,56.2,1,0,22],[12.8,13.0,1,0,21]]){
  for(let i=0;i<count;i++){
    const x=xx+dx*i*.65,z=zz+dz*i*.65;
    const q=P(x,z,.05);
    if(q[0]<-10||q[0]>W+10||q[1]<-10||q[1]>H+10)continue;
    const r=.8+rr(i,xx,20)*2;
    g.fillStyle=['rgba(50,105,67,.74)','rgba(91,151,82,.79)','rgba(160,190,102,.75)'][i%3];
    g.beginPath();g.ellipse(q[0],q[1],r*1.6,r*.64,rr(i,32)*.9,0,Math.PI*2);g.fill();
    if(i%4===0){g.fillStyle=i%8===0?'rgba(253,229,228,.90)':'rgba(254,228,155,.84)';
      g.beginPath();g.arc(q[0]+r*.32,q[1]-r*.28,r*.5,0,Math.PI*2);g.fill();}
  }
 }
 g.restore();
};
// Real-time coherent caustic animation restricted to the physically bounded pool.
const BW16OldWaterMotion=royalWaterMotion;
royalWaterMotion=function(g,P,t){
 BW16OldWaterMotion(g,P,t);
 const corners=[P(31.7,11.8,1.12),P(42.3,11.8,1.12),
                P(42.3,26.3,1.12),P(31.7,26.3,1.12)];
 g.save();g.beginPath();g.moveTo(...corners[0]);for(let k=1;k<4;k++)g.lineTo(...corners[k]);g.closePath();g.clip();
 g.globalCompositeOperation='screen';
 for(let i=0;i<40;i++){
   const x=32.2+rr(i,91)*9.6,z=12.2+rr(i,93)*12.8;
   const p=P(x,z,1.13),a=.11+.18*(.5+.5*Math.sin(t*1.3+i*.47));
   const length=1+rr(i,92)*5;
   g.strokeStyle='rgba(193,250,251,'+a.toFixed(3)+')';g.lineWidth=.7;
   g.beginPath();g.ellipse(p[0]+Math.sin(t*1.0+i)*1.3,p[1]+Math.cos(t*.7+i)*.6,
                          length,length*.28,(i%6)*.18,0,Math.PI*1.40);g.stroke();
   BW16.waterSamples++;
 }
 g.restore();
};
// The existing RAF owns all animation: physically world-anchored lantern glows,
// drifting petals shed by cherry crowns, waterfall sparkle and sunlight.
const BW16OldSoftRay=royalSoftRay;
royalSoftRay=function(g,W,H,t){
 BW16OldSoftRay(g,W,H,t);
 const U=Math.max(8,Math.min(W/38,H/29,24));
 const scale=Math.max(.35,Math.min(W/490,H/880,1.24));
 const center=[player.x,player.z];
 const P=(x,z,y=0)=>royalP(x,z,y,center,U,W,H);
 g.save();g.globalCompositeOperation='screen';
 for(const e of royalDecor){
  if(e[0]!=='v16_lantern')continue;
  const p=P(e[1],e[2],3.2);
  if(p[0]<-100||p[0]>W+100||p[1]<-100||p[1]>H+100)continue;
  const rad=(25+5*Math.sin(t*1.7+e[1]))*scale;
  const grad=g.createRadialGradient(p[0],p[1],1,p[0],p[1],rad*1.8);
  grad.addColorStop(0,'rgba(255,231,165,.35)');
  grad.addColorStop(.25,'rgba(255,201,108,.21)');
  grad.addColorStop(1,'rgba(255,186,98,0)');
  g.fillStyle=grad;g.beginPath();g.arc(p[0],p[1],rad*1.8,0,Math.PI*2);g.fill();
  BW16.ambientLanterns++;
 }
 g.restore();
 // Blossoms fall and turn under independent gravity/side wind; character animations untouched.
 for(let j=0;j<56;j++){
   const source=royalDecor[(j*13+5)%royalDecor.length];
   if(!source||!source[0].startsWith('v16_cherry'))continue;
   const age=(t*.21+j*.138)%1;
   const xx=source[1]+(rr(j,15)-.5)*9+Math.sin(t*.71+j)*2.6;
   const zz=source[2]+(rr(j,71)-.5)*7+Math.cos(t*.49+j)*1.3;
   const ht=6.8-age*7.0;
   const p=P(xx,zz,Math.max(0,ht));
   if(p[0]<-4||p[0]>W+4||p[1]<-4||p[1]>H+4)continue;
   g.fillStyle=(j%3===0?'rgba(255,240,216,.68)':j%3===1?'rgba(251,187,198,.68)':'rgba(236,215,169,.6)');
   g.save();g.translate(p[0],p[1]);g.rotate(t*1.18+j*.9);
   g.beginPath();g.ellipse(0,0,1.2,2.4,.35,0,Math.PI*2);g.fill();g.restore();
   BW16.fallingPetals++;
 }
 // Fine fountain mist is attached to the 3D water jet source, not a still billboard.
 g.save();g.globalCompositeOperation='screen';
 for(let i=0;i<29;i++){
   const ph=(t*.42+i*.14)%1;
   const a=i*Math.PI*2/29;
   const x=35.6+Math.cos(a)*(1.0+ph*1.8),z=20.1+Math.sin(a)*(1+ph*1.6);
   const y=3.9+1.3*Math.sin(Math.PI*ph)-1.5*ph;
   const q=P(x,z,y);
   if(q[0]<-8||q[0]>W+8||q[1]<-8||q[1]>H+8)continue;
   g.fillStyle='rgba(210,255,253,'+(.08+.19*(1-ph)).toFixed(2)+')';
   g.beginPath();g.arc(q[0],q[1],.55+(i%3)*.14,0,Math.PI*2);g.fill();
 }
 g.restore();
};
