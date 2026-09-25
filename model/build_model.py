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
    bm_ = bmesh.new()                      # thin slabs can come out of the boolean with flipped faces
    bm_.from_mesh(new)
    bmesh.ops.recalc_face_normals(bm_, faces=bm_.faces[:])
    bm_.to_mesh(new)
    bm_.free()
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


M_CLAY_HALL = mat_clay('clay_hall', '#D8BD98', '#E3CCAC')
M_CLAY_ROOM = mat_clay('clay_room', '#E0C6A3', '#EAD5B8', scale=1.6)
M_RENDER = mat_clay('lime_render_ext', '#B98F68', '#C49A72', scale=0.6)
M_PLINTH = mat_clay('plinth_stone', '#6F665C', '#80776B', scale=3.0)
M_FLOOR_HALL = mat_boards('floor_hall_oak', '#C8A073', '#D6B086', '#6E5236', board_w=0.18,
                          board_l=2.6)
M_FLOOR_WALK = mat_boards('floor_walkway_oak', '#C8A073', '#D6B086', '#6E5236',
                          board_w=0.14, board_l=1.8, polar=True)
M_FLOOR_ROOM = mat_boards('floor_room_oak', '#CCA276', '#D9B489', '#6E5236', board_w=0.16,
                          board_l=2.0)
M_CEIL = mat_boards('ceiling_spruce', '#E2C9A2', '#EBD4B0', '#8A7156', board_w=0.12,
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
M_TADELAKT = mat_clay('tadelakt_lime', '#C9A882', '#D6B892', scale=2.0)
for n_ in M_TADELAKT.node_tree.nodes:
    if n_.bl_idname == 'ShaderNodeBsdfPrincipled':
        n_.inputs['Roughness'].default_value = 0.35
        n_.inputs['Coat Weight'].default_value = 0.35
M_CERAMIC = mat_simple('ceramic_white', '#EDE8DF', rough=0.15, Coat_Weight=0.4)
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

# path from the east, curving round to the entrance on the north face
bm = bmesh.new()
left, right = [], []
for i in range(70):
    t = i / 69
    a = 90 - 80 * t
    r_ = P.R_OUT + P.ANNEX_D + 2.2 + 22 * t ** 1.6
    left.append(bm.verts.new(pol(r_ - 0.9, a, -0.03)))
    right.append(bm.verts.new(pol(r_ + 0.9, a, -0.03)))
for i in range(69):
    bm.faces.new((left[i], right[i], right[i + 1], left[i + 1]))
ob = mk_obj('site_path', bm, M_GRAVEL, 'site', recalc=False)
for p in ob.data.polygons:
    if p.normal.z < 0:
        p.flip()
bm = bmesh.new()
cyl(bm, tuple(FP(P.ENTRY_SLOT, P.R_OUT + P.ANNEX_D + 2.2, 0, -0.035)), 3.0, 0.03, segs=48)
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
SHUTTER = {0: 'half', 2: 'half', 3: 'open', 4: 'open', 5: 'half', 6: 'closed', 7: 'open'}
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
beams_ob = mk_obj('radial_beams', bm, M_WOOD, 'structure')

s_a0 = P.partition_angle(P.STAIR_SLOT)
s_a1 = P.partition_angle(P.STAIR_SLOT + 1)
bm = bmesh.new()
ring_prism(bm, P.RING_BEAM_OUT, OCT(P.R_IN + 0.02), P.CEIL_GF, P.FFL_UF - 0.01, step=0.5)
slab = mk_obj('upper_slab', bm, [M_CEIL, M_WOOD], 'structure')
set_face_mats(slab, lambda c, n: 0 if n.z < -0.5 else 1)
bm = bmesh.new()
sector(bm, P.R_PAD_OUT - 0.02, P.RING_BEAM_OUT, 0, 360, P.RING_BEAM_TOP, P.FFL_UF - 0.01, step=1.5)
mk_obj('upper_slab_edge', bm, M_WOOD, 'structure')
# floor finish of the stair segment on the upper floor
bm = bmesh.new()
ring_prism(bm, P.APOTHEM_FRONT - 0.05, OCT(P.R_IN), P.FFL_UF - 0.012, P.FFL_UF - 0.0015, a0=s_a0, a1=s_a1, step=0.5)  # just under the walkway floor where they overlap
plat = mk_obj('stair_platform_floor', bm, M_FLOOR_ROOM, 'structure')

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
DOOR_STATES = {0: 'closed', 2: 'open', 3: 'half', 4: 'closed', 5: 'open', 6: 'closed', 7: 'half'}


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


def potted_plant(name, parent, x, y, z, h=1.1, seed=0, reach=None):
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
        s = r.uniform(0.16, 0.26)
        if reach:                                   # keep the leaves within `reach` of the pot axis (walls, fronts)
            L = min(L, max(0.15, (reach - 1.8 * s) / math.cos(rad(el))))
        base = Vector((x, y, z + 0.4))
        d = Vector((math.cos(rad(a)) * math.cos(rad(el)), math.sin(rad(a)) * math.cos(rad(el)), math.sin(rad(el))))
        tip = base + d * L
        rot = Vector((0, 0, 1)).rotation_difference(d).to_matrix().to_4x4()
        cyl(bm, (base + tip) / 2, 0.008, L, segs=5, rot=rot)
        res = bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0)
        lrot = (Matrix.Rotation(rad(a), 4, 'Z') @ Matrix.Rotation(rad(-r.uniform(10, 40)), 4, 'Y'))
        bmesh.ops.transform(bm, verts=res['verts'], matrix=Matrix.Translation(tip + d * s * 0.8) @ lrot @
                            Matrix.Diagonal((s, s * 0.6, 0.012, 1)))
    ob = mk_obj(name + '_leaves', bm, M_PLANT, 'furnishing', smooth=True)
    ob.parent = parent


def indoor_tree(name, x, y, z=0.0, h=2.6, seed=0, coll_name='plants'):
    """Large potted indoor tree (fig / olive-like) in a clay pot."""
    r = random.Random(seed)
    bm = bmesh.new()
    cyl(bm, (x, y, z + 0.28), 0.34, 0.56, segs=32, r2=0.40)
    mk_obj(name + '_pot', bm, M_TERRACOTTA, coll_name, smooth=True)
    bm = bmesh.new()
    bml = bmesh.new()
    base = Vector((x, y, z + 0.5))
    top = base + Vector((r.uniform(-0.15, 0.15), r.uniform(-0.15, 0.15), h * 0.45))
    cyl(bm, (base + top) / 2, 0.04, (top - base).length, segs=8,
        rot=Vector((0, 0, 1)).rotation_difference((top - base).normalized()).to_matrix().to_4x4())
    for b_ in range(6):
        a = r.uniform(0, 360)
        tip = top + Vector((math.cos(rad(a)) * r.uniform(0.3, 0.7), math.sin(rad(a)) * r.uniform(0.3, 0.7),
                            r.uniform(0.3, h * 0.5)))
        d = tip - top
        cyl(bm, (top + tip) / 2, 0.02, d.length, segs=6,
            rot=Vector((0, 0, 1)).rotation_difference(d.normalized()).to_matrix().to_4x4())
        for i in range(22):
            c = tip + Vector((r.uniform(-0.45, 0.45), r.uniform(-0.45, 0.45), r.uniform(-0.4, 0.3)))
            s_ = r.uniform(0.09, 0.15)
            res = bmesh.ops.create_icosphere(bml, subdivisions=1, radius=1.0)
            M = (Matrix.Translation(c) @ Matrix.Rotation(rad(r.uniform(0, 360)), 4, 'Z') @
                 Matrix.Rotation(rad(r.uniform(-60, 60)), 4, 'X') @ Matrix.Diagonal((s_ * 0.6, s_, 0.01, 1)))
            bmesh.ops.transform(bml, verts=res['verts'], matrix=M)
    mk_obj(name + '_wood', bm, M_BARK, coll_name, smooth=True)
    mk_obj(name + '_leaves', bml, M_PLANT, coll_name, smooth=True)


def hanging_greens(name, center, length, seed=0, coll_name='plants', spread=0.35):
    """Trailing plant (pothos / ivy-like) spilling down from a planter."""
    r = random.Random(seed)
    bml = bmesh.new()
    for strand in range(4):
        p = Vector(center) + Vector((r.uniform(-spread, spread), r.uniform(-spread, spread), 0))
        L = length * r.uniform(0.5, 1.0)
        z_ = 0.0
        while z_ < L:
            z_ += 0.07
            q = p + Vector((0.04 * math.sin(z_ * 5 + strand), 0.04 * math.cos(z_ * 4 + strand), -z_))
            for _ in range(2):
                s_ = r.uniform(0.04, 0.07)
                res = bmesh.ops.create_icosphere(bml, subdivisions=1, radius=1.0)
                M = (Matrix.Translation(q + Vector((r.uniform(-0.06, 0.06), r.uniform(-0.06, 0.06), 0))) @
                     Matrix.Rotation(rad(r.uniform(0, 360)), 4, 'Z') @ Matrix.Rotation(rad(r.uniform(40, 80)), 4, 'X') @
                     Matrix.Diagonal((s_, s_ * 1.1, 0.008, 1)))
                bmesh.ops.transform(bml, verts=res['verts'], matrix=M)
    mk_obj(name, bml, M_PLANT, coll_name, smooth=True)


# --- artificial light: paper disc pendants, indirect uplight ledge, clay wall shells ---------
def light(name, kind, loc, power, rot=None, size=None, size_y=None, spot=None, soft=0.05):
    li = bpy.data.lights.new(name, kind)
    li.energy = 0.0
    li.color = (1.0, 0.80, 0.60)
    if kind == 'AREA':
        li.shape = 'RECTANGLE'
        li.size = size
        li.size_y = size_y
    elif kind == 'SPOT':
        li.spot_size = spot
        li.spot_blend = 0.7
        li.shadow_soft_size = soft
    else:
        li.shadow_soft_size = soft
    lo = bpy.data.objects.new(name, li)
    lo.location = loc
    if rot is not None:
        lo.rotation_euler = rot
    lo['lantern_power'] = power
    coll('night_lights').objects.link(lo)
    return lo


def paper_disc(name, center, r, h, parent=None, coll_name='furnishing', cord=None, power=70.0):
    """Large flat paper pendant (Akari-like disc) with a light inside."""
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=40, v_segments=16, radius=1.0)
    for v in bm.verts:
        a_ = math.atan2(v.co.y, v.co.x)
        f = 1 + 0.012 * math.cos(40 * a_)
        v.co = Vector((v.co.x * r * f, v.co.y * r * f, v.co.z * h / 2))
    bmesh.ops.translate(bm, vec=Vector(center), verts=bm.verts[:])
    ob = mk_obj(name, bm, M_LANTERN, coll_name, smooth=True)
    if parent:
        ob.parent = parent
    if cord:
        bm = bmesh.new()
        cyl(bm, (center[0], center[1], (center[2] + h / 2 + cord) / 2), 0.004, cord - center[2] - h / 2, segs=6)
        c_ = mk_obj(name + '_cord', bm, M_STEEL, coll_name)
        if parent:
            c_.parent = parent
    lo = light(name + '_light', 'POINT', center, power, soft=r * 0.7)
    if parent:
        lo.parent = parent
    return ob


