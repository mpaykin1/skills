import * as THREE from 'three';
import {loadVerifiedScenery} from './meshopt-loader.js';
import {FusionPhysics} from './physics-world.js';
import {FusionStoryFlow} from './story-flow.js';
import {FusionNavigation} from './navigation.js';
import {FusionYukaAI} from './ai-yuka.js';
import {FusionSpatialAudio} from './spatial-audio.js';
import {FusionECS} from './ecs-runtime.js';
import {FusionBehaviorXState} from './behavior-xstate.js';
import {FusionSpriteStacks} from './sprite-stacking.js';
import {FusionPostFX, FUSION_STYLES} from './postfx.js';
import {FusionLivingWorld} from './living-world.js';
import {FusionQuarksVFX} from './vfx-quarks.js';
import {FusionSpatialBVH} from './spatial-bvh.js';
import {FusionCSGArchitecture} from './csg-architecture.js';
import {FusionManifoldArchitecture} from './manifold-architecture.js';
import './style.css';

const $=id=>document.getElementById(id);
const renderer=new THREE.WebGLRenderer({canvas:$('world'),antialias:true,powerPreference:'high-performance'});
renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,1.5));
renderer.setSize(window.innerWidth,window.innerHeight);
renderer.outputColorSpace=THREE.SRGBColorSpace;
renderer.toneMapping=THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure=1.28;
const scene=new THREE.Scene();
scene.background=new THREE.Color('#0d1423');
scene.fog=new THREE.FogExp2('#17202d',0.019);
const camera=new THREE.PerspectiveCamera(61,window.innerWidth/window.innerHeight,0.07,170);
camera.position.set(0,4.8,11.2);
scene.add(new THREE.HemisphereLight('#799ac1','#1e161c',2.0));
const key=new THREE.DirectionalLight('#d9c0a2',2.5);key.position.set(-8,16,-18);scene.add(key);
const rim=new THREE.PointLight('#ee996e',26,24);rim.position.set(6,4,-13);scene.add(rim);
const groundMat=new THREE.MeshStandardMaterial({color:'#252733',roughness:.94,metalness:.05});
const paverMat=new THREE.MeshStandardMaterial({color:'#34353c',roughness:1});
const railMat=new THREE.MeshStandardMaterial({color:'#343b47',roughness:.82,metalness:.55});
const pillarMat=new THREE.MeshStandardMaterial({color:'#252a30',roughness:1});
const gold=new THREE.MeshStandardMaterial({color:'#e5a26d',emissive:'#b84d31',emissiveIntensity:2.1,roughness:.31});
const geometry={box:new THREE.BoxGeometry(1,1,1)};
const clock=new THREE.Clock();
const markerObjects=new Map();
const crateMeshes=[];
const legacyFarProps=[],legacyPillars=[],legacyFixedRubble=[];
let physics=null,flow=null,navigation=null,npcAI=null,postFX=null,livingWorld=null,particleVFX=null,csgWorld=null,audio=null,ecs=null,behavior=null,spriteStacks=null,heroStack=null,npcStacks=[],wait=false,storyOpen=false,activeMarker=null;

