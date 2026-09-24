"""Builds the Tempel concept model in Blender (run with plain python + bpy module).

    python3 build_model.py            -> tempel.blend

All dimensions come from params.py. The model is a concept massing with
enough detail for renderings; it is not a construction model.
"""
import math
import os
import random
import sys

import bpy  # noqa: F401  (must come before bmesh when used as a module)
import bmesh
import bpy
from mathutils import Matrix, Vector, Quaternion

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import params as P  # noqa: E402

rnd = random.Random(7)
rad = math.radians


def pol(r, a_deg, z=0.0):
    return Vector((r * math.cos(rad(a_deg)), r * math.sin(rad(a_deg)), z))


def srgb(hexstr, a=1.0):
    h = hexstr.lstrip('#')
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return (lin[0], lin[1], lin[2], a)


# ---------------------------------------------------------------------------
# scene / collections
# ---------------------------------------------------------------------------
bpy.ops.wm.read_factory_settings(use_empty=True)
SCENE = bpy.context.scene
SCENE.unit_settings.system = 'METRIC'
COLLS = {}


def coll(name, parent=None):
    if name in COLLS:
        return COLLS[name]
    c = bpy.data.collections.new(name)
    (parent or SCENE.collection).children.link(c)
    COLLS[name] = c
    return c


def mk_obj(name, bm, mats, collection, smooth=False, recalc=True):
    if recalc:
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for m in mats if isinstance(mats, (list, tuple)) else [mats]:
        me.materials.append(m)
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    coll(collection).objects.link(ob)
    return ob


def set_face_mats(ob, fn):
    """fn(center, normal) -> material index"""
    mw = ob.matrix_world
    for p in ob.data.polygons:
        p.material_index = fn(mw @ p.center, (mw.to_3x3() @ p.normal).normalized())


# ---------------------------------------------------------------------------
# geometry helpers
# ---------------------------------------------------------------------------
def sector(bm, r0, r1, a0, a1, z0, z1, step=2.0, ztop=None, zbot=None):
    """Annular sector prism. Angles in degrees. Full ring if span >= 360."""
    span = a1 - a0
    full = abs(span) >= 359.999
    n = max(1, int(math.ceil(abs(span) / step)))
    angs = [a0 + span * i / n for i in range(n + 1)]
    if full:
        angs = angs[:-1]
    profs = []
    for a in angs:
        zt0 = ztop(r0) if ztop else z1
        zt1 = ztop(r1) if ztop else z1
        zb0 = zbot(r0) if zbot else z0
        zb1 = zbot(r1) if zbot else z0
        profs.append([bm.verts.new(pol(r0, a, zb0)), bm.verts.new(pol(r1, a, zb1)),
                      bm.verts.new(pol(r1, a, zt1)), bm.verts.new(pol(r0, a, zt0))])
    m = len(profs)
    for i in (range(m) if full else range(m - 1)):
        A, B = profs[i], profs[(i + 1) % m]
        for j in range(4):
            bm.faces.new((A[j], A[(j + 1) % 4], B[(j + 1) % 4], B[j]))
    if not full:
        bm.faces.new(profs[0])
        bm.faces.new(profs[-1][::-1])


def cube(bm, center, size, rz=0.0, rx=0.0, ry=0.0):
    M = (Matrix.Translation(Vector(center)) @ Matrix.Rotation(rad(rz), 4, 'Z')
         @ Matrix.Rotation(rad(ry), 4, 'Y') @ Matrix.Rotation(rad(rx), 4, 'X')
         @ Matrix.Diagonal((size[0], size[1], size[2], 1.0)))
    bmesh.ops.create_cube(bm, size=1.0, matrix=M)


def seg_box(bm, p0, p1, t, z0, z1):
    """Box along a horizontal 2D segment p0->p1 with thickness t."""
    p0, p1 = Vector((p0[0], p0[1])), Vector((p1[0], p1[1]))
    d = (p1 - p0)
    L = d.length
    c = (p0 + p1) / 2
    ang = math.degrees(math.atan2(d.y, d.x))
    cube(bm, (c.x, c.y, (z0 + z1) / 2), (L, t, z1 - z0), rz=ang)


def cyl(bm, center, r, h, segs=24, r2=None, rot=None):
    M = Matrix.Translation(Vector(center))
    if rot is not None:
        M = M @ rot
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=segs,
                          radius1=r, radius2=r if r2 is None else r2, depth=h, matrix=M)


def sweep_rect(bm, pts, ups, w, h):
    """Rectangular tube along polyline pts; ups = local 'up' vectors (normals)."""
    rings = []
    n = len(pts)
    for i, p in enumerate(pts):
        t = (pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]).normalized()
        u = ups[i] - t * ups[i].dot(t)
        u.normalize()
        s = t.cross(u)
        rings.append([bm.verts.new(p + s * sx * w / 2 + u * uy * h / 2)
                      for sx, uy in ((-1, -1), (1, -1), (1, 1), (-1, 1))])
    for i in range(n - 1):
        A, B = rings[i], rings[i + 1]
        for j in range(4):
            bm.faces.new((A[j], A[(j + 1) % 4], B[(j + 1) % 4], B[j]))
    bm.faces.new(rings[0][::-1])
    bm.faces.new(rings[-1])


def front_r(a_deg):
    """Radius of the decagonal room-front line at angle a."""
    k = round((a_deg - P.SLOT0_DEG) / P.SLOT_DEG)
    c = P.slot_center(k)
    return P.APOTHEM_FRONT / math.cos(rad(a_deg - c))


# ---------------------------------------------------------------------------
# materials
# ---------------------------------------------------------------------------
class NB:
    """Tiny node-tree builder."""

    def __init__(self, mat):
        self.nt = mat.node_tree
        self.nt.nodes.clear()
        self.out = self.nt.nodes.new('ShaderNodeOutputMaterial')

    def n(self, typ, **kw):
        node = self.nt.nodes.new(typ)
        for k, v in kw.items():
            if k in node.inputs.keys():
                node.inputs[k].default_value = v
            else:
                setattr(node, k, v)
        return node

    def l(self, a, b):
        self.nt.links.new(a, b)

    def coord(self, kind='Object'):
        return self.n('ShaderNodeTexCoord').outputs[kind]

    def mapping(self, vec, scale=(1, 1, 1), rot=(0, 0, 0), loc=(0, 0, 0)):
        m = self.n('ShaderNodeMapping')
        m.inputs['Scale'].default_value = scale
        m.inputs['Rotation'].default_value = rot
        m.inputs['Location'].default_value = loc
        self.l(vec, m.inputs['Vector'])
        return m.outputs['Vector']

    def noise(self, vec, scale=5.0, detail=4.0, rough=0.5):
        t = self.n('ShaderNodeTexNoise', Scale=scale, Detail=detail, Roughness=rough)
        self.l(vec, t.inputs['Vector'])
        return t

    def ramp(self, fac, stops):
        r = self.n('ShaderNodeValToRGB')
        cr = r.color_ramp
        while len(cr.elements) < len(stops):
            cr.elements.new(0.5)
        for el, (pos, col) in zip(cr.elements, stops):
            el.position = pos
            el.color = col
        self.l(fac, r.inputs['Fac'])
        return r.outputs['Color']

    def mix(self, fac, a, b, blend='MIX'):
        m = self.n('ShaderNodeMix', data_type='RGBA', blend_type=blend)
        if isinstance(fac, float):
            m.inputs[0].default_value = fac
        else:
            self.l(fac, m.inputs[0])
        for sock, v in ((m.inputs[6], a), (m.inputs[7], b)):
            if isinstance(v, tuple):
                sock.default_value = v
            else:
                self.l(v, sock)
        return m.outputs[2]

    def bump(self, height, strength=0.2, dist=0.01, normal=None):
        b = self.n('ShaderNodeBump', Strength=strength, Distance=dist)
        self.l(height, b.inputs['Height'])
        if normal is not None:
            self.l(normal, b.inputs['Normal'])
        return b.outputs['Normal']

    def principled(self, color, rough=0.5, normal=None, **kw):
        p = self.n('ShaderNodeBsdfPrincipled')
        if isinstance(color, tuple):
            p.inputs['Base Color'].default_value = color
        else:
            self.l(color, p.inputs['Base Color'])
        p.inputs['Roughness'].default_value = rough
        for k, v in kw.items():
            p.inputs[k.replace('_', ' ')].default_value = v
        if normal is not None:
            self.l(normal, p.inputs['Normal'])
        return p

    def output(self, shader):
        self.l(shader.outputs[0], self.out.inputs['Surface'])


MATS = {}


def new_mat(name, vp, alpha=1.0):
    m = bpy.data.materials.new(name)
    m['vp_color'] = list(vp[:3])
    m['vp_alpha'] = alpha
    m.diffuse_color = (vp[0], vp[1], vp[2], alpha)
    MATS[name] = m
    return m, NB(m)


def mat_clay(name, c_a, c_b, scale=1.3):
    ca, cb = srgb(c_a), srgb(c_b)
    m, b = new_mat(name, ca)
    co = b.coord()
    n1 = b.noise(co, scale=scale, detail=6, rough=0.6)
    n2 = b.noise(co, scale=18.0, detail=8, rough=0.7)
    col = b.ramp(n1.outputs['Fac'], [(0.3, ca), (0.7, cb)])
    col = b.mix(0.12, col, n2.outputs['Color'], blend='OVERLAY')
    n3 = b.noise(co, scale=4.0, detail=10, rough=0.65)
    h = b.n('ShaderNodeMath', operation='ADD')
    b.l(n2.outputs['Fac'], h.inputs[0])
    b.l(n3.outputs['Fac'], h.inputs[1])
    nrm = b.bump(h.outputs[0], strength=0.22, dist=0.006)
    b.output(b.principled(col, rough=0.93, normal=nrm))
    return m


def mat_boards(name, c_a, c_b, c_gap, board_w=0.15, board_l=2.4, polar=False,
               rough=0.42, rot90=False, vp=None):
    ca, cb, cg = srgb(c_a), srgb(c_b), srgb(c_gap)
    m, b = new_mat(name, vp and srgb(vp) or ca)
    co = b.coord()
    if polar:
        sep = b.n('ShaderNodeSeparateXYZ')
        b.l(co, sep.inputs[0])
        at = b.n('ShaderNodeMath', operation='ARCTAN2')
        b.l(sep.outputs['Y'], at.inputs[0])
        b.l(sep.outputs['X'], at.inputs[1])
        s = b.n('ShaderNodeMath', operation='MULTIPLY')
        b.l(at.outputs[0], s.inputs[0])
        s.inputs[1].default_value = 4.8
        ln = b.n('ShaderNodeVectorMath', operation='LENGTH')
        cmb0 = b.n('ShaderNodeCombineXYZ')
        b.l(sep.outputs['X'], cmb0.inputs[0])
        b.l(sep.outputs['Y'], cmb0.inputs[1])
        b.l(cmb0.outputs[0], ln.inputs[0])
        cmb = b.n('ShaderNodeCombineXYZ')
        b.l(s.outputs[0], cmb.inputs[0])
        b.l(ln.outputs['Value'], cmb.inputs[1])
        vec = cmb.outputs[0]
    else:
        vec = b.mapping(co, rot=(0, 0, rad(90) if rot90 else 0))
    br = b.n('ShaderNodeTexBrick', offset=0.37, offset_frequency=1, squash=1.0,
             squash_frequency=1)
    br.inputs['Scale'].default_value = 1.0
    br.inputs['Mortar Size'].default_value = 0.0025
    br.inputs['Mortar Smooth'].default_value = 0.3
    br.inputs['Bias'].default_value = 0.0
    br.inputs['Brick Width'].default_value = board_l
    br.inputs['Row Height'].default_value = board_w
    br.inputs['Color1'].default_value = ca
    br.inputs['Color2'].default_value = cb
    br.inputs['Mortar'].default_value = cg
    b.l(vec, br.inputs['Vector'])
    gv = b.mapping(vec, scale=(2.0, 45.0, 2.0))
    g = b.noise(gv, scale=3.0, detail=6, rough=0.55)
    grain = b.ramp(g.outputs['Fac'], [(0.35, (0.80, 0.80, 0.80, 1)), (0.65, (1.08, 1.05, 1.0, 1))])
    col = b.mix(1.0, br.outputs['Color'], grain, blend='MULTIPLY')
    hsum = b.n('ShaderNodeMath', operation='SUBTRACT')
    hsum.inputs[0].default_value = 1.0
    b.l(br.outputs['Fac'], hsum.inputs[1])
    nrm = b.bump(hsum.outputs[0], strength=0.35, dist=0.003)
    nrm = b.bump(g.outputs['Fac'], strength=0.05, dist=0.002, normal=nrm)
    b.output(b.principled(col, rough=rough, normal=nrm, Coat_Weight=0.08))
    return m


