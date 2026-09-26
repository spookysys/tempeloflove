"""Inside the annex and the bathing room's WCs (called by build_model.py; postfix.py adds it to built files).

Annex on the north face (see build_model section 9): foyer in the middle with the coat benches,
the accessible WC at the east end, the tech room at the west end (district-heating substation, buffer tank,
electrics, a shelf for event gear). Both side rooms get closed doors, so from the foyer they stay private.
Lights: two warm ceiling lights in the foyer, one each in the WC, the tech room and the two WCs upstairs.
Idempotent: does nothing if 'annex_doors' already exists.
"""
import math

import bmesh
import bpy
from mathutils import Matrix, Vector

import params as P

KE = P.ENTRY_SLOT
RZ = P.slot_center(KE)             # box x axis along n (outwards), y along t
AO = P.R_OUT + P.ANNEX_D
T = 0.35                            # annex wall thickness


def FP(k, n, t, z=0.0):
    a = math.radians(P.slot_center(k))
    return Vector((n * math.cos(a) - t * math.sin(a), n * math.sin(a) + t * math.cos(a), z))


def _mat(name, hexcol, rough=0.5, metal=0.0, emit=0.0):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    h = hexcol.lstrip('#')
    c = [((int(h[i:i + 2], 16) / 255) ** 2.2) for i in (0, 2, 4)] + [1.0]
    b.inputs['Base Color'].default_value = c
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    if emit:
        b.inputs['Emission Color'].default_value = c
        b.inputs['Emission Strength'].default_value = emit
    m.diffuse_color = c
    return m


def _mat_or(name, fallback):
    return bpy.data.materials.get(name) or fallback


def _box(bm, c, size, rz=RZ):
    M = Matrix.Translation(Vector(c)) @ Matrix.Rotation(math.radians(rz), 4, 'Z') @ Matrix.Diagonal((*size, 1.0))
    bmesh.ops.create_cube(bm, size=1.0, matrix=M)


def _cyl(bm, c, r, h, seg=24):
    M = Matrix.Translation(Vector(c))
    bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r, radius2=r, depth=h, matrix=M)


def _obj(name, bm, mat, coll_name):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    me.materials.append(mat)
    c = bpy.data.collections.get(coll_name) or bpy.context.scene.collection
    c.objects.link(ob)
    for p in me.polygons:
        p.use_smooth = False
    return ob


def _light(name, loc, power):
    li = bpy.data.lights.new(name, 'POINT')
    li.energy = 0.0
    li.color = (1.0, 0.80, 0.60)
    li.shadow_soft_size = 0.15
    lo = bpy.data.objects.new(name, li)
    lo.location = loc
    lo['lantern_power'] = power                 # render.set_night() switches it on with the other lights
    c = bpy.data.collections.get('night_lights') or bpy.context.scene.collection
    c.objects.link(lo)
    return lo


