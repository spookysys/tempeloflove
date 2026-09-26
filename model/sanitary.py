"""Sanitary objects and tiles modelled after real products (used by build_model.py and annex_interior.py).

- wall_wc():      wall-hung WC (bowl ~36 x 54 cm, rim at 40 cm, tapering to the wall), open seat ring,
                  brass flush plate on the concealed cistern, paper holder
- vessel_basin(): hand-beaten copper vessel basin (40 cm) on a counter, brass wall spout and lever
- rain_head():    round brushed-brass rain shower head (40 cm) on a ceiling arm; wall_mixer(): thermostat
- tile_mat():     scanned tile textures (ambientCG, CC0), mapped in metres (box projection)
- tile_floor(), tile_wall(): thin tiled layers on floors / along walls

All builders take a matrix M: local frame with the wall at y = 0, +y out of the wall into the room, z up.
"""
import math
import os

import bmesh
import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.environ.get('TEMPEL_ASSETS', os.path.join(os.path.dirname(HERE), '.assets'))


# --- materials ---------------------------------------------------------------------------------------------
def _principled(name, rgb, rough, metal=0.0, coat=0.0):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*rgb, 1.0)
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    if coat:
        b.inputs['Coat Weight'].default_value = coat
    m.diffuse_color = (*rgb, 1.0)
    return m


def mat_ceramic():
    return _principled('sanitary_ceramic', (0.86, 0.84, 0.80), 0.08, coat=0.6)


def mat_brass():
    return _principled('brushed_brass', (0.78, 0.56, 0.30), 0.28, metal=1.0)


def mat_copper():
    return _principled('hammered_copper', (0.72, 0.36, 0.20), 0.3, metal=1.0)


def mat_paper():
    return _principled('toilet_paper', (0.9, 0.89, 0.86), 0.9)


def tile_mat(asset, size_m=0.5, name=None):
    """Scanned tiles: one texture repeat = size_m metres (box projection in object space, objects unscaled)."""
    name = name or 'tiles_' + asset
    m = bpy.data.materials.get(name)
    if m:
        return m
    d = os.path.join(ASSETS, 'acg', asset)
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes['Principled BSDF']
    tc = nt.nodes.new('ShaderNodeTexCoord')
    mp = nt.nodes.new('ShaderNodeMapping')
    mp.inputs['Scale'].default_value = (1 / size_m,) * 3
    nt.links.new(tc.outputs['Object'], mp.inputs['Vector'])

    def img(kind, non_color=False):
        f = os.path.join(d, '%s_1K-JPG_%s.jpg' % (asset, kind))
        if not os.path.exists(f):
            return None
        t = nt.nodes.new('ShaderNodeTexImage')
        t.image = bpy.data.images.load(f, check_existing=True)
        if non_color:
            t.image.colorspace_settings.name = 'Non-Color'
        t.projection = 'BOX'
        t.projection_blend = 0.15
        nt.links.new(mp.outputs['Vector'], t.inputs['Vector'])
        return t
    c = img('Color')
    if c:
        nt.links.new(c.outputs['Color'], b.inputs['Base Color'])
        m.diffuse_color = (0.6, 0.4, 0.3, 1)
    r = img('Roughness', True)
    if r:
        nt.links.new(r.outputs['Color'], b.inputs['Roughness'])
    n = img('NormalGL', True)
    if n:
        nm = nt.nodes.new('ShaderNodeNormalMap')
        nm.inputs['Strength'].default_value = 0.8
        nt.links.new(n.outputs['Color'], nm.inputs['Color'])
        nt.links.new(nm.outputs['Normal'], b.inputs['Normal'])
    b.inputs['Coat Weight'].default_value = 0.35          # glazed
    return m


# --- helpers -----------------------------------------------------------------------------------------------
def _obj(name, bm, mat, parent=None, coll='furnishing', smooth=True, subsurf=0):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    me.materials.append(mat)
    (bpy.data.collections.get(coll) or bpy.context.scene.collection).objects.link(ob)
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    if subsurf:
        ob.modifiers.new('sub', 'SUBSURF').levels = subsurf
        ob.modifiers['sub'].render_levels = subsurf
    if parent:
        ob.parent = parent
    return ob


def _ring(cx, cy, rx, ry, z, n=2.4, seg=32, ymin=None):
    pts = []
    for i in range(seg):
        a = 2 * math.pi * i / seg
        c, s = math.cos(a), math.sin(a)
        x = cx + rx * math.copysign(abs(c) ** (2 / n), c)
        y = cy + ry * math.copysign(abs(s) ** (2 / n), s)
        if ymin is not None:
            y = max(y, ymin)
        pts.append(Vector((x, y, z)))
    return pts


