/**
 * META GAME FUSION — XState 5.33.4 actor-state bridge.
 *
 * States are an authorization layer for NPC transitions, NOT a second steering,
 * navmesh, rigid-body solver, input controller, narrative engine, or renderer.
 * ECS receives only bounded chapter / player-input events. Recast remains path
 * authority, YUKA steers, Rapier moves; all hero actions require player input.
 */
import {createActor, createMachine} from 'xstate';

const ENGINE='xstate@5.33.4';
const SCHEMA='meta-game-fusion.behavior-machines.v1';
const STEP_LIMIT=1/10;
const finitePosition=p=>p&&['x','y','z'].every(k=>Number.isFinite(p[k])&&Math.abs(p[k])<200);
const VALID_STATES=new Set(['patrol','investigate','return','recover']);
const PATROL_MACHINE=createMachine({
  id:'mgf-sentinel',initial:'patrol',
  states:{
    patrol:{on:{
      REACHED:{target:'patrol',reenter:true},
      PLAYER_SIGNAL:'investigate',BLOCKED:'recover',
      SCENE:{target:'patrol',reenter:true}
    }},
    investigate:{on:{
      PLAYER_SIGNAL:{target:'investigate',reenter:true},
      REACHED:'return',TIMEOUT:'return',BLOCKED:'recover',SCENE:'patrol'
    }},
    return:{on:{REACHED:'patrol',PLAYER_SIGNAL:'investigate',BLOCKED:'recover',SCENE:'patrol'}},
    recover:{on:{RETRY:'patrol',PLAYER_SIGNAL:'investigate',SCENE:'patrol'}}
  }
});
const GUIDE_MACHINE=createMachine({
  id:'mgf-guide',initial:'idle',
  states:{
    idle:{on:{ROUTE_READY:'following',ROUTE_FAILED:'blocked'}},
    following:{on:{ROUTE_READY:'following',ROUTE_FAILED:'blocked',REACHED:'arrived'}},
    arrived:{on:{ROUTE_READY:'following',ROUTE_FAILED:'blocked'}},
    blocked:{on:{ROUTE_READY:'following',ROUTE_FAILED:'blocked'}}
  }
});