// Stable read-only runtime observability for accessibility, debugging and browser verification.
// This is not a cheat/control API: it cannot set position, bypass gates, select choices or change physics.
Object.defineProperty(window, '__MGF_STATE__', { configurable:false, enumerable:false, value: () => {
  const p=physics?.lastPos, g=physics?.guidePosition;
  return Object.freeze({
    schema:'meta-game-fusion.telemetry.v1',ready:Boolean(physics&&flow&&hero?.parent===scene),
    actorCount:hero?.parent===scene?1:0,
    player:p?Object.freeze({x:p.x,y:p.y,z:p.z,grounded:Boolean(physics.lastGrounded),verticalVelocity:physics.velocityY}):null,
    npc:g?Object.freeze({x:g.x,y:g.y,z:g.z}):null,
    nav: Object.freeze({ready:Boolean(navigation),status:navigation?.status||'unavailable',target:navigation?.targetID||null}),
    node:flow?.current||null,active:flow?.active??null,
    storyOpen, choiceCount:flow?.frame?.choices?.length||0,
    style:postFX?.style||null,quality:postFX?.mode||'off',
    phase:physics?.elapsed||0, livingScene:livingWorld?.active||null,
    vfx:particleVFX?.stats||null,
    npcAI:npcAI?.stats||null,
    audio:audio?.stats||null,
    ecs:ecs?.stats||null,
    behavior:behavior?.stats||null,
    spriteStacking:spriteStacks?Object.freeze({...spriteStacks.stats,primary:true}):Object.freeze({primary:false}),
    spatial:Object.freeze({enabled:spatial?.enabled??false,meshes:spatial?.stats.meshes??0,trees:spatial?.stats.trees??0,visibleTarget:navigation?.targetVisible??null}),
    csg:Object.freeze({portals:csgWorld?.stats.portals??0,triangles:csgWorld?.stats.triangles??0,colliders:csgWorld?.stats.colliders??0}),
  });
}});

