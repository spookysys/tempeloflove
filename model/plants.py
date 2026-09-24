"""Realistic plants for the model (post-process on tempel.blend).

    python3 plants.py            -> updates model/tempel.blend

1. Climbing roses on the octagon facades and the external stair: a small growth generator
   (shoots from the ground bed climb the wall, wander sideways, branch, grow around doors and
   windows), photographic rose leaves (ambientCG LeafSet005 / LeafSet024, CC0) and rose blossoms.
   They replace the old procedural facade vines.
2. (see further below) scanned trees, shrubs, grass and indoor plants from Poly Haven (CC0).

Assets are looked up in PLANT_DIR (default /tmp/claude-0/mh): ph/<asset>/..., acg/<LeafSet>/...
"""
import json
import math
import os
import random
import sys

import bpy  # noqa: E402  (bpy first, then bmesh)
import bmesh  # noqa: E402
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import params as P  # noqa: E402

PLANT_DIR = os.environ.get('PLANT_DIR', '/tmp/claude-0/mh')
ACG = os.path.join(PLANT_DIR, 'acg')
CROPS = json.load(open(os.path.join(HERE, 'leaf_crops.json')))
rad = math.radians


def FP(k, n, t, z=0.0):
    a = rad(P.slot_center(k))
    return Vector((n * math.cos(a) - t * math.sin(a), n * math.sin(a) + t * math.cos(a), z))


def coll(name):
    c = bpy.data.collections.get(name)
    if not c:
        c = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(c)
    return c


# ---------------------------------------------------------------------------
# materials
# ---------------------------------------------------------------------------
def leaf_material(atlas, name, tint=1.0):
    m = bpy.data.materials.new(name)
    m['vp_color'] = [0.18, 0.32, 0.12]
    m['vp_alpha'] = 1.0
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    uv = nt.nodes.new('ShaderNodeTexCoord').outputs['UV']
    img = lambda kind, cs='sRGB': bpy.data.images.load(os.path.join(ACG, atlas, '%s_1K-JPG_%s.jpg' % (atlas, kind)),  # noqa
                                                         check_existing=True)
    col = nt.nodes.new('ShaderNodeTexImage')
    col.image = img('Color')
    op = nt.nodes.new('ShaderNodeTexImage')
    op.image = img('Opacity')
    op.image.colorspace_settings.name = 'Non-Color'
    nm = nt.nodes.new('ShaderNodeTexImage')
    nm.image = img('NormalGL')
    nm.image.colorspace_settings.name = 'Non-Color'
    for t in (col, op, nm):
        nt.links.new(uv, t.inputs['Vector'])
    nmap = nt.nodes.new('ShaderNodeNormalMap')
    nt.links.new(nm.outputs['Color'], nmap.inputs['Color'])
    hsv = nt.nodes.new('ShaderNodeHueSaturation')
    hsv.inputs['Value'].default_value = tint
    nt.links.new(col.outputs['Color'], hsv.inputs['Color'])
    bs = nt.nodes.new('ShaderNodeBsdfPrincipled')
    nt.links.new(hsv.outputs['Color'], bs.inputs['Base Color'])
    nt.links.new(nmap.outputs['Normal'], bs.inputs['Normal'])
    bs.inputs['Roughness'].default_value = 0.45
    tr = nt.nodes.new('ShaderNodeBsdfTranslucent')      # light through the leaves
    nt.links.new(hsv.outputs['Color'], tr.inputs['Color'])
    mix = nt.nodes.new('ShaderNodeMixShader')
    mix.inputs[0].default_value = 0.25
    nt.links.new(bs.outputs[0], mix.inputs[1])
    nt.links.new(tr.outputs[0], mix.inputs[2])
    tp = nt.nodes.new('ShaderNodeBsdfTransparent')
    cut = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(op.outputs['Color'], cut.inputs[0])
    nt.links.new(tp.outputs[0], cut.inputs[1])
    nt.links.new(mix.outputs[0], cut.inputs[2])
    nt.links.new(cut.outputs[0], out.inputs['Surface'])
    try:
        m.surface_render_method = 'DITHERED'
    except AttributeError:
        pass
    return m


