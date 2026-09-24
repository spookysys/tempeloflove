"""Active ragdoll settling for MPFB people (Blender rigid body physics, CPU).

Each person becomes 15 capsules (thickness measured from their own body mesh), joined by
spring joints that pull towards the person's current pose (the 'motors'). Upright people are
held softly at the pelvis (like a powered ragdoll in a game), lying people are free. Gravity and
collisions with the floor, mattresses, net and other bodies then settle everyone: weight is shared,
arms rest on partners, bodies lie on each other. The result is written back to the skeletons.
"""
import math

import bpy
from mathutils import Matrix, Vector

# segment -> bones it drives (first = the bone whose head is the segment start), end bone (tail = segment end)
SEGMENTS = {
    'hips': (['root', 'spine05', 'spine04'], 'spine04', None),
    'belly': (['spine03'], 'spine03', 'hips'),
    'chest': (['spine02', 'spine01', 'clavicle.L', 'clavicle.R', 'shoulder01.L', 'shoulder01.R'], 'spine01', 'belly'),
    'head': (['neck01', 'neck02', 'neck03', 'head'], 'head', 'chest'),
}
for s in 'LR':
    SEGMENTS.update({
        'uarm.' + s: (['upperarm01.' + s, 'upperarm02.' + s], 'upperarm02.' + s, 'chest'),
        'farm.' + s: (['lowerarm01.' + s, 'lowerarm02.' + s, 'wrist.' + s], 'wrist.' + s, 'uarm.' + s),
        'thigh.' + s: (['upperleg01.' + s, 'upperleg02.' + s], 'upperleg02.' + s, 'hips'),
        'shin.' + s: (['lowerleg01.' + s, 'lowerleg02.' + s], 'lowerleg02.' + s, 'thigh.' + s),
        'foot.' + s: (['foot.' + s], 'foot.' + s, 'shin.' + s),
    })
ORDER = ['hips', 'belly', 'chest', 'head'] + [p + s for s in 'LR' for p in ('uarm.', 'farm.', 'thigh.', 'shin.', 'foot.')]
MASS = {'hips': 0.15, 'belly': 0.1, 'chest': 0.2, 'head': 0.08, 'uarm': 0.03, 'farm': 0.02, 'thigh': 0.1, 'shin': 0.045,
        'foot': 0.015}
# how far each joint may bend away from the target pose (degrees) and how hard its 'motor' pulls
LIMIT = {'belly': 15, 'chest': 15, 'head': 25, 'uarm': 40, 'farm': 35, 'thigh': 30, 'shin': 30, 'foot': 20}
STIFF = {'belly': 1500, 'chest': 1500, 'head': 500, 'uarm': 200, 'farm': 100, 'thigh': 800, 'shin': 400, 'foot': 150}


def _coll():
    c = bpy.data.collections.get('ragdoll_tmp')
    if not c:
        c = bpy.data.collections.new('ragdoll_tmp')
        bpy.context.scene.collection.children.link(c)
    return c


def bake_constraints(rig):
    """Freeze IK results into the pose and remove the IK constraints."""
    bpy.context.view_layer.update()
    mats = {pb.name: pb.matrix.copy() for pb in rig.pose.bones}
    had = False
    for pb in rig.pose.bones:
        for c in list(pb.constraints):
            pb.constraints.remove(c)
            had = True
    if not had:
        return
    for pb in sorted(rig.pose.bones, key=lambda b: len(b.parent_recursive)):
        pb.matrix = mats[pb.name]
        bpy.context.view_layer.update()


def _radius(rig, body, bones, a, b, dg):
    """Thickness of the body around the segment a-b, from the vertices weighted to its bones."""
    ev = body.evaluated_get(dg)
    me = ev.to_mesh()
    idx = {body.vertex_groups[n].index for n in bones if n in body.vertex_groups}
    ab = b - a
    L2 = max(ab.length_squared, 1e-6)
    ds = []
    mw = body.matrix_world
    for v in me.vertices:
        if any(g.group in idx and g.weight > 0.5 for g in v.groups):
            p = mw @ v.co
            t = max(0.0, min(1.0, (p - a).dot(ab) / L2))
            ds.append((p - (a + ab * t)).length)
    ev.to_mesh_clear()
    if not ds:
        return 0.05
    ds.sort()
    return ds[int(len(ds) * 0.6)] * 0.7


