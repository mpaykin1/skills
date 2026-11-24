# Strict no-jerk/no-static/no-deform output gate v0.5

**Mandatory**: 40–60 sec seamless cycle, 24fps+, full source aspect ratio, animated every visible living character, GIF + ZIP same answer.

Final renderer: `python scripts/pose_sequence_delivery.py source.png --scene approved_scene.json --out exported --seconds 48 --fps 24`.

The v0.3 `smooth_delivery.py` and v0.4 `visible_delivery.py` cannot certify a v0.5 animation; they may pass technically articulated rotating fragments that still look static, implausible or deformed. No alternate final command may bypass full independently drawn character poses.

For every actor: two different active actions, >=60% time active; >=12 pose frames/active action, >=8 distinct pose PNGs/action; 22% change of translation-aligned silhouette; two joints each sweep >=22% actor height relative to root. Still repeated frames, tiny gestures, single rigid translated crops, FX-only, deformation and morphing are release blockers. Smooth joints, edge behavior, contact logic, actor identity and seam must be reviewed visually. If a single flattened image lacks the additional poses, draw them; if unable, explicitly report the incomplete work and do not send a fake final.

The ZIP contains original image, clean layer, exact masks, RGBA pose frames, scene and activity metadata. Image paths verified. No invented output links.
