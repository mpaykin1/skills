/**
 * META GAME FUSION — bitECS 0.4.0 runtime integration.
 *
 * Rapier owns every physical transform, Recast owns navigable paths, YUKA owns
 * NPC steering intent. The ECS is a read-only spatial projection of Rapier and
 * a bounded, deterministic orchestration bus for approved story events.
 *
 * No player input is created here. Never rewrites an existing hero or imported
 * GLB; all animation and user media remain in their owning subsystems.
 */
import {addComponent, addEntity, createWorld, query} from 'bitecs';

const SCHEMA='meta-game-fusion.ecs-world.v1';
const ENGINE='bitecs@0.4.0';
const MAX_ACTORS=16;
const VALID_QUALITY=new Set(['cinema','eco','off']);
const clamp=(n,lo,hi)=>Math.max(lo,Math.min(hi,n));
const finite=p=>p&&['x','y','z'].every(k=>Number.isFinite(p[k])&&Math.abs(p[k])<250);

export class FusionECS {
  constructor({world,systems=()=>({})}){
    const cfg=world?.entity_system;
    if(cfg?.schema!==SCHEMA||cfg?.engine!==ENGINE||cfg?.position_authority!=='Rapier'||
      cfg?.navigation_authority!=='Recast'||cfg?.steering_authority!=='YUKA'||
      cfg?.hero_actions_input_only!==true||cfg?.max_entities!==MAX_ACTORS||
      !Array.isArray(cfg?.stages)||cfg.stages.length>24||
      !cfg.stages.every(id=>typeof id==='string'&&/^[A-Za-z0-9_\-]{1,128}$/.test(id)) ||
      new Set(cfg.stages).size!==cfg.stages.length || typeof systems!=='function')
      throw Error('Invalid bitECS/Rapier authoritative world manifest');
    this.stages=new Set(cfg.stages);
    this.getSystems=systems;
    this.Position={x:[],y:[],z:[]};
    this.Velocity={x:[],y:[],z:[]};
    this.Player=[];this.Scout=[];this.Sentinel=[];this.AudioEmitter=[];
    this.world=createWorld({components:{Position:this.Position,Velocity:this.Velocity,
      Player:this.Player,Scout:this.Scout,Sentinel:this.Sentinel,AudioEmitter:this.AudioEmitter}});
    this.ids=new Map();this.names=new Map();this.last=new Map();
    this.queue=[];this.totalEvents=0;this.totalFrames=0;
    this.stage=null;this.quality='cinema';
    this._spawn('player','player');
    this._spawn('scout','scout');
  }
  _spawn(id,role){
    if(this.ids.has(id))return this.ids.get(id);
    if(this.ids.size>=MAX_ACTORS)throw Error('ECS actor budget exceeded');
    const eid=addEntity(this.world);
    addComponent(this.world,eid,this.Position);
    addComponent(this.world,eid,this.Velocity);
    if(role==='player')addComponent(this.world,eid,this.Player);
    else if(role==='scout')addComponent(this.world,eid,this.Scout);
    else if(role==='sentinel'){
      addComponent(this.world,eid,this.Sentinel);
      addComponent(this.world,eid,this.AudioEmitter);
    }else throw Error('Unsupported ECS actor role');
    this.ids.set(id,eid);this.names.set(eid,id);
    return eid;
  }
  _record(id,pos,dt){
    if(!finite(pos))return;
    const eid=this.ids.get(id);if(eid===undefined)return;
    const old=this.last.get(eid),step=Math.max(1/120,Math.min(.1,dt));
    this.Position.x[eid]=pos.x;this.Position.y[eid]=pos.y;this.Position.z[eid]=pos.z;
    this.Velocity.x[eid]=old?clamp((pos.x-old.x)/step,-16,16):0;
    this.Velocity.y[eid]=old?clamp((pos.y-old.y)/step,-16,16):0;
    this.Velocity.z[eid]=old?clamp((pos.z-old.z)/step,-16,16):0;
    this.last.set(eid,{x:pos.x,y:pos.y,z:pos.z});
  }
  /** Synchronize FROM Rapier: no ECS state is ever written TO Rapier. */
  sync({physics,npcAI,dt=1/60}){
    if(!physics)return;
    this._record('player',physics.lastPos,dt);
    this._record('scout',physics.guidePosition,dt);
    for(const actor of (npcAI?.agents||[]).slice(0,2)){
      if(!/^sentinel-[12]$/.test(actor.id))continue;
      const physical=physics.patrols.get(actor.id)?.body?.translation();
      if(!physical)continue;
      this._spawn(actor.id,'sentinel');
      this._record(actor.id,physical,dt);
    }
    this.totalFrames++;
  }
  /** The spatial audio engine reads query results, never inferred NPC motion. */
  audioNpcs(){
    const out=[];
    for(const eid of query(this.world,[this.Position,this.Sentinel,this.AudioEmitter])){
      const id=this.names.get(eid);
      if(!id||!this.last.has(eid))continue;
      out.push({id,position:{x:this.Position.x[eid],y:this.Position.y[eid],z:this.Position.z[eid]}});
    }
    return out;
  }
  /** Ordered and bounded ECS event stream. Only internally-authorized types. */
  emit(type,detail={}){
    if(!['scene:enter','player:interact','dialogue:state','quality:mode'].includes(type))
      throw Error('Unrecognized ECS game event');
    if(this.queue.length>=16)throw Error('ECS event budget exceeded');
    if(type==='scene:enter'&&!this.stages.has(detail.id))throw Error('ECS stage not in validated graph');
    if(type==='player:interact'&&!finite(detail.position))throw Error('Invalid player interaction position');
    if(type==='dialogue:state'&&typeof detail.open!=='boolean')throw Error('Invalid dialogue state');
    if(type==='quality:mode'&&!VALID_QUALITY.has(detail.mode))throw Error('Invalid quality state');
    this.queue.push({type,detail});
    this.flush();
  }
  flush(){
    const system=this.getSystems()||{};
    while(this.queue.length){
      const {type,detail}=this.queue.shift();
      if(type==='scene:enter'){
        this.stage=detail.id;
        system.livingWorld?.enter(detail.id);
        system.particleVFX?.enter(detail.id);
        system.npcAI?.enter(detail.id);
        system.behavior?.scene(detail.id);
        system.audio?.enter(detail.id);
        if(detail.style)system.postFX?.setMood(detail.style);
      }else if(type==='player:interact'){
        system.particleVFX?.pulse();
        system.audio?.pulse(detail.position);
        system.npcAI?.signalAt(detail.position);
      }else if(type==='dialogue:state'){
        system.audio?.setDialogue(detail.open);
        system.behavior?.dialogue(detail.open);
      }else if(type==='quality:mode'){
        this.quality=detail.mode;
        system.audio?.setQuality(detail.mode);
      }
      this.totalEvents++;
    }
  }
  get stats(){
    return Object.freeze({engine:ENGINE,entities:this.ids.size,frameCount:this.totalFrames,
      eventCount:this.totalEvents,stage:this.stage,quality:this.quality,
      sentinels:query(this.world,[this.Position,this.Sentinel]).length,
      rapierAuthoritative:true,playerInputAutomated:false});
  }
}