def mat_wood(name, c_a, c_b, grain_axis='Z', rough=0.55):
    ca, cb = srgb(c_a), srgb(c_b)
    m, b = new_mat(name, ca)
    sc = {'Z': (6, 6, 0.25), 'X': (0.25, 6, 6), 'Y': (6, 0.25, 6), 'R': (4, 4, 4)}[grain_axis]
    v = b.mapping(b.coord(), scale=sc)
    t = b.n('ShaderNodeTexWave', wave_type='RINGS', rings_direction='SPHERICAL' if grain_axis == 'R' else 'Z')
    t.inputs['Scale'].default_value = 2.0
    t.inputs['Distortion'].default_value = 6.0
    t.inputs['Detail'].default_value = 3.0
    b.l(v, t.inputs['Vector'])
    nz = b.noise(b.coord(), scale=2.0, detail=3)
    fac = b.n('ShaderNodeMix', data_type='FLOAT')
    fac.inputs[0].default_value = 0.35
    b.l(t.outputs['Fac'], fac.inputs[2])
    b.l(nz.outputs['Fac'], fac.inputs[3])
    col = b.ramp(fac.outputs[0], [(0.25, ca), (0.85, cb)])
    nrm = b.bump(t.outputs['Fac'], strength=0.04, dist=0.002)
    b.output(b.principled(col, rough=rough, normal=nrm, Coat_Weight=0.05))
    return m


def mat_fabric(name, hexcol, rough=0.85, sheen=0.6, weave=260.0, var=0.06):
    c = srgb(hexcol)
    m, b = new_mat(name, c)
    co = b.coord()
    w1 = b.n('ShaderNodeTexWave', wave_type='BANDS', bands_direction='X')
    w1.inputs['Scale'].default_value = weave
    w2 = b.n('ShaderNodeTexWave', wave_type='BANDS', bands_direction='Y')
    w2.inputs['Scale'].default_value = weave
    b.l(co, w1.inputs['Vector'])
    b.l(co, w2.inputs['Vector'])
    mx = b.n('ShaderNodeMath', operation='MULTIPLY')
    b.l(w1.outputs['Fac'], mx.inputs[0])
    b.l(w2.outputs['Fac'], mx.inputs[1])
    nz = b.noise(co, scale=6.0, detail=5)
    col = b.mix(var, c, nz.outputs['Color'], blend='OVERLAY')
    nrm = b.bump(mx.outputs[0], strength=0.12, dist=0.001)
    nrm = b.bump(nz.outputs['Fac'], strength=0.08, dist=0.01, normal=nrm)
    b.output(b.principled(col, rough=rough, normal=nrm, Sheen_Weight=sheen,
                          Sheen_Roughness=0.4))
    return m


def mat_simple(name, hexcol, rough=0.5, metal=0.0, **kw):
    c = srgb(hexcol)
    m, b = new_mat(name, c)
    b.output(b.principled(c, rough=rough, Metallic=metal, **kw))
    return m


def mat_glass(name, tint='#F4F8F6', refl=0.08):
    c = srgb(tint)
    m, b = new_mat(name, c, alpha=0.15)
    tr = b.n('ShaderNodeBsdfTransparent', Color=c)
    gl = b.n('ShaderNodeBsdfGlossy', Roughness=0.02)
    lw = b.n('ShaderNodeLayerWeight', Blend=0.12)
    mixs = b.n('ShaderNodeMixShader')
    fac = b.n('ShaderNodeMath', operation='MULTIPLY_ADD')
    b.l(lw.outputs['Fresnel'], fac.inputs[0])
    fac.inputs[1].default_value = 0.8
    fac.inputs[2].default_value = refl * 0.2
    b.l(fac.outputs[0], mixs.inputs[0])
    b.l(tr.outputs[0], mixs.inputs[1])
    b.l(gl.outputs[0], mixs.inputs[2])
    b.output(mixs)
    return m


def mat_translucent(name, hexcol, emit_hex=None):
    """Paper/linen panels (shoji, lanterns). Emission strength set at render time."""
    c = srgb(hexcol)
    m, b = new_mat(name, c, alpha=0.85)
    co = b.coord()
    nz = b.noise(b.mapping(co, scale=(1, 1, 8)), scale=40.0, detail=6)
    col = b.mix(0.10, c, nz.outputs['Color'], blend='OVERLAY')
    tl = b.n('ShaderNodeBsdfTranslucent')
    b.l(col, tl.inputs['Color'])
    df = b.principled(col, rough=0.9)
    mixs = b.n('ShaderNodeMixShader')
    mixs.inputs[0].default_value = 0.55
    b.l(df.outputs[0], mixs.inputs[1])
    b.l(tl.outputs[0], mixs.inputs[2])
    em = b.n('ShaderNodeEmission', Strength=0.0)
    em.name = 'LANTERN_EMISSION'
    em.inputs['Color'].default_value = srgb(emit_hex or '#FFB86B')
    add = b.n('ShaderNodeAddShader')
    b.l(mixs.outputs[0], add.inputs[0])
    b.l(em.outputs[0], add.inputs[1])
    b.output(add)
    return m


def mat_net(name):
    img = bpy.data.images.load(os.path.join(HERE, 'net_tile.png'))
    img.pack()
    m, b = new_mat(name, srgb('#E9DDC6'), alpha=0.3)
    uv = b.coord('UV')
    t = b.n('ShaderNodeTexImage', interpolation='Cubic')
    t.image = img
    b.l(uv, t.inputs['Vector'])
    p = b.principled((0, 0, 0, 1), rough=0.85, Sheen_Weight=0.4)
    b.l(t.outputs['Color'], p.inputs['Base Color'])
    b.l(t.outputs['Alpha'], p.inputs['Alpha'])
    b.output(p)
    m.surface_render_method = 'DITHERED'
    return m


def mat_grass(name):
    m, b = new_mat(name, srgb('#6E7B3E'))
    co = b.coord()
    n1 = b.noise(co, scale=0.25, detail=6)
    n2 = b.noise(co, scale=6.0, detail=8)
    col = b.ramp(n1.outputs['Fac'], [(0.35, srgb('#55662E')), (0.55, srgb('#7B8440')),
                                      (0.7, srgb('#8E8A4E'))])
    col = b.mix(0.35, col, n2.outputs['Color'], blend='OVERLAY')
    nrm = b.bump(n2.outputs['Fac'], strength=0.6, dist=0.02)
    b.output(b.principled(col, rough=0.95, normal=nrm))
    return m


def mat_sedum(name):
    m, b = new_mat(name, srgb('#7C7F45'))
    co = b.coord()
    n1 = b.noise(co, scale=3.0, detail=6)
    n2 = b.noise(co, scale=25.0, detail=8)
    col = b.ramp(n1.outputs['Fac'], [(0.3, srgb('#6B7A3A')), (0.5, srgb('#8C8A48')),
                                      (0.7, srgb('#9B6448'))])
    col = b.mix(0.3, col, n2.outputs['Color'], blend='OVERLAY')
    nrm = b.bump(n2.outputs['Fac'], strength=0.9, dist=0.03)
    b.output(b.principled(col, rough=0.95, normal=nrm))
    return m


def mat_gravel(name):
    m, b = new_mat(name, srgb('#B8AC98'))
    co = b.coord()
    v = b.n('ShaderNodeTexVoronoi')
    v.inputs['Scale'].default_value = 60.0
    b.l(co, v.inputs['Vector'])
    col = b.ramp(v.outputs['Distance'], [(0.0, srgb('#C9BEAB')), (0.6, srgb('#9E927F'))])
    nrm = b.bump(v.outputs['Distance'], strength=0.6, dist=0.01)
    b.output(b.principled(col, rough=0.95, normal=nrm))
    return m


def mat_figure(name):
    m, b = new_mat(name, srgb('#C9A68A'))
    oi = b.n('ShaderNodeObjectInfo')
    col = b.ramp(oi.outputs['Random'], [(0.0, srgb('#D8B89C')), (0.5, srgb('#B98E6E')),
                                         (1.0, srgb('#8C6248'))])
    p = b.principled(col, rough=0.55, Subsurface_Weight=0.25, Subsurface_Scale=0.03,
                     Sheen_Weight=0.15)
    b.output(p)
    return m


def mat_leaves(name):
    m, b = new_mat(name, srgb('#4E6130'))
    co = b.coord()
    v = b.n('ShaderNodeTexVoronoi')
    v.inputs['Scale'].default_value = 14.0
    b.l(co, v.inputs['Vector'])
    n1 = b.noise(co, scale=0.8, detail=3)
    col = b.ramp(n1.outputs['Fac'], [(0.3, srgb('#3F5226')), (0.7, srgb('#6E7E3A'))])
    col = b.mix(0.4, col, v.outputs['Color'], blend='OVERLAY')
    nrm = b.bump(v.outputs['Distance'], strength=1.0, dist=0.05)
    p = b.principled(col, rough=0.7, normal=nrm, Subsurface_Weight=0.2,
                     Subsurface_Scale=0.05)
    b.output(p)
    return m


M_CLAY_HALL = mat_clay('clay_hall', '#B98A62', '#C79B72')
M_CLAY_ROOM = mat_clay('clay_room', '#CDA67F', '#D8B892', scale=1.6)
M_RENDER = mat_clay('lime_render_ext', '#B98F68', '#C49A72', scale=0.6)
M_PLINTH = mat_clay('plinth_stone', '#6F665C', '#80776B', scale=3.0)
M_FLOOR_HALL = mat_boards('floor_hall_oak', '#A8774A', '#B98755', '#4A3321', board_w=0.18,
                          board_l=2.6)
M_FLOOR_WALK = mat_boards('floor_walkway_oak', '#A8774A', '#B98755', '#4A3321',
                          board_w=0.14, board_l=1.8, polar=True)
M_FLOOR_ROOM = mat_boards('floor_room_oak', '#B0804F', '#C08F5C', '#4A3321', board_w=0.16,
                          board_l=2.0)
M_CEIL = mat_boards('ceiling_spruce', '#D2AE80', '#DDBA8C', '#6B5238', board_w=0.12,
                    board_l=4.0, rough=0.6)
