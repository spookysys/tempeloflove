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


def cut_cylinder(ob, center_xy, r, z0, z1):
    """Boolean-subtract a vertical cylinder from ob (applied)."""
    bmc = bmesh.new()
    bmesh.ops.create_cone(bmc, cap_ends=True, segments=64, radius1=r, radius2=r, depth=z1 - z0,
                          matrix=Matrix.Translation(Vector((center_xy[0], center_xy[1], (z0 + z1) / 2))))
    me = bpy.data.meshes.new('cutter')
    bmc.to_mesh(me)
    bmc.free()
    cutter = bpy.data.objects.new('cutter', me)
    SCENE.collection.objects.link(cutter)
    mod = ob.modifiers.new('cut', 'BOOLEAN')
    mod.operation = 'DIFFERENCE'
    mod.object = cutter
    mod.solver = 'EXACT'
    mod.use_self = True
    mod.use_hole_tolerant = True
    dg = bpy.context.evaluated_depsgraph_get()
    new = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    ob.modifiers.remove(mod)
    ob.data = new
    bpy.data.objects.remove(cutter)


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
    """Lawn around the building fading into a sandy pine-forest floor (Brandenburg)."""
    m, b = new_mat(name, srgb('#6E7B3E'))
    co = b.coord()
    n1 = b.noise(co, scale=0.25, detail=6)
    n2 = b.noise(co, scale=6.0, detail=8)
    lawn = b.ramp(n1.outputs['Fac'], [(0.35, srgb('#5E6E32')), (0.55, srgb('#7A8440')),
                                       (0.7, srgb('#8E8A50'))])
    forest = b.ramp(n1.outputs['Fac'], [(0.3, srgb('#5A4A36')), (0.5, srgb('#76654A')),
                                         (0.65, srgb('#57603A')), (0.8, srgb('#8C7B5C'))])
    sep = b.n('ShaderNodeSeparateXYZ')
    b.l(co, sep.inputs[0])
    cmb = b.n('ShaderNodeCombineXYZ')
    b.l(sep.outputs['X'], cmb.inputs[0])
    b.l(sep.outputs['Y'], cmb.inputs[1])
    ln = b.n('ShaderNodeVectorMath', operation='LENGTH')
    b.l(cmb.outputs[0], ln.inputs[0])
    wob = b.n('ShaderNodeMath', operation='MULTIPLY_ADD')
    b.l(n1.outputs['Fac'], wob.inputs[0])
    wob.inputs[1].default_value = 10.0
    b.l(ln.outputs['Value'], wob.inputs[2])
    mr = b.n('ShaderNodeMapRange')
    b.l(wob.outputs[0], mr.inputs['Value'])
    mr.inputs['From Min'].default_value = 26.0
    mr.inputs['From Max'].default_value = 34.0
    col = b.mix(mr.outputs['Result'], lawn, forest)
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
M_DECK = mat_boards('terrace_deck_larch', '#A08466', '#B39574', '#3E342B', board_w=0.12,
                    board_l=3.0, polar=True, rough=0.7)
M_BATTEN = mat_wood('larch_battens_ext', '#9C7A58', '#B08D69', grain_axis='Z', rough=0.8)
M_LINEN = mat_fabric('linen_natural', '#CBB89B')
M_ROPE = mat_fabric('rope_natural', '#E6D9BF', weave=900.0, sheen=0.3)
M_NET = mat_net('net_mesh')
M_SHOJI = mat_translucent('shoji_linen', '#F0E2C6')
M_LANTERN = mat_translucent('paper_lantern', '#F4E6CC')
M_LANTERN_OFF = mat_translucent('signal_lantern_off', '#E9D9BE')
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
M_MATTRESS = mat_fabric('mattress_cotton', '#D8C6A8', weave=180.0)
M_CURTAIN = mat_fabric('curtain_linen', '#E6D6BC', weave=300.0)
M_CURTAIN['vp_alpha'] = 1.0
M_CANDLE = mat_simple('candle_wax', '#F1E4CE', rough=0.4, Subsurface_Weight=0.6,
                      Subsurface_Scale=0.02)

def mat_cladding(name, c_a, c_b, c_gap):
    """Vertical larch boards (board-and-batten look) on the octagonal facade."""
    ca, cb, cg = srgb(c_a), srgb(c_b), srgb(c_gap)
    m, b = new_mat(name, ca)
    co = b.coord()
    sep = b.n('ShaderNodeSeparateXYZ')
    b.l(co, sep.inputs[0])
    at = b.n('ShaderNodeMath', operation='ARCTAN2')
    b.l(sep.outputs['Y'], at.inputs[0])
    b.l(sep.outputs['X'], at.inputs[1])
    s = b.n('ShaderNodeMath', operation='MULTIPLY')
    b.l(at.outputs[0], s.inputs[0])
    s.inputs[1].default_value = 10.2
    c2 = b.n('ShaderNodeCombineXYZ')
    b.l(sep.outputs['X'], c2.inputs[0])
    b.l(sep.outputs['Y'], c2.inputs[1])
    ln = b.n('ShaderNodeVectorMath', operation='LENGTH')
    b.l(c2.outputs[0], ln.inputs[0])
    hsum = b.n('ShaderNodeMath', operation='ADD')
    b.l(s.outputs[0], hsum.inputs[0])
    b.l(ln.outputs['Value'], hsum.inputs[1])
    cmb = b.n('ShaderNodeCombineXYZ')
    b.l(sep.outputs['Z'], cmb.inputs[0])
    b.l(hsum.outputs[0], cmb.inputs[1])
    br = b.n('ShaderNodeTexBrick', offset=0.5, offset_frequency=1, squash=1.0, squash_frequency=1)
    for k_, v_ in (('Scale', 1.0), ('Mortar Size', 0.006), ('Mortar Smooth', 0.2), ('Bias', 0.0),
                   ('Brick Width', 3.2), ('Row Height', 0.16)):
        br.inputs[k_].default_value = v_
    br.inputs['Color1'].default_value = ca
    br.inputs['Color2'].default_value = cb
    br.inputs['Mortar'].default_value = cg
    b.l(cmb.outputs[0], br.inputs['Vector'])
    gv = b.mapping(cmb.outputs[0], scale=(1.5, 40.0, 1.5))
    g = b.noise(gv, scale=3.0, detail=6, rough=0.6)
    grain = b.ramp(g.outputs['Fac'], [(0.3, (0.82, 0.82, 0.82, 1)), (0.7, (1.06, 1.04, 1.0, 1))])
    col = b.mix(1.0, br.outputs['Color'], grain, blend='MULTIPLY')
    wv = b.noise(co, scale=0.35, detail=3)
    col = b.mix(0.25, col, b.ramp(wv.outputs['Fac'], [(0.3, srgb('#8F8577')), (0.7, srgb('#B08A60'))]),
                blend='MIX')
    inv = b.n('ShaderNodeMath', operation='SUBTRACT')
    inv.inputs[0].default_value = 1.0
    b.l(br.outputs['Fac'], inv.inputs[1])
    nrm = b.bump(inv.outputs[0], strength=0.6, dist=0.01)
    nrm = b.bump(g.outputs['Fac'], strength=0.15, dist=0.003, normal=nrm)
    b.output(b.principled(col, rough=0.75, normal=nrm))
    return m


def mat_foliage(name, c1, c2, c3=None, scale=0.8):
    m, b = new_mat(name, srgb(c1))
    co = b.coord()
    n1 = b.noise(co, scale=scale, detail=3)
    stops = [(0.3, srgb(c1)), (0.62, srgb(c2))] + ([(0.8, srgb(c3))] if c3 else [])
    col = b.ramp(n1.outputs['Fac'], stops)
    oi = b.n('ShaderNodeObjectInfo')
    n2 = b.noise(co, scale=40.0, detail=2)
    col = b.mix(0.25, col, n2.outputs['Color'], blend='OVERLAY')
    p = b.principled(col, rough=0.5, Subsurface_Weight=0.15, Subsurface_Scale=0.02, Coat_Weight=0.15)
    b.output(p)
    return m


def mat_sheer(name, hexcol):
    c = srgb(hexcol)
    m, b = new_mat(name, c, alpha=0.4)
    tl = b.n('ShaderNodeBsdfTranslucent', Color=c)
    tr = b.n('ShaderNodeBsdfTransparent', Color=(1, 0.98, 0.95, 1))
    df = b.principled(c, rough=0.9, Sheen_Weight=0.5)
    m1 = b.n('ShaderNodeMixShader')
    m1.inputs[0].default_value = 0.5
    b.l(df.outputs[0], m1.inputs[1])
    b.l(tl.outputs[0], m1.inputs[2])
    m2 = b.n('ShaderNodeMixShader')
    m2.inputs[0].default_value = 0.45
    b.l(m1.outputs[0], m2.inputs[1])
    b.l(tr.outputs[0], m2.inputs[2])
    b.output(m2)
    return m


def mat_frosted(name):
    m, b = new_mat(name, srgb('#E8EEEC'), alpha=0.5)
    tl = b.n('ShaderNodeBsdfTranslucent', Color=srgb('#F2F5F3'))
    tr = b.n('ShaderNodeBsdfTransparent', Color=(0.9, 0.93, 0.92, 1))
    gl = b.n('ShaderNodeBsdfGlossy', Roughness=0.15)
    m1 = b.n('ShaderNodeMixShader')
    m1.inputs[0].default_value = 0.25
    b.l(tl.outputs[0], m1.inputs[1])
    b.l(tr.outputs[0], m1.inputs[2])
    m2 = b.n('ShaderNodeMixShader')
    m2.inputs[0].default_value = 0.08
    b.l(m1.outputs[0], m2.inputs[1])
    b.l(gl.outputs[0], m2.inputs[2])
    b.output(m2)
    return m


def mat_fur(name, hexcol):
    c = srgb(hexcol)
    m, b = new_mat(name, c)
    co = b.coord()
    n1 = b.noise(co, scale=90.0, detail=8, rough=0.7)
    n2 = b.noise(co, scale=12.0, detail=4)
    col = b.mix(0.15, c, n2.outputs['Color'], blend='OVERLAY')
    nrm = b.bump(n1.outputs['Fac'], strength=0.9, dist=0.02)
    b.output(b.principled(col, rough=0.95, normal=nrm, Sheen_Weight=1.0, Sheen_Roughness=0.3))
    return m


M_CLAD = mat_cladding('larch_cladding', '#9E7B57', '#B08A63', '#3B3027')
M_WOOD_STAVE = mat_wood('larch_column_casing', '#B7874F', '#CFA06A', grain_axis='Z', rough=0.5)
M_PINE_BARK = mat_foliage('pine_bark', '#4E4034', '#7A5540', '#9A6444', scale=0.12)
M_PINE_NEEDLES = mat_foliage('pine_needles', '#27351F', '#3A4A2A', '#4E5A33', scale=0.5)
M_BIRCH_BARK = mat_simple('birch_bark', '#D9D4C9', rough=0.8)
M_IVY = mat_foliage('ivy_vine', '#2F4A22', '#4F6B2E', '#8E3B24', scale=0.9)
M_PLANT = mat_foliage('house_plant', '#2E5227', '#4A7234', scale=2.0)
M_GRASSES = mat_foliage('ornamental_grasses', '#8A8A55', '#B3A56B', '#6E7A45', scale=1.2)
M_SHEER = mat_sheer('sheer_linen', '#F0E6D4')
M_FROSTED = mat_frosted('frosted_glass')
M_FUR = mat_fur('sheepskin', '#EDE3D1')
M_SAIL = mat_translucent('sun_sail', '#EFE7D8')
M_TERRACOTTA = mat_clay('terracotta', '#A65F3D', '#B87050', scale=4.0)
M_DECK_DARK = mat_wood('oiled_larch', '#8E6A4A', '#A07A56', grain_axis='X', rough=0.6)


# ---------------------------------------------------------------------------
# octagon helpers
# ---------------------------------------------------------------------------
def OCT(apo):
    return lambda a: P.octo_r(a, apo)


def ring_prism(bm, rin, rout, z0, z1, a0=0.0, a1=360.0, step=0.5, ztop=None):
    """Prism between two outlines given as radius(angle) callables or floats."""
    f = (lambda v: (lambda a: v)) if True else None
    rin = rin if callable(rin) else f(rin)
    rout = rout if callable(rout) else f(rout)
    span = a1 - a0
    full = span >= 359.999
    n = max(1, int(round(span / step)))
    angs = [a0 + span * i / n for i in range(n + (0 if full else 1))]
    profs = []
    for a in angs:
        ri, ro = rin(a), rout(a)
        zt = z1 if ztop is None else ztop(a)
        profs.append([bm.verts.new(pol(ri, a, z0)), bm.verts.new(pol(ro, a, z0)),
                      bm.verts.new(pol(ro, a, zt)), bm.verts.new(pol(ri, a, zt))])
    m = len(profs)
    for i in (range(m) if full else range(m - 1)):
        A, B = profs[i], profs[(i + 1) % m]
        for j in range(4):
            bm.faces.new((A[j], A[(j + 1) % 4], B[(j + 1) % 4], B[j]))
    if not full:
        bm.faces.new(profs[0])
        bm.faces.new(profs[-1][::-1])


