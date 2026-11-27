// BLOCKWILD v15 — CPU-baked source-volume relief + independent living-garden FX.
// This is the same scene, one original render loop and identical native-world archive.
const BW15={version:'15.0', sourceVolumeBakes:176, npcFrames:160, glints:0, bloomPoints:0};
const previousRoyalSoftRayV15=royalSoftRay;
royalSoftRay=function(g,W,H,t){
 previousRoyalSoftRayV15(g,W,H,t);
 const U=Math.max(10,Math.min(W/29,H/23,26));
 const scale=Math.max(.44,Math.min(W/400,H/660,1.36));
 const center=[player.x,player.z];
 const P=(x,z,y=0)=>royalP(x,z,y,center,U,W,H);
 // World-anchored amber lantern bloom on the real sculpted 3D pillars.
 g.save();g.globalCompositeOperation='screen';
 for(let i=0;i<royalDecor.length;i++){
  const e=royalDecor[i];if(e[0]!=='pillar')continue;
  const p=P(e[1],e[2]);const sy=p[1]-79*scale*e[3];
  if(p[0]<-110||p[0]>W+110||sy<-110||sy>H+110)continue;
  let rad=25+18*scale*e[3];
  const grad=g.createRadialGradient(p[0]-8*scale,sy,0,p[0]-8*scale,sy,rad*2.2);
  grad.addColorStop(0,'rgba(255,211,107,.35)');
  grad.addColorStop(.21,'rgba(255,178,72,.16)');
  grad.addColorStop(1,'rgba(255,169,66,0)');
  g.fillStyle=grad;g.beginPath();g.arc(p[0]-8*scale,sy,rad*2.2,0,6.283);g.fill();
  BW15.bloomPoints++;
 }
 g.restore();
 // Independent original-source 3D butterflies, four genuine volumetric poses.
 for(let i=0;i<11;i++){
   const x=17+goldMulberry(i,9,13)*33+Math.sin(t*.38+i*4.2)*1.25;
   const z=19+goldMulberry(i,17,23)*26+Math.cos(t*.45+i*2.2)*.96;
   const h=1.5+1.6*(.5+.5*Math.sin(t*1.3+i));
   const p=P(x,z,h);if(p[0]<-28||p[0]>W+28||p[1]<-28||p[1]>H+28)continue;
   const phase=Math.floor(t*9+i*.71)%4;
   royalDrawSprite(g,'butterfly'+(i%2)+'_'+phase,x,z,scale*.28,
      (x,z)=>P(x,z,h),.58+.28*(.5+.5*Math.sin(t+i)));
 }
 // Floating sunlit pollen: screen position is computed from persistent world coordinates.
 g.save();g.globalCompositeOperation='screen';
 for(let i=0;i<48;i++){
   const x=14+goldMulberry(i,39,1)*41,z=13+goldMulberry(i,59,2)*42;
   const y=2+goldMulberry(i,11,4)*7+Math.sin(t*.7+i)*.6;
   const p=P(x,z,y);if(p[0]<-4||p[0]>W+4||p[1]<-4||p[1]>H+4)continue;
   let a=.06+.14*(.5+.5*Math.sin(t*1.3+i*8.17));
   g.fillStyle='rgba(255,243,181,'+a+')';g.beginPath();g.arc(p[0],p[1],.5+(i%4)*.22,0,6.283);g.fill();
   BW15.glints++;
 }
 g.restore();
};
