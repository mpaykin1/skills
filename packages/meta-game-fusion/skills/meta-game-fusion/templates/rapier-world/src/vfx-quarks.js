/** META GAME FUSION — bounded, read-only visual particle adapter.
 * three.quarks@0.18.0 + Three.js@0.186.1; no gameplay physics, no hero actions.
 * Scene cues originate only from validated Rete/Ink scene changes.
 */
import * as THREE from 'three';
import {BatchedRenderer, ParticleSystem, ConstantValue, IntervalValue,
  ConstantColor, PointEmitter, RenderMode} from 'three.quarks';

const COLORS=Object.freeze({
  nocturne:['#738a97','#94b5c0','#dbf2fd'],
  ink:['#c1bdab','#ddd0b8','#f8e8c0'],
  ember:['#6f6268','#c46a53','#ffcb89'],
  horror:['#576a69','#779d91','#c3ddd0'],
  dream:['#76648b','#ac8dc7','#f0b9ed'],
  pixel:['#798078','#d3ae86','#ffe6aa'],
});
const CHANNELS=Object.freeze([
  {id:'mist',max:64,rate:3.5,life:[4.5,7],size:[1.15,2.3],speed:.08,opacity:.16,additive:false,offset:[-4,1.8,-3]},
  {id:'ash',max:112,rate:8,life:[2.5,4.5],size:[.07,.22],speed:.45,opacity:.39,additive:false,offset:[2,.9,-1]},
  {id:'rune',max:70,rate:4.2,life:[1.1,2.3],size:[.10,.30],speed:.58,opacity:.65,additive:true,offset:[0,5.3,-6.7]},
]);
const TOTAL=CHANNELS.reduce((sum,c)=>sum+c.max,0);

function softTexture(){
  const side=32,bytes=new Uint8Array(side*side*4);
  for(let y=0;y<side;y++)for(let x=0;x<side;x++){
    const r=Math.hypot((x+.5-side/2)/(side/2),(y+.5-side/2)/(side/2));
    const a=Math.max(0,1-r);const i=(y*side+x)*4;
    bytes[i]=255;bytes[i+1]=255;bytes[i+2]=255;
    bytes[i+3]=Math.round(255*a*a*(3-2*a));
  }
  const texture=new THREE.DataTexture(bytes,side,side,THREE.RGBAFormat);
  texture.needsUpdate=true;texture.magFilter=THREE.LinearFilter;
  texture.minFilter=THREE.LinearFilter;
  return texture;
}

export class FusionQuarksVFX {
  constructor({scene,world}) {
    if(world?.particle_fx?.engine!=='three.quarks@0.18.0')
      throw new Error('Unrecognized VFX specification (expected three.quarks@0.18.0)');
    this.scene=scene;
    this.markers=world.markers||{};
    this.styles=world.visual_direction?.by_node||{};
    this.defaultStyle=world.visual_direction?.default||'nocturne';
    this.mode='off';this.active=null;this.pulseTimer=0;
    this.batch=new BatchedRenderer();
    scene.add(this.batch);
    this.texture=softTexture();
    this.channels=[];
    for(const conf of CHANNELS){
      const mat=new THREE.MeshBasicMaterial({
        color:'#ffffff',map:this.texture,transparent:true,opacity:conf.opacity,
        depthWrite:false,blending:conf.additive?THREE.AdditiveBlending:THREE.NormalBlending,
        side:THREE.DoubleSide, toneMapped:false,
      });
      const rate=new ConstantValue(0);
      const system=new ParticleSystem({
        duration:8,looping:true,worldSpace:true,maxParticle:conf.max,
        startLife:new IntervalValue(...conf.life),startSpeed:new ConstantValue(conf.speed),
        startSize:new IntervalValue(...conf.size),
        startColor:new ConstantColor(new THREE.Vector4(1,1,1,1)),
        emissionOverTime:rate,shape:new PointEmitter(),material:mat,
        renderMode:RenderMode.BillBoard,
      });
      system.emitter.name=`MGF FX ${conf.id}`;
      scene.add(system.emitter);
      this.batch.addSystem(system);
      this.channels.push({conf,mat,system,rate});
    }
    this.applyPalette(this.defaultStyle);
    this.batch.visible=false;
  }
  applyPalette(style){
    const palette=COLORS[style]||COLORS.nocturne;
    this.style=style in COLORS?style:'nocturne';
    for(let i=0;i<this.channels.length;i++){
      this.channels[i].mat.color.set(palette[i]);
    }
  }
  enter(nodeId){
    const mark=this.markers[nodeId];
    if(!mark||![mark.x,mark.y,mark.z].every(Number.isFinite))return false;
    this.active=nodeId;
    this.applyPalette(this.styles[nodeId]||this.defaultStyle);
    for(const e of this.channels){
      const [dx,dy,dz]=e.conf.offset;
      e.system.emitter.position.set(mark.x+dx,Math.max(.3,mark.y+dy),mark.z+dz);
      e.system.emitter.updateMatrixWorld();
    }
    this.pulseTimer=.55;
    return true;
  }
  pulse(){
    // Visual response only: scene events may illuminate particles, never trigger player actions.
    if(this.active)this.pulseTimer=Math.max(this.pulseTimer,.95);
  }
  update(dt,quality){
    this.mode=['cinema','eco','off'].includes(quality)?quality:'eco';
    this.pulseTimer=Math.max(0,this.pulseTimer-Math.max(0,Math.min(dt,.1)));
    this.batch.visible=this.mode!=='off'&&!!this.active;
    const q=this.mode==='cinema'?1:this.mode==='eco'?.35:0;
    for(const entry of this.channels){
      const flash=(entry.conf.id==='rune'&&this.pulseTimer>0)?1+Math.min(1.1,this.pulseTimer):1;
      entry.rate.value=Math.min(entry.conf.max,entry.conf.rate*q*flash);
      entry.system.emitter.visible=this.batch.visible;
    }
    if(this.batch.visible)this.batch.update(Math.max(0,Math.min(dt,.05)));
  }
  get stats(){return Object.freeze({engine:'three.quarks@0.18.0',ready:true,
    quality:this.mode,stage:this.active,cap:TOTAL,emitters:this.channels.length});}
}