def _activate(ob):
    for o in bpy.context.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob


def _capsule(name, a, b, r):
    me = bpy.data.meshes.new(name)
    ob = bpy.data.objects.new(name, me)
    _coll().objects.link(ob)
    L = max((b - a).length, 1e-3)
    import bmesh
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=r, radius2=r, depth=L + 2 * r)
    bm.to_mesh(me)
    bm.free()
    q = Vector((0, 0, 1)).rotation_difference((b - a).normalized())
    ob.matrix_world = Matrix.Translation((a + b) / 2) @ q.to_matrix().to_4x4()
    return ob


def build(rig, body, pinned=False, stiffness=1.0):
    """Create the physical body of one person. Returns dict segment -> capsule object."""
    bake_constraints(rig)
    dg = bpy.context.evaluated_depsgraph_get()
    mw = rig.matrix_world
    seg = {}
    for sname in ORDER:
        bones, end_bone, parent = SEGMENTS[sname]
        pb0 = rig.pose.bones[bones[0]]
        pbe = rig.pose.bones[end_bone]
        a = mw @ pb0.head
        b = mw @ pbe.tail
        if sname == 'hips':
            a = mw @ rig.pose.bones['upperleg01.L'].head.lerp(rig.pose.bones['upperleg01.R'].head, 0.5)
        r = _radius(rig, body, bones + ([] if sname != 'hips' else ['pelvis.L', 'pelvis.R']), a, b, dg)
        r = max(0.03, min(r, 0.2))
        ob = _capsule('rd_%s_%s' % (rig.name, sname), a, b, r)
        _activate(ob)
        bpy.ops.rigidbody.object_add(type='ACTIVE')
        rb = ob.rigid_body
        rb.collision_shape = 'CAPSULE'
        rb.mass = 70 * MASS[sname.split('.')[0]]
        rb.friction = 0.9
        rb.restitution = 0.0
        rb.linear_damping = 0.9
        rb.angular_damping = 0.95
        rb.collision_margin = 0.005
        ob['start'] = [list(r_) for r_ in ob.matrix_world]
        seg[sname] = ob
    for sname in ORDER[1:]:
        bones, end_bone, parent = SEGMENTS[sname]
        piv = mw @ rig.pose.bones[bones[0]].head
        e = bpy.data.objects.new('rdj_%s_%s' % (rig.name, sname), None)
        e.location = piv
        _coll().objects.link(e)
        _activate(e)
        bpy.ops.rigidbody.constraint_add(type='GENERIC_SPRING')
        c = e.rigid_body_constraint
        c.object1, c.object2 = seg[parent], seg[sname]
        c.disable_collisions = True
        c.spring_type = 'SPRING2'
        for ax in 'xyz':
            setattr(c, 'use_limit_lin_' + ax, True)
            setattr(c, 'limit_lin_%s_lower' % ax, 0.0)
            setattr(c, 'limit_lin_%s_upper' % ax, 0.0)
            lim = math.radians(LIMIT[sname.split('.')[0]])
            setattr(c, 'use_limit_ang_' + ax, True)
            setattr(c, 'limit_ang_%s_lower' % ax, -lim)
            setattr(c, 'limit_ang_%s_upper' % ax, lim)
            setattr(c, 'use_spring_ang_' + ax, True)
            setattr(c, 'spring_stiffness_ang_' + ax, STIFF[sname.split('.')[0]] * stiffness)
            setattr(c, 'spring_damping_ang_' + ax, 0.8)
    # no collisions between a person's own body parts
    names = list(seg)
    for i, n1 in enumerate(names):
        for n2 in names[i + 1:]:
            if SEGMENTS[n2][2] == n1 or SEGMENTS[n1][2] == n2:
                continue
            e = bpy.data.objects.new('rdn_%s_%s_%s' % (rig.name, n1, n2), None)
            _coll().objects.link(e)
            _activate(e)
            bpy.ops.rigidbody.constraint_add(type='GENERIC')
            c = e.rigid_body_constraint
            c.object1, c.object2 = seg[n1], seg[n2]
            c.disable_collisions = True
    if pinned:                                # soft 'puppet string' at the pelvis for upright people
        anchor = _capsule('rd_%s_anchor' % rig.name, seg['hips'].matrix_world.translation,
                          seg['hips'].matrix_world.translation + Vector((0, 0, 0.01)), 0.01)
        _activate(anchor)
        bpy.ops.rigidbody.object_add(type='PASSIVE')
        anchor.rigid_body.collision_collections[0] = False
        anchor.rigid_body.collision_collections[19] = True
        anchor.hide_render = True
        e = bpy.data.objects.new('rdj_%s_pin' % rig.name, None)
        e.location = seg['hips'].matrix_world.translation
        _coll().objects.link(e)
        _activate(e)
        bpy.ops.rigidbody.constraint_add(type='GENERIC_SPRING')
        c = e.rigid_body_constraint
        c.object1, c.object2 = anchor, seg['hips']
        c.spring_type = 'SPRING2'
        for ax in 'xyz':
            setattr(c, 'use_spring_' + ax, True)
            setattr(c, 'spring_stiffness_' + ax, 4000.0)
            setattr(c, 'spring_damping_' + ax, 0.9)
            setattr(c, 'use_spring_ang_' + ax, True)
            setattr(c, 'spring_stiffness_ang_' + ax, 3000.0)
            setattr(c, 'spring_damping_ang_' + ax, 0.9)
    return seg


