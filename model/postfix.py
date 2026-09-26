"""Apply the latest small fixes to an already built file (no full rebuild needed):
- stair-foot cushions on the seating tiers where the tier is (see build_model, section 7)
- roof planters and hanging greens as in plants.py

    python3 postfix.py [tempel.blend | tempel_event.blend]
"""
import math
import os
import sys

import bpy
from mathutils import Matrix, Vector

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
    KS, R = P.STAIR_SLOT, P.STAIR_RISE
    n = 0
    for s_, (i, nn, tt) in enumerate(P.stair_cushion_spots()):
        if s_ % 4 == 3:
            continue
        me = me0.copy()
        ob = bpy.data.objects.new('stair_cushion_%d_%d' % (i, s_), me)
        for c in cols:
            c.objects.link(ob)
        ob.location = FP(KS, nn, tt, i * R + 0.065) - c0
        if mats:
            me.materials.clear()
            me.materials.append(mats[(i + s_) % len(mats)])
        n += 1
    return n


def fix_ext_stair_guards():
    """Railings across the external stair's landing ends (added to build_model; here for built files)."""
    if bpy.data.objects.get('ext_stair_guards') or not bpy.data.objects.get('ext_stair_steel'):
        return 0
    import bmesh
    K_ = P.STAIR_SLOT
    RZ_ = P.slot_center(K_) + 90
    W_ = P.EXT_W
    n_in1 = P.R_OUT + 0.05 + W_
    n_out0, n_out1 = n_in1, n_in1 + W_
    t_top1 = P.EXT_T_LAND - (P.TERRACE_RISERS - 1) * P.EXT_GOING
    land_top = (P.TERRACE_GATE[0] - 0.05, t_top1)
    land_uf = (P.EXT_T_LAND, P.face_half(P.R_OUT) - 0.05)
    bm = bmesh.new()

    def cube(c, size):
        M = Matrix.Translation(c) @ Matrix.Rotation(math.radians(RZ_), 4, 'Z') @ Matrix.Diagonal((*size, 1.0))
        bmesh.ops.create_cube(bm, size=1.0, matrix=M)
    for (t, n0, n1, zz) in ((land_top[0] + 0.03, P.R_OUT + 0.02, n_out1, P.TERRACE_Z),
                            (land_top[1] - 0.03, P.R_OUT + 0.02, n_out0 + 0.03, P.TERRACE_Z),
                            (land_uf[1] - 0.03, P.R_OUT + 0.02, n_out1, P.FFL_UF)):
        cube(FP(K_, (n0 + n1) / 2, t, zz + 1.0), (0.05, n1 - n0, 0.05))
        for i in range(int((n1 - n0) / 0.12)):
            cube(FP(K_, n0 + 0.06 + i * 0.12, t, zz + 0.5), (0.02, 0.02, 1.0))
        cube(FP(K_, n0 + 0.04, t, zz + 0.5), (0.06, 0.06, 1.0))
    me = bpy.data.meshes.new('ext_stair_guards')
    bm.to_mesh(me)
    ob = bpy.data.objects.new('ext_stair_guards', me)
    src = bpy.data.objects['ext_stair_steel']
    me.materials.append(src.active_material)
    for c in src.users_collection:
        c.objects.link(ob)
    return 1


if __name__ == '__main__':
    blend = next((a for a in sys.argv[1:] if a.endswith('.blend')), 'tempel.blend')
    path = os.path.join(HERE, blend)
    bpy.ops.wm.open_mainfile(filepath=path)
    print('POSTFIX cushions', fix_stair_cushions())
    print('POSTFIX ext stair guards', fix_ext_stair_guards())
    import annex_interior
    print('POSTFIX annex interior', annex_interior.build())
    PL.build_roof_planters()
    PL.build_hanging_greens()
    bpy.ops.file.pack_all() if os.environ.get('PACK') else None
    bpy.ops.wm.save_as_mainfile(filepath=path, compress=True)
    print('POSTFIX saved', path)