def clay_sconce(name, loc, facing_deg, parent=None, power=8.0, coll_name='furnishing'):
    """Half-bowl clay wall shell; light spills up and down the wall (indirect)."""
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=12, radius=1.0)
    for v in bm.verts:
        v.co = Vector((max(v.co.x, 0.0) * 0.11, v.co.y * 0.17, v.co.z * 0.26))
    M = Matrix.Translation(Vector(loc)) @ Matrix.Rotation(rad(facing_deg), 4, 'Z')
    bmesh.ops.transform(bm, verts=bm.verts[:], matrix=M)
    ob = mk_obj(name, bm, M_CLAY_ROOM, coll_name, smooth=True)
    if parent:
        ob.parent = parent
    back = Vector(loc) - Vector((math.cos(rad(facing_deg)), math.sin(rad(facing_deg)), 0)) * -0.05
    for dz, nm in ((0.2, 'up'), (-0.2, 'dn')):
        lo = light(name + '_' + nm, 'SPOT', back + Vector((0, 0, dz * 0.4)), power,
                   rot=(math.pi if dz > 0 else 0, 0, 0), spot=rad(120), soft=0.04)
        if parent:
            lo.parent = parent
    return ob



def bath_front(k):
    """Front of the bath segment: clay wall with two WC doors and a frosted-glass sliding door."""
    parent = bpy.data.objects.new('bath_front_%d' % k, None)
    coll('rooms').objects.link(parent)
    parent.matrix_world = Matrix.Rotation(rad(P.slot_center(k)), 4, 'Z')
    half = P.APOTHEM_FRONT * math.tan(rad(P.SLOT_DEG / 2)) - P.POST / 2 - 0.01
    x = P.APOTHEM_FRONT + P.FRONT_T / 2
    zf = P.FFL_UF
    holes = [(-2.0, -1.2, 2.1), (-0.75, 0.75, 2.2), (1.2, 2.0, 2.1)]
    bm = bmesh.new()
    edges = [-half] + [h for (a_, b_, _) in holes for h in (a_, b_)] + [half]
    for i in range(0, len(edges), 2):
        y0, y1 = edges[i], edges[i + 1]
        cube(bm, (x, (y0 + y1) / 2, (zf + P.CEIL_UF) / 2), (P.FRONT_T, y1 - y0, P.CEIL_UF - zf))
    for (a_, b_, h_) in holes:
        cube(bm, (x, (a_ + b_) / 2, (zf + h_ + P.CEIL_UF) / 2), (P.FRONT_T, b_ - a_, P.CEIL_UF - zf - h_))
    ob = mk_obj('bath_front_wall_%d' % k, bm, M_CLAY_ROOM, 'rooms')
    ob.parent = parent
    bm = bmesh.new()
    for (a_, b_) in ((-2.0, -1.2), (1.2, 2.0)):
        cube(bm, (x + 0.02, (a_ + b_) / 2, zf + 1.04), (0.04, b_ - a_ - 0.02, 2.06))
    for (a_, b_, h_) in holes:
        cube(bm, (x - 0.07, (a_ + b_) / 2, zf + h_ + 0.03), (0.03, b_ - a_ + 0.1, 0.06))
    cube(bm, (x - 0.09, -0.36, zf + 1.1), (0.04, 0.84, 2.2))          # sliding door frame (half open)
    ob = mk_obj('bath_doors_%d' % k, bm, M_WOOD, 'rooms')
    ob.parent = parent
    bm = bmesh.new()
    cube(bm, (x - 0.12, -0.36, zf + 1.1), (0.01, 0.72, 2.05))
    ob = mk_obj('bath_door_glass_%d' % k, bm, M_FROSTED, 'rooms')
    ob.parent = parent
    return parent


def bathroom_fixtures(k, parent, yw, x0, xb, z):
    """Bathing room for showering together (foreplay / aftercare), pairs or groups.
    Two WCs with their own doors at the front corners; rain showers under the skylight;
    a warm tadelakt bench to sit together; an aftercare nook with a heated daybed."""
    def put(name, bm, mat, smooth=False):
        ob = mk_obj(name, bm, mat, 'furnishing', smooth=smooth)
        ob.parent = parent
        return ob
    XW = 7.35                                          # back walls of the two WC rooms
    YW = 1.05
    bm = bmesh.new()
    for s_ in (-1, 1):
        cube(bm, ((x0 + XW) / 2, s_ * YW, z + 1.3), (XW - x0, 0.1, 2.6))
        y_out = yw(XW)
        cube(bm, (XW, s_ * (YW + y_out) / 2, z + 1.3), (0.1, y_out - YW, 2.6))
    put('bath_wc_walls_%d' % k, bm, M_TADELAKT)
    bm = bmesh.new()
    for s_ in (-1, 1):
        cube(bm, (XW - 0.28, s_ * 1.6, z + 0.2), (0.55, 0.38, 0.4))
        cube(bm, (XW - 0.1, s_ * 1.6, z + 0.55), (0.16, 0.4, 0.5))
        cube(bm, (6.05, s_ * (YW + 0.3), z + 0.85), (0.35, 0.45, 0.1))
    rounded(put('bath_wc_%d' % k, bm, M_CERAMIC), 0.05, 3, 1)
    # entry / changing zone: bench, hooks, basin counter
    bm = bmesh.new()
    cube(bm, (6.5, -YW + 0.3, z + 0.22), (1.3, 0.42, 0.44))
    put('bath_entry_bench_%d' % k, bm, M_WOOD)
    bm = bmesh.new()
    for i in range(6):
        cyl(bm, (5.95 + i * 0.25, -YW + 0.1, z + 1.7), 0.015, 0.12, segs=8,
            rot=Matrix.Rotation(rad(90), 4, 'X'))
    put('bath_hooks_%d' % k, bm, M_WOOD_DARK)
    top = [(5.95, YW - 0.05), (7.2, YW - 0.05), (7.2, YW - 0.55), (5.95, YW - 0.55)]
    extrude_outline('bath_counter_%d' % k, top, z + 0.84, z + 0.9, M_WOOD, parent, bevel=0.01, seg=2)
    bm = bmesh.new()
    for xc in (6.3, 6.9):
        bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=12, radius=0.19,
                                  matrix=Matrix.Translation((xc, YW - 0.3, z + 0.97)) @
                                  Matrix.Diagonal((1, 1, 0.45, 1)))
    put('bath_basins_%d' % k, bm, M_CERAMIC, smooth=True)
    # shower zone under the skylight: three wide rain heads from the ceiling
    bm = bmesh.new()
    for yy in (-1.9, -0.75, 0.4):
        cube(bm, (8.55, yy, P.CEIL_UF - 0.05), (0.34, 0.34, 0.03))
        cyl(bm, (8.55, yy, P.CEIL_UF - 0.02), 0.012, 0.04, segs=8)
    cube(bm, (7.95, -0.75, z + 0.004), (0.05, 3.2, 0.008))           # linear drain
    put('bath_rain_heads_%d' % k, bm, M_STEEL)
    bench = [(xx, yy) for xx, yy in superellipse(9.3, -0.85, 0.24, 1.75, n=3.5)]
    extrude_outline('bath_warm_bench_%d' % k, bench, z, z + 0.45, M_TADELAKT, parent, bevel=0.06, seg=4)
    # aftercare nook: low curved wall, heated daybed with towels + blanket, candle niche, plant
    wall = superellipse(8.45, 1.1, 0.8, 0.09, n=2.0)
    extrude_outline('bath_nook_wall_%d' % k, wall, z, z + 1.2, M_TADELAKT, parent, bevel=0.04)
    bed = superellipse(8.95, 2.3, 0.55, 0.95, n=3.0)
    extrude_outline('bath_nook_daybed_%d' % k, bed, z, z + 0.42, M_TADELAKT, parent, bevel=0.06, seg=4)
    mat_ = superellipse(8.95, 2.3, 0.48, 0.86, n=3.0)
    extrude_outline('bath_nook_mat_%d' % k, mat_, z + 0.42, z + 0.52, M_WOOL['cream'], parent, bevel=0.04, seg=3)
    cushion('bath_nook_blanket_%d' % k, parent, (8.8, 2.6, z + 0.6), (0.7, 0.5, 0.12), M_WOOL['terracotta'])
    for i in range(3):
        cushion('bath_towel_%d_%d' % (k, i), parent, (9.35, 1.65 + i * 0.02, z + 0.6 + i * 0.1),
                (0.45, 0.35, 0.09), M_WOOL['sand'])
    bm = bmesh.new()
    for yy in (2.0, 2.3, 2.6):
        cyl(bm, (9.45, yy, z + 1.3), 0.03, 0.08, segs=12)
    put('bath_candles_%d' % k, bm, M_CANDLE, smooth=True)
    potted_plant('bath_plant_%d' % k, parent, 7.75, -2.55, z, h=1.1, seed=5, reach=0.5)
    lantern('bath_pendant_%d' % k, (8.9, 2.3, P.CEIL_UF - 0.75), 0.24, 0.38, parent=parent, cord=P.CEIL_UF)
    clay_sconce('bath_sconce_%d' % k, (8.2, -yw(8.2) + 0.03, z + 1.8), 67.5, parent=parent, power=6.0)