postFX=new FusionPostFX({renderer,scene,camera,lights:{rim}});
let lastTouchE=false;
function box(x,y,z,sx,sy,sz,mat,parent=scene){const o=new THREE.Mesh(geometry.box,mat);o.position.set(x,y,z);o.scale.set(sx,sy,sz);o.userData.mgfStatic=true;parent.add(o);return o}
function groundVisual(){
  box(0,-.47,-16,89,.3,199,groundMat);
  for(let z=7;z>-73;z-=2){
    box(0,-.13,z,11.4,.14,1.83,paverMat);
    box(-3.9,.025,z,.10,.12,1.82,railMat);
    box(3.9,.025,z,.10,.12,1.82,railMat);
    if(Math.abs(z%6)<3.1){box(-2,.025,z,0.085,.19,1.6,railMat);box(2,.025,z,.085,.19,1.6,railMat)}
  }
  for(let z=4;z>-72;z-=13){
    box(-5.8,1,z,.8,2,11.4,pillarMat).userData.mgfOccluder=true;box(5.8,1,z,.8,2,11.4,pillarMat).userData.mgfOccluder=true;
    for(const x of[-5.85,5.85]){
      const top=new THREE.Mesh(new THREE.CylinderGeometry(.54,.65,4.5,8),pillarMat);
      top.position.set(x,3.1,z);scene.add(top);legacyPillars.push({mesh:top,position:[x,-.25,z]});
      box(x,5.25,z,1.4,.25,1.2,paverMat);
    }
    if(z<-5){box(0,7.8,z,13,.6,.9,pillarMat).userData.mgfOccluder=true;}
  }
  const fixed=[[-2.8,.85,-13.5,1,.85,.75],[2.6,.95,-20.5,1.1,.95,.7],[0,.5,-31.5,1.65,.5,.4],[-3.3,.9,-43.5,.8,.9,1.4],[2.8,.8,-55.5,.8,.8,.7]];
  for(const [x,y,z,hx,hy,hz]of fixed){
    const m=box(x,y,z,2*hx,2*hy,2*hz,pillarMat);
    m.userData.mgfOccluder=true;legacyFixedRubble.push({mesh:m,x,y,z,hx,hy,hz});
  }
  // Low-poly distant silhouettes, static atmospheric depth. Never paired with false physics blockers.
  const rockMat=new THREE.MeshStandardMaterial({color:'#151d29',roughness:1});
  for(let i=0;i<90;i++){
    const seed=(i*7919%997)/997;
    const x=(i%2?1:-1)*(13+seed*44);
    const z=7-(i*23.79%130);
    const h=2+((i*17)%15);
    const t=new THREE.Mesh(new THREE.ConeGeometry(1.6+seed*3,h,4),rockMat);
    t.position.set(x,h/2-.4,z);t.rotation.y=seed*2.3;scene.add(t);legacyFarProps.push({mesh:t,x,z,h,seed});
  }
  const starGeo=new THREE.BufferGeometry();const stars=new Float32Array(650*3);
  for(let i=0;i<650;i++){const f=(i*167.31)%1;stars[i*3]=(Math.sin(i*22.11)*67);stars[i*3+1]=2+((i*1.23)%24);stars[i*3+2]=-70+(i*13.3%100)}
  starGeo.setAttribute('position',new THREE.BufferAttribute(stars,3));
  const points=new THREE.Points(starGeo,new THREE.PointsMaterial({color:'#b3bfd0',size:.12,transparent:true,opacity:.33,depthWrite:false}));points.userData.isDust=true;scene.add(points);
  return points;
}
const dust=groundVisual();
const spatial=new FusionSpatialBVH();
spatial.register(scene); // Shared box geometry receives one BVH; all static meshes use it.
const crateMaterial=new THREE.MeshStandardMaterial({color:'#775445',metalness:.19,roughness:.8});
const hero=new THREE.Group();scene.add(hero);
const cloth=new THREE.MeshStandardMaterial({color:'#8c5046',roughness:.89,metalness:.05,side:THREE.DoubleSide});
const leather=new THREE.MeshStandardMaterial({color:'#2d2734',roughness:1});
const skin=new THREE.MeshStandardMaterial({color:'#bd9881',roughness:1});
const cloak=new THREE.Mesh(new THREE.ConeGeometry(.51,1.5,7,1),cloth);cloak.rotation.y=Math.PI;cloak.position.y=-.10;hero.add(cloak);
const hood=new THREE.Mesh(new THREE.SphereGeometry(.35,10,8),leather);hood.position.set(0,.67,-.02);hero.add(hood);
const face=new THREE.Mesh(new THREE.SphereGeometry(.2,10,8),skin);face.position.set(0,.64,-.2);hero.add(face);
const staff=new THREE.Mesh(new THREE.CylinderGeometry(.035,.055,1.7,7),railMat);staff.position.set(.34,0,-.1);staff.rotation.z=-.09;hero.add(staff);
const ember=new THREE.Mesh(new THREE.IcosahedronGeometry(.09,1),gold);ember.position.set(.34,.85,-.12);hero.add(ember);
const heroLight=new THREE.PointLight('#ff9d63',2.7,5);heroLight.position.set(.3,.85,0);hero.add(heroLight);
async function applyPrimarySpriteStack(world){
  if(!world.sprite_stacking?.primary_renderer)return;
  spriteStacks=await FusionSpriteStacks.create({scene,world});
  if(!spriteStacks)throw Error('Sprite Stacking is mandatory but not loaded');
  if(spriteStacks.assets.has('rock')&&spriteStacks.assets.has('spire')){
    const stone=[],spire=[];
    for(const item of legacyFarProps){
      (item.h>5?spire:stone).push({
        position:[item.x,-.46,item.z],
        scale:item.h>5?Math.min(2,item.h/7):.9+item.seed*.92,
        rotationY:item.seed*Math.PI*2});
      item.mesh.removeFromParent();spatial.unregister(item.mesh);
    }
    spriteStacks.batch('rock',stone);spriteStacks.batch('spire',spire);
  }
  if(spriteStacks.assets.has('pillar')){
    spriteStacks.batch('pillar',legacyPillars.map(v=>({position:v.position,scale:1.35})));
    for(const p of legacyPillars){spatial.unregister(p.mesh);p.mesh.removeFromParent();}
  }
  if(spriteStacks.assets.has('rubble')){
    spriteStacks.batch('rubble',legacyFixedRubble.map(v=>({
      position:[v.x,-.15,v.z],scale:Math.min(1.65,Math.max(1.1,v.hy*1.6))})));
    for(const p of legacyFixedRubble){spatial.unregister(p.mesh);p.mesh.removeFromParent();}
  }

  // Source model is the prior original procedural cloak/hood/staff silhouette,
  // never an imported approved character. User-provided character art is only
  // replaced by an independently approved, identity-matching complete stack.
  if(world.source==='user-authored-concept'&&spriteStacks.assets.has('wanderer')){
    heroStack=await spriteStacks.make('wanderer',{position:[0,-1.10,0],scale:1.04,action:'idle'});
    heroStack.root.removeFromParent();hero.add(heroStack.root);
    for(const o of hero.children){if(o!==heroStack.root&&o!==heroLight)o.visible=false;}
  }
  await livingWorld?.applySpriteStacks(spriteStacks);
}
async function attachNPCStacks(world){
  if(!spriteStacks||world.source!=='user-authored-concept')return;
  const types=['sentinel-blue','sentinel-violet'];
  for(let i=0;i<(npcAI?.agents?.length||0);i++){
    const a=npcAI.agents[i],id=types[i];
    if(!spriteStacks.assets.has(id))continue;
    const inst=await spriteStacks.make(id,{position:[0,-1.0,0],action:'idle'});
    inst.root.removeFromParent();a.art.root.add(inst.root);
    for(const child of a.art.root.children){
      if(child!==inst.root && child!==a.art.light)child.visible=false;
    }
    npcStacks.push({actor:a,inst});
  }
  // If an approved NPC source is supplied, preserve its identity and pose art.
}

