# 2D/2.5D world-space movement — human and quadruped

Each `walk`, `run`, `stairs_up`, `stairs_down` action requires a continuous closed `locomotion.path` with 3+ `{frame,dx,dy}` source-pixel keyframes covering 0..actor cycle length. Real travel >=1.1 body height, max displacement >=0.55 height. Root translation alone cannot count as anatomical motion. Enforce correct position at both ends, no more than 15% body height instantaneous step, no drift during inactive clips, no sliding planted feet, no fake walking in place. Clip pixels are authored RGBA art and never deformed.

## Humans — MMPose

`role:human`; `support` of each cel = `left` / `right` / `double` / `flight`; both annotated ankles and alternating stance; run requires flight, walk forbids it; exposed human reference MMPose COCO17 does not certify animals.

## Quadrupeds — DeepLabCut

`role:cat|dog|animal` with locomotion. Every cels has genuine drawn `joints.root` and `front_left_foot`, `front_right_foot`, `hind_left_foot`, `hind_right_foot` (or `_paw`, `_hoof` aliases), plus `support:["front_left_foot","hind_right_foot"]` or a matching clip-level `support_sequence` list of lists. An empty support list is true flight: mandatory for run, forbidden in ordinary walk/stairs. At least 3 independent stance configurations and at least 3 paws with >14% body-height independent relative sweep; every paw takes a visible contact step; grounded paws must not skate in world-space between adjacent poses. Existing arbitrary `left/right` bipeds do not count as valid support maps for animals.

Optional `deeplabcut_predictions` (.csv/.h5), `deeplabcut_guide` or `deeplabcut_video`+`deeplabcut_config` and trained animal network provides measurable reference movement: at least 3 independently moving paws and front/hind movement variation. Require data confidence >=0.6 by default and explicit tracked identity for multi-animal videos. DLC reference guides do not draw poses and are separate from authored contact checks.

Every character requires source-matched 4 directions and explicit turn pose if route reverses; no turning by mirroring faces. All requested movement must remain inside source image and obey wall/stair occlusion. If motion requires unavailable sprites, block release rather than generating a fake footstep.
