/**
 * META GAME FUSION YUKA steering @0.7.8.
 * Navigation belongs to Recast; collisions/actual positions belong to Rapier.
 * YUKA calculates desired movement only; it never mutates the player, scene
 * chapter, GLB art, or physics authority. Two original animated NPCs plus scout.
 */
import * as THREE from 'three';
import {Vehicle, Path, Vector3, FollowPathBehavior} from 'yuka';

const STEP=1/60;
const clamp=(v,lo,hi)=>Math.max(lo,Math.min(hi,v));
const dist=(a,b)=>Math.hypot(a.x-b.x,a.z-b.z);
const safePoint=p=>p&&['x','z'].every(k=>typeof p[k]==='number'&&Number.isFinite(p[k])&&Math.abs(p[k])<200);

function makeVehicle(x,z,speed=2.4){
  const vehicle=new Vehicle();
  vehicle.position.set(x,0,z);
  vehicle.maxSpeed=speed;
  vehicle.maxForce=18;
  vehicle.mass=1;
  vehicle.updateOrientation=false;
  const path=new Path();
  const follow=new FollowPathBehavior(path,0.55);
  vehicle.steering.add(follow);
  follow.active=false;
  return {vehicle,path,follow,last:{x,z},stalled:0,target:null};
}
function setRoute(agent,route,target){
  if(!Array.isArray(route)||route.length<1||route.length>1024||!route.every(safePoint))return false;
  agent.path.clear();
  for(const p of route)agent.path.add(new Vector3(p.x,0,p.z));
  agent.target={x:target.x,z:target.z};
  agent.vehicle.velocity.set(0,0,0);
  agent.follow.active=true;
  agent.stalled=0;
  return true;
}
function steer(agent,physical){
  if(!safePoint(physical)||!agent.follow.active||!agent.target)return {x:0,z:0};
  // Do not let YUKA's predicted position supersede actual Rapier displacement.
  agent.vehicle.position.set(physical.x,0,physical.z);
  agent.vehicle.velocity.y=0;
  if(dist(physical,agent.target)<0.62){agent.follow.active=false;agent.vehicle.velocity.set(0,0,0);return{x:0,z:0};}
  agent.vehicle.update(STEP);
  const v=agent.vehicle.velocity;
  return {x:clamp(v.x/2.9,-1,1),z:clamp(v.z/2.9,-1,1)};
}
function createSentinel(scene,index){
  const colors=index===0?{coat:'#283d4c',metal:'#b77d5f',glow:'#efac75'}:
    {coat:'#302b43',metal:'#9680ad',glow:'#bda8fd'};
  const root=new THREE.Group();root.name=`YUKA Sentinel ${index+1}`;
  scene.add(root);
  const coat=new THREE.MeshStandardMaterial({color:colors.coat,roughness:.85,flatShading:true});
  const iron=new THREE.MeshStandardMaterial({color:colors.metal,roughness:.55,metalness:.48});
  const glow=new THREE.MeshStandardMaterial({color:colors.glow,emissive:colors.glow,emissiveIntensity:2.4});
  const torso=new THREE.Mesh(new THREE.ConeGeometry(.38,1.05,7),coat);torso.position.y=.18;root.add(torso);
  const head=new THREE.Mesh(new THREE.IcosahedronGeometry(.26,1),iron);head.position.y=.88;root.add(head);
  const arms=[];
  for(const side of[-1,1]){
    const pivot=new THREE.Group();pivot.position.set(side*.31,.5,0);root.add(pivot);
    const limb=new THREE.Mesh(new THREE.CapsuleGeometry(.075,.47,3,6),coat);
    limb.position.y=-.37;pivot.add(limb);
    arms.push(pivot);
    const eye=new THREE.Mesh(new THREE.SphereGeometry(.053,7,5),glow);
    eye.position.set(side*.11,.01,-.22);head.add(eye);
  }
  const lantern=new THREE.Mesh(new THREE.OctahedronGeometry(.12,0),glow);
  lantern.position.set(0,-.48,-.1);head.add(lantern);
  const light=new THREE.PointLight(colors.glow,2.4,4.6);light.position.set(0,.95,-.25);root.add(light);
  return {root,torso,head,arms,light,materials:[coat,iron,glow],lantern};
}