M_WOOD = mat_wood('glulam_larch', '#B7874F', '#CFA06A')
M_WOOD_R = mat_wood('glulam_larch_radial', '#B7874F', '#CFA06A', grain_axis='R')
M_WOOD_DARK = mat_wood('wood_dark_walnut', '#6A4A30', '#7E5A3B', grain_axis='R')
M_BATTEN = mat_wood('larch_battens_ext', '#9C7A58', '#B08D69', grain_axis='Z', rough=0.8)
M_LINEN = mat_fabric('linen_natural', '#CBB89B')
M_ROPE = mat_fabric('rope_natural', '#E6D9BF', weave=900.0, sheen=0.3)
M_NET = mat_net('net_mesh')
M_SHOJI = mat_translucent('shoji_linen', '#F0E2C6')
M_LANTERN = mat_translucent('paper_lantern', '#F4E6CC')
M_GLASS = mat_glass('glass')
M_STEEL = mat_simple('steel_bronze', '#4B4036', rough=0.4, metal=0.8)
M_SEDUM = mat_sedum('green_roof_sedum')
M_GRASS = mat_grass('meadow')
M_GRAVEL = mat_gravel('gravel')
M_FIGURE = mat_figure('figure_sculptural')
M_LEAVES = mat_leaves('tree_leaves')
M_BARK = mat_simple('bark', '#5A4A3C', rough=0.9)
M_WOOL = {k: mat_fabric('wool_' + k, v, rough=0.95, sheen=0.8, weave=120.0, var=0.12)
          for k, v in dict(terracotta='#A9573B', ochre='#C08A3E', sand='#D6C09B',
                           olive='#77744A', rose='#B7837A', wine='#7E3A30',
                           cream='#EAE0CC', umber='#7A5A40').items()}
M_MATTRESS = mat_fabric('mattress_cotton', '#E9DECB', weave=180.0)
M_CURTAIN = mat_fabric('curtain_linen', '#E6D6BC', weave=300.0)
M_CURTAIN['vp_alpha'] = 1.0
M_CANDLE = mat_simple('candle_wax', '#F1E4CE', rough=0.4, Subsurface_Weight=0.6,
                      Subsurface_Scale=0.02)

# ---------------------------------------------------------------------------
# 1. site
# ---------------------------------------------------------------------------
bm = bmesh.new()
bmesh.ops.create_circle(bm, cap_ends=True, segments=96, radius=120.0)
for v in bm.verts:
    v.co.z = -0.05
ground = mk_obj('site_meadow', bm, M_GRASS, 'site')

bm = bmesh.new()
sector(bm, P.R_OUT, P.R_OUT + 0.6, 0, 360, -0.05, -0.02, step=3)
mk_obj('site_gravel_drip_strip', bm, M_GRAVEL, 'site')

# path to the annex entrance (east end of annex), curving in from the east
bm = bmesh.new()
left, right = [], []
for i in range(60):
    t = i / 59
    a = P.ANNEX_A0 - 4 - 40 * t
    r_ = (P.R_OUT + P.ANNEX_R_OUT) / 2 + 3.0 + 22 * t ** 1.5
    c = pol(r_, a, -0.03)
    left.append(bm.verts.new(pol(r_ - 0.9, a, -0.03)))
    right.append(bm.verts.new(pol(r_ + 0.9, a, -0.03)))
for i in range(59):
    bm.faces.new((left[i], right[i], right[i + 1], left[i + 1]))
ob = mk_obj('site_path', bm, M_GRAVEL, 'site', recalc=False)
for p in ob.data.polygons:
    if p.normal.z < 0:
        p.flip()

# entrance forecourt
bm = bmesh.new()
sector(bm, P.R_OUT + 0.6, P.ANNEX_R_OUT + 3.5, P.ANNEX_A0 - 14, P.ANNEX_A0 + 1, -0.05, -0.02)
mk_obj('site_forecourt', bm, M_GRAVEL, 'site')


def tree(name, x, y, h, crown_r, seed):
    r = random.Random(seed)
    bm = bmesh.new()
    cyl(bm, (x, y, h * 0.3), 0.18 * h / 10, h * 0.6, segs=10, r2=0.10 * h / 10)
    mk_obj(name + '_trunk', bm, M_BARK, 'site')
    bm = bmesh.new()
    for i in range(7):
        c = Vector((x + r.uniform(-0.5, 0.5) * crown_r, y + r.uniform(-0.5, 0.5) * crown_r,
                    h * 0.62 + r.uniform(-0.25, 0.3) * crown_r))
        s = crown_r * r.uniform(0.5, 0.75)
        res = bmesh.ops.create_icosphere(bm, subdivisions=3, radius=s,
                                         matrix=Matrix.Translation(c))
        for v in res['verts']:
            d = v.co - c
            v.co = c + d * (1 + 0.18 * math.sin(7 * d.x + seed) * math.cos(5 * d.y) +
                            r.uniform(-0.08, 0.08))
    ob = mk_obj(name + '_crown', bm, M_LEAVES, 'site', smooth=True)
    return ob


for i in range(22):
    a = rnd.uniform(0, 360)
    if -25 < ((a + 180) % 360) - 180 < 40:      # keep the east view corridor open-ish
        a += 70
    d = rnd.uniform(28, 55)
    h = rnd.uniform(9, 16)
    tree('tree_%02d' % i, d * math.cos(rad(a)), d * math.sin(rad(a)), h, h * 0.42, i)

# ---------------------------------------------------------------------------
# 2. hall floor, outer wall, openings
# ---------------------------------------------------------------------------
bm = bmesh.new()
cyl(bm, (0, 0, -0.10), P.R_IN + 0.02, 0.2, segs=180)
mk_obj('hall_floor', bm, M_FLOOR_HALL, 'structure')

bm = bmesh.new()
sector(bm, P.R_OUT - 0.02, P.R_OUT + 0.08, 0, 360, -0.05, 0.35, step=2)
mk_obj('plinth', bm, M_PLINTH, 'structure')

WALL_TOP = P.CEIL_UF
openings = []   # dict(a, w, z0, z1, kind)
for k in range(P.N_SLOTS):
    a = P.slot_center(k)
    if k == P.STAIR_SLOT:
        openings.append(dict(a=a, w=0.9, z0=2.30, z1=5.70, kind='window'))
        continue
    if k == P.ENTRY_SLOT:
        openings.append(dict(a=a, w=P.ENTRY_DOOR['w'], z0=0.0, z1=P.ENTRY_DOOR['h'],
                             kind='door_entry'))
    elif k == P.GARDEN_SLOT:
        openings.append(dict(a=a, w=P.GARDEN_DOOR['w'], z0=0.0, z1=P.GARDEN_DOOR['h'],
                             kind='door_garden'))
    else:
        openings.append(dict(a=a, w=P.GF_CLERESTORY['w'], z0=P.GF_CLERESTORY['sill'],
                             z1=P.GF_CLERESTORY['head'], kind='window'))
    openings.append(dict(a=a, w=P.UF_WINDOW['w'], z0=P.FFL_UF + P.UF_WINDOW['sill'],
                         z1=P.FFL_UF + P.UF_WINDOW['head'], kind='window'))
rmid = (P.R_IN + P.R_OUT) / 2
for o in openings:
    da = math.degrees(o['w'] / 2 / rmid)
    o['a0'], o['a1'] = o['a'] - da, o['a'] + da

cuts = sorted({0.0, 360.0} | {o['a0'] % 360 for o in openings} | {o['a1'] % 360 for o in openings})
bm = bmesh.new()
for a0, a1 in zip(cuts[:-1], cuts[1:]):
    if a1 - a0 < 1e-6:
        continue
    am = (a0 + a1) / 2
    holes = sorted([(o['z0'], o['z1']) for o in openings
                    if (am - o['a0']) % 360 < (o['a1'] - o['a0'])])
    z = 0.0
    for h0, h1 in holes + [(WALL_TOP, WALL_TOP)]:
        if h0 > z + 1e-6:
            sector(bm, P.R_IN, P.R_OUT, a0, a1, z, h0, step=2)
        z = max(z, h1)
wall = mk_obj('outer_wall', bm, [M_CLAY_HALL, M_CLAY_ROOM, M_RENDER, M_BATTEN], 'structure')


def wall_mat(c, n):
    rr = math.hypot(c.x, c.y)
    radial = Vector((c.x, c.y, 0)).normalized()
    if rr > P.R_OUT - 0.01 and n.dot(radial) > 0.5:
        return 2 if c.z < P.FFL_UF - 0.05 else 3
    return 0 if c.z < P.FFL_UF - 0.1 else 1


set_face_mats(wall, wall_mat)


def opening_fill(o):
    rf = P.R_IN + 0.14
    p0, p1 = pol(rf, o['a0']), pol(rf, o['a1'])
    ang = o['a']
    bm = bmesh.new()
    fw = 0.07
    tang = (p1 - p0).normalized()
    w = (p1 - p0).length
    c = (p0 + p1) / 2
    # frame
    for zc, hz in ((o['z0'] + fw / 2, fw), (o['z1'] - fw / 2, fw)):
        cube(bm, (c.x, c.y, zc), (w, 0.12, hz), rz=ang + 90)
    for p in (p0 + tang * fw / 2, p1 - tang * fw / 2):
        cube(bm, (p.x, p.y, (o['z0'] + o['z1']) / 2), (fw, 0.12, o['z1'] - o['z0']), rz=ang + 90)
    if o['kind'] == 'door_entry':
        # two solid oak leaves with a narrow vertical glass strip
        cube(bm, (c.x, c.y, o['z1'] / 2), (w - 2 * fw, 0.06, o['z1'] - fw), rz=ang + 90)
        mk_obj('door_entry', bm, M_WOOD_DARK, 'openings')
        return
    if o['kind'] == 'door_garden':
        cube(bm, (c.x, c.y, (o['z0'] + o['z1']) / 2), (0.06, 0.12, o['z1'] - o['z0']), rz=ang + 90)
    if o['z0'] < P.FFL_UF < o['z1']:
        cube(bm, (c.x, c.y, P.FFL_UF), (w, 0.12, 0.10), rz=ang + 90)
    mk_obj('frame_%03d_%d' % (int(o['a']), int(o['z0'] * 10)), bm, M_WOOD, 'openings')
    bm = bmesh.new()
    q0 = p0 + tang * fw
    q1 = p1 - tang * fw
    vs = [bm.verts.new((q0.x, q0.y, o['z0'] + fw)), bm.verts.new((q1.x, q1.y, o['z0'] + fw)),
          bm.verts.new((q1.x, q1.y, o['z1'] - fw)), bm.verts.new((q0.x, q0.y, o['z1'] - fw))]
    bm.faces.new(vs)
    mk_obj('glass_%03d_%d' % (int(o['a']), int(o['z0'] * 10)), bm, M_GLASS, 'openings',
           recalc=False)


for o in openings:
    opening_fill(o)

# garden-door curtain (inside, drawn to one side)
bm = bmesh.new()
ca = P.slot_center(P.GARDEN_SLOT)
rc = P.R_IN - 0.18
pts = []
for i in range(40):
    t = i / 39
    a = ca - 10 + 7 * t
    rr = rc - 0.05 * math.sin(t * math.pi * 11)
    pts.append((rr, a))
for i in range(len(pts) - 1):
    (r0, a0), (r1, a1) = pts[i], pts[i + 1]
    v = [bm.verts.new(pol(r0, a0, 0.02)), bm.verts.new(pol(r1, a1, 0.02)),
         bm.verts.new(pol(r1, a1, 2.65)), bm.verts.new(pol(r0, a0, 2.65))]
    bm.faces.new(v)
mk_obj('curtain_garden', bm, M_CURTAIN, 'furnishing', smooth=True, recalc=False)

# exterior larch battens on the upper floor (privacy screen, also in front of windows)
bm = bmesh.new()
n_b = int(2 * math.pi * (P.R_OUT + 0.05) / 0.11)
for i in range(n_b):
    a = 360 * i / n_b
    p = pol(P.R_OUT + 0.055, a)
    cube(bm, (p.x, p.y, (P.FFL_UF - 0.25 + WALL_TOP + 0.3) / 2), (0.05, 0.045, WALL_TOP + 0.3 - P.FFL_UF + 0.25), rz=a)