def room(k, bath=False):
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
                                    (x0, yw(x0))], z, M_TADELAKT if bath else M_FLOOR_ROOM, parent, 'rooms')
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

    if bath:
        bathroom_fixtures(k, parent, yw, x0, xb, z)
        return parent
    pal = PALETTES[(k * 3) % len(PALETTES)]
    seed = 11 * k
    NEST_N = P.R_IN - 0.06 - 1.2
    # sleeping nest: earthen plinth with soft edges under the window, mattress, skins, cushions
    nest = superellipse(NEST_N, 0.0, 1.2, 1.6, n=2.4, jitter=0.03, seed=seed)
    extrude_outline('room_nest_base_%d' % k, nest, z - 0.01, z + 0.30, M_CLAY_ROOM, parent, bevel=0.07)
    mat_ = superellipse(NEST_N, 0.0, 1.07, 1.46, n=2.6, seed=seed)
    extrude_outline('room_nest_mattress_%d' % k, mat_, z + 0.30, z + 0.49, M_MATTRESS, parent, bevel=0.08,
                    seg=5)
    fur = superellipse(NEST_N - 0.45, -0.85, 0.45, 0.62, n=2.0, jitter=0.12, seed=seed + 1, rot=20)
    extrude_outline('room_sheepskin_%d' % k, fur, z + 0.48, z + 0.54, M_FUR, parent, bevel=0.025, seg=3)
    drape('room_blanket_%d' % k, parent, NEST_N - 1.05, 0.1, 1.25, NEST_N + 0.05, z + 0.50, z + 0.06, M_WOOL[pal[0]], seed=seed)
    for i, yy in enumerate((-1.05, -0.38, 0.32, 1.0)):
        cushion('room_cushion_%d_%d' % (k, i), parent, (NEST_N + 0.7 - 0.05 * abs(yy), yy, z + 0.75),
                (0.6, 0.22, 0.52), M_WOOL[pal[i % 3]], rz=yy * 10, rx=-12, squish=0.3)
    cushion('room_bolster_%d' % k, parent, (NEST_N - 0.8, 1.05, z + 0.58), (0.25, 0.6, 0.2), M_WOOL[pal[1]], rz=15,
            squish=0.6)
    # cob bench along one side wall with a curved back
    wa = -P.SLOT_DEG / 2
    wd = Vector((math.cos(rad(wa)), math.sin(rad(wa)), 0))
    wn = Vector((math.sin(rad(-wa)), math.cos(rad(-wa)), 0))
    c0 = wd * 7.25 + wn * (e + 0.34)
    seat = superellipse(c0.x, c0.y, 0.95, 0.30, n=2.2, rot=wa, seed=seed + 2)
    extrude_outline('room_cob_bench_%d' % k, seat, z - 0.01, z + 0.42, M_CLAY_ROOM, parent, bevel=0.09, seg=5)
    cb = wd * 7.25 + wn * (e + 0.07)
    back = superellipse(cb.x, cb.y, 1.05, 0.09, n=2.0, rot=wa, seed=seed + 3)
    extrude_outline('room_cob_back_%d' % k, back, z - 0.01, z + 0.95, M_CLAY_ROOM, parent, bevel=0.07, seg=5)
    for i, s in enumerate((-0.45, 0.4)):
        p = wd * (7.25 + s) + wn * (e + 0.36)
        cushion('room_bench_cushion_%d_%d' % (k, i), parent, (p.x, p.y, z + 0.49), (0.55, 0.5, 0.12),
                M_WOOL[pal[(i + 1) % 3]], rz=wa + 5 * s)
    # soft round rug, tray with candles and tea, plant, curtain
    rug = superellipse(6.95, 0.55, 1.15, 1.0, n=2.0, jitter=0.05, seed=seed + 4)
    extrude_outline('room_rug_%d' % k, rug, z, z + 0.015, M_WOOL[pal[1]], parent, bevel=0.006, seg=2)
    bm = bmesh.new()
    cyl(bm, (6.8, -0.45, z + 0.03), 0.27, 0.035, segs=40)
    ob = mk_obj('room_tray_%d' % k, bm, M_WOOD_DARK, 'furnishing', smooth=True)
    ob.parent = parent
    bm = bmesh.new()
    for (cx, cy, h) in ((6.73, -0.52, 0.12), (6.88, -0.38, 0.08), (6.85, -0.56, 0.05)):
        cyl(bm, (cx, cy, z + 0.05 + h / 2), 0.035, h, segs=16)
    ob = mk_obj('room_candles_%d' % k, bm, M_CANDLE, 'furnishing', smooth=True)
    ob.parent = parent
    bm = bmesh.new()
    res = bmesh.ops.create_uvsphere(bm, u_segments=20, v_segments=12, radius=0.075,
                                    matrix=Matrix.Translation((6.67, -0.33, z + 0.13)))
    ob = mk_obj('room_teapot_%d' % k, bm, M_TERRACOTTA, 'furnishing', smooth=True)
    ob.parent = parent
    potted_plant('room_plant_%d' % k, parent, 8.8, 2.55, z, h=1.2, seed=seed, reach=0.55)
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
    for side in (-1, 1):
        wa_ = side * P.SLOT_DEG / 2
        pnt = Vector((math.cos(rad(wa_)), math.sin(rad(wa_)), 0)) * 8.3 + \
            Vector((-math.sin(rad(wa_)), math.cos(rad(wa_)), 0)) * (-side) * (e + 0.02)
        clay_sconce('room_sconce_%d_%d' % (k, side), (pnt.x, pnt.y, z + 1.75), wa_ - side * 90, parent=parent,
                    power=6.0)
    lantern('room_floorlamp_%d' % k, (6.2, 1.55, z + 0.45), 0.2, 0.8, parent=parent)
    return parent


for k in range(P.N_SLOTS):
    if k == P.STAIR_SLOT:
        continue
    if k == P.BATH_SLOT:
        bath_front(k)
    else:
        room_front(k, DOOR_STATES[k])
    room(k, bath=(k == P.BATH_SLOT))

# ---------------------------------------------------------------------------
# 7. stair hall -> upper floor: one wide flight along the NW wall (circumferential), open to
#    the hall. The lowest steps fan out softly into the hall as seating steps; a solid clay
#    balustrade with a rounded top and an oak handrail; flush store doors underneath.
#    It arrives right at the door to the external stair (roof terrace).
# ---------------------------------------------------------------------------
KS = P.STAIR_SLOT
RZS = P.slot_center(KS) + 90          # cube x-axis along the face (t)
R_ = P.STAIR_RISE
G_ = P.STAIR_GOING_T
N0 = P.R_IN - P.STAIR_FLIGHT_W_T      # inner (hall-side) edge of the flight
N1 = P.R_IN - 0.02
T0 = P.STAIR_T0                       # first riser
NT = P.STAIR_RISERS - 1               # treads
T_TOP = T0 + NT * G_                  # last riser -> upper floor
N_FAN = 5                             # fanned seating steps at the bottom


def box_nt(bm, n0, n1, t0, t1, z0, z1):
    cube(bm, FP(KS, (n0 + n1) / 2, (t0 + t1) / 2, (z0 + z1) / 2), (t1 - t0, n1 - n0, z1 - z0), rz=RZS)


def flare(i):
    """How far tread i reaches out into the hall beyond the flight (fan at the bottom)."""
    return 1.6 * max(0.0, 1 - (i - 1) / N_FAN) ** 1.6


def tread_outline(i, grow=0.0):
    ta, tb = T0 + (i - 1) * G_, T0 + i * G_
    f = flare(i)
    n_in = N0 - f
    # rounded plan: soft corners on the hall side, the fanned steps also wrap back along t
    ext_t = 0.6 * f
    cx_n = (n_in + N1) / 2
    cx_t = (ta - ext_t + tb) / 2 + 0.0
    rn = (N1 - n_in) / 2 + grow
    rt = (tb - ta + ext_t) / 2 + grow
    pts = superellipse(cx_n, cx_t, rn, rt, n=4.0 if f < 0.05 else 3.0, N=48)
    return [tuple(FP(KS, n, t))[:2] for n, t in pts]


T_FAN = T0 + N_FAN * G_                 # end of the seating terraces / start of the floating flight


def terrace_outline(i, grow=0.0):
    """Seating terrace i (1..N_FAN): reaches from its own riser to the end of the fan, so the terraces
    nest like contour lines (one sculpted amphitheatre, not separate drums)."""
    ta = T0 + (i - 1) * G_
    f = flare(i)
    n_in = N0 - f
    ext_t = 0.6 * f
    pts = superellipse((n_in + N1) / 2, (ta - ext_t + T_FAN) / 2, (N1 - n_in) / 2 + grow,
                       (T_FAN - ta + ext_t) / 2 + grow, n=3.2, N=56)
    # the fan wraps round the corner: stop it at the inner face of the next wall (north / annex side)
    return clip_halfplane([tuple(FP(KS, n, t))[:2] for n, t in pts], KS - 1, P.R_IN - 0.01)


def clip_halfplane(pts, k, lim):
    """Sutherland-Hodgman: keep the part of the polygon with (p . face-normal k) <= lim"""
    a = rad(P.slot_center(k))
    d = lambda q: q[0] * math.cos(a) + q[1] * math.sin(a) - lim   # noqa: E731
    out = []
    for i in range(len(pts)):
        p, q = pts[i], pts[(i + 1) % len(pts)]
        dp, dq = d(p), d(q)
        if dp <= 0:
            out.append(p)
        if (dp < 0) != (dq < 0) and dp != dq:
            s = dp / (dp - dq)
            out.append((p[0] + (q[0] - p[0]) * s, p[1] + (q[1] - p[1]) * s))
    return out


for i in range(1, N_FAN + 1):
    zt = i * R_
    extrude_outline('stair_terrace_%02d' % i, terrace_outline(i), 0.0, zt - 0.05, M_CLAY_HALL, None,
                    coll_name='structure', bevel=0.05, seg=4)
    extrude_outline('stair_terrace_top_%02d' % i, terrace_outline(i, 0.015), zt - 0.05, zt, M_WOOD, None,
                    coll_name='structure', bevel=0.02, seg=3)
# floating oak treads, cantilevered from the clay wall (steel flats hidden in the wall), open risers
bm = bmesh.new()
for i in range(N_FAN + 1, NT + 1):
    zt = i * R_
    box_nt(bm, N0 + 0.02, N1, T0 + (i - 1) * G_ - 0.015, T0 + i * G_, zt - 0.075, zt)
treads = rounded(mk_obj('stair_floating_treads', bm, M_WOOD, 'structure'), 0.012, 2, 0)
# under the flight: the seating terraces continue as a long low clay bench against the wall
bm = bmesh.new()
box_nt(bm, N0 + 0.25, N1, T_FAN, T_TOP - 0.2, 0.0, 0.42)
rounded(mk_obj('stair_bench', bm, M_CLAY_HALL, 'structure'), 0.05, 3, 1)
bm = bmesh.new()
box_nt(bm, N0 + 0.22, N1, T_FAN, T_TOP - 0.2, 0.42, 0.47)
rounded(mk_obj('stair_bench_top', bm, M_WOOD, 'structure'), 0.015, 2, 0)
t_b0 = T_FAN + 0.5 * G_


def flight_z(t):
    return max(0.0, (t - T0) / G_ * R_)


# balustrade on the hall side: rope net (like the big net) between slender oak posts, oak handrail;
# it ends where the stairwell lining / upper-floor parapet takes over (T_VOID)
T_VOID = T0 + 7 * G_                     # void over the flight starts here (headroom)
bm = bmesh.new()
uvl = bm.loops.layers.uv.new('UVMap')
su = 0.7071 / P.NET_MESH
NS_ = 24
row_b, row_t = [], []
for j in range(NS_ + 1):
    t = t_b0 + (T_VOID - 0.03 - t_b0) * j / NS_
    zb = flight_z(t) + 0.02
    row_b.append((bm.verts.new(FP(KS, N0 - 0.01, t, zb)), t, zb))
    row_t.append((bm.verts.new(FP(KS, N0 - 0.01, t, min(zb + 0.93, P.FFL_UF + 1.0))), t, min(zb + 0.93, P.FFL_UF + 1.0)))
for j in range(NS_):
    f = bm.faces.new((row_b[j][0], row_b[j + 1][0], row_t[j + 1][0], row_t[j][0]))
    for lp, (v, t, z) in zip(f.loops, (row_b[j], row_b[j + 1], row_t[j + 1], row_t[j])):
        lp[uvl].uv = (t * su, z * su)
mk_obj('stair_net_balustrade', bm, M_NET, 'structure', recalc=False)
bm = bmesh.new()
npost = 5
for j in range(npost + 1):
    t = t_b0 + (T_VOID - 0.05 - t_b0) * j / npost
    zb = flight_z(t)
    cyl(bm, FP(KS, N0 + 0.05, t, zb + 0.47), 0.022, 0.96, segs=12)
mk_obj('stair_posts', bm, M_WOOD, 'structure', smooth=True)
cu = bpy.data.curves.new('stair_handrails', 'CURVE')
cu.dimensions = '3D'
cu.bevel_depth = 0.028
cu.bevel_resolution = 3
for nn, dz, t_from, t_to in ((N0 + 0.05, 0.96, t_b0, T_VOID - 0.05), (N1 - 0.06, 0.9, T0 + 2 * G_, T_TOP + 0.3)):
    sp = cu.splines.new('POLY')
    ts_ = [t_from, t_to]
    sp.points.add(1)
    for n_, t in enumerate(ts_):
        p_ = FP(KS, nn, t, min(flight_z(t) + dz, P.FFL_UF + 1.0))
        sp.points[n_].co = (p_.x, p_.y, p_.z, 1)
cu.materials.append(M_WOOD)
coll('structure').objects.link(bpy.data.objects.new('stair_handrails', cu))
# warm light: small LEDs under the wall handrail wash the treads (evening)
for j in range(7):
    t = t_b0 + (T_TOP - t_b0) * (j + 0.5) / 7
    light('stair_led_%d' % j, 'POINT', FP(KS, N1 - 0.12, t, flight_z(t) + 0.8), 3.0, soft=0.05)
