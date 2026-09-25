"""Clash check: pairs of objects whose surfaces intersect (world space), for furniture and fittings.

    python3 check_clashes.py [tempel.blend]      -> CLASH lines, worst first
"""
import os
import sys

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
SKIP = ('rose', 'gp_', 'scan_', 'lib_', 'proto', 'tree', 'pine', 'birch', 'grass', 'ground', 'terrain', 'forest',
        'meadow', 'leaf', 'ivy', 'FLYCAM')
blend = next((a for a in sys.argv[1:] if a.endswith('.blend')), 'tempel.blend')
bpy.ops.wm.open_mainfile(filepath=os.path.join(HERE, blend))
dg = bpy.context.evaluated_depsgraph_get()
obs = []
for o in bpy.data.objects:
    if o.type != 'MESH' or o.hide_render or any(s in o.name.lower() for s in SKIP):
        continue
    if not any(not c.hide_render for c in o.users_collection):
        continue
    e = o.evaluated_get(dg)
    me = e.to_mesh()
    if len(me.polygons) == 0 or len(me.polygons) > 200000:
        e.to_mesh_clear()
        continue
    mw = e.matrix_world
    verts = [mw @ v.co for v in me.vertices]
    polys = [tuple(p.vertices) for p in me.polygons]
    e.to_mesh_clear()
    lo = Vector((min(v.x for v in verts), min(v.y for v in verts), min(v.z for v in verts)))
    hi = Vector((max(v.x for v in verts), max(v.y for v in verts), max(v.z for v in verts)))
    obs.append((o.name, lo, hi, verts, polys, [c.name for c in o.users_collection]))
print('objects', len(obs))


def depth(a, tb, b):
    """how deep a's vertices sit inside b (nearest-surface normal test, inside the other's bounds only)"""
    best, cnt = 0.0, 0
    for v in a[3]:
        if any(v[k] < b[1][k] or v[k] > b[2][k] for k in range(3)):
            continue
        loc, nrm, _, dist = tb.find_nearest(v)
        if loc is not None and (v - loc).dot(nrm) < -0.002:
            cnt += 1
            best = max(best, dist)
    return best, cnt

trees = {}
res = []
for i in range(len(obs)):
    a = obs[i]
    for j in range(i + 1, len(obs)):
        b = obs[j]
        if any(a[2][k] < b[1][k] + 0.005 or b[2][k] < a[1][k] + 0.005 for k in range(3)):
            continue
        for x in (a, b):
            if x[0] not in trees:
                trees[x[0]] = BVHTree.FromPolygons(x[3], x[4], epsilon=0.0)
        n = len(trees[a[0]].overlap(trees[b[0]]))
        if n:
            da, na = depth(a, trees[b[0]], b)
            db, nb = depth(b, trees[a[0]], a)
            res.append((max(da, db), n, a[0], b[0], na + nb, a[5], b[5]))
res.sort(key=lambda r: -r[0])
for d, n, an, bn, ni, ac, bc in res:
    print('CLASH depth %.3f  %-38s %-38s  tris %5d  verts-in %4d  %s | %s' % (d, an, bn, n, ni, ','.join(ac),
                                                                              ','.join(bc)))
print('DONE', len(res))