mk_obj('facade_battens', bm, M_BATTEN, 'structure')
bm = bmesh.new()
sector(bm, P.R_OUT, P.R_OUT + 0.10, 0, 360, P.FFL_UF - 0.40, P.FFL_UF - 0.25, step=2)
mk_obj('facade_batten_rail', bm, M_BATTEN, 'structure')

# ---------------------------------------------------------------------------
# 3. structure: tree pillars, ring beam, radial beams, upper slab
# ---------------------------------------------------------------------------
def tree_pillar(k):
    a = P.partition_angle(k)
    r = random.Random(100 + k)
    mb = bpy.data.metaballs.new('pillar_mb_%d' % k)
    mb.resolution = 0.035
    mb.render_resolution = 0.035
    mb.threshold = 0.6
    ob = bpy.data.objects.new('pillar_mb_%d' % k, mb)
    coll('tmp').objects.link(ob)
    base = pol(P.R_PILLAR, a)
    radial = pol(1, a)
    tang = pol(1, a + 90)
    top_z = P.RING_BEAM_BOT + 0.10
    fork_z = 2.35 + r.uniform(-0.1, 0.1)
    sway = tang * r.uniform(-0.04, 0.04)

    def capsule(p0, p1, rad_):
        e = mb.elements.new(type='CAPSULE')
        d = p1 - p0
        e.co = (p0 + p1) / 2
        e.size_x = d.length / 2
        e.rotation = Vector((1, 0, 0)).rotation_difference(d.normalized())
        e.radius = rad_ / 0.575
        e.stiffness = 2.0

    pts = [base + Vector((0, 0, -0.1)), base + Vector((0, 0, 0.5)) + sway * 0.3,
           base + Vector((0, 0, 1.4)) + sway, base + Vector((0, 0, fork_z)) + sway * 0.5]
    radii = [0.215, 0.18, 0.17, 0.165]
    for i in range(3):
        n = 4
        for j in range(n):
            t0, t1 = j / n, (j + 1) / n
            rr = radii[i] * (1 - t0) + radii[i + 1] * t0
            capsule(pts[i].lerp(pts[i + 1], t0), pts[i].lerp(pts[i + 1], t1), rr)
    fork = pts[-1]
    ends = [base + tang * 0.62 + radial * 0.02, base - tang * 0.62 + radial * 0.02,
            base + radial * 0.55, base - radial * 0.02 + tang * 0.05]
    for i, e in enumerate(ends):
        e = e.copy()
        e.z = top_z
        mid = fork.lerp(e, 0.45) + Vector((0, 0, 0.12))
        rr0 = 0.12 if i < 3 else 0.10
        capsule(fork, mid, rr0)
        capsule(mid, e, rr0 * 0.8)
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    bpy.data.objects.remove(ob)
    me.name = 'pillar_%d' % k
    me.materials.append(M_WOOD)
    for p in me.polygons:
        p.use_smooth = True
    po = bpy.data.objects.new('pillar_%d' % k, me)
    coll('structure').objects.link(po)


for k in range(P.N_PILLARS):
    tree_pillar(k)

bm = bmesh.new()
sector(bm, P.RING_BEAM_IN, P.RING_BEAM_OUT, 0, 360, P.RING_BEAM_BOT, P.RING_BEAM_TOP, step=1.5)
mk_obj('ring_beam', bm, M_WOOD, 'structure')

bm = bmesh.new()
for i in range(P.N_BEAMS):
    a = i * 360 / P.N_BEAMS
    seg_box(bm, pol(P.RING_BEAM_OUT - 0.02, a), pol(P.R_IN + 0.05, a), P.BEAM_W,
            P.CEIL_GF - P.BEAM_D, P.CEIL_GF + 0.01)
mk_obj('radial_beams', bm, M_WOOD, 'structure')

s_a0 = P.partition_angle(P.STAIR_SLOT)
s_a1 = P.partition_angle(P.STAIR_SLOT + 1)
bm = bmesh.new()
sector(bm, P.RING_BEAM_OUT, P.R_IN + 0.02, s_a1, s_a0 + 360, P.CEIL_GF, P.FFL_UF - 0.01, step=1.5)
sector(bm, P.RING_BEAM_OUT, P.APOTHEM_FRONT, s_a0, s_a1, P.CEIL_GF, P.FFL_UF - 0.01, step=1.5)
sector(bm, P.R_PAD_OUT - 0.02, P.RING_BEAM_OUT, 0, 360, P.RING_BEAM_TOP, P.FFL_UF - 0.01, step=1.5)
slab = mk_obj('upper_slab', bm, [M_CEIL, M_WOOD], 'structure')
set_face_mats(slab, lambda c, n: 0 if n.z < -0.5 else 1)

# walkway floor finish (circle inside, decagon outside)
bm = bmesh.new()
N = 360
inner, outer = [], []
for i in range(N):
    a = i * 360 / N
    inner.append(bm.verts.new(pol(P.R_PAD_OUT, a, P.FFL_UF)))
    outer.append(bm.verts.new(pol(front_r(a) + 0.02, a, P.FFL_UF)))
for i in range(N):
    j = (i + 1) % N
    bm.faces.new((inner[i], outer[i], outer[j], inner[j]))
for v in bm.verts:
    v.co.z = P.FFL_UF
walk = mk_obj('walkway_floor', bm, M_FLOOR_WALK, 'structure', recalc=False)
for p in walk.data.polygons:
    if p.normal.z < 0:
        p.flip()

# ---------------------------------------------------------------------------
# 4. the net, padded edge
# ---------------------------------------------------------------------------
NET_DENTS = []   # (x, y, depth, sigma) local dips where people lie


def dent(x, y):
    d = 0.0
    for (cx, cy, dd, sg) in NET_DENTS:
        d += dd * math.exp(-((x - cx) ** 2 + (y - cy) ** 2) / (sg * sg))
    # fade out towards the anchored edge
    return d * max(0.0, 1 - (math.hypot(x, y) / P.RING_BEAM_IN) ** 4)


def build_net(name, zf, collection):
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new('UVMap')
    NR, NA = 60, 216
    rings = []
    center = bm.verts.new((0, 0, zf(0) - dent(0, 0)))
    for i in range(1, NR + 1):
        rr = P.RING_BEAM_IN * i / NR
        ring = []
        for j in range(NA):
            p = pol(rr, 360 * j / NA)
            p.z = zf(rr) - dent(p.x, p.y)
            ring.append(bm.verts.new(p))
        rings.append(ring)
    faces = []
    for j in range(NA):
        faces.append(bm.faces.new((center, rings[0][j], rings[0][(j + 1) % NA])))
    for i in range(NR - 1):
        for j in range(NA):
            faces.append(bm.faces.new((rings[i][j], rings[i + 1][j], rings[i + 1][(j + 1) % NA],
                                       rings[i][(j + 1) % NA])))
    s = 0.7071 / P.NET_MESH
    for f in bm.faces:
        for lp in f.loops:
            lp[uvl].uv = (lp.vert.co.x * s, lp.vert.co.y * s)
    ob = mk_obj(name, bm, M_NET, collection, smooth=True, recalc=False)
    for p in ob.data.polygons:
        if p.normal.z < 0:
            p.flip()
    return ob


def build_ropes(name, zf, collection, with_center_ring=True):
    cu = bpy.data.curves.new(name, 'CURVE')
    cu.dimensions = '3D'
    cu.bevel_depth = 0.012
    cu.bevel_resolution = 2
    r0 = P.NET_RING_RADII[0]
    for j in range(P.N_NET_RADIAL):
        a = 360 * j / P.N_NET_RADIAL + 360 / P.N_NET_RADIAL / 2
        sp = cu.splines.new('POLY')
        n = 30
        sp.points.add(n - 1)
        for i in range(n):
            rr = r0 + (P.RING_BEAM_IN - 0.02 - r0) * i / (n - 1)
            p = pol(rr, a, zf(rr) + 0.012)
            p.z -= dent(p.x, p.y)
            sp.points[i].co = (p.x, p.y, p.z, 1)
    for rr in list(P.NET_RING_RADII) + [P.RING_BEAM_IN - 0.06]:
        sp = cu.splines.new('POLY')
        n = 96
        sp.points.add(n - 1)
        for i in range(n):
            p = pol(rr, 360 * i / n, zf(rr) + 0.012)
            p.z -= dent(p.x, p.y)
            sp.points[i].co = (p.x, p.y, p.z, 1)
        sp.use_cyclic_u = True
    ob = bpy.data.objects.new(name, cu)
    cu.materials.append(M_ROPE)
    coll(collection).objects.link(ob)
    return ob


NET_DENTS.extend([(-0.6, 0.4, 0.16, 0.9), (0.9, -0.2, 0.14, 0.8), (-2.1, -1.8, 0.12, 0.6)])
build_net('net', P.net_z, 'net')
build_ropes('net_ropes', P.net_z, 'net')


def net_z_variant(rr):
    # centre held up by a single rope from the dome crown ring
    rr = min(rr, P.RING_BEAM_IN)
    return P.Z_NET_EDGE - 0.05 - 0.14 * math.sin(math.pi * rr / P.RING_BEAM_IN)


build_net('net_variant_central_rope', net_z_variant, 'variant_central_rope')
build_ropes('net_ropes_variant', net_z_variant, 'variant_central_rope')

# turnbuckle tensioners at the ring beam (under the removable pad)
bm = bmesh.new()
for j in range(P.N_NET_RADIAL):
    a = 360 * j / P.N_NET_RADIAL + 360 / P.N_NET_RADIAL / 2
    p = pol(P.RING_BEAM_IN - 0.10, a, P.Z_NET_EDGE + 0.01)
    rot = Matrix.Rotation(rad(a), 4, 'Z') @ Matrix.Rotation(rad(90), 4, 'Y')
    cyl(bm, p, 0.018, 0.22, segs=10, rot=rot)
mk_obj('net_tensioners', bm, M_STEEL, 'net')

# padded edge: 48 upholstered segments on the ring beam
bm = bmesh.new()
NSEG = 48
for i in range(NSEG):
    a0 = 360 * i / NSEG + 0.25
    a1 = 360 * (i + 1) / NSEG - 0.25
    sector(bm, P.R_NET, P.R_PAD_OUT, a0, a1, P.RING_BEAM_TOP, P.RING_BEAM_TOP + P.PAD_T, step=1.0)
pad = mk_obj('padded_edge', bm, M_LINEN, 'net')
bv = pad.modifiers.new('bevel', 'BEVEL')
bv.width = 0.045
bv.segments = 4
bv.limit_method = 'ANGLE'
pad.modifiers.new('sub', 'SUBSURF').levels = 1
for p in pad.data.polygons:
    p.use_smooth = True
# pad support board (hidden edge beam carrying the pad over the net edge)
bm = bmesh.new()
sector(bm, P.R_NET + 0.02, P.RING_BEAM_IN, 0, 360, P.RING_BEAM_TOP - 0.03, P.RING_BEAM_TOP, step=2)
mk_obj('pad_support_board', bm, M_WOOD, 'net')

# ---------------------------------------------------------------------------
# 5. upper floor: partitions, room fronts with sliding doors, fascia
# ---------------------------------------------------------------------------
RC = P.front_corner_radius()
bm = bmesh.new()
for k in range(P.N_SLOTS):
    a = P.partition_angle(k)
    z0 = P.FFL_UF
    if k in (P.STAIR_SLOT, P.STAIR_SLOT + 1):
        z0 = 0.0
    seg_box(bm, pol(RC - 0.02, a), pol(P.R_IN + 0.05, a), P.PART_T, z0, P.CEIL_UF)
mk_obj('partitions', bm, M_CLAY_ROOM, 'structure')

bm = bmesh.new()
for k in range(P.N_SLOTS):
    a = P.partition_angle(k)
    p = pol(RC - 0.02, a)
    cube(bm, (p.x, p.y, (P.FFL_UF + P.CEIL_UF) / 2), (P.POST, P.POST, P.CEIL_UF - P.FFL_UF), rz=a)
