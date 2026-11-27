 // A second shallow garden canal with copings on the front-left path,
 // in the same world-space stone/water coordinate system as the first pool.
 {
 const xx0=40,xx1=48,zz0=56,zz1=66;
 royalPoly(g,[P(xx0,zz0),P(xx1,zz0),P(xx1,zz1),P(xx0,zz1)],'#208e9a','#b19d87',1.0);
 const wg2=g.createLinearGradient(...P(xx0,zz0),...P(xx1,zz1));
 wg2.addColorStop(0,'#087988');wg2.addColorStop(.5,'#16a9b2');wg2.addColorStop(1,'#6aded6');
 royalPoly(g,[P(xx0+.30,zz0+.3),P(xx1-.3,zz0+.3),P(xx1-.3,zz1-.3),P(xx0+.3,zz1-.3)],wg2);
 for(let x=xx0;x<xx1;x+=1){
   royalBox(g,x+.5,zz0,0,1,.88,.78,['#ded3c2','#ab9582','#c1ae9c'],P);
   royalBox(g,x+.5,zz1,0,1,.88,.78,['#e8dac8','#b7a18e','#d5bf9f'],P);
 }
 for(let z=zz0;z<zz1;z+=1.05){
   royalBox(g,xx0,z+.5,0,.88,1.02,.78,['#e8dac8','#b6a18e','#d1bda7'],P);
   royalBox(g,xx1,z+.5,0,.88,1.02,.78,['#e8dac8','#b6a18e','#d1bda7'],P);
 }
 }