export class FusionYukaAI{
  constructor({scene,physics,navigation,spatial,world}){
    if(world?.npc_ai?.engine!=='yuka@0.7.8'||world.npc_ai.navigation_authority!=='Recast'||world.npc_ai.physics_authority!=='Rapier')
      throw new Error('Invalid YUKA NPC manifest');
    this.scene=scene;this.physics=physics;this.navigation=navigation;this.spatial=spatial;
    this.stage='';this.signalTimeout=0;this.signalTarget=null;this.behavior=null;
    this.cues=world.npc_ai.scene_cues||{};
    this.guide=makeVehicle(physics.guidePosition.x,physics.guidePosition.z,2.9);
    this.agents=[];this.lastProbe=0;this.guideStall=0;
    this.guideLast={x:physics.guidePosition.x,z:physics.guidePosition.z};
    for(const cfg of world.npc_ai.patrols||[]){
      if(this.agents.length>=2||!/^sentinel-[12]$/.test(cfg.id)||!safePoint(cfg.start)||!safePoint(cfg.end))throw new Error('Invalid authored patrol');
      if(navigation.closest(cfg.start)===null||navigation.closest(cfg.end)===null)
        throw new Error('NPC patrol outside Recast NavMesh');
      physics.createPatrolAgent(cfg.id,cfg.start.x,cfg.start.z);
      const a=makeVehicle(cfg.start.x,cfg.start.z,2.25);
      const art=createSentinel(scene,this.agents.length);
      const actor={id:cfg.id,agent:a,art,patrol:[cfg.start,cfg.end],side:1,motion:0,
        mode:'patrol',status:'idle',replan:0};
      this.agents.push(actor);
      this.setDestination(actor,cfg.end);
    }
    navigation.steering=this;
    if(navigation.path.length&&navigation.target)this.setGuidePath(navigation.path,navigation.target);
  }
  setDestination(actor,point){
    const physical=this.physics.patrols.get(actor.id)?.body?.translation();
    const route=this.navigation.routeBetween(physical||actor.patrol[0],point);
    if(!route||!setRoute(actor.agent,route,point)){
      actor.agent.follow.active=false;actor.status='blocked';return false;
    }
    actor.status='following';actor.replan=0;return true;
  }
  setGuidePath(points,target){return setRoute(this.guide,points,target);}
  guideCommand(){
    if(!this.guide.follow.active)return {x:0,z:0};
    const cmd=steer(this.guide,this.physics.guidePosition);
    if(!this.guide.follow.active){this.navigation.status='Проводник у цели';this.navigation.route.visible=false;this.behavior?.guideReached();}
    return cmd;
  }
  enter(stageId){
    this.stage=String(stageId||'').slice(0,128);
    const style=this.cues[this.stage]?.style||'nocturne';
    const palette={ink:'#e8d3b0',nocturne:'#a4b8c8',horror:'#a4f2d1',ember:'#ff995d',dream:'#d1a1ff',pixel:'#f5bb86'};
    for(const a of this.agents){
      a.art.materials[2].emissive.set(palette[style]);
      a.art.materials[2].color.set(palette[style]);
      a.art.light.color.set(palette[style]);
      a.agent.vehicle.maxSpeed=style==='horror'?2.7:style==='dream'?1.8:2.25;
      a.status=a.status==='blocked'?'blocked':'patrolling';
    }
  }
  signalAt(pos){
    if(!safePoint(pos))return;
    this.signalTimeout=7.5;this.signalTarget={x:pos.x,z:pos.z};
    for(const a of this.agents){
      const p=this.physics.patrols.get(a.id)?.body.translation();
      if(!p||dist(p,pos)>11)continue;
      // A player's actual interaction may prompt an NPC to investigate;
      // no NPC may trigger a player action or move a hero on its own.
      if(this.spatial?.lineOfSight&&!this.spatial.lineOfSight(
        {x:p.x,y:p.y+.6,z:p.z},{x:pos.x,y:pos.y+.6,z:pos.z}))continue;
      if(this.behavior){this.behavior.signal(a.id,pos);}
      else if(this.setDestination(a,pos)){a.mode='investigate';a.status='investigating';}
    }
  }
  commandPatrols(){
    if(this.behavior)this.behavior.step(STEP);
    else {this.signalTimeout=Math.max(0,this.signalTimeout-STEP);}
    if(!this.behavior&&this.signalTimeout===0&&this.signalTarget){
      this.signalTarget=null;
      for(const a of this.agents){
        if(a.mode==='investigate'){
          a.mode='patrol';a.side=1-a.side;
          this.setDestination(a,a.patrol[a.side]);
        }
      }
    }
    const commands={};
    for(const a of this.agents){
      const p=this.physics.patrols.get(a.id)?.body.translation();
      if(!p)continue;
      if(a.agent.target&&dist(p,a.agent.target)<.7){
        a.agent.follow.active=false;
        if(this.behavior)this.behavior.reached(a.id);
        else{
          if(a.mode==='investigate'){a.mode='patrol';a.side=1-a.side;}
          else{a.side=1-a.side;}
          this.setDestination(a,a.patrol[a.side]);
        }
      }
      // Retrace a Recast route after colliding with an unanticipated dynamic crate.
      a.replan+=STEP;
      if(a.replan>2.4){
        if(a.agent.follow.active){
          if(dist(p,a.agent.last)<.21){
            if(this.behavior)this.behavior.blocked(a.id);
            else this.setDestination(a,a.agent.target);
          }
        }else if(a.status==='blocked'&&!this.behavior)this.setDestination(a,a.patrol[a.side]);
        a.agent.last={x:p.x,z:p.z};a.replan=0;
      }
      const cmd=steer(a.agent,p);
      a.motion=Math.hypot(cmd.x,cmd.z);
      commands[a.id]=cmd;
    }
    return commands;
  }
  afterStep(){
    const guidePos=this.physics.guidePosition;
    if(guidePos&&this.guide.follow.active){
      this.guideStall+=STEP;
      if(this.guideStall>2.0){
        if(dist(guidePos,this.guideLast)<.2&&this.navigation.target)this.navigation.plan();
        this.guideLast={x:guidePos.x,z:guidePos.z};this.guideStall=0;
      }
    }else if(guidePos){this.guideLast={x:guidePos.x,z:guidePos.z};this.guideStall=0;}
    for(const a of this.agents){
      const p=this.physics.patrols.get(a.id)?.body.translation();
      if(!p)continue;
      // Only Rapier positions drive the rendered actor.
      a.art.root.position.set(p.x,p.y-.83,p.z);
      const vx=a.agent.vehicle.velocity.x,vz=a.agent.vehicle.velocity.z;
      if(vx*vx+vz*vz>.01)a.art.root.rotation.y=Math.atan2(-vx,-vz);
    }
  }
  animate(t,paused){
    for(let i=0;i<this.agents.length;i++){
      const a=this.agents[i],phase=t*(3.5+a.motion*3)+i*2.7;
      const amplitude=paused?.2:(.27+.45*Math.min(1,a.motion));
      a.art.arms[0].rotation.x= Math.sin(phase)*amplitude;
      a.art.arms[1].rotation.x=-Math.sin(phase)*amplitude;
      a.art.head.rotation.z=Math.sin(t*1.7+i*1.3)*.10;
      a.art.head.rotation.y=Math.cos(t*1.19+i)*.23+(a.mode==='investigate'?.22:0);
      a.art.torso.scale.set(1+.045*Math.sin(t*1.5+i),1+.035*Math.sin(t*1.5+i),1);
      a.art.light.intensity=(2.2+.8*(.5+.5*Math.sin(t*3.2+i)))*(a.mode==='investigate'?1.35:a.mode==='recover'?.50:1);
    }
  }
  get stats(){
    return Object.freeze({engine:'yuka@0.7.8',navAuthority:'Recast',physicsAuthority:'Rapier',
      activeNPCs:this.agents.length+1,patrols:this.agents.map(a=>({id:a.id,mode:a.mode,status:a.status,
        x:this.physics.patrols.get(a.id)?.body.translation().x??null,
        z:this.physics.patrols.get(a.id)?.body.translation().z??null})),stage:this.stage});
  }
  destroy(){
    if(this.navigation.steering===this)this.navigation.steering=null;
    for(const a of this.agents){this.scene.remove(a.art.root);
      for(const m of a.art.materials)m.dispose();
      a.art.root.traverse(o=>{if(o.isMesh)o.geometry.dispose();});
    }
    this.agents=[];
  }
}