mk_obj('front_posts', bm, M_WOOD, 'structure')

# fascia band between room ceilings and dome ring (decagon)
bm = bmesh.new()
for k in range(P.N_SLOTS):
    a0, a1 = P.partition_angle(k), P.partition_angle(k + 1)
    seg_box(bm, pol(RC + 0.02, a0) + pol(0.05, a0 - 90), pol(RC + 0.02, a1) + pol(0.05, a1 + 90),
            0.20, P.CEIL_UF, P.ROOF_Z_IN)
fas = mk_obj('fascia_ring', bm, M_CLAY_ROOM, 'structure')

roomfronts = {}
DOOR_STATES = {2: 'open', 3: 'half', 4: 'closed', 5: 'open', 6: 'closed', 7: 'half',
               8: 'closed', 9: 'open', 0: 'half'}


def room_front(k, state):
    """Facet k in local frame: facet along local Y at x = apothem."""
    half = P.APOTHEM_FRONT * math.tan(rad(P.SLOT_DEG / 2)) - P.POST / 2 - 0.01
    L = 2 * half
    x = P.APOTHEM_FRONT + P.FRONT_T / 2
    zf, zh = P.FFL_UF, P.FFL_UF + P.DOOR_H
    parent = bpy.data.objects.new('room_front_%d' % k, None)
    coll('rooms').objects.link(parent)
    parent.matrix_world = Matrix.Rotation(rad(P.slot_center(k)), 4, 'Z')

    def put(name, bm, mat, **kw):
        ob = mk_obj(name, bm, mat, 'rooms', **kw)
        ob.parent = parent
        return ob

    bm = bmesh.new()
    cube(bm, (x, 0, zh + 0.06), (0.16, L, 0.12))              # header / track
    cube(bm, (x, 0, zf + 0.008), (0.16, L, 0.016))              # floor track
    cube(bm, (x, 0, P.CEIL_UF - 0.03), (0.12, L, 0.06))
    for yy in (-L / 6 * 3 + 0.03, L / 6 * 3 - 0.03):
        cube(bm, (x, yy, (zh + P.CEIL_UF) / 2), (0.06, 0.06, P.CEIL_UF - zh))
    put('front_frame_%d' % k, bm, M_WOOD)
    # transom (fixed translucent band above the doors)
    bm = bmesh.new()
    cube(bm, (x, 0, (zh + 0.12 + P.CEIL_UF - 0.06) / 2), (0.012, L, P.CEIL_UF - 0.06 - zh - 0.12))
    put('front_transom_%d' % k, bm, M_SHOJI)
    # three shoji panels: A fixed (y-), B and C sliding
    pw = L / 3 + 0.03
    pos = {'closed': (0, 1), 'half': (-1, 0), 'open': (-1, -1)}[state]
    panels = [(-1, 0.0), (pos[0], -0.045), (pos[1], -0.09)]
    for i, (slot, off) in enumerate(panels):
        yc = slot * L / 3 + (0.0 if slot == 0 else (0.012 * -slot))
        xc = x + off + 0.045
        bm = bmesh.new()
        fr = 0.045
        cube(bm, (xc, yc - pw / 2 + fr / 2, zf + P.DOOR_H / 2), (0.035, fr, P.DOOR_H - 0.02))
        cube(bm, (xc, yc + pw / 2 - fr / 2, zf + P.DOOR_H / 2), (0.035, fr, P.DOOR_H - 0.02))
        for zz in (zf + 0.06, zf + P.DOOR_H - 0.04, zf + 0.95, zf + 1.6):
            cube(bm, (xc, yc, zz), (0.035, pw - 2 * fr, 0.03 if 0.1 < zz - zf < 2.1 else 0.07))
        cube(bm, (xc, yc, zf + 1.275), (0.03, 0.022, 0.65))    # small kumiko mullion
        put('shoji_frame_%d_%d' % (k, i), bm, M_WOOD)
        bm = bmesh.new()
        cube(bm, (xc, yc, zf + P.DOOR_H / 2), (0.006, pw - 2 * fr + 0.01, P.DOOR_H - 0.1))
        put('shoji_panel_%d_%d' % (k, i), bm, M_SHOJI)
        # recessed finger pull
    return parent


# ---------------------------------------------------------------------------
# 6. rooms: floors, ceiling boards, furnishing, lanterns
# ---------------------------------------------------------------------------
PALETTES = [('terracotta', 'sand', 'ochre'), ('olive', 'cream', 'rose'), ('wine', 'sand', 'umber'),
            ('ochre', 'cream', 'terracotta'), ('rose', 'sand', 'olive'),
            ('umber', 'cream', 'wine'), ('sand', 'terracotta', 'olive'),
            ('cream', 'rose', 'ochre'), ('olive', 'sand', 'wine')]


def rounded(ob, w=0.04, seg=3, sub=1):
    bv = ob.modifiers.new('bevel', 'BEVEL')
    bv.width = w
    bv.segments = seg
    if sub:
        ob.modifiers.new('sub', 'SUBSURF').levels = sub
    for p in ob.data.polygons:
        p.use_smooth = True
    return ob


def cushion(name, parent, center, size, mat, rz=0.0, rx=0.0, squish=0.35, coll_name='furnishing'):
    bm = bmesh.new()
    res = bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=4, use_grid_fill=True)
    for v in bm.verts:
        x, y, z = v.co
        # pillow shape: thinner towards the edges
        f = (1 - (2 * x) ** 2 * squish) * (1 - (2 * y) ** 2 * squish)
        v.co = Vector((x * size[0], y * size[1], z * size[2] * max(f, 0.15)))
    M = (Matrix.Translation(Vector(center)) @ Matrix.Rotation(rad(rz), 4, 'Z')
         @ Matrix.Rotation(rad(rx), 4, 'X'))
    bmesh.ops.transform(bm, matrix=M, verts=bm.verts[:])
    ob = mk_obj(name, bm, mat, coll_name, smooth=True)
    ob.modifiers.new('sub', 'SUBSURF').levels = 2
    if parent:
        ob.parent = parent
    return ob


def lantern(name, center, r, h, parent=None, coll_name='furnishing', cord=None):
    bm = bmesh.new()
    res = bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=16, radius=r)
    for v in bm.verts:
        v.co.z *= h / (2 * r)
        # ribbed paper lantern
        a = math.atan2(v.co.y, v.co.x)
        v.co.x *= 1 + 0.015 * math.cos(24 * a)
    bmesh.ops.translate(bm, vec=Vector(center), verts=bm.verts[:])
    ob = mk_obj(name, bm, M_LANTERN, coll_name, smooth=True)
    if parent:
        ob.parent = parent
    if cord:
        bm = bmesh.new()
        cyl(bm, (center[0], center[1], (center[2] + h / 2 + cord) / 2), 0.004,
            cord - center[2] - h / 2, segs=6)
        c = mk_obj(name + '_cord', bm, M_STEEL, coll_name)
        if parent:
            c.parent = parent
    li = bpy.data.lights.new(name + '_light', 'POINT')
    li.energy = 0.0
    li.color = (1.0, 0.82, 0.64)
    li.shadow_soft_size = r * 0.8
    lo = bpy.data.objects.new(name + '_light', li)
    lo.location = center
    coll('night_lights').objects.link(lo)
    if parent:
        lo.parent = parent
    lo['lantern_power'] = 80.0 * (r / 0.25) ** 2
    return ob


def room(k):
    a = P.slot_center(k)
    parent = bpy.data.objects.new('room_%d' % k, None)
    coll('rooms').objects.link(parent)
    parent.matrix_world = Matrix.Rotation(rad(a), 4, 'Z')
    ht = math.tan(rad(P.SLOT_DEG / 2))
    x0 = P.APOTHEM_FRONT + P.FRONT_T
    # floor
    bm = bmesh.new()
    pts = []
    for i in range(0, 11):
        t = i / 10
        aa = -P.SLOT_DEG / 2 + P.SLOT_DEG * t
        pts.append(pol(P.R_IN + 0.02, aa, P.FFL_UF))
    vs = [bm.verts.new((x0, -x0 * ht, P.FFL_UF))] + [bm.verts.new(p) for p in pts] + \
         [bm.verts.new((x0, x0 * ht, P.FFL_UF))]
    bm.faces.new(vs)
    ob = mk_obj('room_floor_%d' % k, bm, M_FLOOR_ROOM, 'rooms', recalc=False)
    if ob.data.polygons[0].normal.z < 0:
        ob.data.polygons[0].flip()
    ob.parent = parent
    # ceiling
    bm = bmesh.new()
    vs = [bm.verts.new((x0 - 0.1, -(x0 - 0.1) * ht, P.CEIL_UF))] + \
         [bm.verts.new((p.x, p.y, P.CEIL_UF)) for p in pts] + \
         [bm.verts.new((x0 - 0.1, (x0 - 0.1) * ht, P.CEIL_UF))]
    bm.faces.new(vs)
    ob = mk_obj('room_ceiling_%d' % k, bm, M_CEIL, 'rooms', recalc=False)
    if ob.data.polygons[0].normal.z > 0:
        ob.data.polygons[0].flip()
    ob.parent = parent

    pal = PALETTES[(k * 4) % len(PALETTES)]
    z = P.FFL_UF
    # rug
    bm = bmesh.new()
    cyl(bm, (0, 0, 0), 1.0, 0.012, segs=48)
    bmesh.ops.scale(bm, vec=(1.25, 1.55, 1), verts=bm.verts[:])
    bmesh.ops.translate(bm, vec=Vector((7.0, 0, z + 0.006)), verts=bm.verts[:])
    ob = mk_obj('room_rug_%d' % k, bm, M_WOOL[pal[1]], 'furnishing')
    ob.parent = parent
    # low platform + mattress under the window
    mx = 8.45
    bm = bmesh.new()
    cube(bm, (mx, 0, z + 0.06), (1.75, 2.15, 0.12))
    ob = rounded(mk_obj('room_platform_%d' % k, bm, M_WOOD, 'furnishing'), 0.02, 2, 0)
    ob.parent = parent
    bm = bmesh.new()
    cube(bm, (mx, 0, z + 0.12 + 0.1), (1.65, 2.05, 0.2))
    ob = rounded(mk_obj('room_mattress_%d' % k, bm, M_MATTRESS, 'furnishing'), 0.06, 3, 1)
    ob.parent = parent
    # blanket (thin layer over part of the mattress, hanging over one side)
    bm = bmesh.new()
    cube(bm, (mx - 0.15, 0.35 * (1 if k % 2 else -1), z + 0.34), (1.45, 1.15, 0.035))
    ob = rounded(mk_obj('room_blanket_%d' % k, bm, M_WOOL[pal[0]], 'furnishing'), 0.015, 2, 1)
    ob.parent = parent
    # cushions against the wall
    for i, yy in enumerate((-0.62, 0.0, 0.62)):
        cushion('room_cushion_%d_%d' % (k, i), parent, (9.03 - 0.02 * abs(yy), yy, z + 0.55),
                (0.58, 0.2, 0.5), M_WOOL[pal[i % 3]], rz=0 + yy * 8, rx=0, squish=0.3)
    # floor cushions + low table near the door
    cushion('room_floorcushion_%d_a' % k, parent, (6.55, -0.75, z + 0.08), (0.7, 0.7, 0.16),
            M_WOOL[pal[2]], rz=12)
    cushion('room_floorcushion_%d_b' % k, parent, (6.65, 0.85, z + 0.08), (0.7, 0.7, 0.16),
            M_WOOL[pal[0]], rz=-8)
    bm = bmesh.new()
    cyl(bm, (7.1, 0.05, z + 0.3), 0.32, 0.04, segs=40)
    for dx, dy in ((0.18, 0.18), (-0.18, 0.18), (0.18, -0.18), (-0.18, -0.18)):
        cyl(bm, (7.1 + dx, 0.05 + dy, z + 0.14), 0.025, 0.28, segs=8)
    ob = mk_obj('room_table_%d' % k, bm, M_WOOD_DARK, 'furnishing')
    ob.parent = parent
    bm = bmesh.new()
    cyl(bm, (7.05, 0.1, z + 0.37), 0.035, 0.1, segs=16)
    cyl(bm, (7.18, -0.02, z + 0.35), 0.03, 0.06, segs=16)
    ob = mk_obj('room_candles_%d' % k, bm, M_CANDLE, 'furnishing')
    ob.parent = parent
    # shelf niche on the side wall
    yw = 8.0 * ht - P.PART_T / 2 - 0.12
    bm = bmesh.new()
    cube(bm, (8.0, yw, z + 1.35), (1.0, 0.24, 0.04), rz=-P.SLOT_DEG / 2)
    ob = mk_obj('room_shelf_%d' % k, bm, M_WOOD, 'furnishing')
    ob.parent = parent
    # paper lanterns: pendant + floor lantern
    lantern('room_pendant_%d' % k, (7.6, 0.0, P.CEIL_UF - 0.75), 0.28, 0.42, parent=parent,
            cord=P.CEIL_UF)
    lantern('room_floorlamp_%d' % k, (6.2, -1.5 if k % 2 else 1.5, z + 0.45), 0.2, 0.8,
            parent=parent)
    return parent