def face_frame(k):
    a = rad(P.slot_center(k))
    return Vector((math.cos(a), math.sin(a), 0)), Vector((-math.sin(a), math.cos(a), 0))


def FP(k, nd, td, z=0.0):
    """face-local (distance along the face normal, position along the face, z) -> world"""
    n, t = face_frame(k)
    return n * nd + t * td + Vector((0, 0, z))


def wall_piece(bm, k, t0, t1, z0, z1, nin, nout):
    """Straight wall piece on face k; t0/t1 = None means the mitred corner."""
    ti0 = -P.face_half(nin) if t0 is None else t0
    to0 = -P.face_half(nout) if t0 is None else t0
    ti1 = P.face_half(nin) if t1 is None else t1
    to1 = P.face_half(nout) if t1 is None else t1
    q = [FP(k, nin, ti0), FP(k, nout, to0), FP(k, nout, to1), FP(k, nin, ti1)]
    vb = [bm.verts.new(p + Vector((0, 0, z0))) for p in q]
    vt = [bm.verts.new(p + Vector((0, 0, z1))) for p in q]
    bm.faces.new(vb[::-1])
    bm.faces.new(vt)
    for i in range(4):
        j = (i + 1) % 4
        bm.faces.new((vb[i], vb[j], vt[j], vt[i]))


def face_wall(bm, k, holes, z0, z1, nin=None, nout=None):
    """holes: list of (t0, t1, zb, zt) in face-local coordinates."""
    nin = P.R_IN if nin is None else nin
    nout = P.R_OUT if nout is None else nout
    ts = sorted({h[0] for h in holes} | {h[1] for h in holes})
    bounds = [None] + ts + [None]
    for i in range(len(bounds) - 1):
        ta, tb = bounds[i], bounds[i + 1]
        lo = -99 if ta is None else ta
        hi = 99 if tb is None else tb
        mid = (lo + hi) / 2
        hz = sorted([(h[2], h[3]) for h in holes if h[0] < mid < h[1]])
        z = z0
        for h0, h1 in hz + [(z1, z1)]:
            if h0 > z + 1e-6:
                wall_piece(bm, k, ta, tb, z, min(h0, z1), nin, nout)
            z = max(z, h1)


def face_of(p):
    a = math.degrees(math.atan2(p.y, p.x))
    return round((a - P.SLOT0_DEG) / P.SLOT_DEG) % P.N_SLOTS


# ---------------------------------------------------------------------------
# 1. site: a clearing in the pine forest (ZEGG, Bad Belzig, Brandenburg)
# ---------------------------------------------------------------------------
bm = bmesh.new()
bmesh.ops.create_circle(bm, cap_ends=True, segments=96, radius=150.0)
for v in bm.verts:
    v.co.z = -0.05
ground = mk_obj('site_meadow', bm, M_GRASS, 'site')

bm = bmesh.new()
ring_prism(bm, OCT(P.R_OUT), OCT(P.R_OUT + 0.6), -0.05, -0.02, step=0.5)
mk_obj('site_gravel_drip_strip', bm, M_GRAVEL, 'site')

# path from the east to the annex entrance (east end of the annex)
bm = bmesh.new()
left, right = [], []
p_start = pol(P.octo_r(22.5, (P.R_OUT + P.ANNEX_D / 2 + P.R_OUT) / 2 + 0.0), 22.5)
for i in range(60):
    t = i / 59
    a = 22.5 - 4 - 38 * t
    r_ = 13.2 + 24 * t ** 1.4
    left.append(bm.verts.new(pol(r_ - 0.9, a, -0.03)))
    right.append(bm.verts.new(pol(r_ + 0.9, a, -0.03)))
for i in range(59):
    bm.faces.new((left[i], right[i], right[i + 1], left[i + 1]))
ob = mk_obj('site_path', bm, M_GRAVEL, 'site', recalc=False)
for p in ob.data.polygons:
    if p.normal.z < 0:
        p.flip()
bm = bmesh.new()
cyl(bm, tuple(pol(14.0, 14, -0.035)), 3.2, 0.03, segs=48)
mk_obj('site_forecourt', bm, M_GRAVEL, 'site')
# garden terrace (south) in front of the garden doors
bm = bmesh.new()
for i in range(18):
    for j in range(5):
        c = FP(P.GARDEN_SLOT, P.R_OUT + 0.6 + j * 0.75 + 0.35, -3.4 + i * 0.4, -0.03)
        cube(bm, (c.x, c.y, -0.025), (0.7, 0.36, 0.05), rz=P.slot_center(P.GARDEN_SLOT))
mk_obj('site_garden_deck', bm, M_DECK, 'site')


def tree(name, x, y, h, crown_r, seed):
    r = random.Random(seed)
    bm = bmesh.new()
    cyl(bm, (x, y, h * 0.3), 0.18 * h / 10, h * 0.6, segs=10, r2=0.10 * h / 10)
    mk_obj(name + '_trunk', bm, M_BIRCH_BARK, 'site')
    bm = bmesh.new()
    for i in range(7):
        c = Vector((x + r.uniform(-0.5, 0.5) * crown_r, y + r.uniform(-0.5, 0.5) * crown_r,
                    h * 0.62 + r.uniform(-0.25, 0.3) * crown_r))
        s = crown_r * r.uniform(0.5, 0.75)
        res = bmesh.ops.create_icosphere(bm, subdivisions=3, radius=s, matrix=Matrix.Translation(c))
        for v in res['verts']:
            d = v.co - c
            v.co = c + d * (1 + 0.18 * math.sin(7 * d.x + seed) * math.cos(5 * d.y) + r.uniform(-0.08, 0.08))
    return mk_obj(name + '_crown', bm, M_LEAVES, 'site', smooth=True)


def pine(name, x, y, h, seed):
    """Scots pine: tall straight trunk, orange upper bark, crown in the top third."""
    r = random.Random(seed)
    bm = bmesh.new()
    lean = Vector((r.uniform(-0.3, 0.3), r.uniform(-0.3, 0.3), 0))
    n = 8
    pts = [Vector((x, y, 0)) + lean * (i / n) ** 2 + Vector((0, 0, h * i / n)) for i in range(n + 1)]
    for i in range(n):
        d = pts[i + 1] - pts[i]
        rot = Vector((0, 0, 1)).rotation_difference(d.normalized()).to_matrix().to_4x4()
        r0 = 0.24 * h / 20 * (1 - 0.8 * i / n)
        cyl(bm, (pts[i] + pts[i + 1]) / 2, r0, d.length + 0.02, segs=10,
            r2=0.24 * h / 20 * (1 - 0.8 * (i + 1) / n), rot=rot)
    mk_obj(name + '_trunk', bm, M_PINE_BARK, 'site', smooth=True)
    bm = bmesh.new()
    top = pts[-1]
    for i in range(r.randint(8, 13)):
        zc = h * r.uniform(0.62, 0.98)
        spread = 2.6 * (1.0 - 0.5 * (zc / h - 0.62) / 0.36)
        c = Vector((x, y, 0)) + lean * (zc / h) ** 2 + Vector((r.uniform(-spread, spread),
                                                                r.uniform(-spread, spread), zc))
        s = r.uniform(0.9, 1.7)
        res = bmesh.ops.create_icosphere(bm, subdivisions=3, radius=s, matrix=Matrix.Translation(c))
        for v in res['verts']:
            d = v.co - c
            v.co = c + Vector((d.x * 1.35, d.y * 1.35, d.z * 0.45)) * (1 + 0.2 * math.sin(9 * d.x + seed) *
                                                                         math.cos(7 * d.y) + r.uniform(-0.1, 0.1))
    mk_obj(name + '_crown', bm, M_PINE_NEEDLES, 'site', smooth=True)


placed = []
for i in range(110):
    for _ in range(60):
        a = rnd.uniform(0, 360)
        d = rnd.uniform(22, 70)
        x, y = d * math.cos(rad(a)), d * math.sin(rad(a))
        # keep the view corridors of the exterior cameras (SW aerial, E path) a bit open
        ok = all((x - px) ** 2 + (y - py) ** 2 > 16 for px, py in placed)
        blocked = ((212 < a < 268 and d < 48) or (283 < a < 312 and d < 32) or (152 < a < 184 and d < 30))
        if ok and not blocked:
            break
    placed.append((x, y))
    pine('pine_%02d' % i, x, y, rnd.uniform(17, 25), i)
# a couple of birches near the building
for i, (a, d) in enumerate(((330, 25), (200, 27), (45, 26))):
    tree('birch_%d' % i, d * math.cos(rad(a)), d * math.sin(rad(a)), 10.0, 3.2, 50 + i)

# ---------------------------------------------------------------------------
# 2. hall floor, octagonal timber facade, openings, shutters, climbing plants
# ---------------------------------------------------------------------------
bm = bmesh.new()
ring_prism(bm, 0.001, OCT(P.R_IN + 0.02), -0.20, 0.0, step=0.5)
mk_obj('hall_floor', bm, M_FLOOR_HALL, 'structure')

bm = bmesh.new()
ring_prism(bm, OCT(P.R_OUT - 0.02), OCT(P.R_OUT + 0.06), -0.05, 0.30, step=0.5)
mk_obj('plinth', bm, M_PLINTH, 'structure')

WALL_TOP = P.CEIL_UF
ANNEX_FACES = P.ANNEX_FACES
FACE_OPEN = P.face_openings()   # (t0, t1, zb, zt, kind) per face

bm = bmesh.new()
for k in range(P.N_SLOTS):
    face_wall(bm, k, [h[:4] for h in FACE_OPEN[k]], 0.0, WALL_TOP)
wall = mk_obj('outer_wall', bm, [M_CLAY_HALL, M_CLAY_ROOM, M_CLAD, M_WOOD], 'structure')


def wall_mat(c, n):
    k = face_of(c)
    fn, _ = face_frame(k)
    d = c.dot(fn)
    if d > P.R_OUT - 0.01 and n.dot(fn) > 0.5:
        return 2
    if d > P.R_IN + 0.02 and abs(n.z) < 0.5 and abs(n.dot(fn)) < 0.5:
        return 3                     # reveals: timber lining
    return 0 if c.z < P.FFL_UF - 0.1 else 1


set_face_mats(wall, wall_mat)


def opening_fill(k, t0, t1, z0, z1, kind):
    bm = bmesh.new()
    fw = 0.075
    nd = P.R_IN + 0.14
    rz = P.slot_center(k) + 90
    w = t1 - t0
    tc = (t0 + t1) / 2
    zc = (z0 + z1) / 2
    for zz in (z0 + fw / 2, z1 - fw / 2):
        c = FP(k, nd, tc, zz)
        cube(bm, c, (w, 0.14, fw), rz=rz)
    for tt in (t0 + fw / 2, t1 - fw / 2):
        c = FP(k, nd, tt, zc)
        cube(bm, c, (fw, 0.14, z1 - z0), rz=rz)
    bars = []
    if kind == 'window_gf':
        bars.append(('h', z0 + 1.95))
    if kind == 'window_uf':
        bars.append(('h', P.FFL_UF + 0.90))           # fixed safety-glass lower part (fall protection)
    if kind in ('door_garden',):
        bars += [('v', tc - w / 6), ('v', tc + w / 6)]
    for typ, v in bars:
        if typ == 'h':
            cube(bm, FP(k, nd, tc, v), (w, 0.12, 0.06), rz=rz)
        else:
            cube(bm, FP(k, nd, v, zc), (0.06, 0.12, z1 - z0), rz=rz)
    if kind in ('door_entry', 'door_exit'):
        cube(bm, FP(k, nd, tc, (z0 + z1) / 2), (w - 2 * fw, 0.06, z1 - z0 - fw), rz=rz)
        mk_obj('door_%s_%d' % (kind, k), bm, M_WOOD_DARK, 'openings')
        return
    mk_obj('frame_%d_%s_%.1f' % (k, kind, t0), bm, M_WOOD, 'openings')
    bm = bmesh.new()
    q = [FP(k, nd, t0 + fw, z0 + fw), FP(k, nd, t1 - fw, z0 + fw), FP(k, nd, t1 - fw, z1 - fw),
         FP(k, nd, t0 + fw, z1 - fw)]
    bm.faces.new([bm.verts.new(p) for p in q])
    mk_obj('glass_%d_%s_%.1f' % (k, kind, t0), bm, M_GLASS, 'openings', recalc=False)


for k in range(P.N_SLOTS):
    for (t0, t1, z0, z1, kind) in FACE_OPEN[k]:
        opening_fill(k, t0, t1, z0, z1, kind)

