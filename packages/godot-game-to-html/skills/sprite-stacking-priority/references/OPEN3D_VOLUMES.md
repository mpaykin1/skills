# Open3D CPU geometry fidelity stage

Upstream: https://github.com/isl-org/Open3D (MIT). Official API: https://www.open3d.org/docs/latest/python_api/open3d.t.geometry.RaycastingScene.html.

This is an actual Open3D Python `RaycastingScene` integration, not a procedural substitute. The CLI auto-selects installed Open3D; otherwise the existing trimesh voxelizer remains a working fallback. To force the new backend, pass `--voxelizer open3d`.

For each original mesh instance: original triangles → Open3D surface distance; closed meshes additionally use occupancy (`nsamples=3`). Results are converted to source-world center coordinates with the same uniform pitch, then **the existing barycentric nearest-surface RGB/A UV sampler** assigns authored colors. Open meshes yield only thin shell points, not fake interior. Output matches previous `stack.json` schema and is still a VISUAL derivative. The original native Godot/Unity runtime preserves gameplay and dynamic FX.

Open3D assumes watertight non-self-intersecting meshes for occupancy. Bad or degenerate meshes must be left in original GLB/native renderer or be repaired only through user-approved topology processing. The optional stage needs its own installed Open3D library; plugin ZIP does not vendor it. Separate benchmark/per-view checks should precede promoting a candidate into a playable scene. For complex geometry, next complementary tool: **Manifold3D** for optional robust manifold inspection/repair. For sparse 3D volumes at scale: **OpenVDB/NanoVDB** reduces allocation of empty space.
