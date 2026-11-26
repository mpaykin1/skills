/* Original, source-validated RGBA full-cel PixiJS sprites + genuine Matter.js 0.20.0 physics.
   PathFinding.js supplies authored-grid A*. Matter.js alone solves body contacts.
   Only complete drawn PNG frames change; character pixels are never morphed. */
(async function(){
'use strict';
const error=document.getElementById('error');
try {
 if(!window.PIXI?.Application||!window.PF?.AStarFinder||!window.Matter?.Engine||!window.Matter?.Bodies)
   throw new Error('Не найдены встроенные реальные PixiJS, PathFinding.js или Matter.js.');
 const S=JSON.parse(document.getElementById('lia-scene').textContent);
 if(S.deformation!==false||!S.physics?.source_authored_geometry||!S.browserNavigation?.actors)
   throw new Error('Не подтверждён источник анимации или карта столкновений.');
 const app=new PIXI.Application();
 await app.init({width:S.width,height:S.height,backgroundAlpha:0,antialias:false,resolution:1,preference:'webgl'});
 const viewport=document.getElementById('viewport');viewport.appendChild(app.canvas);
 app.stage.sortableChildren=true;
 const textures=new Map();
 async function texture(url){
   if(textures.has(url))return textures.get(url);
   const image=new Image();image.decoding='async';
   const pending=new Promise((resolve,reject)=>{image.onload=resolve;image.onerror=reject;});
   image.src=url;await pending;
   const tex=PIXI.Texture.from(image);tex.source.scaleMode='nearest';textures.set(url,tex);return tex;
 }
 function resize(){
   const k=Math.min(window.innerWidth/S.width,window.innerHeight/S.height);
   app.canvas.style.width=Math.max(1,Math.floor(S.width*k))+'px';
   app.canvas.style.height=Math.max(1,Math.floor(S.height*k))+'px';
 }
 window.addEventListener('resize',resize,{passive:true});resize();
 const bg=new PIXI.Sprite(await texture(S.background));bg.zIndex=-10000;app.stage.addChild(bg);
 for(const layer of S.layers){const pl=new PIXI.Sprite(await texture(S.planes[layer.png]));pl.zIndex=layer.z;app.stage.addChild(pl);}
 const engine=Matter.Engine.create({gravity:{x:0,y:0,scale:0},positionIterations:8,velocityIterations:8});
 engine.gravity.x=0;engine.gravity.y=0;engine.gravity.scale=0;
 const solidOptions={isStatic:true,friction:0,frictionStatic:0,restitution:0};
 const staticBodies=[];
 for(const [x,y,w,h] of S.physics.obstacles){
   staticBodies.push(Matter.Bodies.rectangle(x+w/2,y+h/2,w,h,{...solidOptions,label:'original_wall'}));
 }
 // Boundaries prevent NPCs leaving the verified scene; no synthetic drawn walls.
 staticBodies.push(Matter.Bodies.rectangle(-32,S.height/2,64,S.height+128,solidOptions));
 staticBodies.push(Matter.Bodies.rectangle(S.width+32,S.height/2,64,S.height+128,solidOptions));
 staticBodies.push(Matter.Bodies.rectangle(S.width/2,-32,S.width+128,64,solidOptions));
 staticBodies.push(Matter.Bodies.rectangle(S.width/2,S.height+32,S.width+128,64,solidOptions));
 const sensors=new Map();
 for(const item of S.physics.sensors){
   const [x,y,w,h]=item.rect;
   const body=Matter.Bodies.rectangle(x+w/2,y+h/2,w,h,{isStatic:true,isSensor:true,label:'trigger:'+item.id});
   sensors.set(body.id,item);staticBodies.push(body);
 }
 Matter.Composite.add(engine.world,staticBodies);
 const actors=[]; const bodyToActor=new Map();
 const movingActions=new Set(['walk','run','stairs_up','stairs_down']);
 for(const a of S.actors){
   const node=new PIXI.Container();node.zIndex=a.z;app.stage.addChild(node);
   const visual=new PIXI.Sprite();node.addChild(visual);
   const frames=[];for(const path of a.frames)frames.push(await texture(S.spriteData[path]));
   const navconf=S.browserNavigation.actors[a.id];
   const actor={info:a,node,visual,frames,nav:null,moveFrames:[],restFrames:[],last:-1};
   if(navconf){
     actor.moveFrames=a.actions.flatMap((v,i)=>v===navconf.moving_action?[i]:[]);
     actor.restFrames=a.actions.flatMap((v,i)=>!movingActions.has(v)?[i]:[]);
     if(actor.moveFrames.length<12||actor.restFrames.length<12)
       throw new Error('Нет утверждённых кадров ходьбы и остановки: '+a.id);
     const radius=Math.max(2,Math.min(a.box[2],a.box[3])*.14);
     const body=Matter.Bodies.circle(a.box[0],a.box[1],radius,{label:'character:'+a.id,
       friction:0,frictionStatic:0,frictionAir:.05,restitution:0,inertia:Infinity,slop:.01});
     Matter.Composite.add(engine.world,body);bodyToActor.set(body.id,actor);
     actor.nav={config:navconf,body,route:[],waypointIndex:0,stalled:0,moving:false,stepCount:0};
   }
   actors.push(actor);
 }
 function emitPair(phase,pair){
   const actor=bodyToActor.get(pair.bodyA.id)||bodyToActor.get(pair.bodyB.id);
   if(!actor)return;
   const other=pair.bodyA.id===actor.nav?.body.id?pair.bodyB:pair.bodyA;
   const sensor=sensors.get(other.id);
   if(!sensor)return;
   window.dispatchEvent(new CustomEvent('living-image:trigger',{detail:{phase,
     actor_id:actor.info.id,trigger_id:sensor.id,trigger_type:sensor.type}}));
 }
 Matter.Events.on(engine,'collisionStart',event=>event.pairs.forEach(pair=>emitPair('enter',pair)));
 Matter.Events.on(engine,'collisionEnd',event=>event.pairs.forEach(pair=>emitPair('exit',pair)));
 const pathfinder=new PF.AStarFinder({diagonalMovement:PF.DiagonalMovement.Never});
 const toCell=(p,c)=>[Math.max(0,Math.min(c.width-1,Math.floor(p[0]/c.cell_px))),
                        Math.max(0,Math.min(c.height-1,Math.floor(p[1]/c.cell_px)))];
 function routeTo(actor,target){
   const n=actor.nav,c=n.config,from=[n.body.position.x,n.body.position.y];
   const [sx,sy]=toCell(from,c),[ex,ey]=toCell(target,c);
   const grid=new PF.Grid(c.width,c.height,c.matrix);
   const cells=pathfinder.findPath(sx,sy,ex,ey,grid);
   if(cells.length===0) return false;
   const route=cells.slice(1).map(([x,y])=>[(x+.5)*c.cell_px,(y+.5)*c.cell_px]);
   route.push(target.slice());n.route=route;n.stalled=0;return true;
 }
 for(const a of actors){
   if(!a.nav)continue;
   if(!routeTo(a,a.nav.config.waypoints[0]))throw new Error('Маршрут заблокирован: '+a.info.id);
 }
 let frameTime=0;let accumulator=0;let paused=false;
 function stepPhysics(){
   for(const a of actors){
     const n=a.nav;if(!n)continue;
     const body=n.body;
     // Waypoint changes happen ONLY after an actually reached point, no teleport.
     let retries=0;
     while(n.route.length && retries++<12 &&
       Math.hypot(n.route[0][0]-body.position.x,n.route[0][1]-body.position.y)<Math.max(1.2,Math.min(a.info.box[2],a.info.box[3])*.10)) n.route.shift();
     if(!n.route.length){
       n.waypointIndex=(n.waypointIndex+1)%n.config.waypoints.length;
       routeTo(a,n.config.waypoints[n.waypointIndex]);
     }
     const to=n.route[0];
     if(!to){Matter.Body.setVelocity(body,{x:0,y:0});n.moving=false;continue;}
     const dx=to[0]-body.position.x,dy=to[1]-body.position.y;
     const distance=Math.hypot(dx,dy);
     const speed=n.config.speed_px_s/60;
     const scale=Math.min(speed, distance)/Math.max(0.0001,distance);
     Matter.Body.setVelocity(body,{x:dx*scale,y:dy*scale});
     n.moving=distance>1;
   }
   Matter.Engine.update(engine,1000/60);
   for(const a of actors){
     const n=a.nav;if(!n)continue;
     const vel=Math.hypot(n.body.position.x-n.lastX||0,n.body.position.y-n.lastY||0);
     n.lastX=n.body.position.x;n.lastY=n.body.position.y;
     n.moving=vel>.03;
     if(n.moving)n.stalled=0;else if(n.route.length)n.stalled++;
     if(n.stalled===60){
       // Retry within existing authored map. Do NOT phase through a collision.
       routeTo(a,n.config.waypoints[n.waypointIndex]);
     }
   }
 }
 function smoothstep(keys,index){
   if(!Array.isArray(keys)||keys.length<2)return [0,0];
   if(index<=keys[0].frame)return [keys[0].dx,keys[0].dy];
   for(let i=1;i<keys.length;i++){
     if(index<=keys[i].frame){const p=keys[i-1],q=keys[i];let t=(index-p.frame)/(q.frame-p.frame);
       t=t*t*(3-2*t);return [p.dx+(q.dx-p.dx)*t,p.dy+(q.dy-p.dy)*t];}
   }
   const last=keys[keys.length-1];return [last.dx,last.dy];
 }
 function render(){
   for(const a of actors){
     const item=a.info;
     let frame=(Math.floor(frameTime*S.fps)+item.phase)%a.frames.length;
     if(a.nav){
       const valid=a.nav.moving?a.moveFrames:a.restFrames;
       frame=valid[Math.floor(frameTime*S.fps)%valid.length];
       a.node.position.set(a.nav.body.position.x,a.nav.body.position.y);
     } else {
       const offset=item.locomotion?smoothstep(item.locomotion.path,frame):[0,0];
       a.node.position.set(item.box[0]+offset[0],item.box[1]+offset[1]);
     }
     if(frame!==a.last){a.visual.texture=a.frames[frame];a.last=frame;}
   }
 }
 render();
 app.ticker.add(t=>{
   if(paused)return;
   const delta=Math.min(.05,t.deltaMS/1000);frameTime+=delta;accumulator+=delta;
   let steps=0;while(accumulator>=1/60&&steps++<4){stepPhysics();accumulator-=1/60;}
   if(steps>=4&&accumulator>=1/60)accumulator=0;
   render();
 });
 const selected=actors.find(a=>a.nav);
 app.canvas.addEventListener('pointerdown',e=>{
   if(!selected)return;
   const rect=app.canvas.getBoundingClientRect();
   const x=(e.clientX-rect.left)*S.width/rect.width;
   const y=(e.clientY-rect.top)*S.height/rect.height;
   if(!Number.isFinite(x)||!Number.isFinite(y)||x<0||y<0||x>=S.width||y>=S.height)return;
   // Click/touch directs an authentic already-animated character on real A* map.
   if(routeTo(selected,[x,y]))selected.nav.waypointIndex=0;
 });
 window.__livingWorld={engine,actors:actors.map(a=>a.info.id),getBodies:()=>actors.filter(a=>a.nav).map(a=>a.nav.body),
   pause:()=>{paused=true;},play:()=>{paused=false;},physics:'Matter.js 0.20.0'};
} catch(err){error.textContent='Анимация не запущена: '+(err?.message||err);error.style.display='block';console.error(err);}
})();
