# DeepLabCut × Living Image Animator — quadruped gait v1.0

Upstream: https://github.com/DeepLabCut/DeepLabCut (LGPL-3.0 source; models/weights and training-video rights independently reviewed). Official DLC predictions are Pandas MultiIndex `.csv` / `.h5` with `scorer`, optional `individuals`, `bodyparts`, and `x,y,likelihood` coordinates. Never pretend a human COCO17 skeleton is a quadruped gait.

## Real integrated pipeline

`DeepLabCut trained animal model/video -> DLC tracked CSV/H5 -> deeplabcut_bridge.py -> validated quadruped-v1 JSON motion guide -> 4-foot authored contact check in locomotion.py -> original Pixelorama (.pxo) + OpenToonz (.tnz) full-frame painted poses -> fixed-identity character/world path checks -> GIF + ZIP.`

There is NO untrained animal model bundled. `deeplabcut.analyze_videos` is used **only** if the user supplies a trained DLC `config.yaml`, source video, and the external DeepLabCut installation; otherwise consume authentic pre-analyzed DLC CSV/HDF5. No invented joints or synthetic feet. No deformation of original art.

For a walking/running `cat`, `dog`, or quadruped `animal`, provide `locomotion` and TWO or more genuine actions with individually painted `.png`/`.pxo`/`.tnz` full-figure poses and a closed `locomotion.path`. Optional DLC guide **validates real animal reference movement**, not character drawing; when supplied, inference or metrics failure blocks final output.

### Scene declaration: direct predictions

```json
{
  "id":"street_cat", "role":"cat", "box":[125,410,72,48],
  "locomotion":{
    "mode":"walk",
    "path":[{"frame":0,"dx":0,"dy":0},{"frame":24,"dx":40,"dy":0},{"frame":48,"dx":0,"dy":0},{"frame":72,"dx":0,"dy":0}],
    "deeplabcut_predictions":"references/street_catDLC.csv",
    "deeplabcut_fps":24,
    "deeplabcut_confidence":0.6,
    "deeplabcut_bodypart_map":{
      "hip":"pelvis", "shoulder":"withers",
      "front_left_foot":"left_forepaw", "front_right_foot":"right_forepaw",
      "hind_left_foot":"left_hindpaw", "hind_right_foot":"right_hindpaw"
    }
  },
  "clips":[{"action":"walk","frames":"48 annotated full-figure pose objects"},
           {"action":"groom","frames":"24 annotated full-figure pose objects"}]
}
```

This example is structural and deliberately NOT an executable scene: masks, full PNG cels, actual landmarks, timeline and proper contact notes must exist.

For multi-animal prediction data set `deeplabcut_individual` to the **exact existing tracked identity**; if ambiguous or missing, fail. Set `deeplabcut_scorer` if multiple scorers occur. Set `deeplabcut_predictions` to `.h5` or `.csv`, OR supply `deeplabcut_guide` (a previously exported `quadruped-v1` JSON). For installed DeepLabCut inference set `deeplabcut_video`, `deeplabcut_config`, `deeplabcut_fps` and `deeplabcut_bodypart_map` instead. Never combine multiple input modes.

### Four-foot frame contacts

On every original full-figure pose for locomotion, include `joints.root` plus FOUR authentic foot markers (`front_left_foot`, `front_right_foot`, `hind_left_foot`, `hind_right_foot`). Alternative exact suffixes `_paw` / `_hoof` are accepted. Mark actual planted feet using `support: ["front_left_foot", "hind_right_foot"]` on each frame, or `support_sequence` of equally long arrays on the clip. `support: []` represents a **drawn airborne phase**, mandatory for `run`, forbidden for `walk` and stairs. Each foot must take a real turn contacting the surface. This replaces the inappropriate old human `left_ankle`/`right_ankle` assumption for cats and dogs. Avoid world-space foot sliding and teleportation.

### CLI

```bash
# Analyze an actual DLC predictions export (without requiring a DLC installation):
python scripts/deeplabcut_bridge.py --predictions refs/catDLC.csv --bodypart-map refs/cat_map.json --fps 30 --out refs/cat_guide.json --mode walk

# Or run real DeepLabCut (trained network required):
python scripts/deeplabcut_bridge.py --video refs/cat.mp4 --config refs/cat-project/config.yaml --bodypart-map refs/cat_map.json --fps 30 --out refs/cat_guide.json --mode walk

# Actual full scene, shared with MMPose/Pixelorama/OpenToonz:
python scripts/unified_delivery.py source.png --scene scene.json --out output --seconds 48 --fps 24
```

`--preflight-only` never certifies a rendered character. Actual user video/model must already be licensed and accessible. All registered source data and derived guides are included in output ZIP. A DLC data track alone does NOT guarantee accurate walking/run; true directional pose PNGs, contacts, physical scene displacement and loop continuity are mandatory for final certification.
