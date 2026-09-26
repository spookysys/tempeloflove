"""Settle the crowd: everyone ends up resting on what is under them (floor, mattress, step, bench, another
person) instead of hovering above it or sinking into it.

For each person the lowest points of the whole figure (body, clothes, shoes) are traced straight down;
the highest surface found under them (not part of the person) is where they should rest, and the rig
is moved up or down by the difference.

    python3 humans/settle.py [tempel_event.blend]     (fixes the file in place)
    or: import settle; settle.settle_all(scene)       (inside build_crowd, before saving)
"""
import os
import sys

import bpy
from mathutils import Vector

DOWN = Vector((0, 0, -1))


def person_points(rig, dg, step=5):
    pts = []
    for part in [rig] + list(rig.children_recursive):
        if part.type != 'MESH' or part.hide_render:
            continue
        e = part.evaluated_get(dg)
        me = e.to_mesh()
        pts += [e.matrix_world @ me.vertices[i].co for i in range(0, len(me.vertices), step)]
        e.to_mesh_clear()
    return pts


def _hit(sc, dg, start, d, own, dist, people=True):
    """first surface along d that is not part of this person and really rendered; (distance, obj) or None"""
    travelled = 0.0
    for _ in range(12):
        hit, loc, nrm, idx, ob, mw = sc.ray_cast(dg, start, d, distance=dist - travelled)
        if not hit:
            return None
        travelled += (loc - start).length
        o_ = getattr(ob, 'original', ob)
        hidden = o_.hide_render or any(c.hide_render for c in o_.users_collection)
        person = o_.name.startswith('cr_')
        if o_.name.split('.')[0] != own and not hidden and (people or not person):
            return travelled, o_, nrm
        start = loc + d * 0.002
        travelled += 0.002
    return None


UP = Vector((0, 0, 1))


def settle_all(sc, rigs=None, tol=0.04, sink=0.012, log=print):
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    import re
    # only people standing / moving to recorded motion (their feet belong on the ground); seated and lying
    # people keep the place they were built with (their feet may hang from a bench or counter)
    rigs = rigs or sorted((o for o in sc.objects if o.type == 'ARMATURE' and o.name.startswith('cr_')
                           and re.match(r'^\d+_\d+@', str(o.get('pose', '')))), key=lambda o: o.name)
    moved = []
    for rig in rigs:
        total = 0.0
        for _ in range(4):                               # sunk through several layers: raise step by step
            dz = _settle_step(sc, rig, tol, sink)
            if dz is None:
                break
            bpy.context.view_layer.update()
            dg = bpy.context.evaluated_depsgraph_get()
            total += dz
            if dz < 0:
                break
        if total:
            moved.append((rig.name, round(total, 2)))
            log('SETTLE %s %+.2f m' % (rig.name, total))
    return moved


def _settle_step(sc, rig, tol, sink, max_down=0.45):
    dg = bpy.context.evaluated_depsgraph_get()
    if True:
        pts = person_points(rig, dg)
        if not pts:
            return None
        zmin = min(p.z for p in pts)
        low = [p for p in pts if p.z < zmin + 0.04][:50]
        # sunk: most of the lowest points sit under the top of something solid (floor, mattress, step)
        ups = [_hit(sc, dg, p, UP, rig.name, 0.8, people=False) for p in low]
        sunk = [h[0] for h in ups if h and h[2].z > 0.3]        # reached a top face from below: inside it
        if len(sunk) > 0.5 * len(low):
            dz = max(sunk) - sink
        else:
            downs = [_hit(sc, dg, p + UP * 0.01, DOWN, rig.name, 2.0) for p in low]
            gaps = [h[0] - 0.01 for h in downs if h]
            if not gaps:
                return None
            dz = -(min(gaps) - sink)                             # rest on the closest support below
            if dz < -max_down:                                   # nothing near below: leave them (a jump?)
                return None
        if abs(dz) > tol:
            shift_person(rig, dz)
            return dz
        return None


def _location_fcurves(rig):
    ad = rig.animation_data
    if not (ad and ad.action):
        return []
    act = ad.action
    if hasattr(act, 'fcurves') and len(act.fcurves):          # legacy actions
        fcs = act.fcurves
    else:                                                       # Blender 4.4+ slotted actions
        from bpy_extras import anim_utils
        cb = anim_utils.action_get_channelbag_for_slot(act, ad.action_slot)
        fcs = cb.fcurves if cb else []
    return [fc for fc in fcs if fc.data_path == 'location' and fc.array_index == 2]


def shift_person(rig, dz):
    """move the rig (and its keyed motion-blur locations) plus its IK targets by dz"""
    rig.location.z += dz
    for fc in _location_fcurves(rig):
        for kp in fc.keyframe_points:
            kp.co.y += dz
            kp.handle_left.y += dz
            kp.handle_right.y += dz
        fc.update()
    for o in bpy.data.objects:                        # hand / foot targets that belong to this person
        if o.name.startswith(('ik_%s_' % rig.name, 'ikf_%s_' % rig.name)):
            o.location.z += dz


if __name__ == '__main__':
    HUM = os.path.dirname(os.path.abspath(__file__))
    MODEL = os.path.dirname(HUM)
    sys.path.insert(0, MODEL)
    blend = next((a for a in sys.argv[1:] if a.endswith('.blend')), 'tempel_event.blend')
    path = os.path.join(MODEL, blend)
    bpy.ops.wm.open_mainfile(filepath=path)
    import render as R
    R.set_event(True)                                  # posed only when visible in the viewport
    sc = bpy.context.scene
    sc.frame_set(100)
    for rnd in range(1):
        m = settle_all(sc)
        print('SETTLE round', rnd, len(m), 'moved')
        if not m:
            break
        sc.frame_set(100)
    for c in ('event', 'crowd'):                       # saved as build_crowd leaves it
        col = bpy.data.collections.get(c)
        if col:
            col.hide_viewport = c == 'event'
    bpy.ops.wm.save_as_mainfile(filepath=path, compress=True)
    print('SETTLE saved', path)
