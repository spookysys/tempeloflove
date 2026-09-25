"""People on the event mattress groups: flags anyone whose low body parts hang in the air beside a
mattress (lying half off the edge) or sink into the floor next to it.

    python3 humans/check_support.py [tempel_event.blend]
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

blend = next((a for a in sys.argv[1:] if a.endswith('.blend')), 'tempel_event.blend')
bpy.ops.wm.open_mainfile(filepath=os.path.join(MODEL, blend))
bpy.context.scene.frame_set(100)
dg = bpy.context.evaluated_depsgraph_get()

GROUPS = {g: P.mat_group(g) for g in ('field', 'cuddle', 'intimate', 'wrestle')}


def on_mattress(p):
    """thickness of the mattress under point p (None if no mattress there)"""
    for cells, rz, th in GROUPS.values():
        a = math.radians(rz)
        c, s = math.cos(a), math.sin(a)
        for x, y in cells:
            dx, dy = p.x - x, p.y - y
            u, v = dx * c + dy * s, -dx * s + dy * c
            if abs(u) <= P.MAT_W / 2 and abs(v) <= P.MAT_L / 2:
                return th
    return None


def near_group(p, r=3.2):
    for cells, rz, th in GROUPS.values():
        cx = sum(c[0] for c in cells) / len(cells)
        cy = sum(c[1] for c in cells) / len(cells)
        if math.hypot(p.x - cx, p.y - cy) < r:
            return True
    return False


bad = 0
for o in bpy.data.objects:
    if o.type != 'MESH' or not o.name.endswith('.body') or o.hide_render:
        continue
    e = o.evaluated_get(dg)
    me = e.to_mesh()
    pts = [e.matrix_world @ v.co for v in me.vertices]
    e.to_mesh_clear()
    zmin = min(p.z for p in pts)
    low = [p for p in pts if p.z < zmin + 0.06]
    c = sum(low, Vector()) / len(low)
    if c.z > 0.45 or not near_group(c):
        continue
    floating = [p for p in low if on_mattress(p) is None and p.z > 0.06]        # in the air beside a mattress
    sunk = [p for p in low if (on_mattress(p) or 0) > 0 and p.z < on_mattress(p) - 0.06]   # inside a mattress
    if len(floating) > 0.15 * len(low) or len(sunk) > 0.15 * len(low):
        bad += 1
        print('SUPPORT %-10s low z %.2f at (%.2f, %.2f): %d%% in the air, %d%% sunk into a mattress'
              % (o.name[:-5], zmin, c.x, c.y, 100 * len(floating) // len(low), 100 * len(sunk) // len(low)))
print('SUPPORT DONE', bad, 'problems')
