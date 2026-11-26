# OpenSim 4.6 — совместная работа

Official source https://github.com/opensim-org/opensim-core ; release https://github.com/opensim-org/opensim-core/releases/tag/4.6 ; official Python package https://pypi.org/project/opensim/4.6/ ; native API documentation https://github.com/opensim-org/opensim-core/blob/main/doc/APIGuide.md . OpenSim core Apache-2.0; check licenses for the specific model, capture and reference separately. Use isolated CPU Python with official `opensim==4.6` and compatible NumPy/SciPy, installed explicitly on supported OS/Python. Do not modify Blender's Python environment. No automatic downloads or fabricated native output; external dependency not bundled. Python package unavailable in authoring environment (pip index returned no matching distribution). No native model was executed here.

## Routing and requirements

- For humans: MediaPipe/FreeMoCap capture followed by validated multiview calibration, or native 3D markers from a licensed reference. For monsters: DeepLabCut's single-camera 2D estimates are diagnostic only; cannot provide metric 3D or infer muscle forces. OpenSim is allowed for a creature only with its own expert-authored and calibrated `.osim` model and corresponding 3D landmarks. Never substitute a human skeleton. This release's automated reference reader supports the existing FreeMoCap prepared capture contract only; alternate species-specific 3D references need a reviewed adapter, not fabricated human data.
- Use trusted existing `.osim` model, original fitted native coordinate motion and explicit reviewed mapping, units and transforms. OpenSim's own IK tools may fit a measured TRC to the model upstream; this integration does not automatically run IK or convert a 2D video to 3D. No model scaling, solver force estimation, dynamics/contact force claims. Native `Model.initSystem`, `Coordinate.setValue`, `Model.assemble`, `Model.realizePosition`, `Marker.getLocationInGround` evaluate actual poses. Incompatible constraint models stop if assembly changes the provided coordinates. Model ranges are configured limits, not guarantees of physiological safety.
- Export exact CSV `time,<coordinate names>` with all model coordinates in native radians/metres, strictly uniform sample times matching FreeMoCap. No guessed units, degree conversion, missing channels or interpolation. Source capture must be actual output of `freemocap-hybrid/scripts/prepare_capture.py`, no filled gaps. Use the original prepared capture unchanged, reviewed marker correspondence and calibrated rigid transform from its Blender z-up metre coordinates to OpenSim ground. A MediaPipe landmark is not automatically a physical anatomical marker: require a reviewed equivalent marker on the model, not just a matching name.
- Only one-shot smooth movement where unintended jitter has been identified; no cyclic actions, attacks, jumps, intentional impacts, speed transitions or unreviewed smoothing. Input/outputs separate. No geometry edits, root/IK changes outside selected scalar coordinates, no change to frame timing. Freeze every authored event, contact interval and first/last two samples. Explicitly choose a physically justified radius for each coordinate (max 0.05 rad or metres). Smoothing is optional and conservative, not a new motion authoring system.

## Command

`python scripts/opensim_motion.py MODEL.osim MOTION.csv CAPTURE.json SPEC.json --confirm-trusted-calibrated-model-and-mapping` runs native diagnostics. Add `--output CANDIDATE.csv` only for approved correction. The output is a candidate motion table, not a finished rig. Required spec fields (values are illustrative, never defaults; substitute exact approved values):

```json
{
  "rights_confirmed": true,
  "model_sha256": "actual model hash",
  "motion_sha256": "actual motion hash",
  "capture_file_sha256": "actual prepared capture hash",
  "hero_id": "exact hero id",
  "clip": "exact one-shot clip",
  "coordinate_units": "native-rad-m",
  "mode": "once",
  "blender_to_opensim": [[1,0,0],[0,0,1],[0,-1,0]],
  "origin_offset_m": [0,0,0],
  "marker_map": {"model_marker_1":"left_hip", "model_marker_2":"right_hip", "model_marker_3":"left_ankle"},
  "contacts": [{"marker":"model_marker_3","start":20,"end":35}],
  "anchors": [18,42],
  "coordinate_radii": {"exact_coordinate":0.02},
  "confirm_unintended_jitter": true
}
```

For a floating object without contact only, use explicit empty contacts and `no_ground_contact_confirmed: true`. Every ground support interval for each limb must otherwise be supplied. Use marker corresponding to a planted contact point, not a rotating ankle unless that point really remains planted. Ground marker motion in metres is a displacement proxy, not ground collision or force measurement.

SciPy's bounded sparse least squares minimizes deviation and second/third differences on each approved coordinate. NumPy checks exact locked samples and bounded deviation. Require >1% jerk RMS improvement, no acceleration regression, all coordinates within native model ranges, and no regression of reference marker RMS, p95, each marker RMS or contact displacement/error (1e-6 m numerical tolerance). Otherwise leave original. Baseline bad fit stays bad, no artistic PASS. Metrics per coordinate in native units; never combine different units or report an overall quality percent. Report separately only when requested.

## Downstream

1. Native diagnostics/accepted candidate → reviewed source-to-rig coordinate map in existing Rokoko/Rigify/Animation Layers workflow. Manual/native artist retargeting required; this bridge does not convert model coordinates into Blender bone rotations. Preserve original rig/mesh/materials and actions. Compare actual evaluated target contacts with `animation-layers-hybrid/scripts/compare_contacts.py`, and use existing Rigify gate. Check actual rendering with same camera/timeline. Re-evaluate calibrated coordinates if exported from final target with reviewed mapping; reject mismatch.
2. OpenCV motion check plus MediaPipe (human) or trained DeepLabCut (specific creature) on actual rendered frames, not as a replacement for physical model. Keep approved 2D character art protected; no RIFE/Bitmapflow on organic poses. Genuine same-volume full-body poses through Sprite Stacking Grunge Horror; OpenSubdiv retains source identity. Khronos GLB gate and native validation for 3D; Pillow/FFmpeg packaging only after visual acceptance, exact alpha/timing checks. Maintain all existing NLA/physics/event authority, no automatic actions. No force/torque or muscle activation estimates: for inverse dynamics, validated inertial parameters, loads/ground reactions and solver setup are separate prerequisites.

## Actual local check

Python/NumPy/SciPy ran on a synthetic 60-sample 30 FPS scalar trajectory. Before/after jerk RMS 796.9957 → 25.0078, acceleration RMS 15.3422 → 1.5059; locked anchors unchanged, maximum deviation 0.02 native units. Independent marker regression check rejected 0.01 m introduced displacement. These numbers are not native OpenSim execution or measured Bullet Car quality. No official package, calibrated model, or real render available for this stage, no claims of biomechanical validation.