def _loft(bm, rings, cap_bottom=True, cap_top=False):
    vs = [[bm.verts.new(p) for p in r] for r in rings]
    n = len(rings[0])
    for a, b in zip(vs, vs[1:]):
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((a[i], a[j], b[j], b[i]))
    if cap_bottom:
        bm.faces.new(list(reversed(vs[0])))
    if cap_top:
        bm.faces.new(vs[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return vs


def _box(bm, c, s):
    bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(c) @ Matrix.Diagonal((*s, 1)))


def _cyl(bm, c, r, h, seg=24, axis='Z'):
    R = {'Z': Matrix(), 'Y': Matrix.Rotation(math.pi / 2, 4, 'X'), 'X': Matrix.Rotation(math.pi / 2, 4, 'Y')}[axis]
    bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r, radius2=r, depth=h,
                          matrix=Matrix.Translation(c) @ R)


def _place(bm, M):
    bmesh.ops.transform(bm, matrix=M, verts=bm.verts[:])


# --- objects -----------------------------------------------------------------------------------------------
def wall_wc(name, M, parent=None):
    """Wall-hung WC, local frame: wall at y = 0, the bowl reaches to y = 0.54, rim at z = 0.40."""
    bm = bmesh.new()
    # outer shell: from a narrow waist at the wall up to the full rim (tapered towards the wall, as real ones)
    outer = [(0.16, 0.10, 0.155, 0.20, 3.0), (0.22, 0.13, 0.20, 0.24, 2.8), (0.30, 0.165, 0.25, 0.28, 2.5),
             (0.37, 0.18, 0.27, 0.29, 2.4), (0.40, 0.18, 0.27, 0.29, 2.4)]
    rings = [_ring(0, cy, rx, ry, z, n=n, ymin=0.0) for (z, rx, ry, cy, n) in outer]
    # rim top, then the bowl inside, down to the water
    inner = [(0.405, 0.145, 0.225, 0.305, 2.3), (0.36, 0.13, 0.19, 0.33, 2.2), (0.30, 0.09, 0.12, 0.34, 2.0),
             (0.27, 0.06, 0.07, 0.34, 2.0)]
    rings += [_ring(0, cy, rx, ry, z, n=n) for (z, rx, ry, cy, n) in inner]
    _loft(bm, rings, cap_bottom=True, cap_top=True)
    _place(bm, M)
    bowl = _obj(name, bm, mat_ceramic(), parent, subsurf=2)
    # seat ring (open, white) resting on the rim
    bm = bmesh.new()
    o = _ring(0, 0.30, 0.175, 0.265, 0.412, n=2.4, ymin=0.06)
    i = _ring(0, 0.315, 0.12, 0.19, 0.412, n=2.2)
    o2 = [p + Vector((0, 0, 0.022)) for p in o]
    i2 = [p + Vector((0, 0, 0.022)) for p in i]
    vs = [[bm.verts.new(p) for p in r] for r in (o, i, i2, o2)]
    n = len(o)
    for a, b in ((0, 1), (1, 2), (2, 3), (3, 0)):
        for k in range(n):
            j = (k + 1) % n
            bm.faces.new((vs[a][k], vs[a][j], vs[b][j], vs[b][k]))
    _box(bm, Vector((0, 0.035, 0.425)), (0.26, 0.05, 0.03))         # hinge bar
    _place(bm, M)
    _obj(name + '_seat', bm, mat_ceramic(), parent, subsurf=1)
    # flush plate (brushed brass, two buttons) and paper holder with a roll
    bm = bmesh.new()
    _box(bm, Vector((0, 0.006, 1.02)), (0.25, 0.012, 0.165))
    _box(bm, Vector((-0.055, 0.014, 1.02)), (0.1, 0.008, 0.13))
    _box(bm, Vector((0.055, 0.014, 1.02)), (0.1, 0.008, 0.13))
    _cyl(bm, Vector((0.36, 0.05, 0.72)), 0.008, 0.1, 12, 'Y')
    _cyl(bm, Vector((0.36, 0.1, 0.72)), 0.006, 0.14, 12, 'X')
    _place(bm, M)
    _obj(name + '_brass', bm, mat_brass(), parent)
    bm = bmesh.new()
    _cyl(bm, Vector((0.36, 0.1, 0.66)), 0.055, 0.1, 24, 'X')
    _place(bm, M)
    _obj(name + '_paper', bm, mat_paper(), parent)
    return bowl