# exterior sliding lamella shutters on the room windows (open / half / closed per room)
SHUTTER = {0: 'open', 2: 'half', 3: 'open', 4: 'open', 5: 'half', 6: 'closed', 7: 'open'}
for k, state in SHUTTER.items():
    w = P.UF_WINDOW['w']
    sw = w / 2 + 0.06
    zb, zt = P.FFL_UF + P.UF_WINDOW['sill'] - 0.05, P.FFL_UF + P.UF_WINDOW['head'] + 0.05
    pos = {'open': (-w / 2 - sw / 2 - 0.05, w / 2 + sw / 2 + 0.05), 'half': (-w / 4, w / 2 + sw / 2 + 0.05),
           'closed': (-w / 4, w / 4)}[state]
    bm = bmesh.new()
    rz = P.slot_center(k) + 90
    nd = P.R_OUT + 0.07
    for tc in pos:
        for zz in (zb + 0.03, zt - 0.03):
            cube(bm, FP(k, nd, tc, zz), (sw, 0.04, 0.06), rz=rz)
        for tt in (tc - sw / 2 + 0.03, tc + sw / 2 - 0.03):
            cube(bm, FP(k, nd, tt, (zb + zt) / 2), (0.06, 0.04, zt - zb), rz=rz)
        nsl = int(sw / 0.07)
        for i in range(nsl):
            tt = tc - sw / 2 + 0.07 + i * (sw - 0.14) / max(nsl - 1, 1)
            cube(bm, FP(k, nd, tt, (zb + zt) / 2), (0.035, 0.025, zt - zb - 0.08), rz=rz)
    # top rail
    cube(bm, FP(k, nd + 0.02, 0, zt + 0.06), (2 * w + 0.6, 0.06, 0.05), rz=rz)
    mk_obj('shutters_%d' % k, bm, M_BATTEN, 'openings')

# light linen curtains inside the ground-floor windows (drawn to the sides)
bm = bmesh.new()
for k in range(P.N_SLOTS):
    for (t0, t1, z0, z1, kind) in FACE_OPEN[k]:
        if kind not in ('window_gf', 'door_garden'):
            continue
        for side in (-1, 1):
            tb = t0 if side < 0 else t1
            prev = None
            for i in range(25):
                s = i / 24
                tt = tb - side * (0.05 + 0.45 * s)
                nd = P.R_IN - 0.12 - 0.05 * math.sin(s * math.pi * 7)
                col = [bm.verts.new(FP(k, nd, tt, 0.03)), bm.verts.new(FP(k, nd, tt, z1 + 0.25))]
                if prev:
                    bm.faces.new((prev[0], col[0], col[1], prev[1]))
                prev = col
mk_obj('curtains_gf', bm, M_SHEER, 'furnishing', smooth=True, recalc=False)


# climbing plants (ivy + Virginia creeper) on steel cables
def vine(name, k, t_start, height, seed, spread=0.5):
    r = random.Random(seed)
    bm_s = bmesh.new()
    bm_l = bmesh.new()
    fn, ft = face_frame(k)
    for strand in range(3):
        t = t_start + r.uniform(-0.15, 0.15)
        z = 0.2
        pts = []
        while z < height * r.uniform(0.75, 1.0):
            t += 0.06 * math.sin(z * 2.3 + seed + strand) + r.uniform(-0.03, 0.03)
            z += 0.09
            pts.append(FP(k, P.R_OUT + 0.06, t, z))
            for _ in range(r.randint(3, 6)):
                off = Vector((0, 0, 0))
                c = FP(k, P.R_OUT + 0.05 + r.uniform(0.0, 0.12),
                       t + r.uniform(-spread, spread) * (0.3 + 0.7 * min(z / 1.5, 1)),
                       z + r.uniform(-0.12, 0.12))
                s = r.uniform(0.045, 0.085)
                rot = (Matrix.Rotation(rad(P.slot_center(k)), 4, 'Z') @
                       Matrix.Rotation(rad(r.uniform(-50, 50)), 4, 'X') @ Matrix.Rotation(rad(r.uniform(-30, 30)), 4, 'Y'))
                res = bmesh.ops.create_icosphere(bm_l, subdivisions=1, radius=1.0)
                bmesh.ops.transform(bm_l, verts=res['verts'],
                                    matrix=Matrix.Translation(c) @ rot @ Matrix.Diagonal((s * 0.2, s, s * 1.1, 1)))
        for i in range(len(pts) - 1):
            d = pts[i + 1] - pts[i]
            rot = Vector((0, 0, 1)).rotation_difference(d.normalized()).to_matrix().to_4x4()
            cyl(bm_s, (pts[i] + pts[i + 1]) / 2, 0.012, d.length, segs=5, rot=rot)
    # cable
    cyl(bm_s, FP(k, P.R_OUT + 0.08, t_start, height / 2 + 0.2), 0.004, height, segs=5)
    mk_obj(name + '_stems', bm_s, M_BARK, 'plants')
    mk_obj(name + '_leaves', bm_l, M_IVY, 'plants', smooth=True)


VINES = [(2, -3.75, 6.3), (2, 0.0, 3.4), (3, 3.8, 7.6), (3, 0.0, 3.3), (5, -3.8, 7.6), (5, 0.0, 3.3),
         (6, 3.75, 6.8), (6, 0.0, 3.4), (4, -3.9, 5.5), (4, 3.9, 6.0), (1, -3.9, 3.0), (7, -3.9, 3.5)]
for i, (k, t, h) in enumerate(VINES):
    vine('vine_%02d' % i, k, t, h, 300 + i)

# ---------------------------------------------------------------------------
# 3. structure: four slim columns (steel core, timber casing), ring beam, beams, slab
# ---------------------------------------------------------------------------
PILLAR_ANGLES = [P.PILLAR0_DEG + 90 * i for i in range(P.N_PILLARS)]
bm = bmesh.new()
for a in PILLAR_ANGLES:
    c = pol(P.R_PILLAR, a)
    cyl(bm, (c.x, c.y, P.RING_BEAM_BOT / 2), P.PILLAR_D / 2 - 0.035, P.RING_BEAM_BOT, segs=24)   # steel core
    cyl(bm, (c.x, c.y, P.RING_BEAM_BOT - 0.06), P.PILLAR_D / 2 + 0.03, 0.12, segs=40)
    cyl(bm, (c.x, c.y, 0.02), P.PILLAR_D / 2 + 0.02, 0.04, segs=40)
mk_obj('columns', bm, M_WOOD_STAVE, 'structure', smooth=True)

bm = bmesh.new()
sector(bm, P.RING_BEAM_IN, P.RING_BEAM_OUT, 0, 360, P.RING_BEAM_BOT, P.RING_BEAM_TOP, step=1.5)
mk_obj('ring_beam', bm, M_WOOD, 'structure')

bm = bmesh.new()
for i in range(P.N_BEAMS):
    a = i * 360 / P.N_BEAMS + 360 / P.N_BEAMS / 2
    seg_box(bm, pol(P.RING_BEAM_OUT - 0.02, a), pol(P.octo_r(a, P.R_IN) + 0.05, a), P.BEAM_W,
            P.CEIL_GF - P.BEAM_D, P.CEIL_GF + 0.01)
mk_obj('radial_beams', bm, M_WOOD, 'structure')

s_a0 = P.partition_angle(P.STAIR_SLOT)
s_a1 = P.partition_angle(P.STAIR_SLOT + 1)
HELIX_C = pol(P.HELIX_U, P.slot_center(P.STAIR_SLOT))
bm = bmesh.new()
ring_prism(bm, P.RING_BEAM_OUT, OCT(P.R_IN + 0.02), P.CEIL_GF, P.FFL_UF - 0.01, step=0.5)
slab = mk_obj('upper_slab', bm, [M_CEIL, M_WOOD], 'structure')
cut_cylinder(slab, HELIX_C, P.HELIX_CAGE_R + 0.06, P.CEIL_GF - 0.5, P.FFL_UF + 0.5)
set_face_mats(slab, lambda c, n: 0 if n.z < -0.5 else 1)
bm = bmesh.new()
sector(bm, P.R_PAD_OUT - 0.02, P.RING_BEAM_OUT, 0, 360, P.RING_BEAM_TOP, P.FFL_UF - 0.01, step=1.5)
mk_obj('upper_slab_edge', bm, M_WOOD, 'structure')
# floor finish of the stair segment on the upper floor
bm = bmesh.new()
ring_prism(bm, P.APOTHEM_FRONT - 0.05, OCT(P.R_IN), P.FFL_UF - 0.012, P.FFL_UF, a0=s_a0, a1=s_a1, step=0.5)
plat = mk_obj('stair_platform_floor', bm, M_FLOOR_ROOM, 'structure')
cut_cylinder(plat, HELIX_C, P.HELIX_CAGE_R + 0.06, P.FFL_UF - 0.5, P.FFL_UF + 0.5)

# walkway floor finish (circle inside, octagon of room fronts outside)
bm = bmesh.new()
N = 720
inner, outer = [], []
for i in range(N):
    a = i * 360 / N
    inner.append(bm.verts.new(pol(P.R_PAD_OUT, a, P.FFL_UF)))
    outer.append(bm.verts.new(pol(front_r(a) + 0.02, a, P.FFL_UF)))
for i in range(N):
    j = (i + 1) % N
    bm.faces.new((inner[i], outer[i], outer[j], inner[j]))
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
    seg_box(bm, pol(RC - 0.02, a), pol(P.octo_r(a, P.R_IN) + 0.05, a), P.PART_T, P.FFL_UF, P.CEIL_UF)
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
DOOR_STATES = {0: 'half', 2: 'open', 3: 'half', 4: 'closed', 5: 'open', 6: 'closed', 7: 'half'}


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
    # door signal: a small lantern by each door - lit = come in / ask, dark = private
    lit = state != 'closed'
    lantern('door_signal_%d' % k, (x - 0.12, L / 2 - 0.2, zh - 0.25), 0.075, 0.15, parent=parent, cord=zh + 0.12,
            mat=None if lit else M_LANTERN_OFF, power=6.0 if lit else 0.0)
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


def lantern(name, center, r, h, parent=None, coll_name='furnishing', cord=None, mat=None, power=None):
    bm = bmesh.new()
    res = bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=16, radius=r)
    for v in bm.verts:
        v.co.z *= h / (2 * r)
        # ribbed paper lantern
        a = math.atan2(v.co.y, v.co.x)
        v.co.x *= 1 + 0.015 * math.cos(24 * a)
    bmesh.ops.translate(bm, vec=Vector(center), verts=bm.verts[:])
    ob = mk_obj(name, bm, mat or M_LANTERN, coll_name, smooth=True)
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
    lo['lantern_power'] = 80.0 * (r / 0.25) ** 2 if power is None else power
    return ob


def superellipse(cx, cy, rx, ry, n=2.6, N=72, jitter=0.0, seed=0, rot=0.0):
    r = random.Random(seed)
    ph = r.uniform(0, 6.28)
    pts = []
    cr, sr = math.cos(rad(rot)), math.sin(rad(rot))
    for i in range(N):
        t = 2 * math.pi * i / N
        c, s = math.cos(t), math.sin(t)
        f = 1 + jitter * math.sin(3 * t + ph) + jitter * 0.5 * math.sin(7 * t + 2 * ph)
        x = rx * f * math.copysign(abs(c) ** (2 / n), c)
        y = ry * f * math.copysign(abs(s) ** (2 / n), s)
        pts.append((cx + x * cr - y * sr, cy + x * sr + y * cr))
    return pts


def extrude_outline(name, pts, z0, z1, mat, parent=None, coll_name='furnishing', bevel=0.05, seg=4,
                    sub=0):
    bm = bmesh.new()
    vb = [bm.verts.new((x, y, z0)) for x, y in pts]
    vt = [bm.verts.new((x, y, z1)) for x, y in pts]
    bm.faces.new(vb[::-1])
    bm.faces.new(vt)
    n = len(pts)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((vb[i], vb[j], vt[j], vt[i]))
    ob = mk_obj(name, bm, mat, coll_name, smooth=True)
    if bevel:
        bv = ob.modifiers.new('bevel', 'BEVEL')
        bv.width = bevel
        bv.segments = seg
        bv.limit_method = 'ANGLE'
        bv.angle_limit = rad(50)
        bv.harden_normals = False
    if sub:
        ob.modifiers.new('sub', 'SUBSURF').levels = sub
    if parent:
        ob.parent = parent
    return ob


def poly_obj(name, pts, z, mat, parent, coll_name, down=False):
    bm = bmesh.new()
    f = bm.faces.new([bm.verts.new((x, y, z)) for x, y in pts])
    ob = mk_obj(name, bm, mat, coll_name, recalc=False)
    nz = ob.data.polygons[0].normal.z
    if (down and nz > 0) or (not down and nz < 0):
        ob.data.polygons[0].flip()
    ob.parent = parent
    return ob


def drape(name, parent, x_edge, y0, y1, x_in, z_top, z_bottom, mat, seed=0):
    """Blanket lying on a surface (x > x_edge) and falling over its edge (x < x_edge)."""
    r = random.Random(seed)
    bm = bmesh.new()
    NX, NY = 28, 22
    L = (x_in - x_edge) + (z_top - z_bottom) + 0.1
    grid = []
    for i in range(NX + 1):
        s = L * i / NX
        row = []
        for j in range(NY + 1):
            y = y0 + (y1 - y0) * j / NY
            if s <= x_in - x_edge:
                x = x_in - s
                z = z_top + 0.015 * math.sin(y * 9 + seed)
            else:
                d = s - (x_in - x_edge)
                ang = min(d / 0.12, 1.0) * math.pi / 2
                x = x_edge - 0.12 * (1 - math.cos(ang)) * 0.6 - max(0, d - 0.12) * 0.12
                z = z_top - (0.12 * math.sin(ang) if d < 0.12 else 0.12 + (d - 0.12))
                x += 0.035 * math.sin(y * 13 + seed) * min(d / 0.3, 1)
            row.append(bm.verts.new((x, y, max(z, z_bottom))))
        grid.append(row)
    for i in range(NX):
        for j in range(NY):
            bm.faces.new((grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]))
    ob = mk_obj(name, bm, mat, 'furnishing', smooth=True, recalc=False)
    so = ob.modifiers.new('solid', 'SOLIDIFY')
    so.thickness = 0.014
    ob.modifiers.new('sub', 'SUBSURF').levels = 1
    ob.parent = parent
    return ob