# cushions on the fanned seating steps, a tree at the foot, a paper lantern above
for i in range(1, N_FAN):
    zt = i * R_
    for s_ in range(2):
        tt = T0 + (i - 0.5) * G_ - 0.45 * flare(i) - 0.6 * s_
        nn = N0 - flare(i) + 0.35
        cushion('stair_cushion_%d_%d' % (i, s_), None, tuple(FP(KS, nn, tt, zt + 0.07)), (0.5, 0.5, 0.14),
                M_WOOL[['terracotta', 'ochre', 'olive', 'rose', 'sand', 'wine'][(i + s_) % 6]], rz=RZS + 15 * s_)
for j in range(4):
    cushion('stair_bench_cushion_%d' % j, None, tuple(FP(KS, N0 + 0.75, T_FAN + 0.6 + j * 0.85, 0.53)),
            (0.55, 0.5, 0.13), M_WOOL[['sand', 'rose', 'ochre', 'olive'][j]], rz=RZS)
c_ = FP(KS, N0 - 0.9, T0 - 1.1, 0)
indoor_tree('stair_tree', c_.x, c_.y, 0.0, h=2.4, seed=91)
paper_disc('stair_disc', tuple(FP(KS, N0 - 2.2, T0 + 2 * G_, 3.1)), 0.5, 0.24, cord=P.CEIL_GF, power=35.0)

# upper floor: guard along the void, linen / laundry room, open landing with tea niche
bm = bmesh.new()
box_nt(bm, N0 - 0.12, N0, T_VOID, T_TOP, P.FFL_UF, P.FFL_UF + 1.05)                # parapet along the void
box_nt(bm, N0 - 0.12, N1, T_VOID - 0.12, T_VOID, P.FFL_UF, P.CEIL_UF)              # linen room side wall
fr = P.APOTHEM_FRONT + P.FRONT_T
box_nt(bm, fr, N0, -1.3, -1.18, P.FFL_UF, P.CEIL_UF)                              # linen room inner wall
box_nt(bm, N0 - 0.12, N0, T_VOID, -1.18, P.FFL_UF, P.CEIL_UF)
box_nt(bm, fr - 0.12, fr, -P.face_half(fr) + 0.1, -2.35, P.FFL_UF, P.CEIL_UF)     # linen room front + door
box_nt(bm, fr - 0.12, fr, -1.45, -1.18, P.FFL_UF, P.CEIL_UF)
box_nt(bm, fr - 0.12, fr, -2.35, -1.45, P.FFL_UF + 2.1, P.CEIL_UF)
mk_obj('stair_uf_walls', bm, M_CLAY_ROOM, 'structure')
bm = bmesh.new()
box_nt(bm, N0 - 0.14, N0 + 0.02, T_VOID, T_TOP, P.FFL_UF + 1.05, P.FFL_UF + 1.10)
mk_obj('stair_uf_guard_cap', bm, M_WOOD, 'structure')
bm = bmesh.new()
box_nt(bm, 6.2, 7.6, 1.55, 2.05, P.FFL_UF, P.FFL_UF + 0.9)
mk_obj('tea_niche_counter', bm, M_CLAY_ROOM, 'furnishing')
bm = bmesh.new()
box_nt(bm, 6.18, 7.62, 1.53, 2.07, P.FFL_UF + 0.9, P.FFL_UF + 0.95)
mk_obj('tea_niche_top', bm, M_WOOD, 'furnishing')
bm = bmesh.new()
for i in range(4):
    cyl(bm, FP(KS, 6.4 + i * 0.3, 1.8, P.FFL_UF + 1.03), 0.045, 0.16, segs=12)
mk_obj('tea_niche_pots', bm, M_TERRACOTTA, 'furnishing', smooth=True)

# void in the upper slab + floor finish over the flight
c_ = FP(KS, (N0 + N1) / 2, (T_VOID + T_TOP) / 2, (P.CEIL_GF + P.FFL_UF) / 2)
for ob_ in (slab, plat, beams_ob):          # the radial beam over the flight is cut back too (headroom)
    cut_box(ob_, c_, (T_TOP - T_VOID, N1 - N0 + 0.04, 1.4), RZS)
# clay lining where the stairwell meets the outer wall (closes the slab / wall joint)
bm = bmesh.new()
box_nt(bm, N1 - 0.03, P.R_IN + 0.03, T_VOID - 0.02, T_TOP + 0.02, P.CEIL_GF - 0.3, P.FFL_UF + 0.02)
box_nt(bm, N0 - 0.03, N1, T_VOID - 0.03, T_VOID + 0.02, P.CEIL_GF - 0.3, P.FFL_UF + 0.02)
mk_obj('stairwell_lining', bm, M_CLAY_HALL, 'structure')
lantern('stair_pendant', tuple(FP(KS, 8.2, 0.0, P.CEIL_UF - 0.9)), 0.3, 0.45, cord=P.CEIL_UF)

# ---------------------------------------------------------------------------
# 8. roof, dome
# ---------------------------------------------------------------------------
ROOM_SLOTS = [k for k in range(P.N_SLOTS) if k != P.STAIR_SLOT]


def cut_skylights(ob, z0, z1):
    for k in ROOM_SLOTS:
        c = pol(P.SKYLIGHT['u'], P.slot_center(k), (z0 + z1) / 2)
        cut_box(ob, c, (P.SKYLIGHT['d'], P.SKYLIGHT['w'], z1 - z0 + 0.4), P.slot_center(k))


bm = bmesh.new()
ring_prism(bm, P.APOTHEM_FRONT + 0.05, OCT(P.R_OUT), P.CEIL_UF, P.ROOF_Z_IN, step=0.5)
roof = mk_obj('roof', bm, [M_CEIL, M_PLINTH, M_CLAD], 'roof')
cut_skylights(roof, P.CEIL_UF, P.ROOF_Z_IN)
set_face_mats(roof, lambda c, n: 1 if n.z > 0.5 else (0 if n.z < -0.5 else 2))
# terrace deck (outdoor larch boards, laid in rings)
bm = bmesh.new()
ring_prism(bm, P.DOME_RING_OUT, OCT(P.R_TERRACE_OUT), P.ROOF_Z_IN, P.TERRACE_Z, step=0.5)
deck = mk_obj('terrace_deck', bm, M_DECK, 'roof')
cut_skylights(deck, P.ROOF_Z_IN, P.TERRACE_Z)
# dome upstand ring (45 cm above the deck); a timber bench ring runs outside it
bm = bmesh.new()
sector(bm, P.APOTHEM_FRONT - 0.05, P.DOME_RING_OUT, 0, 360, P.ROOF_Z_IN - 0.02, P.DOME_BASE_Z + 0.02,
       step=1.5)
mk_obj('dome_base_ring', bm, M_WOOD, 'roof')
sa_ = P.slot_center(P.STAIR_SLOT)
bm = bmesh.new()
sector(bm, P.DOME_RING_OUT, P.DOME_RING_OUT + 0.47, 0, 360, P.TERRACE_Z + 0.36, P.TERRACE_Z + 0.44,
       step=1.5)
for i in range(44):
    a = 360 * (i + 0.5) / 44
    p = pol(P.DOME_RING_OUT + 0.25, a)
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
# shady side: two big floor mattresses with cushions for lying together (north faces)
# in the corners N/NE and NE/E (k = x.5): clear of the room skylights (mid-face) and of the planters
for i, (k, t) in enumerate(((7.5, 0.0), (6.5, 0.0))):
    rz = P.slot_center(k) + 90
    bm = bmesh.new()
    cube(bm, FP(k, 8.35, t, P.TERRACE_Z + 0.11), (2.3, 2.3, 0.22), rz=rz)
    rounded(mk_obj('roof_floor_mattress_%d' % i, bm, M_WOOL[['cream', 'sand'][i]], 'terrace'), 0.08, 4, 1)
    for j, (tt, nn) in enumerate(((-0.7, 9.3), (0.1, 9.35), (0.8, 9.3), (-0.8, 7.5))):
        cushion('roof_mattress_cushion_%d_%d' % (i, j), None, tuple(FP(k, nn, t + tt, P.TERRACE_Z + 0.36)),
                (0.6, 0.22, 0.45) if nn > 9 else (0.5, 0.5, 0.16),
                M_WOOL[['terracotta', 'rose', 'ochre', 'olive', 'wine'][(i + j) % 5]], rz=rz)
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
# 9. small annex on the north face: foyer with coats + shoes, ground-floor WC, tech room
# ---------------------------------------------------------------------------
KE = P.ENTRY_SLOT
RZE = P.slot_center(KE) + 90
A0, A1 = P.partition_angle(KE), P.partition_angle(KE + 1)       # 67.5 .. 112.5
AO = P.R_OUT + P.ANNEX_D
H = P.ANNEX_H
T = 0.35
DOOR_W = 1.8
bm = bmesh.new()
# outer wall with the entrance door on the axis and a window each side
face_wall(bm, KE, [(-DOOR_W / 2, DOOR_W / 2, 0.0, 2.4), (-3.9, -2.2, 0.9, 2.5), (2.2, 3.9, 0.9, 2.5)], 0.0, H,
          nin=AO - T, nout=AO)
# side walls along the corner rays
for a, side in ((A0, 1), (A1, -1)):
    off = pol(T / 2, a + 90 * side)
    seg_box(bm, pol(P.octo_r(a, P.R_OUT), a) + off, pol(P.octo_r(a, AO - T), a) + off, T, 0.0, H)
ann = mk_obj('annex_walls', bm, [M_CLAD, M_CLAY_ROOM], 'annex')


def annex_mat(c, n):
    if abs(n.z) > 0.5:
        return 1
    a = math.degrees(math.atan2(c.y, c.x))
    radial = Vector((c.x, c.y, 0)).normalized()
    ccw = Vector((-radial.y, radial.x, 0))
    if n.dot(radial) > 0.6 and math.hypot(c.x, c.y) > AO - 0.5:
        return 0
    if abs(a - A1) < 4 and n.dot(ccw) > 0.6:
        return 0
    if abs(a - A0) < 4 and n.dot(ccw) < -0.6:
        return 0
    return 1


set_face_mats(ann, annex_mat)
# partitions: WC (east end) and tech (west end), doors from the foyer
bm = bmesh.new()
for tt, gap in ((-2.6, (P.R_OUT + 3.1, P.R_OUT + 4.0)), (2.6, (P.R_OUT + 3.1, P.R_OUT + 4.0))):
    for n0, n1 in ((P.octo_r(0, P.R_OUT), gap[0]), (gap[1], AO - T)):
        seg_box(bm, FP(KE, n0, tt), FP(KE, n1, tt), 0.12, 0.0, H)
    seg_box(bm, FP(KE, gap[0], tt), FP(KE, gap[1], tt), 0.12, 2.1, H)
mk_obj('annex_partitions', bm, M_CLAY_ROOM, 'annex')
bm = bmesh.new()
ring_prism(bm, OCT(P.R_OUT - 0.02), OCT(AO + 0.45), H, H + 0.35, a0=A0 - 0.8, a1=A1 + 0.8, step=0.5)
aroof = mk_obj('annex_roof', bm, [M_CEIL, M_SEDUM, M_CLAD], 'annex')
set_face_mats(aroof, lambda c, n: 1 if n.z > 0.5 else (0 if n.z < -0.5 else 2))
bm = bmesh.new()
ring_prism(bm, OCT(P.R_OUT), OCT(AO), -0.05, 0.0, a0=A0, a1=A1, step=0.5)
mk_obj('annex_floor', bm, M_FLOOR_ROOM, 'annex')
bm = bmesh.new()
for t0, t1 in ((-3.9, -2.2), (2.2, 3.9)):
    q = [FP(KE, AO - 0.18, t0, 0.9), FP(KE, AO - 0.18, t1, 0.9), FP(KE, AO - 0.18, t1, 2.5), FP(KE, AO - 0.18, t0, 2.5)]
    bm.faces.new([bm.verts.new(p_) for p_ in q])