for k in range(P.N_SLOTS):
    if k == P.STAIR_SLOT:
        continue
    room_front(k, DOOR_STATES[k])
    room(k)

# ---------------------------------------------------------------------------
# 7. stair (half-turn) in slot STAIR_SLOT
# ---------------------------------------------------------------------------
sa = P.slot_center(P.STAIR_SLOT)
stair = bpy.data.objects.new('stair', None)
coll('structure').objects.link(stair)
stair.matrix_world = Matrix.Rotation(rad(sa), 4, 'Z')
R_, G_ = P.STAIR_RISE, P.STAIR_GOING
W_, gap = P.STAIR_FLIGHT_W, P.STAIR_GAP
u0 = P.STAIR_U0
uL = P.STAIR_LANDING_U
bm = bmesh.new()
bmt = bmesh.new()
for i in range(P.STAIR_TREADS_PER_FLIGHT):
    ua = u0 + i * G_
    ztop = (i + 1) * R_
    cube(bm, (ua + G_ / 2 + 0.02, -(gap / 2 + W_ / 2), ztop / 2 - 0.02), (G_ + 0.04, W_, ztop - 0.04))
    cube(bmt, (ua + G_ / 2, -(gap / 2 + W_ / 2), ztop - 0.02), (G_ + 0.03, W_, 0.04))
zl = (P.STAIR_TREADS_PER_FLIGHT + 1) * R_
land_d = math.sqrt(P.R_IN ** 2 - (gap / 2 + W_) ** 2) - uL
cube(bm, (uL + land_d / 2, 0, (zl - 0.04) / 2), (land_d, 2 * W_ + gap, zl - 0.04))
cube(bmt, (uL + land_d / 2 - 0.02, 0, zl - 0.02), (land_d + 0.04, 2 * W_ + gap, 0.04))
for j in range(P.STAIR_TREADS_PER_FLIGHT):
    ub = uL - (j + 1) * G_
    ztop = zl + (j + 1) * R_
    cube(bm, (ub + G_ / 2, gap / 2 + W_ / 2, ztop - 0.04 - 0.12), (G_ + 0.02, W_, 0.24))
    cube(bmt, (ub + G_ / 2 - 0.015, gap / 2 + W_ / 2, ztop - 0.02), (G_ + 0.03, W_, 0.04))
ob = mk_obj('stair_body', bm, M_CLAY_HALL, 'structure')
ob.parent = stair
ob = mk_obj('stair_treads', bmt, M_WOOD, 'structure')
ob.parent = stair
# spine wall between flights
bm = bmesh.new()
cube(bm, ((u0 + uL) / 2, 0, P.CEIL_UF / 2), (uL - u0 + 0.05, gap, P.CEIL_UF))
ob = mk_obj('stair_spine', bm, M_CLAY_HALL, 'structure')
ob.parent = stair
# ground-floor front: closed half under flight 2 (storage), open half for flight 1
bm = bmesh.new()
cube(bm, (P.APOTHEM_FRONT + 0.1, (gap / 2 + P.APOTHEM_FRONT * math.tan(rad(18))) / 2, P.CEIL_GF / 2),
     (0.14, P.APOTHEM_FRONT * math.tan(rad(18)) - gap / 2, P.CEIL_GF))
cube(bm, (P.APOTHEM_FRONT + 0.1, -(gap / 2 + W_ + P.APOTHEM_FRONT * math.tan(rad(18))) / 2,
          P.CEIL_GF / 2), (0.14, P.APOTHEM_FRONT * math.tan(rad(18)) - gap / 2 - W_, P.CEIL_GF))
ob = mk_obj('stair_gf_front', bm, M_CLAY_HALL, 'structure')
ob.parent = stair
# upper-floor guard beside the top of flight 2 (over the void of flight 1)
bm = bmesh.new()
cube(bm, (P.APOTHEM_FRONT + 0.06, -(gap / 2 + P.APOTHEM_FRONT * math.tan(rad(18))) / 2,
          P.FFL_UF + 0.55), (0.12, P.APOTHEM_FRONT * math.tan(rad(18)) - gap / 2, 1.1))
ob = mk_obj('stair_uf_guard', bm, M_CLAY_ROOM, 'structure')
ob.parent = stair
bm = bmesh.new()
cube(bm, (P.APOTHEM_FRONT + 0.06, -(gap / 2 + P.APOTHEM_FRONT * math.tan(rad(18))) / 2,
          P.FFL_UF + 1.12), (0.16, P.APOTHEM_FRONT * math.tan(rad(18)) - gap / 2 + 0.02, 0.05))
ob = mk_obj('stair_uf_guard_cap', bm, M_WOOD, 'structure')
ob.parent = stair
# handrails on the side walls
cu = bpy.data.curves.new('stair_handrails', 'CURVE')
cu.dimensions = '3D'
cu.bevel_depth = 0.022
yw1 = -(gap / 2 + W_) + 0.06
sp = cu.splines.new('POLY')
sp.points.add(1)
sp.points[0].co = (u0 - 0.1, yw1 - 0.02, 0.9, 1)
sp.points[1].co = (uL, yw1 - 0.02, zl + 0.9, 1)
sp = cu.splines.new('POLY')
sp.points.add(1)
sp.points[0].co = (uL, gap / 2 + W_ - 0.06, zl + 0.9, 1)
sp.points[1].co = (u0, gap / 2 + W_ - 0.06, P.FFL_UF + 0.9, 1)
cu.materials.append(M_WOOD)
ob = bpy.data.objects.new('stair_handrails', cu)
coll('structure').objects.link(ob)
ob.parent = stair

# ---------------------------------------------------------------------------
# 8. roof, dome
# ---------------------------------------------------------------------------
def roof_top(rr):
    t = (rr - P.APOTHEM_FRONT) / (P.R_OUT + P.ROOF_OVERHANG - P.APOTHEM_FRONT)
    return P.ROOF_Z_IN + (P.ROOF_Z_OUT - P.ROOF_Z_IN) * t


bm = bmesh.new()
sector(bm, P.APOTHEM_FRONT + 0.05, P.R_OUT + P.ROOF_OVERHANG, 0, 360, P.CEIL_UF, 0,
       step=1.5, ztop=roof_top)
roof = mk_obj('roof', bm, [M_CEIL, M_SEDUM, M_BATTEN], 'roof')
set_face_mats(roof, lambda c, n: 1 if n.z > 0.5 else (0 if n.z < -0.5 else 2))
# eave fascia
bm = bmesh.new()
sector(bm, P.R_OUT + P.ROOF_OVERHANG, P.R_OUT + P.ROOF_OVERHANG + 0.04, 0, 360,
       P.CEIL_UF - 0.08, P.ROOF_Z_OUT + 0.08, step=1.5)
mk_obj('roof_eave_fascia', bm, M_BATTEN, 'roof')
# dome base ring
bm = bmesh.new()
sector(bm, P.APOTHEM_FRONT - 0.05, P.R_DOME + 0.25, 0, 360, P.ROOF_Z_IN - 0.02, P.DOME_BASE_Z + 0.02,
       step=1.5)
mk_obj('dome_base_ring', bm, M_WOOD, 'roof')

# dome glass: spherical cap between oculus and base
rs, zc = P.dome_sphere()
bm = bmesh.new()
NA_D, NR_D = 80, 16
th0 = math.asin(P.DOME_OCULUS_R / rs)
th1 = math.asin(P.R_DOME / rs)
rings = []
for i in range(NR_D + 1):
    th = th0 + (th1 - th0) * i / NR_D
    rr, zz = rs * math.sin(th), zc + rs * math.cos(th)
    rings.append([bm.verts.new(pol(rr, 360 * j / NA_D, zz)) for j in range(NA_D)])
for i in range(NR_D):
    for j in range(NA_D):
        bm.faces.new((rings[i][j], rings[i][(j + 1) % NA_D], rings[i + 1][(j + 1) % NA_D],
                      rings[i + 1][j]))
mk_obj('dome_glass', bm, M_GLASS, 'roof', smooth=True)

# dome ribs (curved glulam) and two horizontal rings
bm = bmesh.new()
for j in range(P.N_DOME_RIBS):
    a = 360 * j / P.N_DOME_RIBS
    pts, ups = [], []
    for i in range(25):
        th = th0 + (th1 - th0) * i / 24
        n = Vector((math.sin(th) * math.cos(rad(a)), math.sin(th) * math.sin(rad(a)), math.cos(th)))
        pts.append(Vector((0, 0, zc)) + n * (rs - 0.11))
        ups.append(n)
    sweep_rect(bm, pts, ups, 0.10, 0.20)
for thf in (0.40, 0.72):
    th = th0 + (th1 - th0) * thf
    pts, ups = [], []
    for j in range(121):
        a = 360 * j / 120
        n = Vector((math.sin(th) * math.cos(rad(a)), math.sin(th) * math.sin(rad(a)), math.cos(th)))
        pts.append(Vector((0, 0, zc)) + n * (rs - 0.07))
        ups.append(n)
    sweep_rect(bm, pts, ups, 0.05, 0.10)
mk_obj('dome_ribs', bm, M_WOOD, 'roof')
# crown ring (steel) + small glass lantern / roof vent over the oculus
zcrown = P.dome_z(P.DOME_OCULUS_R)
bm = bmesh.new()
sector(bm, P.DOME_OCULUS_R - 0.10, P.DOME_OCULUS_R + 0.05, 0, 360, zcrown - 0.2, zcrown + 0.08, step=5)
sector(bm, P.DOME_OCULUS_R - 0.02, P.DOME_OCULUS_R + 0.04, 0, 360, zcrown + 0.08, zcrown + 0.40, step=5)
mk_obj('dome_crown_ring', bm, M_STEEL, 'roof')
bm = bmesh.new()
cyl(bm, (0, 0, zcrown + 0.42), P.DOME_OCULUS_R + 0.08, 0.04, segs=48)
mk_obj('dome_crown_cap', bm, M_GLASS, 'roof')
# hidden portal helper for rendering (sky light through the dome)
li = bpy.data.lights.new('portal_dome', 'AREA')
li.shape = 'DISK'
li.size = 2 * P.R_DOME
li.cycles.is_portal = True
lo = bpy.data.objects.new('portal_dome', li)
lo.location = (0, 0, P.DOME_BASE_Z + 0.05)
lo.rotation_euler = (math.pi, 0, 0)
coll('render_helpers').objects.link(lo)

