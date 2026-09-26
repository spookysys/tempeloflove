# Working rules for this repository

## People: every posture and every interaction comes from a real reference

Hand-made postures and hand-arranged interactions have looked stiff, weird and chaotic every time, so they are
not allowed.

- **Postures.** Every person's pose comes from recorded data:
  - motion capture (`humans/mocap.py`, CMU),
  - recorded resting moments (`humans/rest_poses.json`),
  - or a reconstruction from a real photo.
  Never type joint angles or positions, never use stock library poses, never "improve" a pose by hand.
- **Interactions.** People who touch (holding, leaning, cuddling, lying on or against each other, carrying
  weight, hands on someone) must come from one reference in which those people were recorded or photographed
  together:
  - a multi-person mocap take,
  - an interaction dataset,
  - or a multi-person reconstruction from one photo.
  Never place separately posed people next to each other and pull their hands or heads together with IK or offsets.
- **What code may do.** Choose which reference to use, where to put it in the room and how to turn it. It may
  scale it to the bodies. Physics (ragdoll, cloth) may settle it. Physics must not be used to invent the
  arrangement.
- **No reference, no constellation.** If there is no reference for a constellation, leave it out and say so.
  Do not approximate it by hand.
- **Enforcement.** The crowd build refuses a pose without a recorded source (`pose()` raises). Each group
  records its source in the rig property `pose`: `clip@frame`, `photo:...`, or a dataset id.

## Other standing rules

- The ZEGG Flickr photos stay local (`$TEMPEL_TMP/zegg`). They are never committed or rendered; only derived
  pose data is stored.
- No explicit sex acts in renders; intimate couples keep underwear on.
- Develop on the branch given for the session; commits end with the session's attribution lines.
