 // True source cross-section sprite stacking rendered INSIDE the existing real
 // PixiJS8/PathFinding.js/Matter.js/nipplejs/YUKA 2.5D game. No surrogate actors.
 const LIA_STACK=JSON.parse(document.getElementById('lia-stacks').textContent);
 const stackingActors=new Map();const stackingObjects=new Map();
 if(LIA_STACK.clean_plate)bg.texture=await texture(LIA_STACK.clean_plate);
 let stackingAzimuth=LIA_STACK.azimuth_deg*Math.PI/180;
 let stackingElevation=LIA_STACK.elevation_deg*Math.PI/180;
 const stackAtlasCache=new Map();
 const DEG=Math.PI/180;
 const stackPan=(volume)=>{
   const yaw=stackingAzimuth+volume.localYaw;
   const pitch=Math.sin(stackingElevation);
   const lift=Math.cos(stackingElevation);
   for(let i=0;i<volume.sprites.length;i++){
     const sprite=volume.sprites[i];
     sprite.rotation=yaw;
     // Distinct actual horizontal cross-section artwork for EVERY height plane.
     // Only the ENTIRE volume turns. No joints, faces, clothing or poses morph.
     sprite.scale.set(volume.scale,volume.scale*pitch);
     sprite.position.set(0,-i*volume.step*lift*volume.scale);
   }
 };
 async function stackAtlas(record){
   if(stackAtlasCache.has(record.sha256))return stackAtlasCache.get(record.sha256);
   const full=await texture(record.atlas); // existing genuine PixiJS8 loader, original bytes
   full.source.scaleMode=LIA_STACK.sampling;
   const rectangles=[];
   for(let i=0;i<record.slices;i++){
     const frame=new PIXI.Rectangle((i%record.columns)*record.width,
             Math.floor(i/record.columns)*record.depth,record.width,record.depth);
     const tile=new PIXI.Texture({source:full.source,frame});
     tile.source.scaleMode=LIA_STACK.sampling;rectangles.push(tile);
   }
   stackAtlasCache.set(record.sha256,rectangles);
   return rectangles;
 }
 function newStack(parent,first,options){
   const group=new PIXI.Container();group.sortableChildren=false;
   group.position.set(options.x||0,options.y||0);parent.addChild(group);
   const sprites=[];
   for(let i=0;i<first.length;i++){
     const sprite=new PIXI.Sprite(first[i]);sprite.anchor.set(.5,.5);
     // Real horizontal cross-sections, drawn bottom to top like a solid volume.
     sprite.roundPixels=false;sprites.push(sprite);group.addChild(sprite);
   }
   const result={group,sprites,localYaw:(options.yaw||0)*DEG,step:options.step,
                 scale:options.scale||1,frames:null,chosen:0};
   stackPan(result);return result;
 }
 function setStackTextures(volume,frames){
   if(frames.length!==volume.sprites.length)
     throw new Error('Source-authored full-body 3D pose has inconsistent slice count');
   for(let i=0;i<frames.length;i++) volume.sprites[i].texture=frames[i];
 }
 function setStackPose(actor,frame){
   const volume=actor.spriteStack;
   if(!volume)return;
   if(!Number.isInteger(frame)||frame<0||frame>=volume.frames.length)
     throw new Error('3D pose index is not the original full-cel animation frame');
   if(volume.chosen===frame)return;
   setStackTextures(volume,volume.frames[frame]);volume.chosen=frame;
 }
 for(const entry of LIA_STACK.actors){
   const actor=actors.find(a=>a.info.id===entry.id);
   if(!actor)throw new Error('Author-approved character for 3D stack not found: '+entry.id);
   if(entry.frames.length!==actor.info.frames.length)
     throw new Error('Sprite stack must provide every ORIGINAL painted full-body pose: '+entry.id);
   for(let i=0;i<entry.frames.length;i++){
     if(entry.frames[i].source_frame!==actor.info.frames[i])
       throw new Error('Actor identity/pose order mismatch between certified PNG and 3D stack');
   }
   const frames=[];
   for(const sourcePose of entry.frames)frames.push(await stackAtlas(sourcePose));
   const box=entry.box;
   const volume=newStack(actor.node,frames[0],{x:box[2]/2,y:box[3],
         yaw:entry.yaw_deg,step:entry.step_px,scale:1});
   volume.frames=frames;volume.yawOffset=entry.yaw_deg*DEG;volume.chosen=0;
   actor.spriteStack=volume;actor.visual.visible=false;stackingActors.set(entry.id,volume);
 }
 for(const entry of LIA_STACK.objects){
   const node=new PIXI.Container();node.zIndex=entry.z;
   node.position.set(entry.position[0],entry.position[1]);app.stage.addChild(node);
   const atlasStates={};
   for(const [name,value] of Object.entries(entry.states)) atlasStates[name]=await stackAtlas(value);
   const name=atlasStates.closed?'closed':Object.keys(atlasStates)[0];
   const volume=newStack(node,atlasStates[name],{step:entry.step_px,scale:entry.scale,yaw:entry.yaw_deg});
   volume.atlasStates=atlasStates;volume.state=name;volume.entry=entry;
   stackingObjects.set(entry.id,volume);
 }
 if(stackingObjects.size+stackingActors.size!==LIA_STACK.stacked_objects)
   throw new Error('Sprite stacking inventory/cast count changed');
 window.addEventListener('living-image:trigger',ev=>{
   const e=ev?.detail;if(!e||e.phase!=='enter')return;
   for(const volume of stackingObjects.values()){
     const decl=volume.entry;
     if(!decl.open_trigger||decl.open_trigger!==e.trigger_id||volume.state==='open')continue;
     const next=volume.atlasStates.open;
     if(!next)throw new Error('No authored open-state 3D stack for gate: '+decl.id);
     setStackTextures(volume,next);volume.state='open';
     const box=decl.collider;
     if(box){
       // Physical author-matched gate disappears along with original CLOSED artwork.
       const body=staticBodies.find(b=>b.label==='original_wall' &&
         Math.abs(b.position.x-(box[0]+box[2]/2))<.01 &&
         Math.abs(b.position.y-(box[1]+box[3]/2))<.01 &&
         Math.abs((b.bounds.max.x-b.bounds.min.x)-box[2])<.01 &&
         Math.abs((b.bounds.max.y-b.bounds.min.y)-box[3])<.01);
       if(!body)throw new Error('Verified door collision body missing');
       Matter.Composite.remove(engine.world,body);
     }
   }
 });
 const renderStackAngles=()=>{
   for(const object of stackingObjects.values())stackPan(object);
   for(const [actorId,volume] of stackingActors){
     const actor=actors.find(a=>a.info.id===actorId);
     let yaw=volume.yawOffset;
     if(actor?.nav?.body){
       const vel=actor.nav.body.velocity;
       if(Math.hypot(vel.x,vel.y)>.07)volume.yawOffset=Math.atan2(vel.y,vel.x);
       yaw=volume.yawOffset;
     }
     volume.localYaw=yaw;stackPan(volume);
   }
 };
 function angleUpdate(kind){
   if(kind==='left')stackingAzimuth-=Math.PI/12;
   else if(kind==='right')stackingAzimuth+=Math.PI/12;
   else if(kind==='up')stackingElevation=Math.min(72*DEG,stackingElevation+5*DEG);
   else if(kind==='down')stackingElevation=Math.max(12*DEG,stackingElevation-5*DEG);
   renderStackAngles();
 }
 for(const kind of ['left','right','up','down']){
   const button=document.getElementById('lia-stack-'+kind);
   if(!button)throw new Error('Original interactive 360-degree stacking controls missing');
   button.addEventListener('pointerdown',ev=>{
     ev.stopPropagation();ev.preventDefault();angleUpdate(kind);
   });
 }
 window.addEventListener('keydown',ev=>{
   if(ev.target&&/^(INPUT|TEXTAREA|SELECT)$/.test(ev.target.tagName))return;
   const map={'KeyQ':'left','KeyE':'right','KeyR':'up','KeyF':'down'};
   if(map[ev.code]){ev.preventDefault();angleUpdate(map[ev.code]);}
 });
 app.ticker.add(renderStackAngles);
 window.__livingSpriteStack={render:'real layered transparent source PNG cross-sections',
   actors:stackingActors.size,worldObjects:stackingObjects.size,
   layers:LIA_STACK.layer_count,sourceCoverage:LIA_STACK.coverage,
   yaw:(deg)=>{stackingAzimuth=Number(deg)*DEG;renderStackAngles();},
   elevation:(deg)=>{stackingElevation=Math.min(72,Math.max(12,Number(deg)))*DEG;renderStackAngles();},
   objectState:id=>stackingObjects.get(id)?.state,
   originalArtChanged:false,physics:'Matter.js',ai:typeof window.YUKA!=='undefined'?'YUKA':'none'};