# central-rope variant: steel spider in the crown ring + one rope to the net centre
bm = bmesh.new()
for a in (0, 90):
    cube(bm, (0, 0, zcrown - 0.15), (2 * P.DOME_OCULUS_R, 0.08, 0.14), rz=a)
cyl(bm, (0, 0, zcrown - 0.25), 0.06, 0.14, segs=16)
mk_obj('variant_crown_spider', bm, M_STEEL, 'variant_central_rope')
bm = bmesh.new()
z_top = zcrown - 0.3
z_bot = net_z_variant(0)
cyl(bm, (0, 0, (z_top + z_bot) / 2), 0.014, z_top - z_bot, segs=12)
mk_obj('variant_central_rope', bm, M_ROPE, 'variant_central_rope')

# ---------------------------------------------------------------------------
# 9. annex: entrance, changing, showers, WC, tech (single storey, green roof)
# ---------------------------------------------------------------------------
A0, A1 = P.ANNEX_A0, P.ANNEX_A1
RA, RB, RC_ = P.R_OUT, P.ANNEX_R_CORR, P.ANNEX_R_OUT
H = P.ANNEX_H
T = 0.35
bm = bmesh.new()
# outer curved wall with a glazed band (high windows) and entrance at east end
ann_open = []
# end walls (radial)
# east end: entrance glazing + door
sector(bm, RA + 0.02, RC_, A0, A0 + 1.6, 0, 0.0001)
bm.free()
bm = bmesh.new()
# outer arc wall with high windows between 62 and 118 deg
segs = []
aw = [(A0, 60), (60, 118), (118, A1)]
for a0, a1 in aw:
    if (a0, a1) == (60, 118):
        sector(bm, RC_ - T, RC_, a0, a1, 0, 2.1, step=2)
        sector(bm, RC_ - T, RC_, a0, a1, 2.9, H, step=2)
    else:
        sector(bm, RC_ - T, RC_, a0, a1, 0, H, step=2)
# east end wall with entrance opening (radial wall at A0)
p_in, p_out = pol(RA, A0), pol(RC_, A0)
door_c = 13.2
def radial_wall(bm, a, r0, r1, z0, z1, t=T):
    seg_box(bm, pol(r0, a) + pol(t / 2, a + 90), pol(r1, a) + pol(t / 2, a + 90), t, z0, z1)
radial_wall(bm, A0, RA, door_c - 1.0, 0, H)
radial_wall(bm, A0, door_c + 1.0, RC_ - T, 0, H)
radial_wall(bm, A0, door_c - 1.0, door_c + 1.0, 2.5, H)
radial_wall(bm, A1, RA, RC_ - T, 0, H, t=-T)
ann = mk_obj('annex_walls', bm, [M_RENDER], 'annex')
# interior partitions (corridor wall with door gaps, room dividers)
bm = bmesh.new()
cw = RB
gaps = [(62, 66), (80, 84), (96, 100), (111.5, 114.5)]
edges = [A0 + 1.2] + [g for gp in gaps for g in gp] + [A1 - 1.2]
for i in range(0, len(edges), 2):
    sector(bm, cw, cw + 0.12, edges[i], edges[i + 1], 0, H, step=2)
for a in (72, 90, 108, 116):
    radial_wall(bm, a, cw + 0.12, RC_ - T, 0, H, t=0.12)
mk_obj('annex_partitions', bm, M_CLAY_ROOM, 'annex')
bm = bmesh.new()
sector(bm, RA - 0.02, RC_ + 0.5, A0 - 1.5, A1 + 1.5, H, H + 0.35, step=2)
aroof = mk_obj('annex_roof', bm, [M_CEIL, M_SEDUM, M_BATTEN], 'annex')
set_face_mats(aroof, lambda c, n: 1 if n.z > 0.5 else (0 if n.z < -0.5 else 2))
bm = bmesh.new()
sector(bm, RA, RC_, A0, A1, -0.05, 0.0, step=2)
mk_obj('annex_floor', bm, M_FLOOR_ROOM, 'annex')
# annex high window glass + entrance glazing
bm = bmesh.new()
sector(bm, RC_ - 0.2, RC_ - 0.18, 60, 118, 2.1, 2.9, step=2)
p0, p1 = pol(door_c - 1.0, A0) + pol(0.2, A0 + 90), pol(door_c + 1.0, A0) + pol(0.2, A0 + 90)
seg_box(bm, p0, p1, 0.02, 0, 2.5)
mk_obj('annex_glass', bm, M_GLASS, 'annex')
bm = bmesh.new()
for zz in (0.05, 2.45):
    seg_box(bm, p0, p1, 0.1, zz - 0.05, zz + 0.05)
for pp in (p0, p1, (p0 + p1) / 2):
    cube(bm, (pp.x, pp.y, 1.25), (0.1, 0.1, 2.5), rz=A0)
mk_obj('annex_entrance_frame', bm, M_WOOD_DARK, 'annex')
# entrance canopy
bm = bmesh.new()
pc = pol(door_c, A0)
cube(bm, (pc.x + 0.9 * math.cos(rad(A0 - 90)), pc.y + 0.9 * math.sin(rad(A0 - 90)), 2.85),
     (3.2, 1.8, 0.12), rz=A0)
mk_obj('annex_canopy', bm, M_WOOD, 'annex')

# ---------------------------------------------------------------------------
# 10. hall furnishing
# ---------------------------------------------------------------------------
# round felt/wool mat under the net + circle of cushions
bm = bmesh.new()
cyl(bm, (0, 0, 0.015), 2.9, 0.03, segs=96)
mk_obj('hall_round_rug', bm, M_WOOL['sand'], 'furnishing')
bm = bmesh.new()
cyl(bm, (0.35, 0.9, 0.05), 1.15, 0.08, segs=64)
ob = rounded(mk_obj('hall_round_mat', bm, M_MATTRESS, 'furnishing'), 0.03, 3, 1)
cols = ['terracotta', 'ochre', 'olive', 'rose', 'wine', 'sand', 'umber', 'cream']
for i in range(14):
    a = 360 * i / 14 + 8
    p = pol(2.45, a)
    cushion('hall_zafu_%02d' % i, None, (p.x, p.y, 0.12), (0.5, 0.5, 0.2),
            M_WOOL[cols[i % len(cols)]], rz=a, squish=0.25)
# benches with cushions along the wall
for i, k in enumerate([3, 4, 6, 7, 8, 9]):
    a = P.slot_center(k)
    bm = bmesh.new()
    sector(bm, P.R_IN - 0.55, P.R_IN - 0.02, a - 12, a + 12, 0.0, 0.42, step=2)
    ob = rounded(mk_obj('hall_bench_%d' % k, bm, M_WOOD, 'furnishing'), 0.02, 2, 0)
    bm = bmesh.new()
    sector(bm, P.R_IN - 0.53, P.R_IN - 0.04, a - 11.5, a + 11.5, 0.42, 0.52, step=2)
    ob = rounded(mk_obj('hall_bench_pad_%d' % k, bm, M_WOOL[cols[(i * 3) % 8]], 'furnishing'),
                 0.04, 3, 1)
    for j, da in enumerate((-7, 0, 7)):
        p = pol(P.R_IN - 0.18, a + da)
        cushion('hall_bench_cushion_%d_%d' % (k, j), None, (p.x, p.y, 0.78), (0.5, 0.18, 0.45),
                M_WOOL[cols[(i + j) % 8]], rz=a + da + 90)
# stacked floor mats + blankets near the entrance
p = pol(P.R_IN - 1.0, P.slot_center(9) - 8)
for j in range(5):
    bm = bmesh.new()
    cube(bm, (p.x, p.y, 0.05 + j * 0.09), (1.9, 0.75, 0.08), rz=P.slot_center(9) - 8 + 90)
    rounded(mk_obj('hall_mat_stack_%d' % j, bm, M_WOOL[cols[j]], 'furnishing'), 0.03, 2, 1)
# floor lanterns around the hall (night)
for i in range(8):
    a = P.partition_angle(i) + 18 + 9
    if i == P.STAIR_SLOT:
        continue
    p = pol(P.R_IN - 0.9, a)
    lantern('hall_lantern_%d' % i, (p.x, p.y, 0.55), 0.24, 1.1)
# warm uplights at the pillar crowns (night)
for k in range(P.N_PILLARS):
    a = P.partition_angle(k)
    li = bpy.data.lights.new('pillar_uplight_%d' % k, 'SPOT')
    li.energy = 0.0
    li.spot_size = rad(110)
    li.spot_blend = 0.8
    li.color = (1.0, 0.82, 0.64)
    li.shadow_soft_size = 0.1
    lo = bpy.data.objects.new('pillar_uplight_%d' % k, li)
    lo.location = pol(P.R_PILLAR + 0.35, a, 2.2)
    lo.rotation_euler = (0, 0, 0)
    lo['lantern_power'] = 80.0
    coll('night_lights').objects.link(lo)
# cove light on top of the fascia, lighting the dome ribs (night)
for k in range(P.N_SLOTS):
    li = bpy.data.lights.new('cove_%d' % k, 'AREA')
    li.shape = 'RECTANGLE'
    li.size = 3.2
    li.size_y = 0.08
    li.energy = 0.0
    li.color = (1.0, 0.84, 0.68)
    lo = bpy.data.objects.new('cove_%d' % k, li)
    a = P.slot_center(k)
    p = pol(P.APOTHEM_FRONT - 0.12, a, P.CEIL_UF - 0.05)
    lo.location = p
    lo.rotation_euler = (0, rad(180 + 30), rad(a))
    lo['lantern_power'] = 9.0
    coll('night_lights').objects.link(lo)
# low step lights along the walkway (night): small warm area lights under the pad edge
for i in range(20):
    a = 360 * i / 20 + 9
    li = bpy.data.lights.new('walk_glow_%d' % i, 'POINT')
    li.energy = 0.0
    li.color = (1.0, 0.82, 0.64)
    li.shadow_soft_size = 0.05
    lo = bpy.data.objects.new('walk_glow_%d' % i, li)
    lo.location = pol(front_r(a) - 0.12, a, P.FFL_UF + 0.08)
    lo['lantern_power'] = 0.5
    coll('night_lights').objects.link(lo)

# ---------------------------------------------------------------------------
# 11. people (abstract sculptural figures, metaball mannequins)
# ---------------------------------------------------------------------------
# joint set, standing, facing +Y, x = left
STAND = dict(
    pelvis=(0, 0, 0.95), belly=(0, 0.01, 1.10), chest=(0, 0, 1.30), neck=(0, 0, 1.50),
    head=(0, 0.02, 1.62), ls=(0.18, 0, 1.42), le=(0.22, 0, 1.13), lw=(0.24, 0.03, 0.88),
    lh=(0.245, 0.04, 0.80), lhip=(0.10, 0, 0.92), lk=(0.11, 0.02, 0.50), la=(0.11, 0, 0.08),
    lt=(0.11, 0.14, 0.03),
)
BONES = [('pelvis', 'belly', 0.135, 0.13), ('belly', 'chest', 0.13, 0.145), ('chest', 'neck', 0.10, 0.055),
         ('neck', 'head', 0.055, 0.0),
         ('ls', 'le', 0.052, 0.043), ('le', 'lw', 0.043, 0.032), ('lw', 'lh', 0.03, 0.028),
         ('lhip', 'lk', 0.085, 0.058), ('lk', 'la', 0.056, 0.038), ('la', 'lt', 0.035, 0.028)]


def mirror_pose(p):
    out = dict(p)
    for k_, v in p.items():
        if k_.startswith('l') and k_ not in ('lh',) or k_ == 'lh':
            if k_[0] == 'l':
                out['r' + k_[1:]] = (-v[0], v[1], v[2])
    return out


