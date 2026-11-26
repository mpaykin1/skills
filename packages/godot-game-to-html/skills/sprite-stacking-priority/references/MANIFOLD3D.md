# Manifold3D + sprite stacking

The optional Apache-2.0 [Manifold3D](https://github.com/elalish/manifold) Python `manifold3d` engine performs topology checks and robust Boolean union on closed solids **before** Open3D/trimesh voxelization. It does not replace UnityGLTF, original GLB material/UV samplers, separate scene-node parts, CSG colliders in the actual engine, or original gameplay.

- `stack_from_glb.py --manifold audit` (default) checks watertight candidate topology without changing occupancy. Without Manifold3D it records an unavailable state and uses original source.
- `--manifold normalize` welds UV split vertices on a temporary mesh copy and uses Manifold3D output **only for occupancy** after area/volume/bounds guards. Original materials and colors are read from the original mesh.
- `--manifold union` combines 2–8 closed static meshes, then uses the union surface/volume for occupancy and nearest original source triangles for color. Never apply to separately animated doors, wheels, vehicles or monsters. Boolean union may change apparent geometry/colors; browser compare via Playwright/Pixelmatch.
- For non-watertight geometry: use prior shell voxelization or original GLB. Do **not** invent watertight closures or fill unobserved holes. Without the native library, explicit normalize/union stops instead of fabricating results.
- The `stack.json` Grunge contract, bottom-first RGBA slices, axis/pivot, and original GLB SHA are unchanged. Manifold provenance is added only as a metadata field.

Additional next-stage opportunity: OpenVDB/NanoVDB sparse volumes plus *browser-compatible* WebGPU loader. Native NanoVDB is not itself a ready WebGL2/Three.js renderer; keep existing WebGL2 fallback until a real WebGPU browser and physical device have been checked.