def add_collider(ob, shape='MESH'):
    _activate(ob)
    if not ob.rigid_body:
        bpy.ops.rigidbody.object_add(type='PASSIVE')
    ob.rigid_body.collision_shape = shape
    ob.rigid_body.mesh_source = 'FINAL'          # posed / deformed shape
    ob.rigid_body.friction = 0.9
    ob.rigid_body.collision_margin = 0.005


def simulate(frames=40):
    sc = bpy.context.scene
    w = sc.rigidbody_world
    w.substeps_per_frame = 10
    w.solver_iterations = 15
    w.point_cache.frame_start = 1
    w.point_cache.frame_end = frames + 1
    for f in range(1, frames + 2):
        sc.frame_set(f)


def write_back(rig, seg):
    """Rotate the bones like their segments turned; move the whole person like the pelvis moved."""
    bpy.context.view_layer.update()
    delta = {}
    for sname, ob in seg.items():
        m0 = Matrix([Vector(r_) for r_ in ob['start']])
        delta[sname] = ob.matrix_world @ m0.inverted()
    mw = rig.matrix_world
    mwi = mw.inverted()
    targets = {}
    for sname in ORDER:
        for bn in SEGMENTS[sname][0]:
            targets[bn] = (sname, (mw @ rig.pose.bones[bn].matrix).copy())
    for bn in sorted(targets, key=lambda n: len(rig.pose.bones[n].parent_recursive)):
        sname, wm = targets[bn]
        pb = rig.pose.bones[bn]
        if bn == 'root':
            new = delta[sname] @ wm
        else:                                   # keep the joint where the parent chain puts it
            rot = delta[sname].to_3x3() @ wm.to_3x3()
            new = Matrix.Translation(mw @ pb.head) @ rot.to_4x4()
        pb.matrix = mwi @ new
        bpy.context.view_layer.update()


def cleanup():
    c = bpy.data.collections.get('ragdoll_tmp')
    if c:
        for o in list(c.objects):
            bpy.data.objects.remove(o)
        bpy.data.collections.remove(c)
    sc = bpy.context.scene
    if sc.rigidbody_world:
        bpy.ops.rigidbody.world_remove()


def settle(people, colliders, frames=40):
    """people: list of (rig, body, pinned). colliders: static objects (floor, mats, net, ...)."""
    sc = bpy.context.scene
    fc = sc.frame_current
    if not sc.rigidbody_world:
        bpy.ops.rigidbody.world_add()
    segs = [(rig, build(rig, body, pinned)) for rig, body, pinned in people]
    for ob in colliders:
        add_collider(ob)
    simulate(frames)
    for rig, seg in segs:
        write_back(rig, seg)
    for ob in colliders:
        if ob.rigid_body:
            _activate(ob)
            bpy.ops.rigidbody.object_remove()
    cleanup()
    sc.frame_set(fc)
