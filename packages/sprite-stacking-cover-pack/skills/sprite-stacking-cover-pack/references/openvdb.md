# OpenVDB: sparse storage and atmosphere (v0.5.0)

Official upstream https://github.com/AcademySoftwareFoundation/openvdb ; Python API https://www.openvdb.org/documentation/doxygen/python.html . Use the official OpenVDB Python build with NumPy array support (`openvdb` or `pyopenvdb`), in an isolated compatible Python environment. Record exact installed version and license; do not claim installed if absent. This package includes adapters, not OpenVDB binaries. No paid compute.

## Shared pipeline
SAM 2.1 selected masks → TRELLIS.2 native mesh and O-Voxel attributes → Open3D audit / explicitly eligible opaque solid → OpenVDB RGBA archival candidate → existing horizontal PNG layers and depth-aware Sprite Stacking renderer → scene.json → cover + game pack. OpenVDB never modifies the original object or its materials. It stores four sparse FloatGrids (RGB and alpha) in identical transforms. Exact PNG-channel roundtrip and world transform checks must pass. Native O-Voxel PBR attributes remain in the source NPZ, not replaced by RGB. Existing PNG stack is the web runtime format, not VDB.

- Single: `python scripts/openvdb_stack.py archive --asset native-object --out vdb-object`.
- Batch: `python scripts/openvdb_stack.py batch --generated generated --refined refined --out vdb-pack`. Omit refined only when retaining native surface stacks. IDs, mesh/grid hashes and refinement generation hash must match. A solid is permitted only following the existing Open3D gate. Results include volume.json and volumes.json with source hashes. Retain originals; no fake solid fill. If output is larger than original, keep VDB for authoring only; do not promise compression.

## Real fog / smoke
A separate approved authored or simulated OpenVDB scalar FOG_VOLUME grid from a compatible tool (e.g. Blender) is input, not a mesh or an alpha mask. `python scripts/openvdb_stack.py density --vdb fog.vdb --grid density --tint 156 164 190 --extinction 1 --out fog-stack`. Color/extinction author controlled. The exporter uses alpha=1-exp(-density*extinction*voxelStep) per cell, preserves world placement, and rejects unsupported transforms and non-density grids. Grid axis +Z up must be authored explicitly. No automatic smoke simulation. For animation use actual VDB frame sequence with a common authored grid bounds/pivot; do not independently crop animated frames and claim continuity. Current command converts individual frames; fixed-bound sequence orchestration is still needed. For mobile use low-resolution layers/atlas or GPU raymarch with depth; do not interpret fog as collision, or opaque object alpha as physical density. Respect original character and atmosphere.

OpenVDB runtime and GPU inference must actually run before claiming successful end-to-end reconstruction. If bindings unavailable keep prior valid layers and report the blocker; never fabricate a .vdb file.

The [Infinigen bridge](infinigen.md) can merge reviewed procedural environment stacks and TRELLIS reconstruction stacks before the existing batch archive. Keep source texture maps and original O-Voxel material attributes separate; archive does not replace them.