def pose_sit_cross():
    return dict(pelvis=(0, 0, 0.14), belly=(0, 0.02, 0.30), chest=(0, 0.0, 0.50), neck=(0, 0.02, 0.69),
                head=(0, 0.05, 0.81), ls=(0.18, 0, 0.61), le=(0.24, 0.10, 0.36), lw=(0.18, 0.28, 0.22),
                lh=(0.13, 0.32, 0.19), lhip=(0.10, 0.02, 0.12), lk=(0.42, 0.30, 0.10),
                la=(-0.08, 0.40, 0.07), lt=(-0.18, 0.44, 0.04),
                rs=(-0.18, 0, 0.61), re=(-0.24, 0.10, 0.36), rw=(-0.18, 0.28, 0.22),
                rh=(-0.13, 0.32, 0.19), rhip=(-0.10, 0.02, 0.12), rk=(-0.42, 0.30, 0.10),
                ra=(0.08, 0.32, 0.12), rt=(0.18, 0.34, 0.10))


def pose_sit_knees():
    return dict(pelvis=(0, 0, 0.14), belly=(0, 0.03, 0.30), chest=(0, 0.05, 0.50), neck=(0, 0.09, 0.68),
                head=(0, 0.14, 0.79), ls=(0.18, 0.05, 0.60), le=(0.22, 0.30, 0.46), lw=(0.10, 0.45, 0.42),
                lh=(0.04, 0.48, 0.43), lhip=(0.10, 0.02, 0.12), lk=(0.12, 0.38, 0.50),
                la=(0.11, 0.55, 0.08), lt=(0.11, 0.68, 0.03),
                rs=(-0.18, 0.05, 0.60), re=(-0.22, 0.30, 0.46), rw=(-0.10, 0.45, 0.42),
                rh=(-0.04, 0.48, 0.43), rhip=(-0.10, 0.02, 0.12), rk=(-0.12, 0.38, 0.50),
                ra=(-0.11, 0.55, 0.08), rt=(-0.11, 0.68, 0.03))


def pose_sit_lean():
    return dict(pelvis=(0, 0, 0.13), belly=(0, -0.04, 0.28), chest=(0, -0.12, 0.46), neck=(0, -0.17, 0.63),
                head=(0, -0.17, 0.76), ls=(0.18, -0.14, 0.56), le=(0.25, -0.30, 0.34), lw=(0.27, -0.40, 0.10),
                lh=(0.28, -0.44, 0.03), lhip=(0.10, 0.02, 0.12), lk=(0.13, 0.45, 0.30),
                la=(0.14, 0.78, 0.07), lt=(0.14, 0.90, 0.04),
                rs=(-0.18, -0.14, 0.56), re=(-0.25, -0.30, 0.34), rw=(-0.27, -0.40, 0.10),
                rh=(-0.28, -0.44, 0.03), rhip=(-0.10, 0.02, 0.10), rk=(-0.10, 0.48, 0.12),
                ra=(-0.10, 0.92, 0.06), rt=(-0.12, 1.04, 0.10))


def pose_lie_back(arms='open'):
    # lying on the back, head towards +Y, face up
    p = {}
    for k_, (x, y, z) in mirror_pose(STAND).items():
        p[k_] = (x, z - 0.95, 0.11 + (y if k_ not in ('lt', 'rt') else 0.02))
    p['head'] = (0, 0.67, 0.12)
    p['lt'] = (0.13, -0.90, 0.13)
    p['rt'] = (-0.13, -0.90, 0.13)
    p['la'] = (0.13, -0.87, 0.06)
    p['ra'] = (-0.13, -0.87, 0.06)
    if arms == 'open':
        p['le'] = (0.42, 0.30, 0.07)
        p['lw'] = (0.58, 0.10, 0.05)
        p['lh'] = (0.62, 0.03, 0.04)
        p['re'] = (-0.36, 0.25, 0.07)
        p['rw'] = (-0.20, 0.08, 0.20)
        p['rh'] = (-0.12, 0.05, 0.22)
    elif arms == 'head':
        p['le'] = (0.36, 0.72, 0.08)
        p['lw'] = (0.12, 0.82, 0.10)
        p['lh'] = (0.06, 0.80, 0.10)
        p['re'] = (-0.36, 0.72, 0.08)
        p['rw'] = (-0.12, 0.82, 0.10)
        p['rh'] = (-0.06, 0.80, 0.10)
    return p


def pose_lie_side():
    # lying on the left side, facing -X... knees bent
    return dict(pelvis=(0, 0, 0.16), belly=(0.0, 0.15, 0.16), chest=(0.02, 0.35, 0.17),
                neck=(0.03, 0.55, 0.16), head=(0.05, 0.68, 0.14),
                ls=(0.0, 0.45, 0.07), le=(-0.25, 0.50, 0.06), lw=(-0.30, 0.72, 0.06),
                lh=(-0.30, 0.80, 0.06),
                rs=(0.03, 0.45, 0.30), re=(-0.18, 0.30, 0.30), rw=(-0.32, 0.20, 0.20),
                rh=(-0.35, 0.16, 0.16),
                lhip=(0.0, -0.02, 0.07), lk=(-0.36, -0.22, 0.08), la=(-0.10, -0.55, 0.07),
                lt=(-0.16, -0.64, 0.06),
                rhip=(0.0, -0.02, 0.25), rk=(-0.40, -0.12, 0.24), ra=(-0.20, -0.50, 0.18),
                rt=(-0.28, -0.58, 0.16))


def pose_stand_relaxed():
    p = mirror_pose(STAND)
    p['lw'] = (0.24, 0.10, 0.90)
    p['le'] = (0.22, 0.02, 1.14)
    p['rk'] = (-0.12, 0.06, 0.50)
    p['ra'] = (-0.14, 0.02, 0.08)
    return p


def figure(name, pose, loc, rz=0.0, scale=1.0, parent_coll='people', tilt=None):
    mb = bpy.data.metaballs.new(name + '_mb')
    mb.resolution = 0.018
    mb.render_resolution = 0.018
    mb.threshold = 0.6
    ob = bpy.data.objects.new(name + '_mb', mb)
    coll('tmp').objects.link(ob)
    p = {k_: Vector(v) for k_, v in pose.items()}

    def cap(a, b, r0, r1):
        n = 3 if (b - a).length > 0.12 else 1
        for i in range(n):
            t0, t1 = i / n, (i + 1) / n
            pa, pb = a.lerp(b, t0), a.lerp(b, t1)
            rr = r0 + (r1 - r0) * (t0 + t1) / 2
            e = mb.elements.new(type='CAPSULE')
            d = pb - pa
            e.co = (pa + pb) / 2
            e.size_x = max(d.length / 2, 0.001)
            e.rotation = Vector((1, 0, 0)).rotation_difference(d.normalized())
            e.radius = max(rr, 0.02) / 0.575
            e.stiffness = 2.0

    for a_, b_, r0, r1 in BONES:
        for side in ('l', 'r') if a_[0] == 'l' and a_ not in ('lh',) or a_ in ('lhip',) else ('',):
            pass
    for a_, b_, r0, r1 in BONES:
        if a_ in ('pelvis', 'belly', 'chest', 'neck'):
            if b_ == 'head':
                continue
            cap(p[a_], p[b_], r0, r1)
            continue
        for s in ('l', 'r'):
            A = s + a_[1:]
            B = s + b_[1:]
            if A in p and B in p:
                cap(p[A], p[B], r0, r1)
    # hips/shoulders mass
    for s in ('l', 'r'):
        cap(p['pelvis'], p[s + 'hip'], 0.12, 0.10)
        cap(p['chest'] + (p['neck'] - p['chest']) * 0.4, p[s + 's'], 0.085, 0.06)
    # head: egg
    hd = p['head']
    nk = p['neck']
    up = (hd - nk).normalized()
    e = mb.elements.new(type='ELLIPSOID')
    e.co = hd + up * 0.02
    e.radius = 0.105 / 0.575
    e.size_x, e.size_y, e.size_z = 0.85, 0.95, 1.12
    e.rotation = Vector((0, 0, 1)).rotation_difference(up)
    e.stiffness = 2.0
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    bpy.data.objects.remove(ob)
    me.name = name
    me.materials.append(M_FIGURE)
    for pp in me.polygons:
        pp.use_smooth = True
    fo = bpy.data.objects.new(name, me)
    coll(parent_coll).objects.link(fo)
    fo.location = loc
    fo.rotation_euler = (0, 0, rad(rz))
    if tilt:
        fo.rotation_euler = tilt
    fo.scale = (scale, scale, scale)
    return fo


# on the net (z follows the sagging net + extra local dip under the body)
def on_net(x, y, dip=0.0):
    return P.net_z(math.hypot(x, y)) - dent(x, y) - dip


figure('person_net_a', pose_lie_back('head'), (-0.6, 0.4, on_net(-0.6, 0.4) - 0.03), rz=200)
figure('person_net_b', pose_lie_side(), (0.9, -0.2, on_net(0.9, -0.2) - 0.05), rz=160, scale=0.97)
figure('person_net_c', pose_sit_knees(), (-2.1, -1.8, on_net(-2.1, -1.8, 0.14) - 0.02), rz=50, scale=0.98)
# walkway: someone sitting on the pad edge, feet on the net
pw = pol(4.1, 300)
figure('person_pad', pose_sit_lean(), (pw.x, pw.y, P.RING_BEAM_TOP + P.PAD_T - 0.16), rz=300 + 90)
# hall
figure('person_hall_lie', pose_lie_back('open'), (0.35, 0.95, 0.06), rz=-35)
figure('person_hall_sit_a', pose_sit_cross(), (pol(2.45, 8 + 360 / 14 * 9).x, pol(2.45, 8 + 360 / 14 * 9).y, 0.14),
       rz=8 + 360 / 14 * 9 + 90)
figure('person_hall_sit_b', pose_sit_knees(), (pol(2.45, 8 + 360 / 14 * 11).x, pol(2.45, 8 + 360 / 14 * 11).y, 0.14),
       rz=8 + 360 / 14 * 11 + 90, scale=0.96)
ps = pol(5.3, 205)
figure('person_hall_stand', pose_stand_relaxed(), (ps.x, ps.y, 0.0), rz=205 + 90 + 20)
# rooms: one in the (half-open) room of view 4, one lying in an open room
kv = 3
ang = P.slot_center(kv)
pr = pol(6.55, ang - 6.5)
figure('person_room_sit', pose_sit_cross(), (pr.x, pr.y, P.FFL_UF + 0.13), rz=ang + 90 + 180 + 10)
ang2 = P.slot_center(9)
figure('person_room_lie', pose_lie_side(), (pol(8.4, ang2).x, pol(8.4, ang2).y, P.FFL_UF + 0.33),
       rz=ang2 + 180)

# remove temp collection
tmp = COLLS.get('tmp')
if tmp:
    for o in list(tmp.objects):
        bpy.data.objects.remove(o)
    bpy.data.collections.remove(tmp)

# convert curve objects to meshes (so every exporter sees them)
dg = bpy.context.evaluated_depsgraph_get()
for ob in list(bpy.data.objects):
    if ob.type == 'CURVE':
        me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
        me.name = ob.name
        new = bpy.data.objects.new(ob.name + '_m', me)
        for c in ob.users_collection:
            c.objects.link(new)
        new.parent = ob.parent
        new.matrix_world = ob.matrix_world.copy()
        for p in me.polygons:
            p.use_smooth = True
        bpy.data.objects.remove(ob)
        new.name = new.name[:-2]

# variant hidden by default
COLLS['variant_central_rope'].hide_render = True
COLLS['variant_central_rope'].hide_viewport = True

out = os.path.join(HERE, 'tempel.blend')
bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
print('saved', out, len(bpy.data.objects), 'objects')
