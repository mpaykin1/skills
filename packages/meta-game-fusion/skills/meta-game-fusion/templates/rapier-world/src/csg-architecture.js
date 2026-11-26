/** Original watertight CSG architecture over static Three.js brush volumes.
 * Three CSG outputs feed visuals + Rapier trimesh colliders + MeshBVH raycasts.
 * Never edits original GLB media, animation rigs or hero controller.
 */
import * as THREE from 'three';
import {Brush, Evaluator, SUBTRACTION} from 'three-bvh-csg';

const schema = 'meta-game-fusion.csg-architecture.v1';
const finite = x => typeof x === 'number' && Number.isFinite(x);
const between = (v,lo,hi) => finite(v) && v>=lo && v<=hi;
const validHex = s => /^#[0-9a-fA-F]{6}$/.test(s);

export function validateCSGPlan(config) {
  if (config?.schema!==schema || !Array.isArray(config.structures) || config.structures.length>24)
    throw new Error('Invalid CSG architecture plan');
  const seen=new Set();
  for(const d of config.structures){
    if(!d || typeof d.id!=='string' || !/^portal_\d{1,2}$/.test(d.id) || seen.has(d.id))
      throw new Error('Duplicate/invalid CSG portal ID');
    seen.add(d.id);
    if(d.kind!=='gothic-portal' || d.collider!=='static-trimesh-exact-csg' ||
        !between(d.width,13,20) || !between(d.height,9,12) ||
        !between(d.depth,1,3) || !between(d.z,-160,160) ||
        !between(d.opening_width,10.5,12) || !between(d.opening_straight_height,3,5) ||
        !between(d.arch_radius,5,6) || !validHex(d.palette) ||
        d.width <= d.opening_width+2 || d.height <= d.opening_straight_height+ d.arch_radius+0.25)
      throw new Error('Unsafe CSG solid/opening geometry');
  }
  return config.structures;
}

function newBrush(geo,mat,pos,rotation=null){
  const b=new Brush(geo,mat);
  b.position.set(...pos);
  if(rotation)b.rotation.set(...rotation);
  b.updateMatrixWorld(true);
  return b;
}

/** Mesh attributes must be finite; avoid sending bad WASM data to Rapier. */
function validate(mesh){
  const geo=mesh.geometry, pos=geo?.getAttribute('position');
  const indices=geo?.index;
  if(!pos || pos.itemSize!==3 || pos.count<36 || pos.count>180000 ||
     (indices && indices.count>360000))throw new Error('CSG output missing/oversized');
  for(let i=0;i<pos.count;i++){
    if(!finite(pos.getX(i))||!finite(pos.getY(i))||!finite(pos.getZ(i)))
      throw new Error('Nonfinite CSG result vertices');
  }
  if(indices){
    if(indices.count%3!==0)throw new Error('CSG triangle indices malformed');
    for(let i=0;i<indices.count;i++)if(indices.getX(i)>=pos.count)throw new Error('CSG index invalid');
  }else if(pos.count%3!==0)throw new Error('Nontriangle CSG geometry');
  geo.computeBoundingBox();
  if(!geo.boundingBox || geo.boundingBox.isEmpty())throw new Error('Empty CSG bounds');
  return mesh;
}

export class FusionCSGArchitecture {
  constructor({scene,physics,spatial,plan}){
    this.scene=scene;this.physics=physics;this.spatial=spatial;
    this.group=new THREE.Group();this.group.name='CSG Gothic Viaduct';
    this.meshes=[];this.stats={portals:0,triangles:0,colliders:0};
    const nodes=validateCSGPlan(plan);
    const evaluate=new Evaluator();evaluate.useGroups=false;
    try{
      for(const spec of nodes){
        const mat=new THREE.MeshStandardMaterial({color:spec.palette,roughness:.94,metalness:.07,flatShading:false});
        const z=spec.z, R=spec.arch_radius;
        // Each input is a closed two-manifold solid, overlapping a closed base.
        const base=newBrush(new THREE.BoxGeometry(spec.width,spec.height,spec.depth),mat,[0,spec.height/2-.12,z]);
        // Rectangular aperture cut begins below ground for a genuinely open walkway.
        const door=newBrush(new THREE.BoxGeometry(spec.opening_width,spec.opening_straight_height+1.3,spec.depth+1.6),mat,
          [0,(spec.opening_straight_height-1.3)/2-.12,z]);
        // Cylinder along Z removes the upper semicircular vault. It extends
        // through the entire wall thickness and overlaps the rectangle.
        const vault=newBrush(new THREE.CylinderGeometry(R,R,spec.depth+1.6,52,1,false),mat,
          [0,spec.opening_straight_height-.12,z],[Math.PI/2,0,0]);
        const cut1=evaluate.evaluate(base,door,SUBTRACTION);
        const cut2=evaluate.evaluate(cut1,vault,SUBTRACTION);
        validate(cut2);
        cut2.name=`CSG ${spec.id}`;
        cut2.userData.mgfStatic=true;
        cut2.userData.mgfOccluder=true;
        cut2.userData.mgfCSG=true;
        cut2.userData.mgfAuthor=spec.author;
        this.group.add(cut2);
        cut2.updateMatrixWorld(true);
        // One exact resultant surface is used for Rapier and BVH.
        this.physics.addCSGTrimesh(cut2);
        this.spatial.register(cut2,{occluder:true,minTriangles:1});
        this.meshes.push(cut2);
        this.stats.portals++;
        this.stats.colliders++;
        this.stats.triangles += (cut2.geometry.index?.count || cut2.geometry.attributes.position.count)/3;
        // Decorative stains/lanterns belong to the existing living-world and
        // postfx systems. There is no fake physics or animated character here.
        base.geometry.dispose();door.geometry.dispose();vault.geometry.dispose();
        if(cut1.geometry!==cut2.geometry)cut1.geometry.dispose();
      }
      this.scene.add(this.group);
    }catch(e){
      this.dispose();
      throw e;
    }
  }
  dispose(){
    for(const m of this.meshes){
      this.spatial.unregister(m);
      m.geometry.dispose();m.material?.dispose();
    }
    this.meshes.length=0;
    this.scene.remove(this.group);
  }
}
