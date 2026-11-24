# MobileSAM ViT-T: explicit instance masks, CPU

Official upstream: https://github.com/ChaoningZhang/MobileSAM
License: Apache-2.0 in upstream, subject to checkpoint/license verification. Upstream source and weights are NOT bundled in this plugin.

Pipeline:
1. Clone official upstream to `vendor/MobileSAM` during `setup_cpu` (for first setup, internet needed).
2. `scripts/mobile_sam_cpu.py photo.jpg -o mask_labels.npz` loads official `vit_t` weights `mobile_sam.pt` (from upstream `weights/` or downloaded from official source) and calls `SamAutomaticMaskGenerator` on **CPU** with a 10x10 prompt grid and batch of 8.
3. Masks are filtered for predicted IoU, stability and area, then composed as **instance IDs** into `uint16` label image. They are NOT semantic classes: the skill cannot claim a given mask is specifically a building/tree/person.
4. `scripts/segmentation_fusion.py` computes image-space region boundaries, then a 0..1 confidence for each MoGe UV vertex. At boundaries confidence approaches 0, inhibiting DA-V2 deformation. In mask interiors, normal conservative DA-V2 calibration applies.
5. This never makes up unseen sides, never replaces the photographic texture, never alters MoGe triangle topology. Geometry remains genuine MoGe output.

CPU grid sampling can be slow. `--segment-grid 6` reduces CPU work; `--segment-grid 16` often produces finer boundaries at significantly greater time. To reuse previous segmentation: `--segment-map path/to/mask_labels.npz` (format: compressed npz, `labels` 2D unsigned integer, HxW same orientation as source photograph). Use `--segment-mode off` to explicitly bypass MobileSAM, keeping MoGe + DA-V2.

Known constraints: automatically predicted masks overlap and are not labels of semantic categories. High-confidence small image masks may still be wrong. No guarantee of exact boundary preservation on image artifacts. No GPU inference requirement, but HTML WebGL2 rendering uses device GPU.