q = [FP(KE, AO - 0.18, -DOOR_W / 2, 0), FP(KE, AO - 0.18, DOOR_W / 2, 0), FP(KE, AO - 0.18, DOOR_W / 2, 2.4),
     FP(KE, AO - 0.18, -DOOR_W / 2, 2.4)]
bm.faces.new([bm.verts.new(p_) for p_ in q])
mk_obj('annex_glass', bm, M_GLASS, 'annex', recalc=False)
bm = bmesh.new()
for tt in (-DOOR_W / 2, 0.0, DOOR_W / 2):
    cube(bm, FP(KE, AO - 0.18, tt, 1.2), (0.1, 0.1, 2.4), rz=RZE)
cube(bm, FP(KE, AO - 0.18, 0, 2.42), (DOOR_W + 0.1, 0.1, 0.1), rz=RZE)
mk_obj('annex_entrance_frame', bm, M_WOOD_DARK, 'annex')
bm = bmesh.new()
cube(bm, FP(KE, AO + 0.9, 0, 2.85), (3.6, 1.8, 0.12), rz=RZE)
for tt in (-1.6, 1.6):
    cube(bm, FP(KE, AO + 1.7, tt, 1.4), (0.12, 0.12, 2.8), rz=RZE)
mk_obj('annex_canopy', bm, M_WOOD, 'annex')
bm = bmesh.new()
cube(bm, FP(KE, P.R_OUT + 1.2, -3.4, 0.2), (0.55, 0.38, 0.4), rz=RZE)
cube(bm, FP(KE, P.R_OUT + 0.9, -3.4, 0.55), (0.16, 0.4, 0.5), rz=RZE)
cube(bm, FP(KE, P.R_OUT + 4.1, -3.3, 0.85), (0.4, 0.5, 0.12), rz=RZE)
rounded(mk_obj('annex_wc_fixtures', bm, M_CERAMIC, 'annex'), 0.04, 3, 1)
vine('vine_annex_0', KE, -4.5, 3.0, 901)
vine('vine_annex_1', KE, 4.6, 3.0, 902)
# foyer: coat benches with rails and shoe shelves along both side partitions
for side in (-1, 1):
    tt = side * 2.35
    bm = bmesh.new()
    cube(bm, FP(KE, P.R_OUT + 2.3, tt, 0.22), (2.0, 0.45, 0.44), rz=P.slot_center(KE))
    rounded(mk_obj('coat_bench_%d' % side, bm, M_WOOD, 'annex'), 0.02, 2, 0)
    bm = bmesh.new()
    cube(bm, FP(KE, P.R_OUT + 2.3, side * 2.52, 1.75), (2.0, 0.06, 0.08), rz=P.slot_center(KE) + 90 - 90)
    mk_obj('coat_rail_%d' % side, bm, M_WOOD_DARK, 'annex')
# hall side of the door: heavy linen curtain
bm = bmesh.new()
prev = None
for i in range(30):
    s_ = i / 29
    tt = -1.3 + 1.2 * s_
    nd = P.R_IN - 0.6 - 0.06 * math.sin(s_ * math.pi * 8)
    col_ = [bm.verts.new(FP(KE, nd, tt, 0.02)), bm.verts.new(FP(KE, nd, tt, 2.75))]
    if prev:
        bm.faces.new((prev[0], col_[0], col_[1], prev[1]))
    prev = col_
cube(bm, FP(KE, P.R_IN - 0.6, 0, 2.78), (2.8, 0.04, 0.04), rz=RZE)
mk_obj('entrance_curtain', bm, M_CURTAIN, 'furnishing', smooth=True, recalc=False)

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
# stacked floor mats + blankets against the windowless bar wall, between the corner lantern and the bar
for j in range(5):
    bm = bmesh.new()
    cube(bm, FP(7, P.R_IN - 0.45, -2.45, 0.05 + j * 0.09), (1.8, 0.75, 0.08), rz=P.slot_center(7) + 90)
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
# hall: 8 paper disc pendants round the periphery, between the beams
for i in range(8):
    a = P.slot_center(i) + 11.25
    if i == P.STAIR_SLOT:
        continue
    c_ = pol(7.0, a, 2.95)
    paper_disc('hall_disc_%d' % i, tuple(c_), 0.55, 0.26, cord=P.CEIL_GF, power=40.0)
# hall: continuous timber ledge above the windows with a hidden warm uplight (indirect)
bm = bmesh.new()
for k in range(P.N_SLOTS):
    if k == P.STAIR_SLOT:
        continue
    fh = P.face_half(P.R_IN) - 0.25
    cube(bm, FP(k, P.R_IN - 0.11, 0, 3.3), (2 * fh, 0.22, 0.05), rz=P.slot_center(k) + 90)
    cube(bm, FP(k, P.R_IN - 0.21, 0, 3.36), (2 * fh, 0.03, 0.12), rz=P.slot_center(k) + 90)
    light('hall_cove_%d' % k, 'AREA', FP(k, P.R_IN - 0.1, 0, 3.34), 30.0,
          rot=(math.pi, 0, rad(P.slot_center(k) + 90)), size=2 * fh - 0.2, size_y=0.12)
mk_obj('hall_light_ledge', bm, M_WOOD, 'furnishing')
# hall: clay wall shells in the octagon corners
for k in range(P.N_SLOTS):
    a = P.partition_angle(k)
    if k in (P.STAIR_SLOT, P.STAIR_SLOT + 1):
        continue
    for side in (-1, 1):
        kk = k if side > 0 else k - 1
        tt = -P.face_half(P.R_IN) + 0.6 if side > 0 else P.face_half(P.R_IN) - 0.6
        clay_sconce('hall_sconce_%d_%d' % (k, side), tuple(FP(kk % P.N_SLOTS, P.R_IN - 0.02, tt, 1.95)),
                    P.slot_center(kk % P.N_SLOTS) + 180)

# --- indoor greenery ----------------------------------------------------------------------
for k in range(P.N_SLOTS):
    if k in (P.STAIR_SLOT, P.ENTRY_SLOT, P.BAR_FACE):
        continue
    for tt in (-3.25,) if k != P.GARDEN_SLOT else (-1.95, 1.95):
        c_ = FP(k, P.R_IN - 0.75, tt if k != P.GARDEN_SLOT else tt, 0)
        indoor_tree('hall_tree_%d_%d' % (k, int(tt * 10)), c_.x, c_.y, 0.0, h=2.5 + 0.2 * (k % 2), seed=40 + k)
for k in range(P.N_SLOTS):
    a_ = P.partition_angle(k)
    if k in (P.STAIR_SLOT, P.STAIR_SLOT + 1):
        continue
    c_ = pol(RC - 0.6, a_ + 3.5)
    potted_plant('walk_plant_%d' % k, None, c_.x, c_.y, P.FFL_UF, h=0.9, seed=70 + k, reach=0.4)
bm = bmesh.new()
n_pl = 16
for i in range(n_pl):
    a_ = 360 * (i + 0.5) / n_pl
    sector(bm, P.APOTHEM_FRONT - 0.55, P.APOTHEM_FRONT - 0.06, a_ - 5, a_ + 5, P.ROOF_Z_IN - 0.02, P.ROOF_Z_IN + 0.25,
           step=2)
mk_obj('dome_ring_planters', bm, M_TERRACOTTA, 'plants')
for i in range(n_pl):
    a_ = 360 * (i + 0.5) / n_pl
    c_ = pol(P.APOTHEM_FRONT - 0.42, a_, P.ROOF_Z_IN + 0.2)
    hanging_greens('dome_ring_greens_%d' % i, tuple(c_), 0.6 + 0.25 * (i % 3), seed=200 + i, spread=0.15)   # above head height

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
cb_ = pol(P.DOME_RING_OUT + 0.25, 255, P.TERRACE_Z + 0.44)
figure('person_terrace_bench', pose_sit_knees(), (cb_.x, cb_.y, cb_.z - 0.1), rz=255 - 90)

# ---------------------------------------------------------------------------
# 12. carvings: bodies, touch and embrace in low relief on the columns and the entrance arch.
#     The relief is made from the same sculptural figures as the people in the renderings:
#     each group is posed, scanned as a height map (ray casting), laid out on the surface
#     and displaced into the timber.
# ---------------------------------------------------------------------------
# Switched off: reliefs made from the placeholder mannequins were not good enough.
# Figurative carvings need an artist's drawings; until then the columns get a plain casing.
CARVINGS = False
if not CARVINGS:
    bm = bmesh.new()
    for a in PILLAR_ANGLES:
        c = pol(P.R_PILLAR, a)
        cyl(bm, (c.x, c.y, P.RING_BEAM_BOT / 2), P.PILLAR_D / 2, P.RING_BEAM_BOT - 0.1, segs=48,
            r2=P.PILLAR_D / 2 - 0.015)
    mk_obj('column_casings', bm, M_WOOD_STAVE, 'structure', smooth=True)
else:
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

# ---------------------------------------------------------------------------
# 13. EVENT LAYER (hidden in the normal views): Pfingstfestival ZEGG 2027, early evening.
#     Contact improvisation meets temple: dancing in the sunlit centre, mat zones for cuddling,
#     intimacy (screened by a linen canopy) and wrestling, a musician by the bar, organisers in
#     kimonos with clipboards, couples on the net and in the rooms upstairs.
#     Intimacy is shown non-explicitly (entwined bodies under blankets, closed glowing doors).
# ---------------------------------------------------------------------------
EV = 'event'
EVL = 'event_lights'
coll(EV)
coll(EVL, COLLS[EV])
EVR = random.Random(2027)


def _arms(p, **kw):
    for k_, v_ in kw.items():
        p[k_] = v_
    return p


SKIN = [mat_simple('skin_%d' % i, h, rough=0.5, Subsurface_Weight=0.25, Subsurface_Scale=0.01,
                   Sheen_Weight=0.15)
        for i, h in enumerate(('#EBC7AE', '#D9A987', '#B9825E', '#8E5B3E', '#6A4330', '#F1D5C4'))]
HAIR = [mat_simple('hair_%d' % i, h, rough=0.6, Sheen_Weight=0.4)
        for i, h in enumerate(('#2A1D16', '#4A3222', '#7A5A3A', '#C9A66B', '#9E9A94', '#8A2F22'))]


def silk(name, hexcol, sheen=0.8, trans=0.25, metal=0.0):
    c = srgb(hexcol)
    m, b = new_mat(name, c)
    co = b.coord()
    n1 = b.noise(co, scale=8.0, detail=4)
    col = b.mix(0.12, c, n1.outputs['Color'], blend='OVERLAY')
    p = b.principled(col, rough=0.35, Sheen_Weight=sheen, Sheen_Roughness=0.3, Metallic=metal,
                     Subsurface_Weight=trans, Subsurface_Scale=0.02)
    b.output(p)
    return m


def kimono_mat(name, base, stripe):
    m, b = new_mat(name, srgb(base))
    co = b.coord()
    w = b.n('ShaderNodeTexWave', wave_type='BANDS', bands_direction='DIAGONAL')
    w.inputs['Scale'].default_value = 28.0
    w.inputs['Distortion'].default_value = 2.0
    b.l(co, w.inputs['Vector'])
    col = b.ramp(w.outputs['Fac'], [(0.45, srgb(base)), (0.55, srgb(stripe))])
    b.output(b.principled(col, rough=0.5, Sheen_Weight=0.6))
    return m


