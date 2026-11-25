# Open3D integration

Upstream MIT: https://github.com/isl-org/Open3D . API: https://www.open3d.org/docs/release/tutorial/geometry/distance_queries.html and https://www.open3d.org/docs/latest/python_api/open3d.t.geometry.RaycastingScene.html . Install official Open3D 0.19.0 in a compatible isolated Python environment (e.g. Python 3.11), NumPy, Pillow and SciPy. No automatic installs or paid compute. Package contains adapter code, not Open3D binaries.

TRELLIS saves native_mesh.npz (vertices/faces before GLB processing), native_grid.npz (coords, RGBA, attributes), and geometry-source.json (hashes); SAM preserves IDs, crop, mask and reference provenance. Existing old packs without raw mesh must be re-exported from their actual source; do not guess GLB alignment. Run:

```
python scripts/open3d_stack.py --asset generated/harp --out audited/harp --mode audit
python scripts/open3d_stack.py --asset generated/harp --out solid/harp --mode solid
python scripts/sam2_pack.py refine --generated generated --out refined --solid-ids opaque-ids.json --python /path/to/open3d-python
```

`opaque-ids.json` is a JSON list of reviewed IDs. Omit it for audit only. Open3D RaycastingScene distance is used for geometric alignment diagnostics. Occupancy/signed distance assumes watertight, nonintersecting surfaces. Solid mode is blocked for open, nonmanifold, intersecting or translucent meshes, mismatched bounds or grid deviations. The native layer grid, spacing, pivot, orientation, source RGBA and full material attributes remain unchanged. Only empty cells strictly inside the opaque mesh receive nearest native material RGB as a provisional interior; no arbitrary hole filling, no source mutation. This is not recovery of hidden material detail. For ghost cloth and transparent effects preserve original surface layers. Compare candidate and source at multiple angles and resolutions, including silhouettes and holes. Refine mode does not generate poses or covers; use the same validated asset stack in the existing scene/animation/cover renderer. Geometry audit is an internal intermediate, not a report to the owner. Output always prototype until artistic and animation requirements pass. If Open3D isn't installed, report the blocker and retain the native surface path, never claim an executed audit.

Next: [OpenVDB](openvdb.md) archives native or explicitly eligible solid layers without modifying geometry, preserving their shared grid and RGBA. Batch verifies the exact native grid/mesh and generation provenance. Atmosphere density is separate and is never passed through solid occupancy filling.