def potted_plant(name, parent, x, y, z, h=1.1, seed=0):
    r = random.Random(seed)
    bm = bmesh.new()
    cyl(bm, (x, y, z + 0.21), 0.26, 0.42, segs=32, r2=0.30)
    ob = mk_obj(name + '_pot', bm, M_TERRACOTTA, 'furnishing', smooth=True)
    ob.parent = parent
    bm = bmesh.new()
    for i in range(14):
        a = r.uniform(0, 360)
        el = r.uniform(25, 70)
        L = h * r.uniform(0.5, 1.0)
        base = Vector((x, y, z + 0.4))
        d = Vector((math.cos(rad(a)) * math.cos(rad(el)), math.sin(rad(a)) * math.cos(rad(el)), math.sin(rad(el))))
        tip = base + d * L
        rot = Vector((0, 0, 1)).rotation_difference(d).to_matrix().to_4x4()
        cyl(bm, (base + tip) / 2, 0.008, L, segs=5, rot=rot)
        s = r.uniform(0.16, 0.26)
        res = bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0)
        lrot = (Matrix.Rotation(rad(a), 4, 'Z') @ Matrix.Rotation(rad(-r.uniform(10, 40)), 4, 'Y'))
        bmesh.ops.transform(bm, verts=res['verts'], matrix=Matrix.Translation(tip + d * s * 0.8) @ lrot @
                            Matrix.Diagonal((s, s * 0.6, 0.012, 1)))
    ob = mk_obj(name + '_leaves', bm, M_PLANT, 'furnishing', smooth=True)
    ob.parent = parent


def room(k):
    a = P.slot_center(k)
    parent = bpy.data.objects.new('room_%d' % k, None)
    coll('rooms').objects.link(parent)
    parent.matrix_world = Matrix.Rotation(rad(a), 4, 'Z')
    ht = math.tan(rad(P.SLOT_DEG / 2))
    x0 = P.APOTHEM_FRONT + P.FRONT_T
    xb = P.R_IN
    z = P.FFL_UF
    e = P.PART_T / 2 / math.cos(rad(P.SLOT_DEG / 2))

    def yw(x):
        return x * ht - e

    # floor
    poly_obj('room_floor_%d' % k, [(x0, -yw(x0)), (xb + 0.02, -yw(xb) - 0.1), (xb + 0.02, yw(xb) + 0.1),
                                    (x0, yw(x0))], z, M_FLOOR_ROOM, parent, 'rooms')
    # ceiling with a skylight well
    sx0, sx1 = P.SKYLIGHT['u'] - P.SKYLIGHT['d'] / 2, P.SKYLIGHT['u'] + P.SKYLIGHT['d'] / 2
    sw = P.SKYLIGHT['w'] / 2
    zc = P.CEIL_UF - 0.012        # just below the roof slab (avoid coplanar faces)
    xf = x0 - 0.1
    for nm, pts in (('a', [(xf, -yw(xf)), (sx0, -yw(sx0)), (sx0, yw(sx0)), (xf, yw(xf))]),
                    ('b', [(sx1, -yw(sx1)), (xb + 0.02, -yw(xb)), (xb + 0.02, yw(xb)), (sx1, yw(sx1))]),
                    ('c', [(sx0, sw), (sx1, sw), (sx1, yw(sx1)), (sx0, yw(sx0))]),
                    ('d', [(sx0, -yw(sx0)), (sx1, -yw(sx1)), (sx1, -sw), (sx0, -sw)])):
        poly_obj('room_ceiling_%d%s' % (k, nm), pts, zc, M_CLAY_ROOM, parent, 'rooms', down=True)
    bm = bmesh.new()
    for (xa, ya), (xc, yc) in (((sx0, -sw), (sx1, -sw)), ((sx1, -sw), (sx1, sw)), ((sx1, sw), (sx0, sw)),
                               ((sx0, sw), (sx0, -sw))):
        bm.faces.new([bm.verts.new((xa, ya, zc)), bm.verts.new((xc, yc, zc)),
                      bm.verts.new((xc, yc, P.TERRACE_Z)), bm.verts.new((xa, ya, P.TERRACE_Z))])
    ob = mk_obj('room_lightwell_%d' % k, bm, M_CLAY_ROOM, 'rooms', recalc=False)
    ob.parent = parent
    bm = bmesh.new()
    bm.faces.new([bm.verts.new(v) for v in ((sx0, -sw, P.TERRACE_Z - 0.03), (sx1, -sw, P.TERRACE_Z - 0.03),
                                            (sx1, sw, P.TERRACE_Z - 0.03), (sx0, sw, P.TERRACE_Z - 0.03))])
    ob = mk_obj('skylight_glass_%d' % k, bm, M_FROSTED, 'roof', recalc=False)
    ob.parent = parent
    bm = bmesh.new()
    for (xa, ya, xc, yc) in ((sx0 - 0.06, -sw - 0.06, sx1 + 0.06, -sw), (sx0 - 0.06, sw, sx1 + 0.06, sw + 0.06),
                             (sx0 - 0.06, -sw, sx0, sw), (sx1, -sw, sx1 + 0.06, sw)):
        cube(bm, ((xa + xc) / 2, (ya + yc) / 2, P.TERRACE_Z - 0.01), (xc - xa, yc - ya, 0.03))
    ob = mk_obj('skylight_frame_%d' % k, bm, M_STEEL, 'roof')
    ob.parent = parent

    pal = PALETTES[(k * 3) % len(PALETTES)]
    seed = 11 * k
    # sleeping nest: earthen plinth with soft edges under the window, mattress, skins, cushions
    nest = superellipse(8.55, 0.0, 1.2, 1.6, n=2.4, jitter=0.03, seed=seed)
    extrude_outline('room_nest_base_%d' % k, nest, z - 0.01, z + 0.30, M_CLAY_ROOM, parent, bevel=0.07)
    mat_ = superellipse(8.55, 0.0, 1.07, 1.46, n=2.6, seed=seed)
    extrude_outline('room_nest_mattress_%d' % k, mat_, z + 0.30, z + 0.49, M_MATTRESS, parent, bevel=0.08,
                    seg=5)
    fur = superellipse(8.1, -0.85, 0.45, 0.62, n=2.0, jitter=0.12, seed=seed + 1, rot=20)
    extrude_outline('room_sheepskin_%d' % k, fur, z + 0.48, z + 0.54, M_FUR, parent, bevel=0.025, seg=3)
    drape('room_blanket_%d' % k, parent, 7.5, 0.1, 1.25, 8.6, z + 0.50, z + 0.06, M_WOOL[pal[0]], seed=seed)
    for i, yy in enumerate((-1.05, -0.38, 0.32, 1.0)):
        cushion('room_cushion_%d_%d' % (k, i), parent, (9.25 - 0.05 * abs(yy), yy, z + 0.75),
                (0.6, 0.22, 0.52), M_WOOL[pal[i % 3]], rz=yy * 10, rx=-12, squish=0.3)
    cushion('room_bolster_%d' % k, parent, (7.75, 1.05, z + 0.58), (0.25, 0.6, 0.2), M_WOOL[pal[1]], rz=15,
            squish=0.6)
    # cob bench along one side wall with a curved back
    wa = -P.SLOT_DEG / 2
    wd = Vector((math.cos(rad(wa)), math.sin(rad(wa)), 0))
    wn = Vector((math.sin(rad(-wa)), math.cos(rad(-wa)), 0))
    c0 = wd * 7.0 + wn * (e + 0.34)
    seat = superellipse(c0.x, c0.y, 0.95, 0.30, n=2.2, rot=wa, seed=seed + 2)
    extrude_outline('room_cob_bench_%d' % k, seat, z - 0.01, z + 0.42, M_CLAY_ROOM, parent, bevel=0.09, seg=5)
    cb = wd * 7.0 + wn * (e + 0.07)
    back = superellipse(cb.x, cb.y, 1.05, 0.09, n=2.0, rot=wa, seed=seed + 3)
    extrude_outline('room_cob_back_%d' % k, back, z - 0.01, z + 0.95, M_CLAY_ROOM, parent, bevel=0.07, seg=5)
    for i, s in enumerate((-0.45, 0.4)):
        p = wd * (7.0 + s) + wn * (e + 0.36)
        cushion('room_bench_cushion_%d_%d' % (k, i), parent, (p.x, p.y, z + 0.49), (0.55, 0.5, 0.12),
                M_WOOL[pal[(i + 1) % 3]], rz=wa + 5 * s)
    # soft round rug, tray with candles and tea, plant, curtain
    rug = superellipse(6.95, 0.55, 1.15, 1.0, n=2.0, jitter=0.05, seed=seed + 4)
    extrude_outline('room_rug_%d' % k, rug, z, z + 0.015, M_WOOL[pal[1]], parent, bevel=0.006, seg=2)
    bm = bmesh.new()
    cyl(bm, (7.25, -0.45, z + 0.03), 0.27, 0.035, segs=40)
    ob = mk_obj('room_tray_%d' % k, bm, M_WOOD_DARK, 'furnishing', smooth=True)
    ob.parent = parent
    bm = bmesh.new()
    for (cx, cy, h) in ((7.18, -0.52, 0.12), (7.33, -0.38, 0.08), (7.3, -0.56, 0.05)):
        cyl(bm, (cx, cy, z + 0.05 + h / 2), 0.035, h, segs=16)
    ob = mk_obj('room_candles_%d' % k, bm, M_CANDLE, 'furnishing', smooth=True)
    ob.parent = parent
    bm = bmesh.new()
    res = bmesh.ops.create_uvsphere(bm, u_segments=20, v_segments=12, radius=0.075,
                                    matrix=Matrix.Translation((7.12, -0.33, z + 0.13)))
    ob = mk_obj('room_teapot_%d' % k, bm, M_TERRACOTTA, 'furnishing', smooth=True)
    ob.parent = parent
    potted_plant('room_plant_%d' % k, parent, 9.05, 3.05, z, h=1.2, seed=seed)
    bm = bmesh.new()
    prev = None
    for i in range(22):
        s = i / 21
        yy = -P.UF_WINDOW['w'] / 2 - 0.05 + 0.55 * s
        xx = P.R_IN - 0.1 - 0.05 * math.sin(s * math.pi * 6)
        col = [bm.verts.new((xx, yy, z + 0.02)), bm.verts.new((xx, yy, z + P.UF_WINDOW['head'] + 0.2))]
        if prev:
            bm.faces.new((prev[0], col[0], col[1], prev[1]))
        prev = col
    ob = mk_obj('room_curtain_%d' % k, bm, M_SHEER, 'furnishing', smooth=True, recalc=False)
    ob.parent = parent
    # paper lanterns: pendant + floor lantern
    lantern('room_pendant_%d' % k, (7.0, 0.9, P.CEIL_UF - 0.8), 0.3, 0.44, parent=parent, cord=P.CEIL_UF)
    lantern('room_floorlamp_%d' % k, (6.15, -1.65 if k % 2 else 1.65, z + 0.45), 0.2, 0.8, parent=parent)
    return parent


for k in range(P.N_SLOTS):
    if k == P.STAIR_SLOT:
        continue
    room_front(k, DOOR_STATES[k])
    room(k)

# ---------------------------------------------------------------------------
# 7. helical stair around a wooden trunk: hall -> upper floor -> roof terrace
# ---------------------------------------------------------------------------
sa = P.slot_center(P.STAIR_SLOT)
s_ca, s_sn = math.cos(rad(sa)), math.sin(rad(sa))


def HW(theta, r, z):
    """helix-local polar (theta deg, 0 = outwards along the slot axis) -> world"""
    u = P.HELIX_U + r * math.cos(rad(theta))
    v = r * math.sin(rad(theta))
    return Vector((u * s_ca - v * s_sn, u * s_sn + v * s_ca, z))


def hsector(bm, r0, r1, a0, a1, z0, z1, step=4.0):
    n = max(1, int(math.ceil(abs(a1 - a0) / step)))
    profs = []
    for i in range(n + 1):
        a = a0 + (a1 - a0) * i / n
        profs.append([bm.verts.new(HW(a, r0, z0)), bm.verts.new(HW(a, r1, z0)),
                      bm.verts.new(HW(a, r1, z1)), bm.verts.new(HW(a, r0, z1))])
    for i in range(n):
        A, B = profs[i], profs[i + 1]
        for j in range(4):
            bm.faces.new((A[j], A[(j + 1) % 4], B[(j + 1) % 4], B[j]))
    bm.faces.new(profs[0])
    bm.faces.new(profs[-1][::-1])