FAB = {k: silk('silk_' + k, v) for k, v in dict(rose='#D98C8C', saffron='#E3A23A', turquoise='#3FA3A0',
                                                    ivory='#EFE6D6', crimson='#A8263A', plum='#6E3A6B',
                                                    moss='#6F8A4A', sky='#8FB8D8').items()}
FAB['gold'] = silk('silk_gold', '#D4A548', metal=0.7, trans=0.0)
FAB['magenta'] = silk('silk_magenta', '#D0308A', trans=0.0)
KIMONO = [kimono_mat('kimono_indigo', '#2E3A6B', '#46598E'), kimono_mat('kimono_red', '#8E2A2A', '#A9483A')]
M_PAPER = mat_simple('clipboard_paper', '#F4F1EA', rough=0.8)


def world_joint(pose, j, loc, rz, scale=1.0):
    v = Vector(pose[j]) * scale
    return Matrix.Rotation(rad(rz), 4, 'Z') @ v + Vector(loc)


def cone_cloth(name, top_c, top_r, bot_z, bot_r, mat, n=40, wave=0.06, seed=0, sway=(0.0, 0.0)):
    """Flowing skirt / robe: flared tube with a wavy hem."""
    r = random.Random(seed)
    bm = bmesh.new()
    rings = []
    NZ = 10
    ph = r.uniform(0, 6)
    for i in range(NZ + 1):
        f = i / NZ
        z = top_c.z + (bot_z - top_c.z) * f
        rad_ = top_r + (bot_r - top_r) * f ** 1.3
        cx = top_c.x + sway[0] * f ** 2
        cy = top_c.y + sway[1] * f ** 2
        ring = []
        for j in range(n):
            a = 2 * math.pi * j / n
            rr = rad_ * (1 + wave * f * math.sin(7 * a + ph) + 0.5 * wave * f * math.sin(3 * a + 2 * ph))
            ring.append(bm.verts.new((cx + rr * math.cos(a), cy + rr * math.sin(a),
                                      z + (0.05 * f * math.sin(5 * a + ph) if i == NZ else 0))))
        rings.append(ring)
    for i in range(NZ):
        for j in range(n):
            j2 = (j + 1) % n
            bm.faces.new((rings[i][j], rings[i][j2], rings[i + 1][j2], rings[i + 1][j]))
    ob = mk_obj(name, bm, mat, EV, smooth=True, recalc=False)
    so = ob.modifiers.new('solid', 'SOLIDIFY')
    so.thickness = 0.008
    ob.modifiers.new('sub', 'SUBSURF').levels = 1
    return ob


def sash(name, center, r, tilt_deg, rz_deg, mat, width=0.07):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=False, segments=32, radius1=r, radius2=r, depth=width)
    M = (Matrix.Translation(center) @ Matrix.Rotation(rad(rz_deg), 4, 'Z') @ Matrix.Rotation(rad(tilt_deg), 4, 'X'))
    bmesh.ops.transform(bm, verts=bm.verts[:], matrix=M)
    ob = mk_obj(name, bm, mat, EV, smooth=True, recalc=False)
    ob.modifiers.new('solid', 'SOLIDIFY').thickness = 0.01
    return ob


# The event people are realistic MakeHuman figures added by humans/build_crowd.py; the stylised
# mannequins below are kept only as a fallback (EVENT_MANNEQUINS = True).
EVENT_MANNEQUINS = False


def person(name, pose, loc, rz=0.0, scale=1.0, outfit=None, seed=0):
    """Figure + garments. outfit: None | ('skirt', mat) | ('robe', mat) | ('kimono', mat) | ('cape', mat)"""
    if not EVENT_MANNEQUINS:
        return None
    fo = figure(name, pose, loc, rz=rz, scale=scale, parent_coll=EV)
    r = random.Random(seed)
    fo.data.materials[0] = SKIN[r.randrange(len(SKIN))]
    pel = world_joint(pose, 'pelvis', loc, rz, scale)
    ch = world_joint(pose, 'chest', loc, rz, scale)
    nk = world_joint(pose, 'neck', loc, rz, scale)
    hd = world_joint(pose, 'head', loc, rz, scale)
    up = (hd - nk).normalized()
    bm = bmesh.new()                                    # hair: a cap, sometimes long hair or a bun
    bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=14, radius=0.112 * scale,
                              matrix=Matrix.Translation(hd + up * 0.045 * scale) @
                              up.to_track_quat('Z', 'Y').to_matrix().to_4x4() @
                              Matrix.Diagonal((0.95, 1.0, 0.95, 1)))
    style = r.random()
    if style < 0.4:
        bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=10, radius=0.1 * scale,
                                  matrix=Matrix.Translation(hd - up * 0.12 * scale) @
                                  up.to_track_quat('Z', 'Y').to_matrix().to_4x4() @
                                  Matrix.Diagonal((1.0, 0.55, 2.0, 1)))
    elif style < 0.6:
        bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=8, radius=0.06 * scale,
                                  matrix=Matrix.Translation(hd + up * 0.15 * scale))
    mk_obj(name + '_hair', bm, HAIR[r.randrange(len(HAIR))], EV, smooth=True)
    if not outfit:
        return fo
    kind, mat = outfit
    ank = min(world_joint(pose, 'la', loc, rz, scale).z, world_joint(pose, 'ra', loc, rz, scale).z)
    if kind == 'skirt':
        cone_cloth(name + '_skirt', pel + Vector((0, 0, 0.1)), 0.19 * scale, max(ank + 0.12, loc[2] + 0.05),
                   0.36 * scale, mat, wave=0.14, seed=seed, sway=(r.uniform(-0.15, 0.15), r.uniform(-0.15, 0.15)))
        sash(name + '_top', ch + Vector((0, 0, 0.02)), 0.165 * scale, 12, rz, mat, width=0.16)
    elif kind in ('robe', 'kimono'):
        cone_cloth(name + '_robe', nk + Vector((0, 0, -0.08)), 0.21 * scale, max(ank + 0.05, loc[2] + 0.04),
                   0.33 * scale, mat, wave=0.03, seed=seed)
        if kind == 'kimono':
            sash(name + '_obi', pel + Vector((0, 0, 0.12)), 0.2 * scale, 0, rz, FAB['saffron'], width=0.14)
            for s in ('l', 'r'):
                el = world_joint(pose, s + 'e', loc, rz, scale)
                wr = world_joint(pose, s + 'w', loc, rz, scale)
                c = (el + wr) / 2 + Vector((0, 0, -0.12))
                bm = bmesh.new()
                cube(bm, c, (0.1, 0.3, 0.42), rz=rz)
                rounded(mk_obj(name + '_sleeve_' + s, bm, mat, EV), 0.04, 2, 1)
            # clipboard held in both hands
            hand = (world_joint(pose, 'lh', loc, rz, scale) + world_joint(pose, 'rh', loc, rz, scale)) / 2
            bm = bmesh.new()
            cube(bm, hand + Vector((0, 0, 0.05)), (0.24, 0.012, 0.32), rz=rz, rx=-55)
            mk_obj(name + '_clipboard', bm, M_WOOD_DARK, EV)
            bm = bmesh.new()
            cube(bm, hand + Vector((0, 0, 0.055)) + Matrix.Rotation(rad(rz), 4, 'Z') @ Vector((0, -0.01, 0)),
                 (0.21, 0.004, 0.28), rz=rz, rx=-55)
            mk_obj(name + '_paper', bm, M_PAPER, EV)
    elif kind == 'cape':
        cone_cloth(name + '_cape', nk + Vector((0, 0, -0.02)), 0.24 * scale, max(ank + 0.2, loc[2] + 0.1),
                   0.5 * scale, mat, wave=0.15, seed=seed, sway=(r.uniform(-0.3, 0.3), r.uniform(-0.3, 0.3)))
        bm = bmesh.new()
        for i in range(9):                          # a crown of tall feathers
            a = -80 + 20 * i
            d = Matrix.Rotation(rad(rz), 4, 'Z') @ Vector((math.sin(rad(a)) * 0.35, -0.1, 1.0)).normalized()
            base = hd + Vector((0, 0, 0.06))
            tip = base + d * 0.42
            rot = Vector((0, 0, 1)).rotation_difference(d).to_matrix().to_4x4()
            cyl(bm, (base + tip) / 2, 0.035, 0.42, segs=8, r2=0.005, rot=rot)
        mk_obj(name + '_feathers', bm, mat, EV, smooth=True)
    return fo


def blanket(name, center, size, rz, mat):
    return cushion(name, None, tuple(center), size, mat, rz=rz, squish=0.15, coll_name=EV)


def mattress(name, center, rz, mat=None, size=(1.4, 2.0, 0.18)):
    bm = bmesh.new()
    cube(bm, (center[0], center[1], size[2] / 2), size, rz=rz)
    return rounded(mk_obj(name, bm, mat or M_MATTRESS, EV), 0.06, 3, 1)


def ev_light(name, loc, power, color=(1.0, 0.75, 0.5), soft=0.15):
    li = bpy.data.lights.new(name, 'POINT')
    li.energy = power
    li.color = color
    li.shadow_soft_size = soft
    lo = bpy.data.objects.new(name, li)
    lo.location = loc
    COLLS[EVL].objects.link(lo)
    return lo


# --- extra poses ---------------------------------------------------------------------------
def pose_dance_open():
    return _arms(mirror_pose(STAND), head=(0, -0.03, 1.62),
                 le=(0.42, 0.06, 1.45), lw=(0.68, 0.12, 1.52), lh=(0.76, 0.12, 1.54),
                 re=(-0.40, 0.1, 1.30), rw=(-0.62, 0.2, 1.18), rh=(-0.7, 0.22, 1.15),
                 rk=(-0.13, 0.18, 0.52), ra=(-0.12, 0.28, 0.12), rt=(-0.12, 0.4, 0.06))


def pose_lean():
    p = mirror_pose(STAND)
    return _arms(p, chest=(0, 0.12, 1.28), neck=(0, 0.2, 1.45), head=(0, 0.27, 1.55),
                 ls=(0.18, 0.13, 1.40), rs=(-0.18, 0.13, 1.40),
                 le=(0.22, 0.38, 1.28), lw=(0.14, 0.58, 1.33), lh=(0.1, 0.63, 1.33),
                 re=(-0.22, 0.38, 1.22), rw=(-0.14, 0.56, 1.12), rh=(-0.1, 0.6, 1.1),
                 lk=(0.12, 0.08, 0.5), rk=(-0.12, -0.08, 0.52), ra=(-0.12, -0.28, 0.1), rt=(-0.12, -0.18, 0.04))


def pose_crouch():
    return dict(pelvis=(0, 0, 0.64), belly=(0, 0.1, 0.8), chest=(0, 0.22, 0.96), neck=(0, 0.32, 1.08),
                head=(0, 0.38, 1.17), ls=(0.18, 0.24, 1.0), rs=(-0.18, 0.24, 1.0), le=(0.26, 0.46, 0.95),
                re=(-0.26, 0.46, 0.95), lw=(0.18, 0.64, 1.02), rw=(-0.18, 0.64, 1.02), lh=(0.15, 0.7, 1.03),
                rh=(-0.15, 0.7, 1.03), lhip=(0.1, 0, 0.62), rhip=(-0.1, 0, 0.62), lk=(0.22, 0.3, 0.36),
                rk=(-0.22, 0.3, 0.36), la=(0.24, 0.02, 0.07), ra=(-0.24, 0.02, 0.07), lt=(0.24, 0.15, 0.03),
                rt=(-0.24, 0.15, 0.03))


