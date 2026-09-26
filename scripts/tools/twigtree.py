"""Light scanned pine: keep trunk + bark + branch meshes (small), replace the millions of twig
triangles by a few thousand twig cards textured with the scan's own twig texture (alpha).
Run: python3 twigtree.py <assets_dir>   (needs <assets_dir>/ph/pine_tree_01/, writes ph/pine_tree_01_lod.blend)"""
import bpy, bmesh, sys, os, random
from mathutils import Vector, Matrix
from mathutils.kdtree import KDTree
A = sys.argv[-1]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=os.path.join(A, 'ph', 'pine_tree_01', 'pine_tree_01_1k.gltf'))
rnd = random.Random(1)
out = []
for o in [o for o in bpy.data.objects if o.type == 'MESH']:
    me = o.data
    tw = [i for i, m in enumerate(me.materials) if m and m.name.endswith('twig')][0]
    twig_mat = me.materials[tw]
    # sample twig positions + normals from the twig triangles, then delete them
    bm = bmesh.new(); bm.from_mesh(me)
    faces = [f for f in bm.faces if f.material_index == tw]
    samp = [(o.matrix_world @ f.calc_center_median(), f.normal.copy()) for f in rnd.sample(faces, min(len(faces), 60000))]
    bmesh.ops.delete(bm, geom=faces, context='FACES')
    bm.to_mesh(me); bm.free()
    # cluster samples on a 0.35 m grid -> one twig card cluster per cell
    cells = {}
    for p, n in samp:
        key = (round(p.x / 0.35), round(p.y / 0.35), round(p.z / 0.35))
        cells.setdefault(key, []).append((p, n))
    bm = bmesh.new(); uvl = bm.loops.layers.uv.new('UVMap')
    for key, pts in cells.items():
        c = sum((p for p, n in pts), Vector()) / len(pts)
        for k in range(3 if len(pts) > 20 else 2):
            d = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-0.3, 0.3))).normalized()
            up = d.cross(Vector((0, 0, 1))).normalized()
            s = 0.45
            q = [c - d * s - up * s * 0.5, c + d * s - up * s * 0.5, c + d * s + up * s * 0.5, c - d * s + up * s * 0.5]
            f = bm.faces.new([bm.verts.new(v) for v in q])
            for loop, uv in zip(f.loops, ((0, 0), (1, 0), (1, 1), (0, 1))):
                loop[uvl].uv = uv
    tme = bpy.data.meshes.new(o.name + '_twigs'); bm.to_mesh(tme); bm.free()
    tme.materials.append(twig_mat)
    t = bpy.data.objects.new(o.name + '_twigs', tme); bpy.context.scene.collection.objects.link(t)
    print('TWIG', o.name, len(cells), 'clusters', len(tme.polygons), 'cards; trunk polys', len(me.polygons))
for m in bpy.data.materials:                     # twig texture has alpha: make sure it cuts out
    if m.name.endswith('twig'):
        try:
            m.surface_render_method = 'DITHERED'
        except AttributeError:
            pass
bpy.ops.file.pack_all()
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(A, 'ph', 'pine_tree_01_lod.blend'), compress=True)
print('SIZE', os.path.getsize(os.path.join(A, 'ph', 'pine_tree_01_lod.blend')) // 1024, 'KB')