S_ = P.HELIX_STEP_DEG
TH0 = 180.0 - (P.STAIR_RISERS - 1) * S_          # first riser (hall)
TH_UF0 = TH0 + (P.STAIR_RISERS - 1) * S_          # = 180: arrival on the upper floor
TH_UF1 = TH_UF0 + 2 * S_                          # end of the upper-floor landing
TH_TOP = TH_UF1 + (P.TERRACE_RISERS - 1) * S_     # arrival at terrace level
R0 = P.HELIX_CORE_R
R1 = P.HELIX_R


def z_line(th):
    if th <= TH_UF0:
        return max(0.0, (th - TH0) / S_ * P.STAIR_RISE)
    if th <= TH_UF1:
        return P.FFL_UF
    if th <= TH_TOP:
        return P.FFL_UF + (th - TH_UF1) / S_ * P.TERRACE_RISE
    return P.TERRACE_Z


bm = bmesh.new()
for k in range(1, P.STAIR_RISERS):
    hsector(bm, R0, R1, TH0 + (k - 1) * S_, TH0 + k * S_ + 0.6, k * P.STAIR_RISE - 0.07, k * P.STAIR_RISE)
hsector(bm, R0, R1 + 0.08, TH_UF0, TH_UF1, P.FFL_UF - 0.14, P.FFL_UF)
for j in range(1, P.TERRACE_RISERS):
    z = P.FFL_UF + j * P.TERRACE_RISE
    hsector(bm, R0, R1, TH_UF1 + (j - 1) * S_, TH_UF1 + j * S_ + 0.6, z - 0.07, z)
hsector(bm, R0, R1 + 0.08, TH_TOP, TH_TOP + 150, P.TERRACE_Z - 0.16, P.TERRACE_Z)
mk_obj('stair_treads', bm, M_WOOD, 'structure')

# outer helical stringer + handrail on the screen side
bm = bmesh.new()
pts, ups = [], []
th = TH0
while th <= TH_TOP + 0.01:
    pts.append(HW(th, R1 + 0.035, z_line(th) - 0.14))
    ups.append(Vector((0, 0, 1)))
    th += 2.0
sweep_rect(bm, pts, ups, 0.06, 0.26)
pts = [HW(th_, R1 - 0.02, z_line(th_) + 0.9) for th_ in [TH0 + S_ + i * 2.0 for i in
                                                          range(int((TH_TOP - TH0 - S_) / 2.0) + 1)]]
sweep_rect(bm, pts, [Vector((0, 0, 1))] * len(pts), 0.05, 0.05)
mk_obj('stair_stringer_handrail', bm, M_WOOD, 'structure')

# central trunk
bm = bmesh.new()
cyl(bm, HW(0, 0, P.STAIR_HOUSE_TOP / 2), R0 + 0.02, P.STAIR_HOUSE_TOP, segs=32, r2=R0 - 0.03)
trunk = mk_obj('stair_trunk', bm, M_WOOD, 'structure', smooth=True)

# slatted larch screen around the stair (hall to roof), open at the access points
SCREEN_OPEN = [((165, 232), (0.0, 2.35)),                     # from the hall
               ((-16, 16), (0.0, 2.15)),                      # exit straight outside (escape route)
               ((150, 214), (P.FFL_UF, P.FFL_UF + 2.25))]     # to the walkway / upper floor
bm = bmesh.new()
nbat = 88
for i in range(nbat):
    th = 360.0 * i / nbat
    zs = [(0.0, P.ROOF_Z_IN)]
    for (a0, a1), (z0, z1) in SCREEN_OPEN:
        if a0 <= th <= a1:
            new = []
            for (za, zb) in zs:
                if z1 <= za or z0 >= zb:
                    new.append((za, zb))
                else:
                    if z0 > za:
                        new.append((za, z0))
                    if z1 < zb:
                        new.append((z1, zb))
            zs = new
    p = HW(th, P.HELIX_CAGE_R, 0)
    for za, zb in zs:
        if zb - za > 0.05:
            cube(bm, (p.x, p.y, (za + zb) / 2), (0.035, 0.05, zb - za), rz=sa + th)
for (a0, a1), (z0, z1) in SCREEN_OPEN:    # lintel rings over the openings
    hsector(bm, P.HELIX_CAGE_R - 0.03, P.HELIX_CAGE_R + 0.03, a0, a1, z1, z1 + 0.08)
mk_obj('stair_screen', bm, M_BATTEN, 'structure')
# fire-rated glass drum just inside the slats: the stair is its own enclosure (Treppenraum)
bm = bmesh.new()
cuts = sorted({-180.0, 180.0} | {a for (a0, a1), _ in SCREEN_OPEN for a in ((a0 + 180) % 360 - 180, (a1 + 180) % 360 - 180)})
for a0, a1 in zip(cuts[:-1], cuts[1:]):
    am = (a0 + a1) / 2
    zs = [(0.0, P.ROOF_Z_IN)]
    for (o0, o1), (z0, z1) in SCREEN_OPEN:
        if (am - o0) % 360 < (o1 - o0) % 360:
            new = []
            for (za, zb) in zs:
                if z1 <= za or z0 >= zb:
                    new.append((za, zb))
                else:
                    if z0 > za:
                        new.append((za, z0))
                    if z1 < zb:
                        new.append((z1, zb))
            zs = new
    for za, zb in zs:
        if zb - za > 0.05:
            hsector(bm, P.HELIX_CAGE_R - 0.045, P.HELIX_CAGE_R - 0.035, a0, a1, za, zb, step=3.0)
mk_obj('stair_glass_drum', bm, M_GLASS, 'structure')

# round stair house on the roof, doors on both sides onto the terrace
DOORS = [(119, 143), (226, 250)]
zd0, zd1 = P.TERRACE_Z, P.TERRACE_Z + 2.15
zw0, zw1 = P.TERRACE_Z + 1.85, P.STAIR_HOUSE_TOP - 0.25      # glazed band above
bm = bmesh.new()
cuts = sorted({0.0, 360.0} | {a for d in DOORS for a in d})
for a0, a1 in zip(cuts[:-1], cuts[1:]):
    am = (a0 + a1) / 2
    door = any(d0 < am < d1 for d0, d1 in DOORS)
    zs = [(zw1, P.STAIR_HOUSE_TOP)] if door else [(P.ROOF_Z_IN, zw0), (zw1, P.STAIR_HOUSE_TOP)]
    for za, zb in zs:
        hsector(bm, P.HELIX_CAGE_R + 0.02, P.HELIX_CAGE_R + 0.16, a0, a1, za, zb, step=3.0)
hs = mk_obj('stair_house_wall', bm, M_BATTEN, 'roof')
bm = bmesh.new()
for a0, a1 in zip(cuts[:-1], cuts[1:]):
    am = (a0 + a1) / 2
    if any(d0 < am < d1 for d0, d1 in DOORS):
        continue
    hsector(bm, P.HELIX_CAGE_R + 0.08, P.HELIX_CAGE_R + 0.09, a0, a1, zw0, zw1, step=3.0)
for d0, d1 in DOORS:
    hsector(bm, P.HELIX_CAGE_R + 0.08, P.HELIX_CAGE_R + 0.09, d0 + 1.5, d1 - 1.5, zd0 + 0.05, zw1, step=3.0)
mk_obj('stair_house_glass', bm, M_GLASS, 'roof')
bm = bmesh.new()
for d0, d1 in DOORS:
    for a in (d0 + 0.8, (d0 + d1) / 2, d1 - 0.8):
        p = HW(a, P.HELIX_CAGE_R + 0.09, 0)
        cube(bm, (p.x, p.y, (zd0 + zw1) / 2), (0.07, 0.06, zw1 - zd0), rz=sa + a)
    hsector(bm, P.HELIX_CAGE_R + 0.05, P.HELIX_CAGE_R + 0.13, d0, d1, zd1 - 0.03, zd1 + 0.04)
    hsector(bm, P.HELIX_CAGE_R + 0.05, P.HELIX_CAGE_R + 0.13, d0, d1, zd0, zd0 + 0.05)
mk_obj('stair_house_door_frames', bm, M_WOOD_DARK, 'roof')
bm = bmesh.new()
cyl(bm, HW(0, 0, P.STAIR_HOUSE_TOP + 0.08), P.HELIX_CAGE_R + 0.45, 0.16, segs=64)
mk_obj('stair_house_roof', bm, M_WOOD, 'roof')
bm = bmesh.new()
cyl(bm, HW(0, 0, P.STAIR_HOUSE_TOP + 0.19), P.HELIX_CAGE_R + 0.30, 0.06, segs=64)
mk_obj('stair_house_roof_sedum', bm, M_SEDUM, 'roof')
bm = bmesh.new()
cyl(bm, HW(0, 0, P.STAIR_HOUSE_TOP + 0.24), 0.55, 0.06, segs=40)
mk_obj('stair_house_smoke_vent', bm, M_GLASS, 'roof')
lantern('stair_house_lantern', tuple(HW(0, 0.75, P.STAIR_HOUSE_TOP - 0.55)), 0.22, 0.34,
        cord=P.STAIR_HOUSE_TOP)

# ---------------------------------------------------------------------------
# 8. roof, dome
# ---------------------------------------------------------------------------
def cut_box(ob, center, size, rz):
    bmc = bmesh.new()
    cube(bmc, center, size, rz=rz)
    me = bpy.data.meshes.new('cutter')
    bmc.to_mesh(me)
    bmc.free()
    cutter = bpy.data.objects.new('cutter', me)
    SCENE.collection.objects.link(cutter)
    mod = ob.modifiers.new('cut', 'BOOLEAN')
    mod.operation = 'DIFFERENCE'
    mod.object = cutter
    mod.solver = 'EXACT'
    mod.use_self = True
    mod.use_hole_tolerant = True
    dg = bpy.context.evaluated_depsgraph_get()
    new = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    ob.modifiers.remove(mod)
    ob.data = new
    bpy.data.objects.remove(cutter)


ROOM_SLOTS = [k for k in range(P.N_SLOTS) if k != P.STAIR_SLOT]


def cut_skylights(ob, z0, z1):
    for k in ROOM_SLOTS:
        c = pol(P.SKYLIGHT['u'], P.slot_center(k), (z0 + z1) / 2)
        cut_box(ob, c, (P.SKYLIGHT['d'], P.SKYLIGHT['w'], z1 - z0 + 0.4), P.slot_center(k))


bm = bmesh.new()
ring_prism(bm, P.APOTHEM_FRONT + 0.05, OCT(P.R_OUT), P.CEIL_UF, P.ROOF_Z_IN, step=0.5)
roof = mk_obj('roof', bm, [M_CEIL, M_PLINTH, M_CLAD], 'roof')
cut_cylinder(roof, HELIX_C, P.HELIX_CAGE_R + 0.10, P.CEIL_UF - 0.5, P.ROOF_Z_IN + 0.5)
cut_skylights(roof, P.CEIL_UF, P.ROOF_Z_IN)
set_face_mats(roof, lambda c, n: 1 if n.z > 0.5 else (0 if n.z < -0.5 else 2))
# terrace deck (outdoor larch boards, laid in rings)
bm = bmesh.new()
ring_prism(bm, P.R_DOME + 0.25, OCT(P.R_TERRACE_OUT), P.ROOF_Z_IN, P.TERRACE_Z, step=0.5)
deck = mk_obj('terrace_deck', bm, M_DECK, 'roof')
cut_cylinder(deck, HELIX_C, P.HELIX_CAGE_R + 0.10, P.ROOF_Z_IN - 0.5, P.TERRACE_Z + 0.5)
cut_skylights(deck, P.ROOF_Z_IN, P.TERRACE_Z)
# dome upstand ring (45 cm above the deck); a timber bench ring runs outside it
bm = bmesh.new()
sector(bm, P.APOTHEM_FRONT - 0.05, P.R_DOME + 0.25, 0, 360, P.ROOF_Z_IN - 0.02, P.DOME_BASE_Z + 0.02,
       step=1.5)
mk_obj('dome_base_ring', bm, M_WOOD, 'roof')
sa_ = P.slot_center(P.STAIR_SLOT)
bm = bmesh.new()
sector(bm, P.R_DOME + 0.25, P.R_DOME + 0.72, sa_ + 21, sa_ + 339, P.TERRACE_Z + 0.36, P.TERRACE_Z + 0.44,
       step=1.5)
for i in range(40):
    a = sa_ + 21 + 318 * (i + 0.5) / 40
    p = pol(P.R_DOME + 0.5, a)
    cube(bm, (p.x, p.y, P.TERRACE_Z + 0.18), (0.4, 0.08, 0.36), rz=a)
mk_obj('terrace_bench_ring', bm, M_WOOD, 'roof')

