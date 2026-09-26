"""Is everyone held up by something? For each person, the lowest parts of the body are traced straight
down; if none of them rests on a surface (floor, mattress, bench, cushion, another person...) within a
few cm, the person floats.

    python3 humans/check_support.py [tempel_event.blend]
"""
import os
import sys

import bpy
from mathutils import Vector

HUM = os.path.dirname(os.path.abspath(__file__))
MODEL = os.path.dirname(HUM)
sys.path.insert(0, MODEL)

blend = next((a for a in sys.argv[1:] if a.endswith('.blend')), 'tempel_event.blend')
bpy.ops.wm.open_mainfile(filepath=os.path.join(MODEL, blend))
import render as R  # noqa: E402
R.set_event(True)                                # the event layer is viewport-hidden by default (never posed)
sc = bpy.context.scene
sc.frame_set(100)
dg = bpy.context.evaluated_depsgraph_get()
DOWN = Vector((0, 0, -1))
GAP = 0.05                                       # counts as resting on something


def support_below(p, own):
    """distance down to the nearest surface that is not part of this person (None = nothing within 1 m)"""
    start = p + Vector((0, 0, 0.03))
    for _ in range(8):
        hit, loc, nrm, idx, ob, mw = sc.ray_cast(dg, start, DOWN, distance=1.0)
        if not hit:
            return None
        o_ = getattr(ob, 'original', ob)
        hidden = o_.hide_render or any(c.hide_render for c in o_.users_collection)
        if ob.name.split('.')[0] != own and not hidden:
            return (p - loc).z
        start = loc + DOWN * 0.002               # skip the person's own clothes / hair
    return None


bad = 0
for o in sorted(sc.objects, key=lambda o: o.name):
    if o.type != 'MESH' or not o.name.endswith('.body') or o.hide_render:
        continue
    own = o.name[:-5]
    pts = []
    rig = o.parent
    for part in ([rig] + list(rig.children_recursive)) if rig else [o]:   # body + clothes + shoes + hair
        if part.type != 'MESH' or part.hide_render:                     # (covered body parts are masked away)
            continue
        e = part.evaluated_get(dg)
        me = e.to_mesh()
        pts += [e.matrix_world @ me.vertices[i].co for i in range(0, len(me.vertices), 5)]
        e.to_mesh_clear()
    zmin = min(p.z for p in pts)
    low = [p for p in pts if p.z < zmin + 0.04]
    gaps = [support_below(p, own) for p in low[:40]]
    rest = [g for g in gaps if g is not None and g < GAP]
    if not rest:                                 # no low point rests on anything
        g = [x for x in gaps if x is not None]
        c = sum(low, Vector()) / len(low)
        bad += 1
        print('SUPPORT %-8s floats %s at (%.2f, %.2f, %.2f)' % (own, ('%.2f m' % min(g)) if g else '> 1 m',
                                                              c.x, c.y, zmin))
print('SUPPORT DONE', bad, 'floating')