def pose_all_fours():
    return dict(pelvis=(0, 0, 0.62), belly=(0, 0.2, 0.64), chest=(0, 0.42, 0.66), neck=(0, 0.6, 0.7),
                head=(0, 0.72, 0.72), ls=(0.18, 0.5, 0.64), rs=(-0.18, 0.5, 0.64), le=(0.2, 0.52, 0.35),
                re=(-0.2, 0.52, 0.35), lw=(0.2, 0.55, 0.06), rw=(-0.2, 0.55, 0.06), lh=(0.2, 0.62, 0.03),
                rh=(-0.2, 0.62, 0.03), lhip=(0.1, 0, 0.6), rhip=(-0.1, 0, 0.6), lk=(0.12, -0.02, 0.06),
                rk=(-0.12, -0.02, 0.06), la=(0.12, -0.45, 0.06), ra=(-0.12, -0.45, 0.06),
                lt=(0.12, -0.55, 0.03), rt=(-0.12, -0.55, 0.03))


def pose_organiser():
    return _arms(mirror_pose(STAND), le=(0.22, 0.12, 1.14), lw=(0.12, 0.36, 1.18), lh=(0.06, 0.42, 1.2),
                 re=(-0.21, 0.12, 1.12), rw=(-0.06, 0.36, 1.2), rh=(-0.02, 0.42, 1.21), head=(0, 0.05, 1.61))


# --- couples: making love, shown without anatomical detail (abstract figures, blankets) -----------
from mathutils.bvhtree import BVHTree  # noqa: E402


def _pose_bottom(kind):
    p = pose_lie_back('open')
    if kind == 'straddle':      # hands on the partner's thighs, legs long
        _arms(p, le=(0.3, 0.15, 0.2), lw=(0.3, -0.05, 0.3), lh=(0.29, -0.1, 0.31),
              re=(-0.3, 0.15, 0.2), rw=(-0.3, -0.05, 0.3), rh=(-0.29, -0.1, 0.31))
    else:                       # arms around the partner, knees up and apart
        _arms(p, le=(0.35, 0.35, 0.3), lw=(0.2, 0.45, 0.45), lh=(0.12, 0.45, 0.47),
              re=(-0.35, 0.35, 0.3), rw=(-0.2, 0.45, 0.45), rh=(-0.12, 0.45, 0.47),
              lk=(0.3, -0.35, 0.32), la=(0.36, -0.72, 0.06), lt=(0.38, -0.82, 0.03),
              rk=(-0.3, -0.35, 0.32), ra=(-0.36, -0.72, 0.06), rt=(-0.38, -0.82, 0.03))
    return p


def pose_straddle():
    """Kneeling astride a partner who lies on the back (same origin, facing the partner's head)."""
    return dict(pelvis=(0, 0.02, 0.36), belly=(0, 0.04, 0.52), chest=(0, 0.02, 0.72), neck=(0, 0.02, 0.9),
                head=(0, 0.05, 1.02), ls=(0.18, 0.02, 0.84), rs=(-0.18, 0.02, 0.84),
                le=(0.26, 0.16, 0.62), re=(-0.24, 0.1, 0.6), lw=(0.18, 0.32, 0.42), rw=(-0.16, 0.3, 0.4),
                lh=(0.16, 0.37, 0.36), rh=(-0.14, 0.35, 0.34), lhip=(0.11, 0.02, 0.34), rhip=(-0.11, 0.02, 0.34),
                lk=(0.34, 0.08, 0.07), rk=(-0.34, 0.08, 0.07), la=(0.3, -0.36, 0.06), ra=(-0.3, -0.36, 0.06),
                lt=(0.28, -0.46, 0.03), rt=(-0.28, -0.46, 0.03))


def pose_on_top():
    """Lying face down on a partner, between the partner's knees, weight on the elbows."""
    return dict(pelvis=(0, -0.05, 0.36), belly=(0, 0.12, 0.37), chest=(0, 0.32, 0.39), neck=(0.03, 0.5, 0.38),
                head=(0.13, 0.62, 0.32), ls=(0.18, 0.4, 0.39), rs=(-0.18, 0.4, 0.39),
                le=(0.32, 0.5, 0.14), re=(-0.32, 0.5, 0.14), lw=(0.24, 0.68, 0.08), rw=(-0.24, 0.68, 0.08),
                lh=(0.2, 0.74, 0.07), rh=(-0.2, 0.74, 0.07), lhip=(0.1, -0.07, 0.34), rhip=(-0.1, -0.07, 0.34),
                lk=(0.13, -0.5, 0.13), rk=(-0.13, -0.5, 0.13), la=(0.13, -0.95, 0.07), ra=(-0.13, -0.95, 0.07),
                lt=(0.13, -1.03, 0.02), rt=(-0.13, -1.03, 0.02))


def pose_lap():
    """Sitting in the lap of a cross-legged partner, face to face, legs around the partner."""
    return dict(pelvis=(0, 0.24, 0.26), belly=(0, 0.22, 0.42), chest=(0, 0.19, 0.6), neck=(0.04, 0.15, 0.78),
                head=(0.13, 0.13, 0.88), ls=(0.18, 0.19, 0.7), rs=(-0.18, 0.19, 0.7),
                le=(0.3, 0.02, 0.62), re=(-0.3, 0.02, 0.6), lw=(0.16, -0.14, 0.6), rw=(-0.16, -0.14, 0.58),
                lh=(0.1, -0.16, 0.6), rh=(-0.1, -0.16, 0.58), lhip=(0.1, 0.24, 0.24), rhip=(-0.1, 0.24, 0.24),
                lk=(0.32, -0.02, 0.22), rk=(-0.32, -0.02, 0.22), la=(0.22, -0.28, 0.1), ra=(-0.22, -0.28, 0.1),
                lt=(0.16, -0.36, 0.08), rt=(-0.16, -0.36, 0.08))


def pose_hold_cross():
    p = pose_sit_cross()
    return _arms(p, le=(0.28, 0.2, 0.5), lw=(0.18, 0.4, 0.62), lh=(0.12, 0.44, 0.63),
                 re=(-0.28, 0.2, 0.46), rw=(-0.18, 0.4, 0.5), rh=(-0.12, 0.44, 0.5),
                 head=(-0.1, 0.06, 0.8))


def pose_spoon_big():
    p = pose_lie_side()
    return _arms(p, re=(-0.08, 0.42, 0.36), rw=(-0.3, 0.42, 0.3), rh=(-0.36, 0.4, 0.27))


def drape(name, objs, center, size, rz, mat, base_fn, n=34):
    """Blanket laid over bodies: a grid dropped onto the figures, softened, edges hanging down."""
    bpy.context.view_layer.update()
    verts, polys = [], []
    for ob in objs:
        o = len(verts)
        verts += [ob.matrix_world @ v.co for v in ob.data.vertices]
        polys += [[o + i for i in p.vertices] for p in ob.data.polygons]
    tree = BVHTree.FromPolygons(verts, polys)
    R = Matrix.Rotation(rad(rz), 3, 'Z')
    W, L = size
    grid, base = [], []
    for j in range(n + 1):
        row, brow = [], []
        for i in range(n + 1):
            p = Vector(center) + R @ Vector(((i / n - 0.5) * W, (j / n - 0.5) * L, 0))
            b = base_fn(p.x, p.y)
            hit = tree.ray_cast(Vector((p.x, p.y, b + 2.5)), Vector((0, 0, -1)))
            z = max(b + 0.015, hit[0].z + 0.03) if hit[0] is not None else b + 0.015
            row.append([p.x, p.y, z])
            brow.append(b)
        grid.append(row)
        base.append(brow)
    raw = [[c[2] for c in row] for row in grid]
    z = [r[:] for r in raw]
    for _ in range(6):
        z2 = [r[:] for r in z]
        for j in range(1, n):
            for i in range(1, n):
                z2[j][i] = max(raw[j][i], (z[j - 1][i] + z[j + 1][i] + z[j][i - 1] + z[j][i + 1]) / 4)
        z = z2
    bm = bmesh.new()
    vv = []
    for j in range(n + 1):
        rowv = []
        for i in range(n + 1):
            e = min(i, j, n - i, n - j) / n
            f = min(1.0, e / 0.08)
            zz = base[j][i] + 0.01 + (z[j][i] - base[j][i] - 0.01) * (0.35 + 0.65 * f)
            rowv.append(bm.verts.new((grid[j][i][0], grid[j][i][1], zz)))
        vv.append(rowv)
    for j in range(n):
        for i in range(n):
            bm.faces.new((vv[j][i], vv[j][i + 1], vv[j + 1][i + 1], vv[j + 1][i]))
    ob = mk_obj(name, bm, mat, EV, smooth=True, recalc=False)
    ob.modifiers.new('solid', 'SOLIDIFY').thickness = 0.02
    ob.modifiers.new('sub', 'SUBSURF').levels = 1
    return ob


def couple(name, kind, loc, rz, seed, blanket_mat=None, base_fn=None, cover=(-1.15, 0.0)):
    if not EVENT_MANNEQUINS:
        return []
    loc = Vector(loc)
    if kind == 'straddle':
        obs = [person(name + '_a', _pose_bottom('straddle'), loc, rz, seed=seed),
               person(name + '_b', pose_straddle(), loc, rz, seed=seed + 1)]
    elif kind == 'on_top':
        obs = [person(name + '_a', _pose_bottom('on_top'), loc, rz, seed=seed),
               person(name + '_b', pose_on_top(), loc, rz, seed=seed + 1)]
    elif kind == 'lap':
        obs = [person(name + '_a', pose_hold_cross(), loc, rz, seed=seed),
               person(name + '_b', pose_lap(), loc, rz, seed=seed + 1)]
    else:  # spoon
        d = Matrix.Rotation(rad(rz), 4, 'Z') @ Vector((0.25, -0.03, 0.0))
        obs = [person(name + '_a', pose_lie_side(), loc, rz, seed=seed),
               person(name + '_b', pose_spoon_big(), loc + d, rz, seed=seed + 1)]
    if blanket_mat:
        y0, y1 = cover
        c = loc + Matrix.Rotation(rad(rz), 4, 'Z') @ Vector((0.0, (y0 + y1) / 2, 0))
        bf = base_fn or (lambda x, y: loc.z)
        drape(name + '_blanket', obs, (c.x, c.y, 0), (1.35, y1 - y0), rz, blanket_mat, bf)
    return obs


def at(r, a, z=0.0):
    p = pol(r, a)
    return (p.x, p.y, z)


# --- centre: contact improvisation in the evening light ---------------------------------------
pairs = [(1.3, 20), (1.5, 140), (1.2, 255), (2.2, 320)]
for i, (rr, a) in enumerate(pairs):
    c = pol(rr, a)
    if i == 3:
        person('ev_ci_base_%d' % i, pose_all_fours(), (c.x, c.y, 0.03), rz=a, seed=i)
        person('ev_ci_top_%d' % i, pose_lie_back('open'), (c.x + 0.05, c.y + 0.05, 0.62), rz=a + 90, seed=i + 1)
        continue
    person('ev_ci_a_%d' % i, pose_lean(), (c.x, c.y, 0.03), rz=a, outfit=('skirt', list(FAB.values())[i]), seed=i)
    d = Matrix.Rotation(rad(a), 4, 'Z') @ Vector((0, 0.72, 0))
    person('ev_ci_b_%d' % i, pose_lean(), (c.x + d.x, c.y + d.y, 0.03), rz=a + 180,
           outfit=('skirt', list(FAB.values())[i + 3]) if i % 2 else None, seed=i + 10)
