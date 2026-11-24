# Visible-character release contract v0.5 (supersedes rig-based v0.4)

**If the world glows, but a person does not visibly act, FAIL.**

- Require each person/animal, including seated and distant figures, in scene inventory and final animation.
- Require 2+ visibly different, anatomically coherent active actions per actor. Source still/crop bobbing, color flicker, particles, facial opacity, frame blending, deforming parts, camera pan or swapping unrelated silhouettes are NOT actions.
- Full-character pose PNGs per actor: 12+ 24fps frames per active clip, 8+ unique authored pose images; >=60% time active. Pose identity locked in every frame.
- Each active action requires two independently tracked joints spanning >=22% of full body height (minimum 4px) RELATIVE to character's root, and >=22% change of aligned silhouette after removal of rigid whole-figure translation. User must see clear large-amplitude motion at native scale.
- Every adjacent pose and action boundary must be visibly continuous, no foot sliding or hand/object misses; human review required in addition to numerical gates. Fixed pixel registration and chronological frame numbering. No hero idle-only trick.
- Legacy `visible_delivery.py` performs cutout-rig rotation. It is DEPRECATED for release and MUST NEVER be run as the final animator. The only release renderer is `pose_sequence_delivery.py`.
- When no authentic newly drawn poses are available, the only permitted result is a specific failure about missing art; never mislabel environmental animation as animated characters.
