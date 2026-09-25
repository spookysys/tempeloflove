"""Post-fix for a crowd file built before the roof floor mattresses moved to mid-face:
moves the mattresses, their cushions and the people lying on them by the same offset.

    python3 humans/fix_roof_mattresses.py      (edits model/tempel_event.blend in place)
"""
import math
import os
import sys

import bpy
from mathutils import Vector

HUM = os.path.dirname(os.path.abspath(__file__))
MODEL = os.path.dirname(HUM)
sys.path.insert(0, MODEL)
import params as P  # noqa: E402


def FP(k, n, t, z=0.0):
    a = math.radians(P.slot_center(k))
    return Vector((n * math.cos(a) - t * math.sin(a), n * math.sin(a) + t * math.cos(a), z))


path = os.path.join(MODEL, 'tempel_event.blend')
bpy.ops.wm.open_mainfile(filepath=path)
moved = []
for i, (k, t_old) in enumerate(((0, 1.8), (7, -0.6))):
    old, new = FP(k, 8.35, t_old), FP(k, 8.55, 0.0)
    d = new - old
    obs = [o for o in bpy.data.objects if o.name.startswith(('roof_floor_mattress_%d' % i,
                                                             'roof_mattress_cushion_%d_' % i))]
    crowd = bpy.data.collections.get('crowd')
    if crowd:
        for o in crowd.objects:
            if o.type == 'ARMATURE' and abs(o.location.z - P.TERRACE_Z) < 1.2 and \
                    (Vector((o.location.x, o.location.y, 0)) - Vector((old.x, old.y, 0))).length < 1.7:
                obs.append(o)
    for o in obs:
        if o.parent and o.parent in obs:
            continue
        o.location += d
        moved.append(o.name)
    for o in bpy.data.objects:                       # IK targets of the moved people
        if o.name.startswith(('ik_', 'ikf_')) and any(m in o.name for m in moved):
            o.location += d
bpy.ops.wm.save_as_mainfile(filepath=path, compress=True)
print('FIXED roof mattresses, moved:', moved)