def build():
    if bpy.data.objects.get('annex_doors'):
        return 0
    wood = _mat_or('wood_dark_walnut', _mat('wood_dark_walnut', '#6A4A30'))
    larch = _mat_or('glulam_larch', _mat('glulam_larch', '#B7874F'))
    steel = _mat_or('steel_bronze', _mat('steel_bronze', '#4B4036', 0.4, 0.8))
    ceramic = _mat_or('ceramic_white', _mat('ceramic_white', '#EDE8DF', 0.15))
    grey = _mat('tech_enamel', '#C9C4BA', 0.45, 0.2)
    copper = _mat('copper_pipe', '#B87333', 0.3, 1.0)
    mirror = _mat('mirror', '#E8E8E8', 0.02, 1.0)
    shade = _mat('ceiling_light_opal', '#FFF1DC', 0.4, 0.0, emit=3.0)
    felt = _mat('storage_felt', '#8C7A64', 0.9)
    gap = (P.R_OUT + 3.1, P.R_OUT + 4.0)             # door openings in both partitions (build_model section 9)
    nd = sum(gap) / 2
    # doors (closed), with a wooden pull
    bm = bmesh.new()
    for tt in (-2.6, 2.6):
        _box(bm, FP(KE, nd, tt, 1.04), (gap[1] - gap[0] - 0.02, 0.045, 2.06))
    _obj('annex_doors', bm, larch, 'annex')
    bm = bmesh.new()
    for tt in (-2.6, 2.6):
        for s in (-1, 1):
            _box(bm, FP(KE, gap[0] + 0.12, tt + s * 0.05, 1.05), (0.03, 0.03, 0.28))
    _obj('annex_door_pulls', bm, wood, 'annex')
    # accessible WC (east, t < -2.6): grab bars beside the toilet, mirror over the basin, a shelf
    bm = bmesh.new()
    for s in (-1, 1):
        _box(bm, FP(KE, P.R_OUT + 1.1, -3.4 + s * 0.38, 0.78), (0.7, 0.035, 0.035))
    _obj('annex_wc_grab_bars', bm, steel, 'annex')
    bm = bmesh.new()
    _box(bm, FP(KE, AO - T - 0.015, -3.3, 1.55), (0.02, 0.55, 0.75))
    _obj('annex_wc_mirror', bm, mirror, 'annex')
    bm = bmesh.new()
    _box(bm, FP(KE, AO - T - 0.1, -3.3, 1.08), (0.18, 0.6, 0.03))
    _obj('annex_wc_shelf', bm, wood, 'annex')
    # tech room (west, t > 2.6): substation, buffer tank, electrics, pipes, a shelf with event gear
    bm = bmesh.new()
    _box(bm, FP(KE, P.R_OUT + 0.5, 3.5, 0.85), (0.5, 0.8, 1.7))                     # district-heating substation
    _box(bm, FP(KE, AO - T - 0.15, 3.3, 1.45), (0.25, 0.9, 1.2))                    # electrics cabinet
    _obj('annex_tech_units', bm, grey, 'annex')
    bm = bmesh.new()
    _cyl(bm, FP(KE, P.R_OUT + 1.45, 4.3, 0.98), 0.42, 1.95)                           # buffer tank
    _obj('annex_tech_tank', bm, grey, 'annex')
    bm = bmesh.new()
    for i, tt in enumerate((3.25, 3.45, 3.65)):
        _box(bm, FP(KE, P.R_OUT + 0.3, tt, 2.35), (0.035, 0.035, 1.3))                # risers from the substation
        _box(bm, FP(KE, P.R_OUT + 0.9, tt, 2.95 - 0.08 * i), (1.2, 0.035, 0.035))
    _obj('annex_tech_pipes', bm, copper, 'annex')
    bm = bmesh.new()
    for z in (0.35, 0.9, 1.45, 2.0):
        _box(bm, FP(KE, P.R_OUT + 3.0, 5.0, z), (1.6, 0.45, 0.03))                    # shelf boards
    for dn in (-0.78, 0.78):
        _box(bm, FP(KE, P.R_OUT + 3.0 + dn, 5.0, 1.05), (0.04, 0.45, 2.1))
    _obj('annex_tech_shelf', bm, larch, 'annex')
    bm = bmesh.new()
    for i, (z, dn, w) in enumerate(((0.36, -0.4, 0.6), (0.36, 0.35, 0.7), (0.91, -0.3, 0.8), (0.91, 0.45, 0.5),
                                    (1.46, 0.0, 1.2), (2.01, -0.35, 0.7))):
        _box(bm, FP(KE, P.R_OUT + 3.0 + dn, 5.0, z + 0.2), (w, 0.4, 0.38))           # boxes: cushions, cables...
    _obj('annex_tech_boxes', bm, felt, 'annex')
    # ceiling lights (opal discs) and their light sources
    spots = [('annex_foyer_a', FP(KE, P.R_OUT + 1.5, 0.0, P.ANNEX_H - 0.06), 45.0),
             ('annex_foyer_b', FP(KE, P.R_OUT + 3.6, 0.0, P.ANNEX_H - 0.06), 45.0),
             ('annex_wc', FP(KE, P.R_OUT + 2.4, -4.0, P.ANNEX_H - 0.06), 25.0),
             ('annex_tech', FP(KE, P.R_OUT + 2.4, 4.0, P.ANNEX_H - 0.06), 20.0)]
    for s in (-1, 1):                                     # the two WCs of the bathing room upstairs
        spots.append(('bath_wc_light_%d' % s, FP(P.BATH_SLOT, 6.5, s * 1.6, P.CEIL_UF - 0.06), 18.0))
    bm = bmesh.new()
    for name, loc, power in spots:
        _cyl(bm, loc + Vector((0, 0, 0.02)), 0.17, 0.04)
        _light(name + '_light', loc - Vector((0, 0, 0.12)), power)
    _obj('annex_ceiling_lights', bm, shade, 'annex')
    return 1


if __name__ == '__main__':
    print('annex interior', build())