# railing: vertical larch slats on the octagon edge; taller (1.80 m) privacy screen on the
# sunny south side where the daybeds are, 1.20 m elsewhere; gate to the external stair
SUN_FACES = P.SUN_FACES
GATE = (P.STAIR_SLOT,) + P.TERRACE_GATE
bm = bmesh.new()
bmh = bmesh.new()
for k in range(P.N_SLOTS):
    hh = 1.80 if k in SUN_FACES else P.RAIL_H
    fh = P.face_half(P.R_OUT - 0.04)
    n_s = int(2 * fh / 0.10)
    for i in range(n_s):
        t = -fh + 0.05 + i * (2 * fh - 0.1) / (n_s - 1)
        if k == GATE[0] and GATE[1] < t < GATE[2]:
            continue
        c = FP(k, P.R_OUT - 0.04, t, P.TERRACE_Z + hh / 2)
        cube(bm, c, (0.045, 0.05, hh), rz=P.slot_center(k) + 90)
    for tt0, tt1 in ([(-fh, GATE[1]), (GATE[2], fh)] if k == GATE[0] else [(-fh, fh)]):
        c = FP(k, P.R_OUT - 0.04, (tt0 + tt1) / 2, P.TERRACE_Z + hh + 0.025)
        cube(bmh, c, (tt1 - tt0 + 0.02, 0.12, 0.05), rz=P.slot_center(k) + 90)
mk_obj('terrace_railing', bm, M_BATTEN, 'roof')
mk_obj('terrace_handrail', bmh, M_WOOD, 'roof')
# roof edge fascia (octagon)
bm = bmesh.new()
ring_prism(bm, OCT(P.R_OUT - 0.02), OCT(P.R_OUT + 0.04), P.CEIL_UF - 0.1, P.TERRACE_Z + 0.02, step=0.5)
mk_obj('roof_edge', bm, M_CLAD, 'roof')

# planters with grasses along the railing on the non-sunbathing faces
bm = bmesh.new()
bmg = bmesh.new()
for k in (0, 2, 6, 7):
    for t0, t1 in ((-3.6, -1.2), (1.2, 3.6)):
        c = FP(k, P.R_OUT - 0.40, (t0 + t1) / 2, P.TERRACE_Z + 0.27)
        cube(bm, c, (t1 - t0, 0.55, 0.54), rz=P.slot_center(k) + 90)
        for i in range(8):
            cc = FP(k, P.R_OUT - 0.40, t0 + 0.15 + i * (t1 - t0 - 0.3) / 7, P.TERRACE_Z + 0.55)
            res = bmesh.ops.create_icosphere(bmg, subdivisions=2, radius=0.28, matrix=Matrix.Translation(cc))
            for v in res['verts']:
                d = v.co - cc
                v.co = cc + Vector((d.x, d.y, d.z * 1.9 if d.z > 0 else d.z * 0.3))
mk_obj('terrace_planters', bm, M_WOOD_DARK, 'roof')
mk_obj('terrace_grasses', bmg, M_GRASSES, 'roof', smooth=True)

# sun deck: daybeds with thick mattresses on the three south faces
DAYBEDS = []
for k in SUN_FACES:
    for t in P.DAYBED_T:
        DAYBEDS.append((k, t))
for i, (k, t) in enumerate(DAYBEDS):
    rz = P.slot_center(k) + 90
    c = FP(k, 8.15, t, P.TERRACE_Z + 0.16)
    bm = bmesh.new()
    cube(bm, c, (2.05, 2.1, 0.30), rz=rz)
    rounded(mk_obj('daybed_%d' % i, bm, M_DECK_DARK, 'terrace'), 0.03, 3, 0)
    bm = bmesh.new()
    cube(bm, FP(k, 8.15, t, P.TERRACE_Z + 0.41), (1.95, 2.0, 0.20), rz=rz)
    rounded(mk_obj('daybed_mattress_%d' % i, bm, M_WOOL[['sand', 'cream', 'terracotta', 'ochre', 'cream', 'rose'][i]],
                   'terrace'), 0.08, 4, 1)
    for j, tt in enumerate((-0.55, 0.05, 0.62)):
        cushion('daybed_cushion_%d_%d' % (i, j), None, tuple(FP(k, 9.0, t + tt, P.TERRACE_Z + 0.68)),
                (0.55, 0.2, 0.45), M_WOOL[['olive', 'ochre', 'rose', 'wine', 'sand'][(i + j) % 5]],
                rz=P.slot_center(k) + 90, rx=-15, coll_name='terrace')

# sun sails over the daybeds (tensioned triangles on three masts)
bm = bmesh.new()
bmm = bmesh.new()
for k in SUN_FACES:
    A = FP(k, P.R_OUT - 0.25, -3.6, P.TERRACE_Z + 3.0)
    B = FP(k, P.R_OUT - 0.25, 3.6, P.TERRACE_Z + 2.7)
    C = FP(k, 6.55, 0.0, P.TERRACE_Z + 2.35)
    for pnt in (A, B, C):
        cyl(bmm, (pnt.x, pnt.y, (P.TERRACE_Z + pnt.z) / 2 + 0.1), 0.045, pnt.z - P.TERRACE_Z + 0.2, segs=12)
    N_ = 16
    rows = []
    for i in range(N_ + 1):
        row = []
        for j in range(N_ + 1 - i):
            u_, v_ = i / N_, j / N_
            w_ = 1 - u_ - v_
            p = A * w_ + B * u_ + C * v_
            p.z -= 0.35 * (u_ * v_ + v_ * w_ + w_ * u_) * 2.2
            row.append(bm.verts.new(p))
        rows.append(row)
    for i in range(N_):
        for j in range(N_ - i):
            bm.faces.new((rows[i][j], rows[i + 1][j], rows[i][j + 1]))
            if j < N_ - i - 1:
                bm.faces.new((rows[i + 1][j], rows[i + 1][j + 1], rows[i][j + 1]))
mk_obj('terrace_sun_sails', bm, M_SAIL, 'terrace', smooth=True, recalc=False)
mk_obj('terrace_sail_masts', bmm, M_STEEL, 'terrace', smooth=True)
# wooden sun loungers on the west and east faces
for k in (2, 6):
    for t in (-2.7, -1.0):
        rz = P.slot_center(k) + 90
        bm = bmesh.new()
        cube(bm, FP(k, 8.0, t, P.TERRACE_Z + 0.25), (0.7, 1.4, 0.06), rz=rz)
        for dt in (-0.3, 0.3):
            for nd in (7.4, 8.9):
                cube(bm, FP(k, nd, t + dt, P.TERRACE_Z + 0.12), (0.05, 0.05, 0.24), rz=rz)
        ob = mk_obj('lounger_%d_%.1f' % (k, t), bm, M_DECK_DARK, 'terrace')
        # backrest, tilted about the axis along the face
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0, matrix=(Matrix.Translation(FP(k, 8.9, t, P.TERRACE_Z + 0.55)) @
                                                    Matrix.Rotation(rad(P.slot_center(k)), 4, 'Z') @
                                                    Matrix.Rotation(rad(55), 4, 'Y') @
                                                    Matrix.Diagonal((0.75, 0.7, 0.05, 1))))
        mk_obj('lounger_back_%d_%.1f' % (k, t), bm, M_DECK_DARK, 'terrace')
        cushion('lounger_pad_%d_%.1f' % (k, t), None, tuple(FP(k, 8.0, t, P.TERRACE_Z + 0.31)), (1.35, 0.64, 0.07),
                M_WOOL['cream'], rz=P.slot_center(k), squish=0.1, coll_name='terrace')

# ---------------------------------------------------------------------------
# external stair on the stair segment's face: 2nd escape route, ground <-> upper floor <-> terrace
# ---------------------------------------------------------------------------
K_ = P.STAIR_SLOT
RZ_ = P.slot_center(K_) + 90
W_ = P.EXT_W
G_ = P.EXT_GOING
T_LAND = P.EXT_T_LAND        # upper-floor landing from here to the face end
n_in0, n_in1 = P.R_OUT + 0.05, P.R_OUT + 0.05 + W_          # run 1 (down to the ground), against the wall
n_out0, n_out1 = n_in1, n_in1 + W_                           # run 2 (up to the terrace), outer lane
bm = bmesh.new()
bms = bmesh.new()
R1 = P.STAIR_RISE
for i in range(1, P.STAIR_RISERS):
    ztop = P.FFL_UF - i * R1
    t = T_LAND - (i - 0.5) * G_
    cube(bm, FP(K_, (n_in0 + n_in1) / 2, t, ztop - 0.025), (G_ + 0.03, W_, 0.05), rz=RZ_ - 90 + 90)
R2 = P.TERRACE_RISE
for j in range(1, P.TERRACE_RISERS):
    ztop = P.FFL_UF + j * R2
    t = T_LAND - (j - 0.5) * G_
    cube(bm, FP(K_, (n_out0 + n_out1) / 2, t, ztop - 0.025), (G_ + 0.03, W_, 0.05), rz=RZ_ - 90 + 90)
t_top1 = T_LAND - (P.TERRACE_RISERS - 1) * G_
# landings
land_uf = (T_LAND, P.face_half(P.R_OUT) - 0.05)
cube(bm, FP(K_, (n_in0 + n_out1) / 2, sum(land_uf) / 2, P.FFL_UF - 0.08), (land_uf[1] - land_uf[0], 2 * W_, 0.16),
     rz=RZ_)
land_top = (GATE[1] - 0.05, t_top1)
cube(bm, FP(K_, (P.R_OUT - 0.02 + n_out1) / 2, sum(land_top) / 2, P.TERRACE_Z - 0.08),
     (land_top[1] - land_top[0], n_out1 - P.R_OUT + 0.02, 0.16), rz=RZ_)
mk_obj('ext_stair_treads', bm, M_DECK_DARK, 'ext_stair')
# stringers (steel) as sloped boxes, posts, guard rails
t_bot = T_LAND - (P.STAIR_RISERS - 1) * G_


def sloped(bm_, nd, t0, z0, t1, z1, w, h):
    a = FP(K_, nd, t0, z0)
    b = FP(K_, nd, t1, z1)
    d = b - a
    rot = Vector((1, 0, 0)).rotation_difference(d.normalized()).to_matrix().to_4x4()
    M = Matrix.Translation((a + b) / 2) @ rot @ Matrix.Diagonal((d.length, w, h, 1))
    bmesh.ops.create_cube(bm_, size=1.0, matrix=M)


for nd in (n_in0 + 0.03, n_in1 - 0.03):
    sloped(bms, nd, T_LAND, P.FFL_UF - 0.1, t_bot, 0.0, 0.03, 0.22)
for nd in (n_out0 + 0.03, n_out1 - 0.03):
    sloped(bms, nd, T_LAND, P.FFL_UF - 0.1, t_top1, P.TERRACE_Z - 0.1, 0.03, 0.22)
for (nd, t, ztop) in ((n_out1 - 0.05, land_uf[1] - 0.1, P.FFL_UF), (n_out1 - 0.05, T_LAND, P.FFL_UF),
                      (n_out1 - 0.05, 0.0, P.FFL_UF + 0.1 + (T_LAND / G_) * R2),
                      (n_out1 - 0.05, land_top[0] + 0.1, P.TERRACE_Z), (n_out1 - 0.05, t_top1, P.TERRACE_Z),
                      (n_in1, t_bot + 0.1, 0.9)):
    cube(bms, FP(K_, nd, t, ztop / 2), (0.08, 0.08, ztop), rz=RZ_)
# guard: slatted rail along the outer edge and between the lanes
for (nd, t0, z0, t1, z1) in ((n_out1 - 0.03, T_LAND, P.FFL_UF, t_top1, P.TERRACE_Z),
                             (n_out0 + 0.03, T_LAND, P.FFL_UF, t_top1, P.TERRACE_Z)):
    sloped(bms, nd, t0, z0 + 1.0, t1, z1 + 1.0, 0.05, 0.05)
    n_bal = int(abs(t1 - t0) / 0.12)
    for i in range(n_bal):
        f = (i + 0.5) / n_bal
        tt = t0 + (t1 - t0) * f
        zz = z0 + (z1 - z0) * f
        cube(bms, FP(K_, nd, tt, zz + 0.5), (0.02, 0.02, 1.0), rz=RZ_)
for (t0, t1, zz) in ((land_uf[0], land_uf[1], P.FFL_UF), (land_top[0], land_top[1], P.TERRACE_Z)):
    cube(bms, FP(K_, n_out1 - 0.03, (t0 + t1) / 2, zz + 1.0), (t1 - t0, 0.05, 0.05), rz=RZ_)
    for i in range(int((t1 - t0) / 0.12)):
        cube(bms, FP(K_, n_out1 - 0.03, t0 + 0.06 + i * 0.12, zz + 0.5), (0.02, 0.02, 1.0), rz=RZ_)
mk_obj('ext_stair_steel', bms, M_STEEL, 'ext_stair')
# climbing plant on the external stair posts
vine('vine_ext_stair', K_, 3.9, 4.0, 777, spread=0.4)

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
# 9. annex against the NE and N faces: entrance, changing + showers, WC, tech
# ---------------------------------------------------------------------------
A0, A1 = 22.5, 112.5
AO = P.R_OUT + P.ANNEX_D          # outer apothem
AC = P.R_OUT + P.ANNEX_CORR       # corridor wall apothem
H = P.ANNEX_H
T = 0.35
bm = bmesh.new()
for k in (7, 0):
    face_wall(bm, k, [(-3.4, 3.4, 2.05, 2.85)] if k == 0 else [(-3.0, 3.0, 2.05, 2.85)], 0.0, H,
              nin=AO - T, nout=AO)