def simple_material(name, hexcol, rough=0.6, sss=0.0, sheen=0.0):
    h = hexcol.lstrip('#')
    c = [((int(h[i:i + 2], 16) / 255) / 12.92 if int(h[i:i + 2], 16) / 255 <= 0.04045 else
          (((int(h[i:i + 2], 16) / 255) + 0.055) / 1.055) ** 2.4) for i in (0, 2, 4)]
    m = bpy.data.materials.new(name)
    m['vp_color'] = c
    m['vp_alpha'] = 1.0
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = c + [1.0]
    b.inputs['Roughness'].default_value = rough
    b.inputs['Subsurface Weight'].default_value = sss
    b.inputs['Subsurface Radius'].default_value = (0.3, 0.1, 0.1)
    b.inputs['Sheen Weight'].default_value = sheen
    return m


# ---------------------------------------------------------------------------
# rose blossom prototypes (instanced)
# ---------------------------------------------------------------------------
def rose_mesh(name, rng):
    """A rose head: a tight bud and three rings of cupped petals opening outwards (~7 cm)."""
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=10, v_segments=6, radius=0.012,
                              matrix=Matrix.Translation((0, 0, 0.018)) @ Matrix.Diagonal((1, 1, 1.4, 1)))
    rings = [(5, 0.018, 20, 0.024), (6, 0.026, 45, 0.03), (7, 0.034, 70, 0.034)]
    for ri, (n, r, open_deg, size) in enumerate(rings):
        for i in range(n):
            a = 2 * math.pi * (i + 0.5 * ri) / n + rng.uniform(-0.15, 0.15)
            verts = []
            for u in range(5):
                row = []
                for v in range(4):
                    s = (u / 4 - 0.5) * size          # across the petal
                    h = v / 3 * size * 1.1            # up the petal
                    cup = 0.35 * size * (2 * (u / 4 - 0.5)) ** 2
                    tilt = rad(open_deg) * (v / 3)
                    x = r * 0.4 + h * math.sin(tilt) + cup * 0.5
                    z = 0.006 + h * math.cos(tilt) + cup * 0.3
                    p = Vector((x, s, z))
                    p.rotate(Matrix.Rotation(a, 3, 'Z'))
                    row.append(bm.verts.new(p))
                verts.append(row)
            for u in range(4):
                for v in range(3):
                    bm.faces.new((verts[u][v], verts[u + 1][v], verts[u + 1][v + 1], verts[u][v + 1]))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    return me


# ---------------------------------------------------------------------------
# climbing roses
# ---------------------------------------------------------------------------
OPEN = P.face_openings()


def blocked(k, t, z, margin=0.12):
    for (t0, t1, z0, z1, kind) in OPEN[k]:
        if t0 - margin < t < t1 + margin and z0 - margin < z < z1 + margin:
            return (t0, t1, z0, z1)
    return None


def grow_shoot(k, t, z, height, rng, half):
    """One shoot climbing the wall (face-local t, z), steering around openings."""
    pts = [(t, z)]
    dt = rng.uniform(-0.45, 0.45)
    step = 0.06
    while z < height and len(pts) < 400:
        dt += rng.uniform(-0.25, 0.25)
        dt = max(-0.9, min(0.9, dt))
        nt_, nz = t + dt * step, z + step
        b = blocked(k, nt_, nz)
        if b:                                   # steer around a door / window
            t0, t1, z0, z1 = b
            if nz < z1 + 0.15 and (t1 - t0) > 0.3:
                go = t0 - 0.2 if abs(nt_ - t0) < abs(nt_ - t1) else t1 + 0.2
                nt_ = t + math.copysign(step * 1.2, go - t)
                nz = z + step * 0.25
            if blocked(k, nt_, nz):
                break
        if abs(nt_) > half - 0.12:
            nt_ = math.copysign(half - 0.12, nt_)
            dt = -dt
        t, z = nt_, nz
        pts.append((t, z))
    return pts


