/**
 * META GAME FUSION × Howler 2.2.4. Original, packaged Ogg/MP3 audio only.
 * User gesture unlocks sound. YUKA/Recast are behavior/path authorities;
 * Rapier positions are the only spatial sources. No hero automation.
 */
import * as THREE from 'three';
import {Howl, Howler} from 'howler';

const STYLES=new Set(['nocturne','ink','ember','horror','dream','pixel']);
const HEX=/^[a-f0-9]{64}$/;
const MOODS=Object.freeze({
  nocturne:{wind:.30,drone:.21},ink:{wind:.26,drone:.12},
  ember:{wind:.17,drone:.27},horror:{wind:.24,drone:.32},
  dream:{wind:.20,drone:.14},pixel:{wind:.18,drone:.13},
});
const EXPECTED=['wind','drone','step','rune'];
const clip=(x,a,b)=>Math.max(a,Math.min(b,x));
const distance=(a,b)=>Math.hypot(a.x-b.x,a.z-b.z);
const finitePosition=p=>p&&['x','y','z'].every(k=>Number.isFinite(p[k])&&Math.abs(p[k])<250);
const forward=new THREE.Vector3();

function verifiedSources(name,entry){
  if(entry?.origin!=='original-synthesized'||entry?.license!=='authored-demo'||
     !Array.isArray(entry.sources)||entry.sources.length!==2)throw Error('Audio pack provenance error: '+name);
  return entry.sources.map((x,i)=>{
    const ext=i===0?'ogg':'mp3';
    if(x.uri!==`/audio/${name}.${ext}`||!HEX.test(x.sha256)||!Number.isInteger(x.bytes)||x.bytes<200||x.bytes>2_000_000)
      throw Error('Untrusted audio track: '+name);
    return x.uri;
  });
}

export class FusionSpatialAudio {
  constructor({world}){
    const cfg=world?.audio;
    if(cfg?.schema!=='meta-game-fusion.spatial-audio.v1'||cfg?.engine!=='howler@2.2.4'||
       cfg.external_audio!==false||cfg.audio_locked_until_user_gesture!==true||
       Object.keys(cfg.assets??{}).sort().join(',')!==EXPECTED.slice().sort().join(','))
      throw Error('Invalid Howler audio manifest');
    this.world=world;this.cues=cfg.scene_cues||{};
    this.stage=null;this.style=world.visual_direction?.default||'nocturne';
    this.enabled=false;this.lastError='';this.realPlaying=false;
    this.dialogue=false;this.mood={...MOODS.nocturne};this.quality='cinema';
    this.playerAt=null;this.stepClock=new Map();this.stepClock.set('player',0);
    this.tracks={};
    for(const name of EXPECTED){
      this.tracks[name]=new Howl({src:verifiedSources(name,cfg.assets[name]),
        preload:false,autoplay:false,loop:name==='wind'||name==='drone',
        volume:0,html5:false,pool:name==='step'?5:2,
        onplay:()=>{this.realPlaying=true;},
        onplayerror:(id,e)=>{this.lastError=`${name}: ${String(e).slice(0,100)}`;},
        onloaderror:(id,e)=>{this.lastError=`${name}: ${String(e).slice(0,100)}`;},
      });
    }
    this.tracks.step.volume(.25);
    this.tracks.rune.volume(.36);
    this.lastNpc=new Map();
  }
  async toggle(){
    if(this.enabled){this.disable();return false;}
    // Must run from actual user button/key gesture, never an autoplay effect.
    try{
      // Both resume() and play() are invoked synchronously in the user gesture
      // (important for iOS Safari audio activation).
      const pending=Howler.ctx?.state==='suspended'?Howler.ctx.resume():null;
      this.enabled=true;this.lastError='';
      for(const name of ['wind','drone']){
        const h=this.tracks[name];if(!h.playing())h.play();
      }
      this.applyMix();
      if(pending)await pending;
      return true;
    }catch(e){this.disable();this.lastError=String(e?.message||e);return false;}
  }
  disable(){
    this.enabled=false;
    for(const h of Object.values(this.tracks))h.stop();
    this.realPlaying=false;
    this.stepClock.clear();this.stepClock.set('player',0);
  }
  enter(nodeId){
    const cue=this.cues[nodeId];
    if(!cue || !STYLES.has(cue.style)||!MOODS[cue.style])return false;
    this.stage=nodeId;this.style=cue.style;
    this.mood={...MOODS[cue.style]};
    const p=this.world.markers?.[nodeId];
    if(finitePosition(p))this.tracks.drone.pos(p.x,p.y+1,p.z);
    this.applyMix();
    return true;
  }
  applyMix(){
    if(!this.enabled)return;
    const duck=this.dialogue?.35:1;
    for(const name of ['wind','drone']){
      const h=this.tracks[name];
      const target=clip(this.mood[name]*duck,0,.38);
      h.fade(h.volume(),target,850);
    }
  }
  setDialogue(open){this.dialogue=Boolean(open);this.applyMix();}
  setQuality(mode){if(['cinema','eco','off'].includes(mode))this.quality=mode;}
  pulse(p){
    if(!this.enabled||!finitePosition(p))return;
    const h=this.tracks.rune;const id=h.play();h.pos(p.x,p.y,p.z,id);h.volume(.37,id);
  }
  _step(pos,key,rate=.55){
    if(!finitePosition(pos))return;
    const h=this.tracks.step;
    const id=h.play();
    h.pos(pos.x,pos.y,pos.z,id);h.volume(.22,id);
    this.stepClock.set(key,rate);
  }
  update(dt,{camera,player,grounded,paused=false,npcs=[]}={}){
    if(!this.enabled||!camera||!finitePosition(player))return;
    dt=clip(Number(dt)||0,0,.075);
    camera.getWorldDirection(forward);
    Howler.pos(camera.position.x,camera.position.y,camera.position.z);
    Howler.orientation(forward.x,forward.y,forward.z,0,1,0);
    for(const [key,remaining] of this.stepClock)this.stepClock.set(key,Math.max(0,remaining-dt));
    if(this.playerAt){
      const displacement=distance(this.playerAt,player);
      // Real Rapier movement, not keyboard input (no sound for a wall push).
      if(!paused&&grounded&&displacement>.022&&displacement<.3&&(this.stepClock.get('player')||0)===0){
        this._step(player,'player',.33);
      }
    }
    this.playerAt={x:player.x,y:player.y,z:player.z};
    // At most 2 NPCs; no additional physics or navigation queries.
    for(const npc of npcs.slice(0,2)){
      if(!npc||typeof npc.id!=='string'||!finitePosition(npc.position))continue;
      const key='npc:'+npc.id,prior=this.lastNpc.get(key),now=npc.position;
      if(prior&&!paused&&distance(prior,now)>.024&&distance(prior,now)<.3&&
        distance(player,now)<13&&(this.stepClock.get(key)||0)===0&&
        (this.quality==='cinema'||npc.id==='sentinel-1')){
        this._step(now,key,.61);
      }
      this.lastNpc.set(key,{x:now.x,y:now.y,z:now.z});
    }
  }
  get stats(){return Object.freeze({engine:'howler@2.2.4',enabled:this.enabled,
    actuallyStarted:this.realPlaying,stage:this.stage,quality:this.quality,
    originalAudio:true,remoteAudio:false,error:this.lastError||null});}
  destroy(){this.disable();for(const h of Object.values(this.tracks))h.unload();}
}