function makeMarker(n,pos){
  const obj=new THREE.Group();obj.position.set(pos.x,pos.y,pos.z);scene.add(obj);
  const outer=new THREE.Mesh(new THREE.TorusGeometry(.73,.043,6,40),gold);outer.rotation.x=Math.PI/2;outer.position.y=-1.13;obj.add(outer);
  const peak=new THREE.Mesh(new THREE.OctahedronGeometry(.34),gold);obj.add(peak);
  const light=new THREE.PointLight('#f0a274',9,9);obj.add(light);markerObjects.set(n.id,{group:obj,outer,peak,light});
}
const inputs=new Set();
let jumpPressed=false,interactPressed=false;
const keys={arrowup:'w',arrowdown:'s',arrowleft:'a',arrowright:'d',' ':'space',spacebar:'space'};
function norm(k){return keys[k.toLowerCase()]||k.toLowerCase()}
addEventListener('keydown',e=>{
  const k=norm(e.key);if(k==='n'&&!e.repeat){e.preventDefault();if(navigation){$('message').textContent=navigation.toggleDebug()?'NavMesh: ON':'NavMesh: OFF';}return;}if(['w','a','s','d','e','space'].includes(k)){e.preventDefault();if(!e.repeat&&k==='space')jumpPressed=true;if(!e.repeat&&k==='e')interactPressed=true;inputs.add(k)}
});
addEventListener('keyup',e=>{inputs.delete(norm(e.key))});
addEventListener('blur',()=>inputs.clear());
for(const el of document.querySelectorAll('.touch [data-key]')){
  const key=el.dataset.key;
  el.addEventListener('pointerdown',e=>{e.preventDefault();el.setPointerCapture(e.pointerId);if(key==='e')interactPressed=true;if(key==='space')jumpPressed=true;inputs.add(key);el.classList.add('pressed')});
  for(const type of['pointerup','pointercancel','lostpointercapture'])el.addEventListener(type,()=>{inputs.delete(key);el.classList.remove('pressed')});
}

