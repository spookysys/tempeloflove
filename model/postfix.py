"""Apply the latest small fixes to an already built file (no full rebuild needed):
- stair-foot cushions on the seating tiers where the tier is (see build_model, section 7)
- roof planters and hanging greens as in plants.py

    python3 postfix.py [tempel.blend | tempel_event.blend]
"""
import math
import os
import sys

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import params as P  # noqa: E402
import plants as PL  # noqa: E402


def FP(k, n, t, z=0.0):
    a = math.radians(P.slot_center(k))
    return Vector((n * math.cos(a) - t * math.sin(a), n * math.sin(a) + t * math.cos(a), z))


def fix_stair_cushions():
    olds = sorted((o for o in bpy.data.objects if o.name.startswith('stair_cushion_')), key=lambda o: o.name)
    if not olds:
        return 0
    tmpl = olds[0]
    mats = [o.active_material for o in olds if o.active_material]
    cols = list(tmpl.users_collection)
    vs = [tmpl.matrix_world @ v.co for v in tmpl.data.vertices]
    c0 = sum(vs, Vector()) / len(vs)
    me0 = tmpl.data.copy()
    for o in olds:
        bpy.data.objects.remove(o)
    KS, N_FAN = P.STAIR_SLOT, P.STAIR_N_FAN
    N0 = P.R_IN - P.STAIR_FLIGHT_W_T
    T0, G, R = P.STAIR_T0, P.STAIR_GOING_T, P.STAIR_RISE
    T_FAN = T0 + N_FAN * G
    n = 0
    for i in range(1, N_FAN + 1):
        k_ = N_FAN + 1 - i
        d_, d_s = P.TIER_DEPTH * k_, 0.24 * k_
        t_end = T_FAN + P.TIER_RUN - P.TIER_STEP_BACK * (i - 1)
        tt, s_ = T0 + (i - 1) * G + 0.1, 0
        while tt < t_end - 0.35:
            nn = N0 - d_s / 2 if tt < T_FAN - 0.5 else (N0 - d_ + 0.24 if tt > T_FAN + 1.0 else None)
            if nn is not None and d_s / 2 < 0.25 and tt < T_FAN - 0.5:
                nn = None
            if nn is not None and (i + s_) % 3 != 2:
                me = me0.copy()
                ob = bpy.data.objects.new('stair_cushion_%d_%d' % (i, s_), me)
                for c in cols:
                    c.objects.link(ob)
                ob.location = FP(KS, nn, tt, i * R + 0.07) - c0
                if mats:
                    me.materials.clear()
                    me.materials.append(mats[(i + s_) % len(mats)])
                n += 1
            tt += 0.62
            s_ += 1
    return n


if __name__ == '__main__':
    blend = next((a for a in sys.argv[1:] if a.endswith('.blend')), 'tempel.blend')
    path = os.path.join(HERE, blend)
    bpy.ops.wm.open_mainfile(filepath=path)
    print('POSTFIX cushions', fix_stair_cushions())
    PL.build_roof_planters()
    PL.build_hanging_greens()
    bpy.ops.file.pack_all() if os.environ.get('PACK') else None
    bpy.ops.wm.save_as_mainfile(filepath=path, compress=True)
    print('POSTFIX saved', path)
