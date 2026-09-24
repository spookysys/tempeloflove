"""Cloth simulation for dancers' flowing clothes (Blender cloth, CPU).

The dancer performs the last second of their recorded dance (CMU motion capture) up to the moment
we see; skirts, dresses, kimonos, lungis and chiffon layers are simulated as cloth: held where they
sit on the torso (waist / shoulders), free at hems and sleeves, colliding with the body. Air: a
'relative wind' against the dancer's movement (what really lifts fabric) plus soft swirling air in
the hall. The final shape is baked into the garment.
"""
import math

import bpy
from mathutils import Matrix, Vector

import mocap as MC

FPS = 30
TORSO = ('root', 'spine', 'pelvis', 'clavicle', 'shoulder', 'neck', 'breast')
# fabric weight / stiffness by look
FABRIC = {
    'chiffon': dict(mass=0.08, tension=4, bending=0.02, air=0.4),
    'light': dict(mass=0.15, tension=8, bending=0.08, air=0.8),
    'cotton': dict(mass=0.3, tension=15, bending=0.3, air=1.0),
    'fur': dict(mass=0.6, tension=30, bending=3.0, air=1.2),
}


def fabric_kind(ob):
    m = ob.active_material.name if ob.active_material else ''
    if m.startswith('chiffon'):
        return 'chiffon'
    if m.startswith('fur_'):
        return 'fur'
    if m.startswith('lungi') or 'kimono' in ob.name:
        return 'cotton'
    return 'light'


def pin_group(ob):
    """Pin weight = how much a vertex belongs to the torso (waistbands, shoulder straps stay put)."""
    vg = ob.vertex_groups.get('cloth_pin') or ob.vertex_groups.new(name='cloth_pin')
    torso = {g.index for g in ob.vertex_groups if g.name.startswith(TORSO)}
    for v in ob.data.vertices:
        w = sum(g.weight for g in v.groups if g.group in torso)
        vg.add([v.index], min(1.0, w * 1.3) ** 2, 'REPLACE')
    return vg


def animate_lead_in(rig, clip, f, face, loc, seconds=1.0):
    """Key the recorded dance for `seconds` before frame f (ending exactly in the chosen pose/place)."""
    step = int(120 / FPS)
    n = int(seconds * FPS)
    j_end, _ = MC.joints(clip, f)
    yaw0 = MC.yaw_of(j_end)
    R = Matrix.Rotation(math.radians(face + 90), 3, 'Z') @ Matrix.Rotation(-(yaw0 - math.pi / 2), 3, 'Z')
    rig.animation_data_clear()
    vel = []
    for i in range(n + 1):
        fr = f - (n - i) * step
        _, j = MC.apply(rig, clip, fr, yaw0=yaw0)
        for pb in rig.pose.bones:
            pb.keyframe_insert('rotation_quaternion', frame=i + 1)
        jr, _ = MC.joints(clip, fr)
        d = R @ (jr['root'] - j_end['root'])
        rig.location = Vector(loc) + Vector((d.x, d.y, 0))
        rig.keyframe_insert('location', frame=i + 1)
        vel.append(Vector((d.x, d.y, 0)))
    return n + 1, [(vel[i + 1] - vel[i]) * FPS for i in range(len(vel) - 1)]


def to_metres(ob):
    """MakeHuman meshes are stored at 10x scale and scaled by the parent inverse matrix; physics needs metres."""
    M = ob.matrix_parent_inverse.copy()
    if abs(M.to_scale().x - 1.0) < 1e-4:
        return
    ob.data.transform(M, shape_keys=True)
    ob.matrix_parent_inverse = Matrix.Identity(4)


def simulate(rig, body, garments, clip, f, face, loc, seconds=1.0, breeze=True, wind=True):
    sc = bpy.context.scene
    for ob in [body] + list(garments):
        to_metres(ob)
    last, vel = animate_lead_in(rig, clip, f, face, loc, seconds)
    sc.frame_start, sc.frame_end = 1, last
    # collider: an invisible copy of the body, 2 cm slimmer (tight clothes start partly inside the real surface)
    cb = body.copy()
    sc.collection.objects.link(cb)
    cb.hide_render = True
    for md in list(cb.modifiers):
        if md.type not in ('ARMATURE',):
            cb.modifiers.remove(md)
    dsp = cb.modifiers.new('slim', 'DISPLACE')
    dsp.strength = -0.02
    dsp.mid_level = 0.0
    col = cb.modifiers.new('cloth_collider', 'COLLISION')
    fields = []
    # relative wind against the dancer's movement (animated per frame)
    if wind:
        w = bpy.data.objects.new('rel_wind_' + rig.name, None)
        sc.collection.objects.link(w)
        bpy.context.view_layer.objects.active = w
        w.select_set(True)
        bpy.ops.object.forcefield_toggle()
        w.field.type = 'WIND'
        w.field.shape = 'PLANE'
        for i, v in enumerate(vel):
            sp = v.length
            d = -v.normalized() if sp > 1e-3 else Vector((0, 0, 1))
            w.rotation_euler = d.to_track_quat('Z', 'Y').to_euler()
            w.location = Vector(loc) - d * 2
            w.field.strength = min(3.0, 1.2 * sp)
            w.keyframe_insert('rotation_euler', frame=i + 1)
            w.keyframe_insert('location', frame=i + 1)
            w.keyframe_insert(data_path='field.strength', frame=i + 1)
        fields.append(w)
    if breeze:                                      # soft swirling air in the hall
        t = bpy.data.objects.new('breeze_' + rig.name, None)
        sc.collection.objects.link(t)
        t.location = Vector(loc) + Vector((0, 0, 1))
        bpy.context.view_layer.objects.active = t
        bpy.ops.object.forcefield_toggle()
        t.field.type = 'TURBULENCE'
        t.field.strength = 0.4
        t.field.size = 0.6
        t.field.flow = 0.5
        fields.append(t)
    sims = []
    for g in garments:
        k = FABRIC[fabric_kind(g)]
        pin_group(g)
        m = g.modifiers.new('cloth', 'CLOTH')
        s = m.settings
        s.quality = 10
        s.mass = k['mass']
        s.tension_stiffness = s.compression_stiffness = k['tension']
        s.shear_stiffness = k['tension'] * 0.5
        s.bending_stiffness = k['bending']
        s.air_damping = k['air']
        s.vertex_group_mass = 'cloth_pin'
        m.collision_settings.use_self_collision = False
        m.point_cache.frame_start, m.point_cache.frame_end = 1, last
        sims.append(g)
    for fr in range(1, last + 1):
        sc.frame_set(fr)
    # bake the final shape into the garments
    dg = bpy.context.evaluated_depsgraph_get()
    for g in sims:
        me = bpy.data.meshes.new_from_object(g.evaluated_get(dg))
        mw = g.matrix_world.copy()
        g.modifiers.clear()
        g.parent = None
        g.data = me
        g.matrix_world = mw
    bpy.data.objects.remove(cb)
    for fo in fields:
        bpy.data.objects.remove(fo)
    return last