async function attachModels(config){
  for(const asset of config.assets||[]){
    const p=config.markers[asset.scene_id];if(!p)continue;
    try{
      const gltf=await loadVerifiedScenery(asset, renderer);
      // Never animate imported hero or replace the single controller. Models are scenery only.
      gltf.scene.position.set(p.x+2.9,0,p.z-2.6);
      gltf.scene.rotation.y=-Math.PI*.23;
      scene.add(gltf.scene);
      // ScanCode/hash-approved imported scenery only: animated or skinned rigs are never indexed.
      if(!gltf.animations?.length && !asset.animation_clips?.length){
        gltf.scene.userData.mgfStatic=true;
        spatial.register(gltf.scene,{occluder:true});
      }
    } catch(e){throw new Error('Approved model failed integrity/decoder checks: '+asset.src+' — '+String(e?.message||e))}
  }
}
function showDialogue(payload){
  $('story').hidden=false;storyOpen=true;inputs.clear();
  $('storyTitle').textContent=payload.node.title;
  const lines=$('storyLines');lines.replaceChildren();
  for(const t of payload.frame?.lines||[]){const p=document.createElement('p');p.textContent=t;lines.append(p)}
  if(ecs)ecs.emit('dialogue:state',{open:true});else audio?.setDialogue(true);
  const choices=$('choices');choices.replaceChildren();
  for(const c of payload.frame?.choices||[]){
    const b=document.createElement('button');b.textContent=c.text;
    b.addEventListener('click',()=>{try{flow.choose(c.index)}catch(e){error(e)}});choices.append(b)
  }
  $('storyNext').hidden=!payload.frame?.complete;
}
function nextScene(node){
  $('chapter').textContent=node.title;
  const style=flow?.world?.visual_direction?.by_node?.[node.id] || node.visual_style;
  if(ecs){ecs.emit('scene:enter',{id:node.id,style});updateFxLabels();}
  else{
    livingWorld?.enter(node.id);particleVFX?.enter(node.id);
    npcAI?.enter(node.id);behavior?.scene(node.id);audio?.enter(node.id);
    if(style&&postFX?.setMood(style))updateFxLabels();
  }
  const name=node.type==='mechanic'?'Найди сигнал и используй механику':((flow?.world?.source==='user-authored-concept')?'Исследуй главу: '+node.title:'Исследуй руины и найди сигнальный огонь');
  $('objective').textContent=name;
  if(node.type==='mechanic')$('message').textContent='Ссылка на механику из библиотеки; исполняется только физический демонстратор.';
  if(navigation&&flow?.world?.markers?.[node.id]){const reached=navigation.setTarget(node.id,flow.world.markers[node.id]);$('navStatus').textContent=reached?'ПРОВОДНИК · ПУТЬ':'ПРОВОДНИК · НЕТ ПУТИ';}
}
function gameStatus(payload){
  if(payload.type==='dialogue'){showDialogue(payload);return}
  $('story').hidden=true;storyOpen=false;
  if(ecs)ecs.emit('dialogue:state',{open:false});else audio?.setDialogue(false);
  if(payload.type==='scene')nextScene(payload.node);
}
function error(e){$('message').textContent=String(e?.message||e);console.error(e)}
$('storyNext').addEventListener('click',async()=>{try{$('story').hidden=true;storyOpen=false;if(ecs)ecs.emit('dialogue:state',{open:false});else audio?.setDialogue(false);await flow.interact()}catch(e){error(e)}});
$('restart').addEventListener('click',()=>location.reload());
$('nav').addEventListener('click',()=>{if(navigation){$('message').textContent=navigation.toggleDebug()?'NavMesh: ON':'NavMesh: OFF';}});
function updateBVHLabel(){ $('spatial').textContent=`BVH: ${spatial.enabled?'ON':'OFF'} · ${spatial.stats.meshes}`; }
$('spatial').addEventListener('click',()=>{ spatial.enabled=!spatial.enabled;updateBVHLabel(); });
renderer.domElement.addEventListener('pointerdown',e=>{
  if(storyOpen || !physics || !flow?.active || !spatial.enabled) return;
  const hit=spatial.pick(e.clientX,e.clientY,camera,renderer.domElement);
  if(hit){ $('message').textContent=`BVH: ${hit.object.name||'поверхность'} · ${hit.distance.toFixed(1)} м`; }
});
updateBVHLabel();
function updateFxLabels(){
  $('quality').textContent='FX: '+(postFX?.mode||'off').toUpperCase();
  $('style').textContent='СТИЛЬ: '+(postFX?.styleLabel||'ОБЫЧНЫЙ');
}
$('quality').addEventListener('click',()=>{postFX?.cycleMode();updateFxLabels();});
$('style').addEventListener('click',()=>{postFX?.cycleMood();updateFxLabels();});
function updateSoundLabel(){const el=$('sound');el.textContent=audio?.enabled?'ЗВУК: ВКЛ':'ЗВУК: ВЫКЛ';el.setAttribute('aria-pressed',audio?.enabled?'true':'false');}
async function toggleSound(){if(!audio){$('message').textContent='Звук пока не готов';return;}await audio.toggle();updateSoundLabel();if(audio.lastError)$('message').textContent='Ошибка аудио: '+audio.lastError;}
$('sound').addEventListener('click',toggleSound);
addEventListener('visibilitychange',()=>{if(document.hidden&&audio?.enabled){audio.disable();updateSoundLabel();}});
window.addEventListener('keydown',e=>{
  if(e.repeat||e.altKey||e.ctrlKey||e.metaKey)return;
  if(e.key.toLowerCase()==='p'){postFX?.cycleMode();updateFxLabels();}
  if(e.key.toLowerCase()==='v'){postFX?.cycleMood();updateFxLabels();}
  if(e.key.toLowerCase()==='m')toggleSound();
});
$('save').addEventListener('click',()=>{try{const s={story:flow.save(),position:physics.lastPos};localStorage.setItem('mgf-world-save:'+flow.world.title,JSON.stringify(s));$('message').textContent='Прогресс сохранён'}catch(e){error(e)}});
$('load').addEventListener('click',async()=>{try{const s=JSON.parse(localStorage.getItem('mgf-world-save:'+flow.world.title)||'null');if(!s)throw new Error('Нет сохранения');await flow.restore(s.story);const p=s.position;if(p && Number.isFinite(p.x)&&Number.isFinite(p.y)&&Number.isFinite(p.z)&&Math.max(Math.abs(p.x),Math.abs(p.z))<200){physics.player.setTranslation(p,true);physics.lastPos=p;physics.velocityY=0} $('message').textContent='Прогресс восстановлен'}catch(e){error(e)}});
let accumulator=0;let movePhase=0;
function renderLoop(){
  const dt=Math.min(clock.getDelta(),.075);accumulator=Math.min(accumulator+dt,.12);
  const paused=storyOpen||!flow?.active;
  while(accumulator>=1/60){
    if(physics){
      const vx=paused?0: (inputs.has('d')?1:0)-(inputs.has('a')?1:0);
      const vz=paused?0: (inputs.has('s')?1:0)-(inputs.has('w')?1:0);
      const guide=(!paused&&navigation)?navigation.command():{x:0,z:0};
      const patrols=(!paused&&npcAI)?npcAI.commandPatrols():{};
      physics.step({x:vx,z:vz,jump:!paused&&(jumpPressed||inputs.has('space'))},guide,patrols);
      npcAI?.afterStep();
      navigation?.afterStep(paused);
      ecs?.sync({physics,npcAI,dt:1/60});
      if(!paused&&vx*vx+vz*vz>.01)movePhase+=1/60;
    }
    accumulator-=1/60;
  }
  jumpPressed=false;
  if(physics){
    const p=physics.lastPos;hero.position.set(p.x,p.y-.09,p.z);
    for(const entry of crateMeshes){entry.mesh.position.copy(entry.body.translation());entry.mesh.quaternion.copy(entry.body.rotation());}
    const moving=inputs.has('w')||inputs.has('s')||inputs.has('a')||inputs.has('d');
    if(!paused&&moving){hero.rotation.y=THREE.MathUtils.lerp(hero.rotation.y,Math.atan2((inputs.has('a')?1:0)-(inputs.has('d')?1:0),(inputs.has('w')?1:0)-(inputs.has('s')?1:0)),.15)}
    cloak.scale.x=1+(moving?.06*Math.sin(movePhase*12):0);
    const target=new THREE.Vector3(p.x,p.y+3.35,p.z+8.5);camera.position.lerp(target,.065);camera.lookAt(p.x,p.y+.1,p.z-4.3);
    const node=flow?.nodes?.get(flow.current);
    const physicalNode=(node?.type==='scene'||node?.type==='mechanic')?node.id:null;
    const near=physicalNode&&physics.nearSensor(physicalNode);
    $('prompt').hidden=!near||paused;
    if(interactPressed&&!paused){
      interactPressed=false;
      if(near){
        if(ecs)ecs.emit('player:interact',{position:physics.lastPos});
        else{particleVFX?.pulse();audio?.pulse(physics.lastPos);npcAI?.signalAt(physics.lastPos);}
        flow.interact().catch(error);
      }
    }
  }
  // Action changes are explicitly derived from player input and physics only.
  if(heroStack){
    const moving=!paused&&['w','a','s','d'].some(k=>inputs.has(k));
    const action=!physics?.lastGrounded?'jump':moving?'walk':'idle';
    heroStack.setAction(action).catch(error);
  }
  for(const {actor,inst} of npcStacks){
    const route=(actor.status==='following'||actor.status==='patrolling');
    const action=actor.mode==='investigate'?'investigate':route?'walk':'idle';
    inst.setAction(action).catch(console.warn);
  }
  spriteStacks?.update(dt,camera);
  const time=performance.now()*0.001;navigation?.animate(time,paused);
  npcAI?.animate(time,paused);
  livingWorld?.update(dt,time,postFX?.mode||'off');
  particleVFX?.update(dt,postFX?.mode||'off');
  const qualityMode=postFX?.mode||'off';
  if(ecs){if(ecs.quality!==qualityMode)ecs.emit('quality:mode',{mode:qualityMode});}
  else audio?.setQuality(qualityMode);
  if(physics)audio?.update(dt,{camera,player:physics.lastPos,grounded:physics.lastGrounded,paused,
    npcs:ecs?ecs.audioNpcs():(npcAI?.agents?.map(a=>({id:a.id,position:physics.patrols.get(a.id)?.body.translation()}))||[])});
  if(postFX?.mode!=='off'){dust.material.opacity=.26+.06*Math.sin(time*.41);for(const o of markerObjects.values()){o.peak.rotation.y=time*.6;o.peak.position.y=Math.sin(time*1.3)*.14}}
  if(postFX){postFX.render(dt);if($('quality').textContent!==`FX: ${postFX.mode.toUpperCase()}`)updateFxLabels();}
  else renderer.render(scene,camera);
  requestAnimationFrame(renderLoop);
}
async function boot(){
  try{
    const res=await fetch('/world.json',{cache:'no-store'});
    if(!res.ok)throw new Error('Не найден файл мира');
    const world=await res.json();if(world.schema!=='meta-game-fusion.physics-world.v1')throw new Error('Неизвестный формат мира');
    $('chapter').textContent=world.title;
    if(world.source==='user-authored-concept')$('endingNote').textContent='Путь завершён. Мир ждёт продолжения.';
    livingWorld=new FusionLivingWorld({scene,world,seed:world.scene_composer?.seed||0});
    await applyPrimarySpriteStack(world);
    if(world.particle_fx)particleVFX=new FusionQuarksVFX({scene,world});
    if(world.audio)audio=new FusionSpatialAudio({world});
    updateSoundLabel();
    postFX?.setMood(world.visual_direction?.default||'nocturne',true);
    postFX?.setMode(world.visual_direction?.quality||'cinema');
    updateFxLabels();
    physics=await FusionPhysics.create();
    if(world.entity_system)ecs=new FusionECS({world,systems:()=>({livingWorld,particleVFX,npcAI,audio,postFX,behavior})});
    // CSG runs before Recast queries so static architecture is coherent in
    // Three.js, MeshBVH and Rapier; the open passage stays navigable.
    if(world.csg_architecture){
      const config = {scene,physics,spatial,plan:world.csg_architecture};
      csgWorld = world.csg_architecture.backend === 'manifold-3d@3.5.5'
        ? await FusionManifoldArchitecture.create(config)
        : new FusionCSGArchitecture(config);
    }
    // Physical arch remains Manifold/CSG; sprite stacks add volumetric
    // weathered masonry to its *outside* shoulders, not false door blockers.
    if(spriteStacks?.assets.has('gothic-arch')){
      const ornaments=[];
      for(const arch of world.csg_architecture?.structures||[]){
        ornaments.push({position:[-arch.width*.58,-.12,arch.z-1.8],scale:1.2});
        ornaments.push({position:[arch.width*.58,-.12,arch.z-1.8],scale:1.2});
      }
      if(ornaments.length)spriteStacks.batch('gothic-arch',ornaments);
    }
    // Navigation is optional; its absence never prevents the Rapier game from running.
    try{navigation=await FusionNavigation.create({physics,scene});
      navigation.setVisibilityProbe((from,to)=>spatial.lineOfSight(from,to));
      $('navStatus').textContent='ПРОВОДНИК · NAVMESH';}
    catch(e){console.warn('Recast unavailable:',e);$('navStatus').textContent='ПРОВОДНИК · НЕДОСТУПЕН';}
    if(navigation&&world.npc_ai){
      try{npcAI=new FusionYukaAI({scene,physics,navigation,spatial,world});
        $('navStatus').textContent='ПРОВОДНИК · RECAST + YUKA';
      }catch(e){console.warn('YUKA NPC AI unavailable:',e);npcAI=null;}
    }
    if(world.behavior_machine){
      if(!npcAI||!ecs||!navigation)throw Error('XState requires YUKA, bitECS and Recast; no silent fallback');
      behavior=new FusionBehaviorXState({world,npcAI,navigation});
      $('navStatus').textContent='ПРОВОДНИК · RECAST + YUKA + XSTATE';
    }
    await attachNPCStacks(world);
    ecs?.sync({physics,npcAI,dt:1/60});
    for(const item of physics.dynamic){
      let mesh;
      if(spriteStacks?.assets.has('crate')){
        mesh=new THREE.Group();scene.add(mesh);
        const volume=await spriteStacks.make('crate',{position:[0,-item.half,0],
            scale:item.half*2/1.12});
        volume.root.removeFromParent();mesh.add(volume.root);
        mesh.userData.mgfSpriteStack=true;
      }else{
        mesh=new THREE.Mesh(geometry.box,crateMaterial);
        mesh.scale.setScalar(item.half*2);scene.add(mesh);
        const brace=new THREE.Mesh(new THREE.BoxGeometry(item.half*1.66,item.half*1.66,item.half*1.66),railMat);
        brace.position.y=item.half*.12;mesh.add(brace);
      }
      mesh.position.copy(item.body.translation());
      crateMeshes.push({mesh,body:item.body});
    }
    for(const node of world.nodes){
      const p=world.markers[node.id];if(p){physics.addSensor(node.id,p.x,p.y,p.z,1.65);makeMarker(node,p)}
    }
    let manifest={stories:[]};
    try{const data=await fetch('/stories/manifest.json',{cache:'no-store'});if(data.ok)manifest=await data.json()}catch(e){console.warn('No story list',e)}
    flow=new FusionStoryFlow({world,manifest,onDisplay:gameStatus,onScene:nextScene,onFinish:r=>{
      $('story').hidden=true;storyOpen=false;if(ecs)ecs.emit('dialogue:state',{open:false});else audio?.setDialogue(false);$('ending').hidden=false;$('endingTitle').textContent=r.title;
      $('prompt').hidden=true;inputs.clear();
    }});
    await attachModels(world);
    updateBVHLabel();
    await flow.begin();
    $('veil').style.opacity='0';setTimeout(()=>$('veil').remove(),850);
    renderLoop();
  }catch(e){$('boot').textContent='Не удалось запустить мир: '+String(e?.message||e);console.error(e)}
}
addEventListener('resize',()=>{camera.aspect=innerWidth/innerHeight;camera.updateProjectionMatrix();postFX ? postFX.resize(innerWidth,innerHeight) : renderer.setSize(innerWidth,innerHeight)});
boot();