for i, (rr, a, mat) in enumerate(((2.6, 80, 'turquoise'), (2.9, 200, 'saffron'), (3.2, 110, 'ivory'))):
    person('ev_dancer_%d' % i, pose_dance_open(), at(rr, a, 0.03), rz=a + 60 * i, outfit=('skirt', FAB[mat]), seed=30 + i)
person('ev_crazy_0', pose_dance_open(), at(3.4, 30, 0.03), rz=210, outfit=('cape', FAB['gold']), seed=41)
person('ev_crazy_1', pose_stand_relaxed(), at(3.6, 290, 0.03), rz=100, outfit=('cape', FAB['magenta']), seed=42)

# --- mat zones ----------------------------------------------------------------------------------
# cuddle zone (east)
cz = 310
for i, (dr, da, rz) in enumerate(((0, -6, 10), (0, 6, 10), (1.5, 0, 100), (-1.2, -2, 100))):
    c = pol(7.2 + dr, cz + da)
    mattress('ev_cuddle_mat_%d' % i, (c.x, c.y), cz + rz, mat=M_WOOL['cream'] if i % 2 else M_MATTRESS)
for i, (dr, da, rz, pose) in enumerate(((0.2, -4, 90, pose_lie_side()), (-0.3, -3, 270, pose_lie_back('open')),
                                        (0.4, 5, 80, pose_lie_side()), (-0.2, 6, 260, pose_lie_back('head')),
                                        (1.5, 1, 190, pose_sit_lean()))):
    c = pol(7.2 + dr, cz + da)
    person('ev_cuddle_%d' % i, pose, (c.x, c.y, 0.18), rz=cz + rz, seed=50 + i)
# mattress field under the net: people below can look up at the people on the net
MF = [(0, 0, 0)] + [(1.45 * math.cos(rad(a)), 1.45 * math.sin(rad(a)), a + 90) for a in range(0, 360, 60)] + \
     [(2.75 * math.cos(rad(a)), 2.75 * math.sin(rad(a)), a) for a in range(30, 360, 60)]
for i, (x, y, rz) in enumerate(MF):
    mattress('ev_field_mat_%02d' % i, (x, y), rz, mat=[M_MATTRESS, M_WOOL['cream'], M_WOOL['sand']][i % 3],
             size=(1.4, 1.9, 0.15 + 0.012 * (i % 3)))
# intimacy zone (south-west) under a round linen canopy, half open towards the hall
iz = 235
cc = pol(7.0, iz)
bm = bmesh.new()
prev = None
for i in range(90):
    a = 360 * i / 89
    if 330 < (a - (iz + 180)) % 360 or (a - (iz + 180)) % 360 < 30:     # opening towards the hall
        prev = None
        continue
    rr = 2.0 + 0.06 * math.sin(a * 0.4)
    col_ = [bm.verts.new((cc.x + rr * math.cos(rad(a)), cc.y + rr * math.sin(rad(a)), 0.02)),
            bm.verts.new((cc.x + rr * math.cos(rad(a)), cc.y + rr * math.sin(rad(a)), 3.3))]
    if prev:
        bm.faces.new((prev[0], col_[0], col_[1], prev[1]))
    prev = col_
mk_obj('ev_canopy', bm, M_SHEER, EV, smooth=True, recalc=False)
bm = bmesh.new()
sector(bm, 1.95, 2.05, 0, 360, 3.28, 3.34, step=4)
bmesh.ops.translate(bm, vec=Vector((cc.x, cc.y, 0)), verts=bm.verts[:])
mk_obj('ev_canopy_ring', bm, M_WOOD, EV)
for i, (dx, dy) in enumerate(((-0.72, 0.0), (0.72, 0.0), (0.0, 1.05))):
    v = Matrix.Rotation(rad(iz), 4, 'Z') @ Vector((dx, dy - 0.3, 0))
    mattress('ev_int_mat_%d' % i, (cc.x + v.x, cc.y + v.y), iz, mat=M_WOOL['wine'] if i == 2 else M_MATTRESS)
for i, (dx, dy, kind, bl) in enumerate(((-0.72, -0.15, 'straddle', 'terracotta'), (0.72, -0.2, 'spoon', 'rose'),
                                        (0.0, 0.95, 'lap', None))):
    v = Matrix.Rotation(rad(iz), 4, 'Z') @ Vector((dx, dy, 0))
    couple('ev_int_%d' % i, kind, (cc.x + v.x, cc.y + v.y, 0.18), iz + (90 if kind == 'lap' else 0), 60 + 2 * i,
           blanket_mat=M_WOOL[bl] if bl else None, cover=(-1.0, -0.1) if kind == 'straddle' else (-1.15, 0.25))
for i in range(3):
    ev_light('ev_int_candle_%d' % i, tuple(pol(1.6, iz + 150 + 30 * i) + Vector((cc.x, cc.y, 0.3))), 3.0)
# wrestling zone (west)
wz = 178
for i, (dr, da) in enumerate(((0, -5), (0, 5), (1.4, -5), (1.4, 5))):
    c = pol(6.6 + dr, wz + da)
    mattress('ev_wrestle_mat_%d' % i, (c.x, c.y), wz + 90, mat=M_WOOL['olive'] if i % 3 == 0 else M_WOOL['sand'],
             size=(1.4, 2.0, 0.12))
c = pol(7.2, wz - 3)
person('ev_wrestle_a', pose_crouch(), (c.x, c.y, 0.12), rz=wz + 90, seed=70)
d = Matrix.Rotation(rad(wz + 90), 4, 'Z') @ Vector((0, 0.95, 0))
person('ev_wrestle_b', pose_crouch(), (c.x + d.x, c.y + d.y, 0.12), rz=wz + 270, seed=71)
c = pol(7.0, wz + 6)
person('ev_wrestle_c', pose_all_fours(), (c.x, c.y, 0.12), rz=wz, seed=72)
person('ev_wrestle_d', pose_lie_side(), (c.x + 0.1, c.y, 0.7), rz=wz + 90, seed=73)
# musician + speakers by the bar
mc = FP(P.BAR_FACE, P.R_IN - 3.0, -2.4, 0)
person('ev_musician', pose_sit_cross(), (mc.x, mc.y, 0.14), rz=P.slot_center(P.BAR_FACE) + 90,
       outfit=('robe', FAB['moss']), seed=80)
bm = bmesh.new()
cyl(bm, (mc.x + 0.3, mc.y - 0.3, 0.2), 0.28, 0.12, segs=40)
mk_obj('ev_handpan', bm, M_STEEL, EV, smooth=True)
for s in (-1, 1):
    sp = FP(P.BAR_FACE, P.R_IN - 1.0, -2.4 + s * 1.6, 0)
    bm = bmesh.new()
    cube(bm, (sp.x, sp.y, 1.2), (0.35, 0.3, 0.55), rz=P.slot_center(P.BAR_FACE))
    cyl(bm, (sp.x, sp.y, 0.46), 0.02, 0.9, segs=8)
    mk_obj('ev_speaker_%d' % s, bm, M_WOOD_DARK, EV)
# people at the bar and on the stair seating steps
bc = FP(P.BAR_FACE, P.R_IN - 2.2, 1.0, 0)
person('ev_bar_0', pose_stand_relaxed(), (bc.x, bc.y, 0), rz=P.slot_center(P.BAR_FACE) - 90 + 30,
       outfit=('robe', FAB['ivory']), seed=81)
person('ev_bar_1', pose_stand_relaxed(), (bc.x + 0.4, bc.y - 0.6, 0), rz=P.slot_center(P.BAR_FACE) - 90 - 40,
       outfit=('skirt', FAB['plum']), seed=82)
for i, (tr, dn) in enumerate(((2, -0.7), (3, -0.1))):
    sc = FP(P.STAIR_SLOT, P.R_IN - P.STAIR_FLIGHT_W_T + dn, P.STAIR_T0 + (tr - 0.5) * P.STAIR_GOING_T, 0)
    person('ev_steps_%d' % i, pose_sit_knees(), (sc.x, sc.y, P.STAIR_RISE * tr - 0.12),
           rz=P.slot_center(P.STAIR_SLOT) + 90, outfit=('skirt', FAB['crimson']) if i else None, seed=85 + i)
# organisers: kimono + clipboard
oc = FP(P.ENTRY_SLOT, P.R_IN - 1.6, 1.1, 0)
person('ev_org_0', pose_organiser(), (oc.x, oc.y, 0), rz=P.slot_center(P.ENTRY_SLOT) + 90 - 25,
       outfit=('kimono', KIMONO[0]), seed=90)
o2 = pol(5.0, 284, P.FFL_UF)
person('ev_org_1', pose_organiser(), tuple(o2), rz=284 - 90 - 30, outfit=('kimono', KIMONO[1]), seed=91)

# --- the net: couples lying entwined, one resting alone ----------------------------------------
NETB = lambda x, y: on_net(x, y) - 0.03  # noqa: E731
couple('ev_net_0', 'straddle', (-0.9, 0.7, on_net(-0.9, 0.7) - 0.05), 30, 100)
couple('ev_net_1', 'on_top', (1.4, -0.5, on_net(1.4, -0.5) - 0.05), 120, 102, blanket_mat=M_WOOL['rose'],
       base_fn=NETB, cover=(-1.2, -0.05))
couple('ev_net_2', 'spoon', (0.3, -2.2, on_net(0.3, -2.2) - 0.05), 80, 104)
person('ev_net_3', pose_lie_back('head'), (-2.1, -1.2, on_net(-2.1, -1.2) - 0.05), rz=250, seed=106)
pw_ = pol(4.08, 250)
person('ev_pad', pose_sit_lean(), (pw_.x, pw_.y, P.RING_BEAM_TOP + P.PAD_T - 0.16), rz=250 + 90,
       outfit=('robe', FAB['sky']), seed=110)

# --- rooms upstairs: couples on the nests in the open / half-open rooms --------------------------
for k in (2, 3, 5, 7):
    a = P.slot_center(k)
    kind = {2: 'straddle', 3: 'spoon', 5: 'lap', 7: 'on_top'}[k]
    v = Matrix.Rotation(rad(a), 4, 'Z') @ Vector((8.45, 0.0, 0))
    couple('ev_room_%d' % k, kind, (v.x, v.y, P.FFL_UF + 0.47), a + (0 if kind == 'lap' else 90), 120 + 3 * k,
           blanket_mat=M_WOOL['cream'] if kind in ('on_top', 'spoon') else None)

# --- warm candle / lantern light for the event ------------------------------------------------
bm = bmesh.new()
for i in range(10):
    a = 36 * i + 10
    ev_light('ev_floor_candle_%d' % i, at(8.9, a, 0.3), 4.0)
    for j in range(3):
        c = pol(8.9 + 0.1 * (j - 1), a + 0.8 * j)
        cyl(bm, (c.x, c.y, 0.08 + 0.02 * j), 0.035, 0.16 + 0.04 * j, segs=12)
mk_obj('ev_candles', bm, M_CANDLE, EV, smooth=True)
for i, a in enumerate((358, 178)):
    ev_light('ev_zone_glow_%d' % i, at(7.2, a, 1.2), 25.0, soft=0.5)

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
# event layer hidden by default (render.py switches it on for the event views)
COLLS[EV].hide_render = True
COLLS[EV].hide_viewport = True

out = os.path.join(HERE, 'tempel.blend')
bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
print('saved', out, len(bpy.data.objects), 'objects')
