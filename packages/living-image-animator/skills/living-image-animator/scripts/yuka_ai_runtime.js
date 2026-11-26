/* YUKA 0.7.8 author-registered 2D NPC logic on ORIGINAL full-body RGBA cels.
   YUKA steers toward A* waypoints. Matter.js ALONE resolves physical contacts.
   Visual frames/clips and node textures are not modified. */
const LIA_AI=JSON.parse(document.getElementById('lia-ai').textContent);
if(!window.YUKA || !YUKA.Vehicle || !YUKA.SeekBehavior || !YUKA.Vector3)
  throw new Error('Подлинный YUKA 0.7.8 не загрузился');
const yukaAgents=new Map();
const aiPlayer=actors.find(a=>a.nav && a.info.id===LIA_AI.player_actor);
if(!aiPlayer)throw new Error('Исходный управляемый персонаж не найден для YUKA');
for(const def of LIA_AI.agents){
  const actor=actors.find(a=>a.nav&&a.info.id===def.actor_id);
  if(!actor)throw new Error('YUKA NPC отсутствует в проверенной карте: '+def.actor_id);
  const v=new YUKA.Vehicle();
  v.maxSpeed=actor.nav.config.speed_px_s*def.speed_multiplier;
  v.maxForce=Math.max(45,v.maxSpeed*12);
  v.updateOrientation=false; // Never rotate or reshape original full-pose sprites.
  v.position.set(actor.nav.body.position.x,0,actor.nav.body.position.y);
  const seek=new YUKA.SeekBehavior(new YUKA.Vector3(v.position.x,0,v.position.z));
  v.steering.add(seek);
  yukaAgents.set(def.actor_id,{actor,def,vehicle:v,seek,state:'patrol',nextRepath:0,
    lostSeconds:0,lastTargetCell:null});
}
let yukaClock=0;
function yukaSight(x0,y0,x1,y1){
  // Segment/AABB clipping against *source-authored* wall rectangles.
  const dx=x1-x0,dy=y1-y0;
  for(const [rx,ry,rw,rh] of S.physics.obstacles){
    let lo=0,hi=1;
    for(const [p,qmin,qmax] of [[dx,rx-x0,rx+rw-x0],[dy,ry-y0,ry+rh-y0]]){
      if(Math.abs(p)<1e-9){if(qmin>0||qmax<0){lo=2;break;}}
      else{const a=qmin/p,b=qmax/p;lo=Math.max(lo,Math.min(a,b));hi=Math.min(hi,Math.max(a,b));}
    }
    if(lo<=hi)return false;
  }
  return true;
}
function yukaDecide(actor){
  const ai=yukaAgents.get(actor.info.id);
  if(!ai)return;
  const n=actor.nav,body=n.body,player=aiPlayer.nav.body.position;
  const dist=Math.hypot(player.x-body.position.x,player.y-body.position.y);
  const sight=yukaSight(body.position.x,body.position.y,player.x,player.y);
  const wantsChase=ai.def.mode==='patrol_chase';
  const detectable=wantsChase&&dist<=ai.def.detection_radius_px&&sight;
  if(ai.state==='patrol' && detectable){
    ai.state='chase';ai.nextRepath=0;ai.lostSeconds=0;
    n.route=[];
  }
  if(ai.state==='chase'){
    if(dist>ai.def.forget_radius_px){ai.lostSeconds=ai.def.forget_after_s;}
    else if(!sight)ai.lostSeconds+=1/60;
    else ai.lostSeconds=0;
    if(ai.lostSeconds>=ai.def.forget_after_s){
      ai.state='patrol';ai.lastTargetCell=null;n.route=[];
      // Return to the existing source-authored patrol waypoint via real A*.
      routeTo(actor,n.config.waypoints[n.waypointIndex]);
      return;
    }
    if(yukaClock>=ai.nextRepath){
      const target=[player.x,player.y];
      const cell=[Math.floor(target[0]/n.config.cell_px),Math.floor(target[1]/n.config.cell_px)];
      if(!ai.lastTargetCell || ai.lastTargetCell[0]!==cell[0] || ai.lastTargetCell[1]!==cell[1] || !n.route.length){
        if(routeTo(actor,target))ai.lastTargetCell=cell;
      }
      ai.nextRepath=yukaClock+ai.def.repath_interval_s;
    }
  }
}
function yukaSteer(actor){
  const ai=yukaAgents.get(actor.info.id);
  if(!ai || !actor.nav.route.length)return null;
  const body=actor.nav.body,nav=actor.nav;
  const target=nav.route[0],d=Math.hypot(target[0]-body.position.x,target[1]-body.position.y);
  if(d<0.001)return {x:0,y:0};
  const vehicle=ai.vehicle;
  vehicle.position.set(body.position.x,0,body.position.y);
  // Matter velocity is pixels/step; YUKA velocity is pixels/second.
  vehicle.velocity.set(body.velocity.x*60,0,body.velocity.y*60);
  ai.seek.target.set(target[0],0,target[1]);
  vehicle.update(1/60);
  const limit=Math.min(d,vehicle.maxSpeed/60);
  let dx=vehicle.velocity.x/60,dy=vehicle.velocity.z/60;
  const mag=Math.hypot(dx,dy);
  if(mag>limit){const ratio=limit/mag;dx*=ratio;dy*=ratio;}
  // A* diagonal movement is prohibited: do not steer into an uncleared cell.
  if(!clampControlsToGrid(body.position.x+dx,body.position.y+dy,nav.config)){
    if(clampControlsToGrid(body.position.x+dx,body.position.y,nav.config))dy=0;
    else if(clampControlsToGrid(body.position.x,body.position.y+dy,nav.config))dx=0;
    else {dx=0;dy=0;}
  }
  return {x:dx,y:dy};
}
window.__livingAI={engine:'YUKA 0.7.8',agents:[...yukaAgents.keys()],
  states:()=>Object.fromEntries([...yukaAgents].map(([id,a])=>[id,a.state])),
  originalCharactersModified:0,collision:'Matter.js',navigation:'PathFinding.js'};