# end walls along the corner rays; entrance door in the east end
door_r = (P.octo_r(A0, P.R_OUT) + P.octo_r(A0, AO)) / 2 + 0.6
for a, gaps in ((A0, [(door_r - 1.0, door_r + 1.0)]), (A1, [])):
    r0, r1 = P.octo_r(a, P.R_OUT), P.octo_r(a, AO - T)
    pts = [r0] + [g for gp in gaps for g in gp] + [r1]
    off = pol(T / 2, a + 90 if a == A0 else a - 90)
    for i in range(0, len(pts), 2):
        seg_box(bm, pol(pts[i], a) + off, pol(pts[i + 1], a) + off, T, 0.0, H)
    for g0, g1 in gaps:
        seg_box(bm, pol(g0, a) + off, pol(g1, a) + off, T, 2.5, H)
ann = mk_obj('annex_walls', bm, [M_CLAD, M_CLAY_ROOM], 'annex')
def annex_mat(c, n):
    if abs(n.z) > 0.5:
        return 1
    a = math.degrees(math.atan2(c.y, c.x))
    radial = Vector((c.x, c.y, 0)).normalized()
    ccw = Vector((-radial.y, radial.x, 0))
    if n.dot(radial) > 0.6 and math.hypot(c.x, c.y) > P.R_OUT + P.ANNEX_D - 0.5:
        return 0
    if abs(a - A1) < 4 and n.dot(ccw) > 0.6:
        return 0
    if abs(a - A0) < 4 and n.dot(ccw) < -0.6:
        return 0
    return 1


set_face_mats(ann, annex_mat)
# corridor wall (doors) and partitions
bm = bmesh.new()
face_wall(bm, 7, [(-2.9, -1.9, 0, 2.2), (-1.35, -0.45, 0, 2.2), (0.6, 1.6, 0, 2.2), (2.9, 3.9, 0, 2.2)], 0.0, H,
          nin=AC, nout=AC + 0.12)
face_wall(bm, 0, [(-3.2, -2.2, 0, 2.2), (-0.9, 0.9, 0, 2.4), (2.1, 3.1, 0, 2.2)], 0.0, H, nin=AC, nout=AC + 0.12)
for a in (36.5, 44.0, 90.0 + 11.0, 90.0 + 16.0):
    seg_box(bm, pol(P.octo_r(a, AC + 0.12), a), pol(P.octo_r(a, AO - T), a), 0.12, 0.0, H)
seg_box(bm, pol(P.octo_r(67.5, AC + 0.12), 67.5), pol(P.octo_r(67.5, AO - T), 67.5), 0.12, 0.0, H)
mk_obj('annex_partitions', bm, M_CLAY_ROOM, 'annex')
bm = bmesh.new()
ring_prism(bm, OCT(P.R_OUT - 0.02), OCT(AO + 0.45), H, H + 0.35, a0=A0 - 0.8, a1=A1 + 0.8, step=0.5)
aroof = mk_obj('annex_roof', bm, [M_CEIL, M_SEDUM, M_CLAD], 'annex')
set_face_mats(aroof, lambda c, n: 1 if n.z > 0.5 else (0 if n.z < -0.5 else 2))
bm = bmesh.new()
ring_prism(bm, OCT(P.R_OUT), OCT(AO), -0.05, 0.0, a0=A0, a1=A1, step=0.5)
mk_obj('annex_floor', bm, M_FLOOR_ROOM, 'annex')
bm = bmesh.new()
for k, w in ((7, 3.0), (0, 3.4)):
    q = [FP(k, AO - 0.18, -w, 2.05), FP(k, AO - 0.18, w, 2.05), FP(k, AO - 0.18, w, 2.85), FP(k, AO - 0.18, -w, 2.85)]
    bm.faces.new([bm.verts.new(p) for p in q])
off = pol(0.2, A0 + 90)
p0, p1 = pol(door_r - 1.0, A0) + off, pol(door_r + 1.0, A0) + off
seg_box(bm, p0, p1, 0.02, 0.0, 2.5)
mk_obj('annex_glass', bm, M_GLASS, 'annex')
bm = bmesh.new()
for zz in (0.05, 2.45):
    seg_box(bm, p0, p1, 0.1, zz - 0.05, zz + 0.05)
for pp in (p0, p1, (p0 + p1) / 2):
    cube(bm, (pp.x, pp.y, 1.25), (0.1, 0.1, 2.5), rz=A0)
mk_obj('annex_entrance_frame', bm, M_WOOD_DARK, 'annex')
bm = bmesh.new()
pc = pol(door_r, A0) + pol(0.9, A0 - 90)
cube(bm, (pc.x, pc.y, 2.85), (3.2, 1.8, 0.12), rz=A0)
mk_obj('annex_canopy', bm, M_WOOD, 'annex')
vine('vine_annex_0', 7, -3.6, 3.0, 901)
vine('vine_annex_1', 0, 3.8, 3.0, 902)

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
# deep window seats under the big ground-floor windows
i = 0
for k in range(P.N_SLOTS):
    for (t0, t1, z0, z1, kind) in FACE_OPEN[k]:
        if kind != 'window_gf':
            continue
        tc, w = (t0 + t1) / 2, t1 - t0 + 0.3
        rz = P.slot_center(k) + 90
        bm = bmesh.new()
        cube(bm, FP(k, P.R_IN - 0.28, tc, 0.19), (w, 0.58, 0.38), rz=rz)
        rounded(mk_obj('hall_window_seat_%d' % i, bm, M_WOOD, 'furnishing'), 0.02, 2, 0)
        bm = bmesh.new()
        cube(bm, FP(k, P.R_IN - 0.28, tc, 0.43), (w - 0.06, 0.54, 0.09), rz=rz)
        rounded(mk_obj('hall_window_pad_%d' % i, bm, M_WOOL[cols[(i * 3) % 8]], 'furnishing'), 0.04, 3, 1)
        for j, dt in enumerate((-0.6, 0.55)):
            cushion('hall_window_cushion_%d_%d' % (i, j), None, tuple(FP(k, P.R_IN - 0.12, tc + dt, 0.7)),
                    (0.5, 0.18, 0.45), M_WOOL[cols[(i + j) % 8]], rz=rz, rx=-10)
        i += 1
# stacked floor mats + blankets against the (windowless) annex side
for j in range(5):
    bm = bmesh.new()
    cube(bm, FP(6, P.R_IN - 0.45, -2.9, 0.05 + j * 0.09), (1.9, 0.75, 0.08), rz=P.slot_center(6) + 90)
    rounded(mk_obj('hall_mat_stack_%d' % j, bm, M_WOOL[cols[j]], 'furnishing'), 0.03, 2, 1)
# tea / party bar on the windowless NE wall: curved clay counter with a timber top, back shelf
bar_pts = [tuple(FP(7, P.R_IN - 1.25 + y, x + 0.6))[:2] for x, y in superellipse(0, 0, 1.9, 0.38, n=2.2, N=64)]
extrude_outline('hall_bar_counter', bar_pts, 0.0, 1.02, M_CLAY_HALL, None, bevel=0.06, seg=4)
bar_top = [tuple(FP(7, P.R_IN - 1.25 + y, x + 0.6))[:2] for x, y in superellipse(0, 0, 2.0, 0.46, n=2.2, N=64)]
extrude_outline('hall_bar_top', bar_top, 1.02, 1.08, M_WOOD, None, bevel=0.02, seg=3)
bm = bmesh.new()
for zz in (1.35, 1.85):
    cube(bm, FP(7, P.R_IN - 0.15, 0.6, zz), (3.4, 0.28, 0.04), rz=P.slot_center(7) + 90)
mk_obj('hall_bar_shelves', bm, M_WOOD, 'furnishing')
bm = bmesh.new()
for i in range(9):
    cyl(bm, FP(7, P.R_IN - 0.15, -0.9 + i * 0.36, 1.37 + 0.09 + 0.5 * (i % 2)), 0.05, 0.18, segs=12)
mk_obj('hall_bar_jars', bm, M_TERRACOTTA, 'furnishing', smooth=True)
for i in range(4):
    c_ = FP(7, P.R_IN - 2.05, -0.8 + i * 0.95, 0.35)
    cushion('hall_bar_pouf_%d' % i, None, tuple(c_), (0.45, 0.45, 0.35), M_WOOL[['umber', 'ochre', 'wine', 'olive'][i]],
            squish=0.2)
# floor lanterns in the octagon corners (night)
for i in range(P.N_SLOTS):
    a = P.partition_angle(i)
    if i in (P.STAIR_SLOT, P.STAIR_SLOT + 1):
        continue
    p = pol(P.octo_r(a, P.R_IN) - 0.8, a)
    lantern('hall_lantern_%d' % i, (p.x, p.y, 0.55), 0.24, 1.1)
# warm uplights at the column heads (night)
for k, a in enumerate(PILLAR_ANGLES):
    li = bpy.data.lights.new('pillar_uplight_%d' % k, 'SPOT')
    li.energy = 0.0
    li.spot_size = rad(110)
    li.spot_blend = 0.8
    li.color = (1.0, 0.82, 0.64)
    li.shadow_soft_size = 0.1
    lo = bpy.data.objects.new('pillar_uplight_%d' % k, li)
    lo.location = pol(P.R_PILLAR + 0.3, a, 2.6)
    lo.rotation_euler = (math.pi, 0, 0)
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
# rooms: one sitting on the nest in the (half-open) room of view 4, one resting in another room
kv = 3
ang = P.slot_center(kv)
pr = Matrix.Rotation(rad(ang), 4, 'Z') @ Vector((7.75, -0.35, 0))
figure('person_room_sit', pose_sit_cross(), (pr.x, pr.y, P.FFL_UF + 0.47), rz=ang + 90)
ang2 = P.slot_center(7)
pr2 = Matrix.Rotation(rad(ang2), 4, 'Z') @ Vector((8.6, 0.2, 0))
figure('person_room_lie', pose_lie_side(), (pr2.x, pr2.y, P.FFL_UF + 0.47), rz=ang2)
# roof terrace: two on the daybeds, one on the bench ring
for i_, (k_, t_, pose_) in enumerate(((4, -2.25, pose_lie_back('head')), (3, 2.25, pose_lie_side()))):
    c_ = FP(k_, 8.05, t_, P.TERRACE_Z + 0.50)
    figure('person_terrace_%d' % i_, pose_, (c_.x, c_.y, c_.z), rz=P.slot_center(k_) - 90 + (0 if i_ == 0 else 90))
cb_ = pol(P.R_DOME + 0.5, 255, P.TERRACE_Z + 0.44)
figure('person_terrace_bench', pose_sit_knees(), (cb_.x, cb_.y, cb_.z - 0.1), rz=255 - 90)

# ---------------------------------------------------------------------------
# 12. carvings: bodies, touch and embrace in low relief on the columns and the entrance arch.
#     The relief is made from the same sculptural figures as the people in the renderings:
#     each group is posed, scanned as a height map (ray casting), laid out on the surface
#     and displaced into the timber.
# ---------------------------------------------------------------------------
import numpy as np  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402
from PIL import Image  # noqa: E402

CARVE_DIR = os.path.join(HERE, 'carvings')
os.makedirs(CARVE_DIR, exist_ok=True)


def _arms(p, **kw):
    for k_, v_ in kw.items():
        p[k_] = v_
    return p


def pose_embrace():
    return _arms(mirror_pose(STAND), head=(0, 0.07, 1.61),
                 le=(0.21, 0.20, 1.24), lw=(0.12, 0.38, 1.30), lh=(0.06, 0.42, 1.31),
                 re=(-0.21, 0.20, 1.16), rw=(-0.12, 0.36, 1.04), rh=(-0.06, 0.40, 1.02))


def pose_dance():
    return _arms(mirror_pose(STAND), pelvis=(0.04, 0, 0.95), head=(-0.03, 0.02, 1.62),
                 le=(0.30, 0.05, 1.66), lw=(0.24, 0.06, 1.92), lh=(0.21, 0.06, 2.0),
                 re=(-0.45, 0.02, 1.40), rw=(-0.68, 0.05, 1.50), rh=(-0.75, 0.05, 1.53),
                 rk=(-0.16, 0.14, 0.52), ra=(-0.12, -0.04, 0.16), rt=(-0.12, 0.08, 0.06))


def pose_reach():
    return _arms(mirror_pose(STAND), head=(0, 0.0, 1.63),
                 le=(0.20, 0.03, 1.72), lw=(0.15, 0.05, 1.97), lh=(0.12, 0.05, 2.05),
                 re=(-0.20, 0.03, 1.72), rw=(-0.15, 0.05, 1.97), rh=(-0.12, 0.05, 2.05))


def pose_shoulders(side):
    p = mirror_pose(STAND)
    if side in ('mid', 'l'):   # right arm over the neighbour's shoulder (towards -x)
        _arms(p, re=(-0.34, 0.02, 1.38), rw=(-0.56, 0.02, 1.42), rh=(-0.62, 0.02, 1.43))
    if side in ('mid', 'r'):
        _arms(p, le=(0.34, 0.02, 1.38), lw=(0.56, 0.02, 1.42), lh=(0.62, 0.02, 1.43))
    return p


