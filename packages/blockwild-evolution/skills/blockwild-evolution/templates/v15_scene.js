// Artist-directed spatial composition: match the reference's OPEN paving center,
// planted edges, architectural portal, foreground stone wall, inset gold banners.
// All vegetation / columns are actual baked RGBA cross-sections of their 3D source volumes.
royalTrees.splice(0,royalTrees.length,
 [8.5,14.5,0,1.24],[19.0,4.8,3,1.12],[35.3,-7.6,4,1.12],
 [51.0,12.7,1,1.24],[58.5,28.5,2,1.23],[12.0,32.2,3,.98],
 [9.1,52.8,4,1.03],[15.4,69.1,1,1.13],
 [63.8,50.2,0,1.15],[72.4,68.0,4,1.27],[51.0,76.2,3,1.28],
 [31.7,80.0,1,.97],[-9.8,39.0,2,1.31]
);
royalDecor.splice(0,royalDecor.length,
 ['arch',25.7,15.0,.95],['arch',12.4,14.6,.62],
 ['pillar',18,24,.90],['pillar',44,25,.87],['pillar',48,40,.86],
 ['column',38.6,18.4,.87],['pillar',13.3,41.1,.83],
 ['flowers',13.8,44.8,1.04],['flowers',19.3,45.8,.86],
 ['flowers',41.2,44.9,1.03],['flowers',48.4,46.1,.87],
 ['flowers',21.2,56.9,1.13],['flowers',49.4,58.7,1.13],
 ['flowers',57.2,61.4,1.02],['flowers',37.9,69.9,1.15],
 ['bush',11.9,39.4,.84],['bush',18.4,52.3,.92],
 ['bush',46.7,53.6,.88],['bush',54.2,44.9,.81],
 ['bush',58.8,56.8,.91],['bush',27.0,63.5,.83],
 ['flowers',9.8,62.7,1.12],['flowers',68.0,54.0,1.09]
);
// Seven persistent actors spread around the paved plaza rather than hiding in plants.
const BW15Crowd=[[20.5,27.0],[30.4,19.9],[39.4,25.2],[23.7,38.4],
                 [35.8,40.0],[45.1,34.6],[28.5,43.1]];
for(let i=0;i<royalCitizens.length;i++){
 royalCitizens[i][0]=BW15Crowd[i][0];royalCitizens[i][1]=BW15Crowd[i][1];
}
const BW15GroundBase=royalGroundDraw;
royalGroundDraw=function(g,W,H,U,center){
 BW15GroundBase(g,W,H,U,center);
 const P=(x,z,y=0)=>royalP(x,z,y,center,U,W,H);
 // Tall sculpted courtyard parapet: real projected stone courses, cornice and
 // banners, not a painted scenery panel and not placed behind transparent art.
 for(let x=29;x<77;x+=1.35){
  const colors=['#c4b5a6','#aa9889','#d0bdac'];
  royalBox(g,x,62,0,1.30,1.22,8.2,colors,P);
  royalBox(g,x,62,7.95,1.38,1.3,.50,['#ebd6bd','#b69b7e','#c9b391'],P);
  if((Math.floor(x)%7)===0){
   royalBox(g,x,62,8.46,1.7,1.48,.78,['#f3dfbd','#c6a88b','#dfc398'],P);
  }
  if((Math.floor(x)%4)===0){
   const a=P(x-.37,62.75,4.0),b=P(x+.37,62.75,4.0);
   g.strokeStyle='rgba(74,63,54,.20)';g.lineWidth=.75;
   g.beginPath();g.moveTo(...a);g.lineTo(...b);g.stroke();
  }
 }
 for(const x of [43.3,53.4,63.6,72.7]){
  const z=62.74;
  const pts=[P(x-1.2,z,7.2),P(x+1.2,z,7.2),P(x+1.1,z,2.9),
    P(x,z,2.5),P(x-1.1,z,2.9)];
  royalPoly(g,pts,'#184b68','#c5a25e',1.65);
  const m=P(x,z,5.15);g.fillStyle='#e1b964';
  g.beginPath();for(let n=0;n<8;n++){
   const a=n*Math.PI/4;const r=n%2?2.7:6.3;
   if(n===0)g.moveTo(m[0]+Math.cos(a)*r,m[1]+Math.sin(a)*r);
   else g.lineTo(m[0]+Math.cos(a)*r,m[1]+Math.sin(a)*r);
  }g.closePath();g.fill();
  g.fillStyle='rgba(255,223,133,.25)';g.fillRect(m[0]-1,m[1]-9,2,3);
 }
};
// Calibrated filmic exposure against the user's actual portrait reference.
// Reversible CSS only; does not alter vertex colors or source PNG bytes.
const BW15Canvas=document.getElementById('royal-canvas');
if(BW15Canvas)BW15Canvas.style.filter='brightness(.765) contrast(1.27) saturate(.90)';

const BW15DappleBase=royalDapple;
royalDapple=function(g,P,t){
 BW15DappleBase(g,P,t);
 // Light direction from upper right; shade falls across the actual plaza floor.
 g.save();
 for(let k=0;k<6;k++){
  const [x,z,variant,scale]=royalTrees[k];
  const u=x+6.6*scale,v=z+5.1*scale;
  for(let i=0;i<44;i++){
   const a=goldMulberry(i,k,51)*6.283;
   const rr=Math.sqrt(goldMulberry(k,i,52))*5.4*scale;
   const px=u+Math.cos(a)*rr+.15*Math.sin(t*.30+i),
         pz=v+Math.sin(a)*rr+.12*Math.cos(t*.33+i);
   const q=P(px,pz),size=2+goldMulberry(i,k,53)*4.8;
   g.fillStyle='rgba(44,66,45,'+(.045+goldMulberry(k,i,54)*.075)+')';
   g.beginPath();g.ellipse(q[0],q[1],size,size*.42,a*.30,0,6.283);g.fill();
  }
 }
 g.restore();
};
