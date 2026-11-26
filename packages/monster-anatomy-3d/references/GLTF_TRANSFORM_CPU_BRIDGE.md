# glTF-Transform × Monster Anatomy 3D — CPU-only

Official: https://github.com/donmccurdy/glTF-Transform
CLI: https://gltf-transform.dev/cli
Upstream NPM: `@gltf-transform/cli@4.5.1`, MIT, Node.js >=20.
Pinned reviewed upstream Git commit: `8e2a94a2616d293c4b503d0fb6a4b42e6ec7c62f`.

## Purpose

The **terminal** export stage after Blender skinning, MyoGenerator muscles,
PyMeshLab static mesh repair, Instant Meshes LOD and Rigger/Open Mocap animation.
Run **after** the final GLB is generated, not before skinning or sculpting.
It is CPU only; no GPU, CUDA, machine learning, browser rendering or cloud API.

Default safe mode calls the real upstream CLI `dedup` on a separate temporary
GLB, retaining node hierarchy, joints, skinning, animation channel interpolation
and accessor layouts, morph target counts and materials. It does not resample
animations, quantize positions, change textures, simplify geometry or add
compression extensions. The original is never overwritten, and if the new GLB
is larger, the original bytes are copied to the separate output filename.

Optional `--gltf-mode meshopt` adds the official `meshopt --level medium`
compression: smaller geometry and motion data is possible, but quantization is
not a pixel/vertex-perfect guarantee. This output **requires a Meshopt decoder**
in Three.js if the compressed extension is present; do not enable it for
standalone HTML lacking this decoder. For default standalone HTML choose `safe`.

## Installation

Requires Node 20+, npm, Python 3.10+, and Blender for the model generation.
The CLI itself runs on CPU and does not require Blender once a .glb exists.

```
python scripts/install_gltf_transform.py --install
```

It installs the pinned official release into `vendor/gltf-transform-node`,
**not** system-wide. When offline or already installed, use an explicit CLI:

```
python scripts/build_with_anatomy.py --blender blender --gltf-optimize \
  --gltf-transform-bin /path/to/gltf-transform
```

Or for any existing GLB without Blender:

```
python scripts/gltf_transform_worker.py --input source.glb --output source.safe.glb --mode safe --cli /path/to/gltf-transform
```

For compressed output (only with an explicitly configured Three.js decoder):

```
python scripts/gltf_transform_worker.py --input source.glb --output source.meshopt.glb --mode meshopt --cli /path/to/gltf-transform
```

## Three.js compressed model loader

```js
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { MeshoptDecoder } from 'three/addons/libs/meshopt_decoder.module.js';
const loader = new GLTFLoader();
loader.setMeshoptDecoder(MeshoptDecoder);
loader.load('monster.meshopt.glb', ({scene, animations}) => {
  world.add(scene);
  const mixer = new THREE.AnimationMixer(scene);
  // Play clips only in response to user input, not automatically.
});
```

## Integrity gates

Only publish a separate output path after structural comparison: skin joint
names, inverse bind matrix counts, node hierarchy/transforms, mesh primitive
attribute types and vertex counts, morph target layouts, animation channel
paths and interpolation/sample counts, material/image/texture counts.
Note: these checks cannot prove rendered visual equivalence, animation timing
at every frame, or file portability. Validate final models inside the actual
game before release. The upstream CLI is separately installed; archive includes
our bridge and source reference, not the third-party npm package or dependencies.
