// Shared physics, independent of network and rendering. Rapier must be initialized by caller.
export const DT=1/30, SPEED=4;
export const DEMO_BOXES=Object.freeze([
 [0,-0.5,0,50,0.5,50],[-50,2,0,0.5,2,50],[50,2,0,0.5,2,50],
 [0,2,-50,50,2,0.5],[0,2,50,50,2,0.5],[0,1,6,2,1,1]
].map(Object.freeze));
const HEIGHT=0.8, RADIUS=0.3, HALF=HEIGHT-RADIUS;
export function createPhysics(R,{boxes=DEMO_BOXES}={}){
 const world=new R.World({x:0,y:-9.81,z:0});world.timestep=DT;
 const actors=new Map(), statics=new Set();let closed=false;
 for(const b of boxes){if(!Array.isArray(b)||b.length!==6||!b.every(Number.isFinite)||b.slice(3).some(n=>n<=0))throw Error('Invalid static collider');
  const [x,y,z,hx,hy,hz]=b;const c=world.createCollider(R.ColliderDesc.cuboid(hx,hy,hz).setTranslation(x,y,z));statics.add(c.handle);}
 world.step();
 function add(id,spawn={x:0,y:0.05,z:0}){if(closed||actors.has(id)||!['x','y','z'].every(k=>Number.isFinite(spawn[k])))throw Error('Invalid actor');
  const body=world.createRigidBody(R.RigidBodyDesc.kinematicPositionBased().setTranslation(spawn.x,spawn.y+HEIGHT,spawn.z));
  const collider=world.createCollider(R.ColliderDesc.capsule(HALF,RADIUS),body);
  const controller=world.createCharacterController(0.01);controller.enableSnapToGround(0.2);
  actors.set(id,{body,collider,controller,vy:0,yaw:0,anim:'idle',phase:0});
 }
 function remove(id){const a=actors.get(id);if(!a)return;world.removeCharacterController(a.controller);world.removeRigidBody(a.body);actors.delete(id);}
 function sample(id){const a=actors.get(id);if(!a)return null;const p=a.body.translation();return {x:p.x,y:p.y-HEIGHT,z:p.z,yaw:a.yaw,anim:a.anim,phase:a.phase};}
 function step(inputs){if(closed)throw Error('Physics closed');
  for(const [id,a] of actors){const i=inputs.get(id)||{};let dx=Number.isFinite(i.dx)?Math.max(-1,Math.min(1,i.dx)):0,dz=Number.isFinite(i.dz)?Math.max(-1,Math.min(1,i.dz)):0;const norm=Math.max(1,Math.hypot(dx,dz));dx/=norm;dz/=norm;
   a.vy=Math.max(-20,a.vy-9.81*DT);
   // Static geometry only: casual avatars do not push or block one another.
   a.controller.computeColliderMovement(a.collider,{x:dx*SPEED*DT,y:a.vy*DT,z:dz*SPEED*DT},undefined,undefined,c=>statics.has(c.handle));
   const d=a.controller.computedMovement(),p=a.body.translation();if(a.controller.computedGrounded())a.vy=0;
   a.body.setNextKinematicTranslation({x:p.x+d.x,y:p.y+d.y,z:p.z+d.z});
   if(Math.hypot(dx,dz)>0.01)a.yaw=Math.atan2(dx,dz);
   const moved=Math.hypot(d.x,d.z);a.anim=moved>0.001?'walk':'idle';a.phase=a.anim==='walk'?(a.phase+moved/SPEED)%1:0;
  }world.step();
 }
 return {add,remove,sample,step,dispose(){if(closed)return;for(const id of [...actors.keys()])remove(id);closed=true;world.free();}};
}
// Solo and P2P use the exact same movement controller. Call advance from existing loop only.
export function createLocalPhysics(R,options={}){const sim=createPhysics(R,options);sim.add('self',options.spawn);let acc=0,closed=false;return {advance(seconds,input){if(closed)return;if(!Number.isFinite(seconds)||seconds<0)return;acc=Math.min(acc+seconds,DT*5);while(acc>=DT){sim.step(new Map([['self',input]]));acc-=DT;}},sample:()=>sim.sample('self'),dispose(){if(!closed){closed=true;sim.dispose();}}};}