CARVE_GROUPS = {
    # name: (view axis, [(pose, location, rz)])
    'embrace': ('X', [(pose_embrace(), (0, 0, 0), 0), (pose_embrace(), (0, 0.30, 0), 180)]),
    'dance': ('Y', [(pose_dance(), (0, 0, 0), 0)]),
    'reach': ('Y', [(pose_reach(), (0, 0, 0), 0)]),
    'trio': ('Y', [(pose_shoulders('l'), (0.46, 0, 0), 0), (pose_shoulders('mid'), (0, 0, 0), 0),
                   (pose_shoulders('r'), (-0.46, 0, 0), 0)]),
    'lap': ('X', [(pose_sit_cross(), (0, 0, 0), 0), (pose_sit_knees(), (0, 0.40, 0.10), 180)]),
    'lovers': ('X', [(pose_lie_back('open'), (0, 0, 0), 0), (pose_lie_side(), (0.30, 0.25, 0.06), 0)]),
    'rest': ('X', [(pose_sit_lean(), (0, 0, 0), 0), (pose_lie_back('head'), (0, 0.62, 0.0), 180)]),
}


def carve_heightmap(name, px):
    axis, members = CARVE_GROUPS[name]
    obs = [figure('carve_%s_%d' % (name, i), pose, loc, rz=rz, parent_coll='tmp')
           for i, (pose, loc, rz) in enumerate(members)]
    bpy.context.view_layer.update()
    verts, polys = [], []
    for ob in obs:
        off = len(verts)
        mw = ob.matrix_world
        verts += [mw @ v.co for v in ob.data.vertices]
        polys += [[off + i for i in p.vertices] for p in ob.data.polygons]
    tree = BVHTree.FromPolygons(verts, polys)
    ia, ib, idp = (1, 2, 0) if axis == 'X' else (0, 2, 1)
    lo = [min(v[i] for v in verts) for i in range(3)]
    hi = [max(v[i] for v in verts) for i in range(3)]
    W = int((hi[ia] - lo[ia]) / px) + 4
    H = int((hi[ib] - lo[ib]) / px) + 4
    depth = np.full((H, W), np.nan)
    d = [0.0, 0.0, 0.0]
    d[idp] = 1.0
    d = Vector(d)
    for r in range(H):
        zb = hi[ib] - (r - 2) * px
        for c in range(W):
            o = [0.0, 0.0, 0.0]
            o[ia] = lo[ia] + (c - 2) * px
            o[ib] = zb
            o[idp] = lo[idp] - 1.0
            hit = tree.ray_cast(Vector(o), d)
            if hit[0] is not None:
                depth[r, c] = hit[3]
    for ob in obs:
        bpy.data.objects.remove(ob)
    m = ~np.isnan(depth)
    # nearer = higher, over a fixed 0.45 m depth range (so single bodies keep their volume)
    dn = np.clip((depth - np.nanmin(depth)) / 0.45, 0, 1)
    h = np.where(m, 0.45 + 0.55 * (1.0 - dn), 0.0)
    # rounded edges like a carved relief: distance to the silhouette edge (in px)
    dist = np.where(m, 1.0, 0.0)
    acc = dist.copy()
    cur = m.copy()
    R = max(3, int(0.05 / px))
    for i in range(R):
        cur = cur & np.roll(cur, 1, 0) & np.roll(cur, -1, 0) & np.roll(cur, 1, 1) & np.roll(cur, -1, 1)
        acc += cur
    rnd = np.sqrt(1 - (1 - np.clip(acc / R, 0, 1)) ** 2)
    return h * rnd


def soften(a, it=2):
    for _ in range(it):
        a = (a + np.roll(a, 1, 0) + np.roll(a, -1, 0) + np.roll(a, 1, 1) + np.roll(a, -1, 1)) / 5.0
    return a


def place(tex, hm, cu, cv_from_top, wrap=True):
    """Stamp height map hm (centre at column cu, row cv) into tex with max()."""
    H, W = hm.shape
    r0 = int(cv_from_top - H / 2)
    c0 = int(cu - W / 2)
    for r in range(H):
        rr = r0 + r
        if not 0 <= rr < tex.shape[0]:
            continue
        cols = (np.arange(W) + c0)
        if wrap:
            cols %= tex.shape[1]
            tex[rr, cols] = np.maximum(tex[rr, cols], hm[r])
        else:
            ok = (cols >= 0) & (cols < tex.shape[1])
            tex[rr, cols[ok]] = np.maximum(tex[rr, cols[ok]], hm[r][ok])


def save_height(tex, name):
    path = os.path.join(CARVE_DIR, name + '.png')
    Image.fromarray((np.clip(tex, 0, 1) * 65535).astype(np.uint16)).save(path)
    img = bpy.data.images.load(path)
    img.colorspace_settings.name = 'Non-Color'
    img.pack()
    return img


def mat_carved(name):
    m, b = new_mat(name, srgb('#B7874F'))
    v = b.mapping(b.coord(), scale=(6, 6, 0.25))
    t = b.n('ShaderNodeTexWave', wave_type='RINGS', rings_direction='Z')
    t.inputs['Scale'].default_value = 2.0
    t.inputs['Distortion'].default_value = 6.0
    b.l(v, t.inputs['Vector'])
    col = b.ramp(t.outputs['Fac'], [(0.25, srgb('#AE7E48')), (0.85, srgb('#C99C66'))])
    ao = b.n('ShaderNodeAmbientOcclusion', samples=12, only_local=True)
    ao.inputs['Distance'].default_value = 0.05
    b.l(col, ao.inputs['Color'])
    shade = b.ramp(ao.outputs['AO'], [(0.0, srgb('#6A4A2C')), (1.0, (1, 1, 1, 1))])
    col2 = b.mix(1.0, col, shade, blend='MULTIPLY')
    b.output(b.principled(col2, rough=0.5, Coat_Weight=0.1, Coat_Roughness=0.3))
    return m


M_CARVED = mat_carved('carved_larch')

# height maps at 3 mm per pixel of the carved surface
PX = 0.003
SCALE_FIG = 0.40            # carved figures ~ 75 cm tall on the columns
HM = {n: soften(carve_heightmap(n, PX / SCALE_FIG)) for n in CARVE_GROUPS}

# columns: 3 panels each, winding round the shaft
Z0, Z1 = 0.06, P.RING_BEAM_BOT - 0.12
R_SHAFT = P.PILLAR_D / 2 - 0.03
CIRC = 2 * math.pi * R_SHAFT
TW, TH = int(CIRC / PX), int((Z1 - Z0) / PX)
LAYOUT = [[('dance', 0.10, 0.55), ('embrace', 0.55, 1.45), ('lovers', 0.25, 2.45)],
          [('trio', 0.60, 0.55), ('lap', 0.12, 1.40), ('reach', 0.50, 2.40)],
          [('embrace', 0.30, 0.55), ('rest', 0.80, 1.40), ('dance', 0.25, 2.40)],
          [('trio', 0.80, 0.55), ('lap', 0.80, 1.50), ('dance', 0.80, 2.42)]]
for ci, a in enumerate(PILLAR_ANGLES):
    tex = np.zeros((TH, TW))
    for (g, u, v) in LAYOUT[ci % len(LAYOUT)]:
        place(tex, HM[g], u * TW, TH - v / PX)
    img = save_height(soften(tex, 1), 'column_%d' % ci)
    # UV cylinder
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new('UVMap')
    NS, NZ = 180, 620
    c = pol(P.R_PILLAR, a)
    rows = []
    for i in range(NZ + 1):
        z = Z0 + (Z1 - Z0) * i / NZ
        rows.append([bm.verts.new((c.x + R_SHAFT * math.cos(2 * math.pi * j / NS),
                                   c.y + R_SHAFT * math.sin(2 * math.pi * j / NS), z)) for j in range(NS)])
    for i in range(NZ):
        for j in range(NS):
            j2 = (j + 1) % NS
            f = bm.faces.new((rows[i][j], rows[i][j2], rows[i + 1][j2], rows[i + 1][j]))
            for lp, (uu, vv) in zip(f.loops, ((j, i), (j + 1, i), (j + 1, i + 1), (j, i + 1))):
                lp[uvl].uv = (uu / NS, vv / NZ)
    ob = mk_obj('column_carved_%d' % ci, bm, M_CARVED, 'structure', smooth=True, recalc=False)
    for p_ in ob.data.polygons:
        if (Vector(p_.center) - Vector((c.x, c.y, p_.center[2]))).dot(Vector(p_.normal)) < 0:
            p_.flip()
    tx_ = bpy.data.textures.new('carve_col_%d' % ci, 'IMAGE')
    tx_.image = img
    tx_.extension = 'REPEAT'
    dm = ob.modifiers.new('carving', 'DISPLACE')
    dm.texture = tx_
    dm.texture_coords = 'UV'
    dm.strength = 0.048
    dm.mid_level = 0.0

# grazing accent light on each carved column (evening)
for ci, a in enumerate(PILLAR_ANGLES):
    li = bpy.data.lights.new('carving_spot_%d' % ci, 'SPOT')
    li.energy = 0.0
    li.spot_size = rad(32)
    li.spot_blend = 0.6
    li.color = (1.0, 0.80, 0.60)
    li.shadow_soft_size = 0.03
    lo = bpy.data.objects.new('carving_spot_%d' % ci, li)
    c = pol(P.R_PILLAR, a)
    src = pol(P.R_PILLAR + 0.75, a - 9, P.CEIL_GF - 0.28)
    lo.location = src
    lo.rotation_euler = (Vector((c.x, c.y, 1.5)) - src).to_track_quat('-Z', 'Y').to_euler()
    lo['lantern_power'] = 120.0
    coll('night_lights').objects.link(lo)

# entrance arch on the inside of the hall door (face 0): the figures rise up the jambs and
# meet as lovers at the top
KA = P.ENTRY_SLOT
AW, AH = 2.70, 3.30
ATW, ATH = int(AW / PX), int(AH / PX)
tex = np.zeros((ATH, ATW))
hm_reach = soften(carve_heightmap('reach', PX / 0.82))
hm_dance = soften(carve_heightmap('dance', PX / 0.70))
place(tex, hm_reach, (0.225) / PX, ATH - (0.25 + hm_reach.shape[0] * PX / 2) / PX, wrap=False)
place(tex, hm_reach[:, ::-1], (AW - 0.225) / PX, ATH - (0.25 + hm_reach.shape[0] * PX / 2) / PX, wrap=False)
hm_top = soften(carve_heightmap('lovers', PX / 0.62))
place(tex, hm_top, ATW / 2, ATH - 3.07 / PX, wrap=False)
img = save_height(soften(tex, 1), 'entrance_arch')
arr = np.array(Image.open(os.path.join(CARVE_DIR, 'entrance_arch.png')), dtype=np.float64) / 65535.0


def in_band(t, z):
    outer = abs(t) <= AW / 2 and (z <= 2.35 or (abs(t) < AW / 2 and
                                                  z <= 2.35 + 0.95 * math.sqrt(max(0, 1 - (t / (AW / 2)) ** 2))))
    inner = abs(t) < 0.9 and (z < 2.35 or z < 2.35 + 0.55 * math.sqrt(max(0, 1 - (t / 0.9) ** 2)))
    return outer and not inner


bm = bmesh.new()
STEP = 0.012
NT, NZ_ = int(AW / STEP), int(AH / STEP)
grid = {}
nd0 = P.R_IN - 0.13
for i in range(NT + 1):
    for j in range(NZ_ + 1):
        t = -AW / 2 + i * STEP
        z = j * STEP
        col_ = min(int((t + AW / 2) / PX), ATW - 1)
        row_ = min(int((AH - z) / PX), ATH - 1)
        h = arr[row_, col_]
        grid[i, j] = (t, z, h)
vmap = {}
for i in range(NT):
    for j in range(NZ_):
        tc = -AW / 2 + (i + 0.5) * STEP
        zc_ = (j + 0.5) * STEP
        if not in_band(tc, zc_):
            continue
        quad = []
        for (a_, b_) in ((i, j), (i, j + 1), (i + 1, j + 1), (i + 1, j)):
            if (a_, b_) not in vmap:
                t, z, h = grid[a_, b_]
                vmap[a_, b_] = bm.verts.new(FP(KA, nd0 - 0.055 * h, t, z))
            quad.append(vmap[a_, b_])
        bm.faces.new(quad)
arch = mk_obj('entrance_arch_carved', bm, M_CARVED, 'structure', smooth=True, recalc=False)
for side in (-1, 1):
    li = bpy.data.lights.new('arch_spot_%d' % side, 'SPOT')
    li.energy = 0.0
    li.spot_size = rad(45)
    li.spot_blend = 0.5
    li.color = (1.0, 0.80, 0.60)
    li.shadow_soft_size = 0.03
    lo = bpy.data.objects.new('arch_spot_%d' % side, li)
    src = FP(KA, P.R_IN - 0.55, side * 0.9, P.CEIL_GF - 0.25)
    lo.location = src
    lo.rotation_euler = (FP(KA, P.R_IN - 0.12, side * 1.1, 1.3) - src).to_track_quat('-Z', 'Y').to_euler()
    lo['lantern_power'] = 90.0
    coll('night_lights').objects.link(lo)
so = arch.modifiers.new('solid', 'SOLIDIFY')
so.thickness = 0.10
so.offset = -1.0

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
