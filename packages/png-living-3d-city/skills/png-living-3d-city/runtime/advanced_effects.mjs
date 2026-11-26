/**
 * PNG Living 3D City: integrated npm-backed CSG, Quarks and postprocessing.
 * Requires `npm install --ignore-scripts` in this directory, then npm run build.
 * This module deliberately imports the real libraries; it is not a mock.
 * For no-network standalone HTML bundle advanced_effects.mjs with esbuild.
 */
import * as THREE from 'three';
import {Brush, Evaluator, SUBTRACTION} from 'three-bvh-csg';
import {BatchedRenderer, ParticleSystem, SphereEmitter, IntervalValue, ConstantValue, ConstantColor} from 'three.quarks';
import {EffectComposer, EffectPass, RenderPass, BloomEffect, SMAAEffect} from 'postprocessing';

/** Build a genuine open masonry Gothic arch via two CSG subtractions. */
export function buildGothicArcade({width=9,height=10,depth=2.0,opening=5, spring=4,
                                   material=new THREE.MeshStandardMaterial({color:0x183e65,roughness:.94})}={}){
  const cutterRadius = opening/2;
  const outer = new Brush(new THREE.BoxGeometry(width,height,depth),material);
  outer.position.y=height/2;
  outer.updateMatrixWorld(true);
  const passage = new Brush(new THREE.BoxGeometry(opening,spring+.15,depth+1.0));
  passage.position.y=(spring+.15)/2-.02;
  passage.updateMatrixWorld(true);
  const round = new Brush(new THREE.CylinderGeometry(cutterRadius,cutterRadius,depth+1.0,48,1,false));
  round.rotation.x=Math.PI/2;
  round.position.y=spring;
  round.updateMatrixWorld(true);
  const evaluator=new Evaluator();
  evaluator.attributes=['position','normal','uv'];
  const first=evaluator.evaluate(outer,passage,SUBTRACTION);
  first.updateMatrixWorld(true);
  const result=evaluator.evaluate(first,round,SUBTRACTION);
  result.name='true_csg_gothic_arch';
  result.userData.pngCityEffect='open-arch';
  outer.geometry.dispose(); passage.geometry.dispose(); round.geometry.dispose(); first.geometry.dispose();
  return result;
}

/** Quarks batch particles: drifting blue crystal sparks around a broken foundation. */
export function installMagicDebris(scene, {x=0,y=0,z=0, quality='mobile'}={}) {
  const batch = new BatchedRenderer();
  batch.name='png_city_quarks_batch';
  scene.add(batch);
  const material = new THREE.MeshBasicMaterial({
    color:0x65cfff, transparent:true, opacity:.8, blending:THREE.AdditiveBlending,
    depthWrite:false, side:THREE.DoubleSide,
  });
  const particles = new ParticleSystem({
    duration:6, looping:true, worldSpace:true,
    shape:new SphereEmitter({radius:1.4,thickness:.7}),
    emissionOverTime:new ConstantValue(quality==='mobile'?9:24),
    startLife:new IntervalValue(2.5,5),
    startSpeed:new IntervalValue(.05,.28),
    startSize:new IntervalValue(.035,.18),
    startColor:new ConstantColor(new THREE.Vector4(.24,.64,1,.65)),
    material, behaviors:[],
  });
  particles.emitter.position.set(x,y,z);
  scene.add(particles.emitter);
  batch.addSystem(particles);
  return {
    update(deltaSeconds){batch.update(Math.min(.05,Math.max(0,deltaSeconds)));},
    dispose(){particles.dispose();particles.emitter.removeFromParent();batch.removeFromParent();material.dispose();}
  };
}

/** Postprocessing bloom on physically painted luminous windows and portals. */
export function createCityComposer(renderer,scene,camera,{quality='mobile'}={}) {
  const bloom = new BloomEffect({intensity:quality==='mobile'?.28:.48,luminanceThreshold:.82,luminanceSmoothing:.16,mipmapBlur:true});
  const composer = new EffectComposer(renderer,{frameBufferType:THREE.HalfFloatType});
  composer.addPass(new RenderPass(scene,camera));
  composer.addPass(new EffectPass(camera,bloom));
  return {composer,bloom,
    render(deltaSeconds){composer.render(deltaSeconds);},
    setSize(w,h){composer.setSize(w,h);},
    dispose(){composer.dispose();}
  };
}

/** Unified three-library enhancement; never disables existing procedural foundation FX. */
export function installPremiumFoundation({renderer,scene,camera,center=new THREE.Vector3(),quality='mobile',arcade=true}={}) {
  if(!renderer||!scene||!camera)throw new Error('renderer, scene and camera required');
  const root=new THREE.Group();root.name='png_city_enhanced_foundation';scene.add(root);
  const arch=arcade?buildGothicArcade({}):null;
  if(arch){root.add(arch);root.position.copy(center);}
  const particles=installMagicDebris(scene,{x:center.x,y:center.y,z:center.z,quality});
  const post=createCityComposer(renderer,scene,camera,{quality});
  return {root,post,update(dt){particles.update(dt);post.render(dt);},dispose(){particles.dispose();post.dispose();if(arch)arch.geometry.dispose();root.removeFromParent();}};
}
