/** ManifoldCAD/WASM backend for original static architecture.
 * The SAME closed triangle surface feeds rendering, Rapier and three-mesh-bvh.
 * Never sends skinned/animated/imported GLB meshes through Boolean CSG.
 * Upstream: manifold-3d@3.5.5, Apache-2.0.
 */
import * as THREE from 'three';
import {validateCSGPlan} from './csg-architecture.js';

const finite = x => typeof x === 'number' && Number.isFinite(x);

function manifoldGeometry(data) {
  if (!data || data.numProp !== 3 || !data.vertProperties || !data.triVerts)
    throw new Error('Manifold output lacks 3D indexed mesh');
  const positions = new Float32Array(data.vertProperties);
  const faces = new Uint32Array(data.triVerts);
  if (!positions.length || positions.length % 3 !== 0 || faces.length < 108 ||
      faces.length % 3 !== 0 || positions.length / 3 > 180000 || faces.length > 360000)
    throw new Error('Manifold output empty or excessive');
  for (const c of positions) if (!finite(c)) throw new Error('Invalid Manifold coordinate');
  for (const i of faces) if (i >= positions.length / 3) throw new Error('Invalid Manifold triangle index');
  // A real watertight solid must use every undirected edge exactly twice.
  const edges = new Map();
  const edge = (a, b) => {
    const key = a < b ? `${a}:${b}` : `${b}:${a}`;
    const prev = edges.get(key) || 0;
    if (prev >= 2) throw new Error('Nonmanifold edge in generated architecture');
    edges.set(key, prev + 1);
  };
  for (let i = 0; i < faces.length; i += 3) {
    const a = faces[i], b = faces[i + 1], c = faces[i + 2];
    if (a === b || a === c || b === c) throw new Error('Degenerate Manifold triangle');
    edge(a,b); edge(b,c); edge(c,a);
  }
  for (const n of edges.values()) if (n !== 2) throw new Error('Open boundary in generated architecture');
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  geometry.setIndex(new THREE.BufferAttribute(faces, 1));
  geometry.computeVertexNormals();
  geometry.computeBoundingBox();
  if (!geometry.boundingBox || geometry.boundingBox.isEmpty()) {
    geometry.dispose(); throw new Error('Empty bounds on generated architecture');
  }
  return geometry;
}

/** Construct a genuinely open arch using closed solids, never decorative overlay. */
function makePortal(wasm, spec) {
  const {Manifold} = wasm;
  const keep = [];
  const track = solid => {keep.push(solid); return solid;};
  try {
    const baseCube = track(Manifold.cube([spec.width, spec.height, spec.depth], true));
    const base = track(baseCube.translate([0, spec.height / 2 - .12, spec.z]));
    const rectCube = track(Manifold.cube([
      spec.opening_width, spec.opening_straight_height + 1.3, spec.depth + 1.6
    ], true));
    const rect = track(rectCube.translate([0, (spec.opening_straight_height - 1.3) / 2 - .12, spec.z]));
    // Manifold cylinders already extend on the Z axis; centre it inside the
    // wall and extend 0.8m beyond both faces to avoid coplanar fragments.
    const cylinder = track(Manifold.cylinder(spec.depth + 1.6,
      spec.arch_radius, spec.arch_radius, 52, true));
    const vault = track(cylinder.translate([0, spec.opening_straight_height - .12, spec.z]));
    const cut1 = track(Manifold.difference(base, rect));
    const carved = track(Manifold.difference(cut1, vault));
    if (carved.isEmpty() || carved.numTri() < 36 || carved.numTri() > 120000)
      throw new Error('Manifold generated an empty/oversized portal');
    const data = carved.getMesh();
    try { return manifoldGeometry(data); }
    finally { data?.delete?.(); }
  } finally {
    // WASM objects must be released explicitly; static meshes are copied into
    // Three.js arrays before releasing the temporary geometry engine objects.
    for (const m of keep.reverse()) m?.delete?.();
  }
}

export class FusionManifoldArchitecture {
  static async create(options) {
    // Lazy-load WASM only for this backend, keeping older three-bvh-csg worlds
    // fully compatible and avoiding an unnecessary runtime download.
    const {default: loadModule} = await import('manifold-3d');
    const wasm = await loadModule();
    wasm.setup();
    return new FusionManifoldArchitecture(options, wasm);
  }

  constructor({scene, physics, spatial, plan}, wasm) {
    if (!plan || plan.backend !== 'manifold-3d@3.5.5')
      throw new Error('Expected explicit Manifold architecture backend');
    this.scene = scene; this.physics = physics; this.spatial = spatial;
    this.group = new THREE.Group(); this.group.name = 'Manifold Gothic Architecture';
    this.meshes = []; this.colliders = [];
    this.stats = {portals:0, triangles:0, colliders:0, engine:'manifold-3d@3.5.5'};
    const specs = validateCSGPlan(plan);
    try {
      for (const spec of specs) {
        const geometry = makePortal(wasm, spec);
        const material = new THREE.MeshStandardMaterial({color:spec.palette, roughness:.94, metalness:.07});
        const mesh = new THREE.Mesh(geometry, material);
        mesh.name = `Manifold ${spec.id}`;
        Object.assign(mesh.userData, {
          mgfStatic:true, mgfOccluder:true, mgfCSG:true, mgfManifold:true,
          mgfAuthor:spec.author
        });
        this.meshes.push(mesh);
        this.group.add(mesh);
        mesh.updateMatrixWorld(true);
        // This is the same geometry for world visuals, Rapier hitboxes and BVH.
        this.colliders.push(physics.addCSGTrimesh(mesh));
        spatial.register(mesh, {occluder:true, minTriangles:1});
        this.stats.portals++;
        this.stats.colliders++;
        this.stats.triangles += geometry.index.count / 3;
      }
      scene.add(this.group);
    } catch (error) {
      this.dispose();
      throw error;
    }
  }

  dispose() {
    for (const mesh of this.meshes) {
      this.spatial.unregister(mesh);
      mesh.geometry.dispose();mesh.material.dispose();
    }
    for (const body of this.colliders) {
      try { this.physics.world.removeRigidBody(body); } catch (_) { /* physics freed */ }
    }
    this.colliders.length=0;this.meshes.length=0;
    this.scene.remove(this.group);
  }
}