def roses_on_face(k, rng, plants=3, n_off=0.07):
    half = P.face_half(P.R_OUT)
    shoots = []
    ts = []
    for i in range(plants):
        for _ in range(20):
            t = rng.uniform(-half + 0.4, half - 0.4)
            if not blocked(k, t, 0.3, margin=0.25) and all(abs(t - u) > 0.9 for u in ts):
                ts.append(t)
                break
    for t in ts:
        for s in range(rng.randint(6, 9)):     # several canes from one root
            h = rng.uniform(2.6, 6.2)
            shoots.append(grow_shoot(k, t + rng.uniform(-0.1, 0.1), 0.0, h, rng, half))
            # side branches
            main = shoots[-1]
            for _ in range(rng.randint(3, 6)):
                if len(main) < 12:
                    break
                bi = rng.randrange(len(main) // 3, len(main) - 3)
                bt, bz = main[bi]
                shoots.append(grow_shoot(k, bt, bz, bz + rng.uniform(0.5, 1.8), rng, half))
    return [[FP(k, n_off_i(n_off, rng), t, z) for (t, z) in sh] for sh in shoots]


def n_off_i(n, rng):
    return P.R_OUT + n + rng.uniform(-0.015, 0.02)


def build_roses(seed=7):
    rng = random.Random(seed)
    col = coll('roses')
    # old procedural facade vines out
    for o in list(bpy.data.objects):
        if o.name.startswith(('vine_', 'vine')) and o.users_collection and o.users_collection[0].name == 'plants':
            bpy.data.objects.remove(o)
    stem_mat = simple_material('rose_cane', '#5B6B3A', rough=0.7)
    leaf_mats = [leaf_material('LeafSet005', 'rose_leaf_a', 0.85), leaf_material('LeafSet024', 'rose_leaf_b', 0.8)]
    colours = [('#E8A3B5', 'rose_pink'), ('#B3243A', 'rose_red'), ('#F3E3C8', 'rose_cream'), ('#E57A6A', 'rose_coral')]
    petal_mats = [simple_material(n, h, rough=0.45, sss=0.25, sheen=0.4) for h, n in colours]
    protos = [rose_mesh('rose_head_%d' % i, rng) for i in range(3)]
    faces = [k for k in range(P.N_SLOTS) if k not in P.ANNEX_FACES]
    all_shoots = []
    for k in faces:
        all_shoots += roses_on_face(k, rng, plants=4 if k != P.STAIR_SLOT else 5)
    # canes as one curve object
    cu = bpy.data.curves.new('rose_canes', 'CURVE')
    cu.dimensions = '3D'
    cu.bevel_depth = 0.006
    cu.bevel_resolution = 1
    for sh in all_shoots:
        sp = cu.splines.new('POLY')
        sp.points.add(len(sh) - 1)
        for i, p in enumerate(sh):
            sp.points[i].co = (p.x, p.y, p.z, 1)
            sp.points[i].radius = 1.6 - 1.2 * i / max(1, len(sh) - 1)
    cu.materials.append(stem_mat)
    ob = bpy.data.objects.new('rose_canes', cu)
    col.objects.link(ob)
    # leaves: cards with a photographic leaf each, facing out from the wall with some tilt
    for li, lm in enumerate(leaf_mats):
        atlas = ['LeafSet005', 'LeafSet024'][li]
        bm = bmesh.new()
        uvl = bm.loops.layers.uv.new('UVMap')
        for sh in all_shoots[li::2]:
            for i in range(1, len(sh) - 1, 1):
                if rng.random() > 0.95:
                    continue
                p = sh[i]
                d = (sh[i + 1] - sh[i - 1]).normalized()
                outw = Vector((p.x, p.y, 0)).normalized()
                for _ in range(rng.randint(2, 4)):
                    x0, y0, x1, y1 = rng.choice(CROPS[atlas])
                    size = rng.uniform(0.06, 0.11)
                    asp = (x1 - x0) / max(1e-3, (y1 - y0))
                    side = outw.cross(d).normalized() * rng.choice((-1, 1))
                    axis = (side * 0.8 + d * rng.uniform(-0.3, 0.6) + outw * rng.uniform(0.2, 0.9)).normalized()
                    up = axis.cross(outw).normalized()
                    up = (up + outw * rng.uniform(0.3, 1.0)).normalized()
                    w = size * asp * 0.5
                    base = p + outw * 0.01
                    q = [base - up * w, base + up * w, base + up * w + axis * size, base - up * w + axis * size]
                    vs = [bm.verts.new(v) for v in q]
                    f = bm.faces.new(vs)
                    for loop, uv in zip(f.loops, ((x0, y0), (x1, y0), (x1, y1), (x0, y1))):
                        loop[uvl].uv = uv
        me = bpy.data.meshes.new('rose_leaves_%d' % li)
        bm.to_mesh(me)
        bm.free()
        me.materials.append(lm)
        o = bpy.data.objects.new('rose_leaves_%d' % li, me)
        col.objects.link(o)
    # blossoms: mostly in the upper, sunnier parts, often in clusters
    n = 0
    for sh in all_shoots:
        for i in range(len(sh) // 3, len(sh), 1):
            if rng.random() > 0.11:
                continue
            p = sh[i]
            outw = Vector((p.x, p.y, 0)).normalized()
            ci = rng.randrange(len(colours))
            for _ in range(rng.choice((1, 1, 2, 3))):
                o = bpy.data.objects.new('rose_%d' % n, rng.choice(protos))
                o.data.materials.clear() if o.data.users == 1 and not o.data.materials else None
                o.material_slots  # noqa
                o.location = p + outw * 0.03 + Vector((rng.uniform(-0.05, 0.05), rng.uniform(-0.05, 0.05),
                                                       rng.uniform(-0.04, 0.04)))
                look = (outw + Vector((0, 0, rng.uniform(0.2, 0.9))) +
                        Vector((rng.uniform(-0.4, 0.4), rng.uniform(-0.4, 0.4), 0))).normalized()
                o.rotation_euler = look.to_track_quat('Z', 'Y').to_euler()
                o.scale = [rng.uniform(0.85, 1.35)] * 3
                o.active_material = None
                col.objects.link(o)
                o.material_slots  # noqa
                if not o.data.materials:
                    o.data.materials.append(petal_mats[0])
                o.material_slots[0].link = 'OBJECT'
                o.material_slots[0].material = petal_mats[ci]
                n += 1
    print('roses:', len(all_shoots), 'canes,', n, 'blossoms')


# ---------------------------------------------------------------------------
# scanned forest (Poly Haven, CC0): the three pines of pine_tree_01, rebuilt light (twig cards),
# instanced in place of the old procedural pines; shrubs and meadow grass near the building
# ---------------------------------------------------------------------------
def append_objects(blend, prefix):
    with bpy.data.libraries.load(blend, link=False) as (src, dst):
        dst.objects = list(src.objects)
    obs = [o for o in dst.objects if o is not None]
    for o in obs:
        o.name = prefix + o.name
    return obs


def build_forest(seed=11):
    rng = random.Random(seed)
    col = coll('forest_scanned')
    lib = coll('forest_library')
    lib.hide_render = True
    lib.hide_viewport = True
    pines = append_objects(os.path.join(PLANT_DIR, 'ph', 'pine_tree_01_lod.blend'), 'lib_')
    groups = {}
    for o in pines:
        lib.objects.link(o)
        key = o.name.replace('_twigs', '')
        groups.setdefault(key, []).append(o)
    # one collection per pine variant (trunk + twigs), instanced
    protos = []
    for key, obs in groups.items():
        c = bpy.data.collections.new('pine_' + key[-10:])
        for o in obs:
            c.objects.link(o)
            o.location = (o.location.x - obs[0].location.x, o.location.y - obs[0].location.y, o.location.z)
        protos.append(c)
    # replace old pines (trunk + crown) by instances at the same spots
    n = 0
    for o in list(bpy.data.objects):
        if o.name.startswith('pine_') and o.name.endswith('_trunk'):
            base = o.name[:-6]
            bb = [o.matrix_world @ Vector(c_) for c_ in o.bound_box]
            x = sum(v.x for v in bb) / 8
            y = sum(v.y for v in bb) / 8
            h = max(v.z for v in bb)
            inst = bpy.data.objects.new('scan_' + base, None)
            inst.instance_type = 'COLLECTION'
            inst.instance_collection = rng.choice(protos)
            inst.location = (x, y, 0)
            inst.rotation_euler = (0, 0, rng.uniform(0, 6.283))
            inst.scale = [h / 20.0 * rng.uniform(0.95, 1.1)] * 3
            col.objects.link(inst)
            for suffix in ('_trunk', '_crown'):
                ob = bpy.data.objects.get(base + suffix)
                if ob:
                    bpy.data.objects.remove(ob)
            n += 1
    print('forest:', n, 'scanned pines')


def build_ground_plants(seed=13):
    """Scanned shrubs and grass tufts around the building (meadow edge, beds by the walls)."""
    rng = random.Random(seed)
    col = coll('ground_plants')
    lib = coll('forest_library')
    protos = {}
    for a in ('shrub_01', 'shrub_02', 'shrub_03', 'shrub_04', 'fern_02', 'grass_medium_01', 'grass_medium_02'):
        path = os.path.join(PLANT_DIR, 'ph', a, a + '_1k.gltf')
        if not os.path.exists(path):
            continue
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=path)
        new = [o for o in bpy.data.objects if o not in before]
        c = bpy.data.collections.new('proto_' + a)
        for o in new:
            for uc in list(o.users_collection):
                uc.objects.unlink(o)
            c.objects.link(o)
        protos[a] = c
    placed = 0
    for i in range(420):
        a = rng.uniform(0, 360)
        d = rng.uniform(P.R_OUT + 0.4, P.R_OUT + 14) if i % 3 else rng.uniform(P.R_OUT + 0.25, P.R_OUT + 1.0)
        x, y = d * math.cos(rad(a)), d * math.sin(rad(a))
        kind = rng.choice(['grass_medium_01', 'grass_medium_02'] * 4 + ['fern_02', 'shrub_01', 'shrub_02',
                                                                         'shrub_03', 'shrub_04'])
        if kind not in protos:
            continue
        # keep paths, the garden deck and doors free
        if (P.slot_center(P.GARDEN_SLOT) - 20 < a < P.slot_center(P.GARDEN_SLOT) + 20 and d < P.R_OUT + 5) or \
                (P.slot_center(P.ENTRY_SLOT) - 25 < a < P.slot_center(P.ENTRY_SLOT) + 25):
            continue
        inst = bpy.data.objects.new('gp_%03d' % i, None)
        inst.instance_type = 'COLLECTION'
        inst.instance_collection = protos[kind]
        inst.location = (x, y, 0)
        inst.rotation_euler = (0, 0, rng.uniform(0, 6.283))
        inst.scale = [rng.uniform(1.4, 2.6) if 'shrub' in kind else rng.uniform(0.8, 1.5)] * 3
        col.objects.link(inst)
        placed += 1
    print('ground plants:', placed)


if __name__ == '__main__':
    bpy.ops.wm.open_mainfile(filepath=os.path.join(HERE, 'tempel.blend'))
    build_roses()
    build_forest()
    build_ground_plants()
    bpy.ops.file.pack_all() if os.environ.get('PACK') else None
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, 'tempel.blend'), compress=True)
    print('PLANTS saved')