def vessel_basin(name, M, counter_z, parent=None):
    """Copper vessel basin standing on a counter (top at counter_z), wall spout and lever above it."""
    bm = bmesh.new()
    rings = []
    for k in range(9):                       # hemispherical bowl: outer wall up, then the inner wall down
        a = math.pi / 2 * k / 8
        rings.append(_ring(0, 0.3, 0.2 * math.sin(a) + 0.02, 0.2 * math.sin(a) + 0.02,
                           counter_z + 0.14 * (1 - math.cos(a)), n=2.0))
    for k in range(8, -1, -1):
        a = math.pi / 2 * k / 8
        rings.append(_ring(0, 0.3, 0.19 * math.sin(a) + 0.015, 0.19 * math.sin(a) + 0.015,
                           counter_z + 0.012 + 0.13 * (1 - math.cos(a)), n=2.0))
    _loft(bm, rings, cap_bottom=True, cap_top=True)
    _place(bm, M)
    _obj(name, bm, mat_copper(), parent, subsurf=1)
    bm = bmesh.new()
    zs = counter_z + 0.27
    _cyl(bm, Vector((0, 0.1, zs)), 0.014, 0.2, 16, 'Y')             # spout from the wall
    _cyl(bm, Vector((0, 0.2, zs - 0.02)), 0.014, 0.05, 16)          # the turned-down tip
    _cyl(bm, Vector((0, 0.01, zs)), 0.035, 0.02, 24, 'Y')           # rosette
    _cyl(bm, Vector((0.12, 0.03, zs)), 0.025, 0.05, 20, 'Y')        # lever body
    _box(bm, Vector((0.12, 0.09, zs + 0.02)), (0.012, 0.09, 0.012))  # lever
    _place(bm, M)
    _obj(name + '_tap', bm, mat_brass(), parent)


def round_mirror(name, M, z, r=0.3, parent=None):
    """Round mirror with a thin brass frame on the wall."""
    bm = bmesh.new()
    _cyl(bm, Vector((0, 0.008, z)), r, 0.008, 64, 'Y')
    _place(bm, M)
    _obj(name, bm, _principled('mirror_glass', (0.9, 0.9, 0.9), 0.02, metal=1.0), parent, smooth=False)
    bm = bmesh.new()
    _cyl(bm, Vector((0, 0.005, z)), r + 0.015, 0.01, 64, 'Y')
    _place(bm, M)
    _obj(name + '_frame', bm, mat_brass(), parent, smooth=False)


def rain_head(name, c, ceil_z, parent=None, r=0.2):
    """Round rain head r (m) hanging from the ceiling on an arm; c = centre (x, y) in the parent frame."""
    bm = bmesh.new()
    zh = ceil_z - 0.32
    _cyl(bm, Vector((c[0], c[1], zh)), r, 0.012, 48)
    _cyl(bm, Vector((c[0], c[1], zh + 0.014)), r * 0.5, 0.02, 32)
    _cyl(bm, Vector((c[0], c[1], (zh + ceil_z) / 2)), 0.012, ceil_z - zh, 16)
    _cyl(bm, Vector((c[0], c[1], ceil_z - 0.006)), 0.04, 0.012, 24)
    _obj(name, bm, mat_brass(), parent)


def wall_mixer(name, M, z=1.05, parent=None):
    """Thermostatic shower mixer: round brass rosette with a knob and a lever."""
    bm = bmesh.new()
    _cyl(bm, Vector((0, 0.006, z)), 0.085, 0.012, 32, 'Y')
    _cyl(bm, Vector((0, 0.035, z)), 0.03, 0.05, 24, 'Y')
    _box(bm, Vector((0, 0.07, z - 0.05)), (0.014, 0.014, 0.1))
    _place(bm, M)
    _obj(name, bm, mat_brass(), parent)


def tile_floor(name, poly, z, mat, parent=None):
    """A tiled layer (8 mm) over a floor outline poly [(x, y), ...]."""
    bm = bmesh.new()
    lo = [bm.verts.new((x, y, z)) for x, y in poly]
    hi = [bm.verts.new((x, y, z + 0.008)) for x, y in poly]
    bm.faces.new(hi)
    bm.faces.new(list(reversed(lo)))
    n = len(poly)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((lo[i], lo[j], hi[j], hi[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return _obj(name, bm, mat, parent, smooth=False)


def tile_wall(name, p0, p1, z0, z1, mat, parent=None, off=0.006):
    """Tiles along a wall from p0 to p1 (x, y), z0..z1, on the room side (left of p0 -> p1)."""
    bm = bmesh.new()
    a, b = Vector((*p0, 0)), Vector((*p1, 0))
    d = (b - a).normalized()
    nrm = Vector((-d.y, d.x, 0)) * off
    q = [a + nrm + Vector((0, 0, z0)), b + nrm + Vector((0, 0, z0)), b + nrm + Vector((0, 0, z1)),
         a + nrm + Vector((0, 0, z1))]
    q2 = [p + nrm * 1.3 for p in q]
    v1 = [bm.verts.new(p) for p in q]
    v2 = [bm.verts.new(p) for p in q2]
    bm.faces.new(v2)
    bm.faces.new(list(reversed(v1)))
    for i in range(4):
        j = (i + 1) % 4
        bm.faces.new((v1[i], v1[j], v2[j], v2[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return _obj(name, bm, mat, parent, smooth=False)


def frame(x, y, z, face_deg):
    """Local frame at (x, y, z) whose +y points in direction face_deg (the room side of a wall)."""
    return Matrix.Translation((x, y, z)) @ Matrix.Rotation(math.radians(face_deg - 90), 4, 'Z')