export class FusionBehaviorXState {
  constructor({world,npcAI,navigation}){
    const plan=world?.behavior_machine;
    const stages=world?.entity_system?.stages;
    const stageValid=Array.isArray(stages)&&stages.length>=1&&stages.length<=24&&
      stages.every(s=>typeof s==='string'&&/^[A-Za-z0-9_-]{1,128}$/.test(s));
    if(plan?.schema!==SCHEMA||plan.engine!==ENGINE||plan.position_authority!=='Rapier'||
      plan.navigation_authority!=='Recast'||plan.steering_authority!=='YUKA'||
      plan.event_authority!=='bitECS'||plan.hero_actions_input_only!==true||
      !stageValid||!Array.isArray(plan.stages)||
      JSON.stringify(plan.stages)!==JSON.stringify(stages)||
      !Array.isArray(plan.agents)||!Array.isArray(npcAI?.agents)||
      plan.agents.length!==npcAI.agents.length||plan.agents.length>2||
      new Set(plan.agents).size!==plan.agents.length||
      !plan.agents.every((id,i)=>id===npcAI.agents[i].id&&/^sentinel-[12]$/.test(id))||
      !navigation||!Number.isFinite(plan.investigation_seconds)||plan.investigation_seconds<1||
      plan.investigation_seconds>15||!Number.isFinite(plan.recovery_seconds)||
      plan.recovery_seconds<.2||plan.recovery_seconds>4){
      throw Error('Invalid XState behavior contract; NPC physics/control preserved');
    }
    this.plan=plan;this.npcAI=npcAI;this.navigation=navigation;
    this.stages=new Set(stages);
    this.actors=new Map();this.positions=new Map();this.elapsed=new Map();
    this.eventCount=0;this.stage=null;this.dialogueOpen=false;
    this.guide=createActor(GUIDE_MACHINE);this.guide.start();
    npcAI.behavior=this;navigation.behavior=this;
    for(const agent of npcAI.agents){
      const actor=createActor(PATROL_MACHINE);
      this.actors.set(agent.id,actor);
      actor.subscribe(snapshot=>{if(VALID_STATES.has(snapshot.value))this._apply(agent,snapshot.value);});
      actor.start();
    }
  }
  _apply(agent,state){
    agent.mode=state;
    this.elapsed.set(agent.id,0);
    if(state==='recover'){
      agent.agent.follow.active=false;
      agent.agent.vehicle.velocity.set(0,0,0);
      agent.status='recovering';
      return;
    }
    let goal;
    if(state==='investigate'){
      goal=this.positions.get(agent.id);
      if(!finitePosition(goal)){
        this._send(agent.id,'BLOCKED');return;
      }
    }else{
      goal=agent.patrol[agent.side];
    }
    const ok=this.npcAI.setDestination(agent,goal);
    if(!ok){this._send(agent.id,'BLOCKED');return;}
    agent.status=state==='investigate'?'investigating':state==='return'?'returning':'patrolling';
  }
  _send(id,type){
    const actor=this.actors.get(id);
    if(!actor)return;
    actor.send({type});this.eventCount++;
  }
  scene(stageId){
    if(!this.stages.has(stageId))throw Error('Unapproved XState chapter');
    this.stage=stageId;this.positions.clear();
    for(const id of this.actors.keys())this._send(id,'SCENE');
  }
  dialogue(open){if(typeof open!=='boolean')throw Error('Invalid XState dialogue state');this.dialogueOpen=open;}
  signal(id,position){
    if(!finitePosition(position)||!this.actors.has(id))return false;
    const copy={x:position.x,y:position.y,z:position.z};
    this.positions.set(id,copy);this._send(id,'PLAYER_SIGNAL');
    return this.state(id)==='investigate';
  }
  reached(id){
    const state=this.state(id);
    const agent=this.npcAI.agents.find(a=>a.id===id);
    if(!agent)return;
    if(state==='patrol')agent.side=1-agent.side;
    if(state==='return')agent.side=1-agent.side;
    if(state!=='recover')this._send(id,'REACHED');
  }
  blocked(id){if(this.state(id)!=='recover')this._send(id,'BLOCKED');}
  step(dt){
    if(this.dialogueOpen)return;
    const delta=Math.min(STEP_LIMIT,Math.max(0,Number.isFinite(dt)?dt:0));
    for(const id of this.actors.keys()){
      const state=this.state(id);const elapsed=(this.elapsed.get(id)||0)+delta;
      this.elapsed.set(id,elapsed);
      if(state==='investigate'&&elapsed>=this.plan.investigation_seconds){
        this.positions.delete(id);this._send(id,'TIMEOUT');
      }else if(state==='recover'&&elapsed>=this.plan.recovery_seconds){
        this._send(id,'RETRY');
      }
    }
  }
  routeGuide(ok){this.guide.send({type:ok?'ROUTE_READY':'ROUTE_FAILED'});this.eventCount++;}
  guideReached(){if(this.guide.getSnapshot().value==='following'){
    this.guide.send({type:'REACHED'});this.eventCount++;}}
  state(id){return this.actors.get(id)?.getSnapshot()?.value||null;}
  get stats(){
    return Object.freeze({engine:ENGINE,stage:this.stage,events:this.eventCount,
      npcStates:Object.fromEntries([...this.actors.keys()].map(id=>[id,this.state(id)])),
      guideState:this.guide.getSnapshot().value,dialogueOpen:this.dialogueOpen,
      steering:'YUKA',physics:'Rapier',navigation:'Recast',eventSource:'bitECS',
      heroCommands:0});
  }
  destroy(){
    if(this.npcAI?.behavior===this)this.npcAI.behavior=null;
    if(this.navigation?.behavior===this)this.navigation.behavior=null;
    for(const a of this.actors.values())a.stop();
    this.guide.stop();this.actors.clear();this.positions.clear();this.elapsed.clear();
  }
}
