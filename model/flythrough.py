"""Fly-through of the event scene (Pfingstfestival ZEGG 2027, dusk).

    python3 flythrough.py check                 # path diagnostics: speed, turn rate, clearance
    python3 flythrough.py stills [N]            # N test stills spread over the path (renders/fly_test/)
    python3 flythrough.py frames A B [STEP]     # render frames A..B (every STEP-th) to renders/fly_frames/
    python3 flythrough.py video                 # assemble renders/fly_frames/ -> renders/flythrough.mp4

One continuous, calm shot: arrival over the meadow -> garden door -> hall (mattress field, look up at
the net) -> contact-improvisation area -> up the stair -> a slow loop on the walkway around the net ->
door to the external stair -> up to the roof terrace -> glide around the dome -> rise to a wide aerial.
Positions and look targets are Catmull-Rom splines through hand-placed waypoints; the view direction is
smoothed over ~1.5 s so it never turns abruptly.
"""
import math
import os
import sys

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree  # noqa: F401

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import params as P  # noqa: E402
import render as R  # noqa: E402

FPS = 24
OUT = os.path.join(os.path.dirname(HERE), 'renders')
rad = math.radians
UF = P.FFL_UF
TZ = P.TERRACE_Z


def pol(r, a, z=0.0):
    return Vector((r * math.cos(rad(a)), r * math.sin(rad(a)), z))


def FP(k, n, t, z=0.0):
    a = rad(P.slot_center(k))
    return Vector((n * math.cos(a) - t * math.sin(a), n * math.sin(a) + t * math.cos(a), z))


def tread_z(t):                      # inner stair: tread height at face coordinate t
    return max(0.0, min(P.FFL_UF, (t - P.STAIR_T0) / P.STAIR_GOING_T * P.STAIR_RISE))


KS = P.STAIR_SLOT
# (position, look target, speed to this point [m/s], lens [mm])
WAY = [
    # arrival: high over the meadow in the south-west (tree-free corridor), gliding down to the garden door
    (pol(44, 238, 16), Vector((0, 0, 4)), 0, 30),
    (pol(33, 246, 11), Vector((0, -1, 3.8)), 3.0, 30),
    (pol(22, 258, 5.5), FP(4, 10, 0, 2.6), 2.6, 28),
    (FP(4, 15.5, -0.8, 2.3), FP(4, 10, 0, 1.8), 2.0, 26),
    (FP(4, 11.6, 0.0, 1.85), FP(4, 6, 0.3, 1.6), 1.4, 22),
    # through the garden door into the hall
    (FP(4, 9.0, 0.0, 2.1), FP(4, 3, 0.5, 1.4), 1.1, 20),
    (FP(4, 5.6, 0.4, 2.45), Vector((0.8, 0.8, 1.4)), 1.0, 20),
    # over the mattress field; a slow look up at the people on the net
    (Vector((0.6, -2.3, 2.4)), Vector((0.6, 1.5, 3.6)), 1.0, 18),
    (Vector((0.3, -0.4, 2.3)), Vector((0.0, 2.0, 5.2)), 0.8, 18),
    (Vector((-0.6, 1.2, 2.3)), pol(6.5, 120, 1.3), 0.9, 18),
    # towards the contact-improvisation groups and the stair
    (pol(3.6, 145, 2.3), pol(8, 165, 1.1), 1.0, 20),
    (FP(KS, 7.25, -4.0, 2.0), FP(KS, 8.8, -1.5, 1.9), 1.0, 20),
    # up the stair (flight along the NW wall, t increasing = up)
    (FP(KS, 8.75, -3.4, tread_z(-3.4) + 1.65), FP(KS, 8.75, 0.5, tread_z(0.5) + 1.5), 0.9, 20),
    (FP(KS, 8.75, -1.0, tread_z(-1.0) + 1.65), FP(KS, 8.6, 2.5, UF + 1.5), 0.9, 20),
    (FP(KS, 8.7, 1.4, tread_z(1.4) + 1.65), FP(KS, 5.0, 0.2, UF + 1.2), 0.9, 20),
    # onto the walkway, then a slow loop around the net (counter-clockwise: net on the left)
    (FP(KS, 7.1, 0.35, UF + 1.7), FP(KS, 3.0, -1.0, UF + 0.6), 0.9, 20),
]
for i, a in enumerate(range(135, 135 + 330 + 1, 30)):
    look = pol(2.6, a + 55, UF - 0.3)                         # forward-left, down into the net
    if (a % 360) in (225, 315):                               # a gentle glance ahead-right into an open room
        look = pol(7.0, a + 48, UF + 0.9)
    WAY.append((pol(5.15, a, UF + 1.72), look, 1.25, 19))
WAY += [
    # completing the loop, the view turns slowly towards the stair landing and the door outside
    (pol(5.25, 482, UF + 1.72), FP(KS, 7.5, 1.6, UF + 1.3), 0.8, 20),
    # back at the stair: across the landing to the door of the external stair
    (FP(KS, 7.0, 0.6, UF + 1.7), FP(KS, 10.5, 2.8, UF + 1.6), 0.9, 20),
    (FP(KS, 8.6, 2.3, UF + 1.62), FP(KS, 12, 2.8, UF + 1.6), 0.8, 20),
    (FP(KS, 10.0, 2.8, UF + 1.6), FP(KS, 12, 1.0, UF + 2.2), 0.8, 20),
    # outside on the landing, turning onto the flight up to the terrace (outer lane, t decreasing)
    (FP(KS, 11.6, 2.2, UF + 1.7), FP(KS, 11.8, -2.0, TZ + 1.0), 0.8, 22),
    (FP(KS, 11.85, 0.2, UF + 1.7 + 0.6 * (TZ - UF)), FP(KS, 11.8, -3.0, TZ + 1.5), 0.9, 22),
    (FP(KS, 11.7, -2.0, TZ + 1.75), FP(KS, 7.5, -3.5, TZ + 1.0), 0.9, 22),
    # over the railing onto the terrace
    (FP(KS, 9.3, -2.9, TZ + 1.8), pol(6.5, 165, TZ + 0.9), 0.9, 20),
    # around the dome (counter-clockwise, dome on the left), below the sun sails
    (pol(8.55, 160, TZ + 1.75), pol(6.3, 200, TZ + 0.8), 1.0, 20),
    (pol(8.55, 185, TZ + 1.75), pol(7.6, 232, TZ + 0.6), 1.0, 20),
    (pol(8.6, 205, TZ + 1.75), pol(7.8, 255, TZ + 0.5), 1.0, 20),
    # rise and pull back to a wide aerial over the south-west meadow
    (pol(11.8, 198, TZ + 3.2), Vector((0, 0, TZ)), 1.4, 22),
    (pol(20, 222, TZ + 7.0), Vector((0, 0, 6)), 2.2, 26),
    (pol(30, 228, TZ + 10.0), Vector((0, 0, 5)), 2.6, 30),
]


# ---------------------------------------------------------------------------
def catmull(p0, p1, p2, p3, u):
    return 0.5 * ((2 * p1) + (-p0 + p2) * u + (2 * p0 - 5 * p1 + 4 * p2 - p3) * u * u +
                  (-p0 + 3 * p1 - 3 * p2 + p3) * u * u * u)


def times():
    ts = [0.0]
    for i in range(1, len(WAY)):
        d = (WAY[i][0] - WAY[i - 1][0]).length
        v = (WAY[i][2] + WAY[i - 1][2]) / 2 if WAY[i - 1][2] else WAY[i][2]
        ts.append(ts[-1] + max(d / max(v, 0.3), 1.2))
    return ts


def sample(pts, ts, t):
    """Catmull-Rom through pts at times ts (segment-local parameter), clamped ends."""
    if t <= ts[0]:
        return pts[0].copy()
    if t >= ts[-1]:
        return pts[-1].copy()
    i = max(k for k in range(len(ts) - 1) if ts[k] <= t)
    u = (t - ts[i]) / (ts[i + 1] - ts[i])
    u = u * u * (3 - 2 * u) * 0.25 + u * 0.75           # tiny ease: softer at waypoints, no stops
    p0 = pts[max(0, i - 1)]
    p3 = pts[min(len(pts) - 1, i + 2)]
    return catmull(p0, pts[i], pts[i + 1], p3, u)


def build_path():
    ts = times()
    T = ts[-1]
    E = 3.0                                              # ease in / out over 3 s (velocity ramps 0 -> 1)

    def warp(t):
        if t < E:
            return t * t / (2 * E)
        if t > T:
            u = T + E - t
            return T - u * u / (2 * E)
        return t - E / 2
    n = int((T + E) * FPS) + 1
    tt = [warp(f / FPS) for f in range(n)]
    pos = [sample([w[0] for w in WAY], ts, t) for t in tt]
    tgt = [sample([w[1] for w in WAY], ts, t) for t in tt]
    lens = [sample([Vector((w[3], 0, 0)) for w in WAY], ts, t).x for t in tt]
    dirs = [(b - a).normalized() for a, b in zip(pos, tgt)]
    # smooth the view direction (gaussian, sigma 0.6 s) - no sudden turns
    sig = 1.5 * FPS
    k = [math.exp(-0.5 * (i / sig) ** 2) for i in range(-int(3 * sig), int(3 * sig) + 1)]
    sm = []
    for f in range(n):
        acc = Vector()
        for j, w in enumerate(k):
            g = min(n - 1, max(0, f + j - len(k) // 2))
            acc += dirs[g] * w
        sm.append(acc.normalized())
    return pos, sm, lens, T


def diagnostics(pos, dirs):
    sp = [(pos[f + 1] - pos[f]).length * FPS for f in range(len(pos) - 1)]
    ang = [math.degrees(dirs[f].angle(dirs[f + 1])) * FPS for f in range(len(dirs) - 1)]
    print('DIAG duration %.1f s, frames %d' % (len(pos) / FPS, len(pos)))
    print('DIAG speed m/s: max %.2f' % max(sp))
    worst = sorted(range(len(ang)), key=lambda f: -ang[f])[:5]
    print('DIAG max turn rate deg/s:', ['%.0f@%.1fs' % (ang[f], f / FPS) for f in worst])


def clearance(pos, step=6):
    """Nearest geometry around the camera (rays in 26 directions)."""
    sc = bpy.context.scene
    dg = bpy.context.evaluated_depsgraph_get()
    dirs = [Vector((x, y, z)).normalized() for x in (-1, 0, 1) for y in (-1, 0, 1) for z in (-1, 0, 1)
            if (x, y, z) != (0, 0, 0)]
    bad = []
    for f in range(0, len(pos), step):
        best = (9, None)
        for d in dirs:
            hit, loc, nrm, idx, ob, mw = sc.ray_cast(dg, pos[f], d, distance=0.5)
            if hit:
                dist = (loc - pos[f]).length
                if dist < best[0]:
                    best = (dist, ob.name)
        if best[0] < 0.3:
            bad.append((f / FPS, round(best[0], 2), best[1]))
    return bad


def people_near_path(pos, r=0.45):
    """People whose body comes within r of the path (they would be flown through)."""
    c = bpy.data.collections.get('crowd')
    if not c:
        return []
    dg = bpy.context.evaluated_depsgraph_get()
    near = []
    samp = pos[::4]
    for o in c.objects:
        if o.type != 'MESH' or not o.name.endswith('.body'):
            continue
        bb = [o.matrix_world @ Vector(v) for v in o.bound_box]
        lo = Vector((min(v.x for v in bb), min(v.y for v in bb), min(v.z for v in bb))) - Vector((r, r, r))
        hi = Vector((max(v.x for v in bb), max(v.y for v in bb), max(v.z for v in bb))) + Vector((r, r, r))
        if any(lo.x < p.x < hi.x and lo.y < p.y < hi.y and lo.z < p.z < hi.z for p in samp):
            ev = o.evaluated_get(dg)
            me = ev.to_mesh()
            vs = [o.matrix_world @ v.co for v in me.vertices[::7]]
            ev.to_mesh_clear()
            if any((v - p).length < r for p in samp for v in vs if abs(v.z - p.z) < 1.2):
                near.append(o.parent.name if o.parent else o.name)
    return sorted(set(near))


def setup(render_quality='video'):
    bpy.ops.wm.open_mainfile(filepath=os.path.join(HERE, 'tempel_event.blend'))
    sc = bpy.context.scene
    v = dict(R.VIEWS['15_event_hall'])
    R.setup_world('dusk', *v['sun'])
    R.setup_volume(0.0)
    R.set_night(0.6)
    R.set_variant(False)
    R.set_event(True)
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.samples = 10 if render_quality == 'video' else 20
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.adaptive_threshold = 0.05
    sc.cycles.use_denoising = True
    sc.cycles.denoiser = 'OPENIMAGEDENOISE'
    sc.cycles.max_bounces = 6
    sc.cycles.diffuse_bounces = 3
    sc.cycles.glossy_bounces = 2
    sc.cycles.transmission_bounces = 4
    sc.cycles.transparent_max_bounces = 24
    sc.cycles.sample_clamp_indirect = 6.0
    sc.render.use_simplify = True
    sc.render.simplify_subdivision_render = 0
    sc.cycles.texture_limit_render = '1024'
    sc.render.use_motion_blur = False
    sc.render.use_persistent_data = True
    sc.render.resolution_x, sc.render.resolution_y = (480, 270) if render_quality == 'video' else (640, 360)
    sc.render.resolution_percentage = 100
    sc.view_settings.view_transform = 'AgX'
    sc.view_settings.look = 'AgX - Medium High Contrast'
    sc.view_settings.exposure = 0.8
    sc.render.fps = FPS
    pos, dirs, lens, T = build_path()
    hidden = people_near_path(pos)
    for name in hidden:
        rig = bpy.data.objects.get(name)
        if rig:
            for o in [rig] + list(rig.children_recursive):
                o.hide_render = True
                o.hide_viewport = True
    print('hidden (on the camera path):', hidden)
    cam = bpy.data.objects.get('FLYCAM') or bpy.data.objects.new('FLYCAM', bpy.data.cameras.new('FLYCAM'))
    if cam.name not in sc.collection.objects:
        sc.collection.objects.link(cam)
    cam.data.sensor_width = 36
    cam.data.clip_start = 0.05
    cam.data.clip_end = 400
    sc.camera = cam
    # poses of the crowd are keyed at frames 9/10 (motion blur); hold them for the whole film
    sc.frame_start, sc.frame_end = 100, 100 + len(pos) - 1
    return sc, cam, pos, dirs, lens


def place(cam, pos, dirs, lens, f):
    cam.location = pos[f]
    cam.rotation_euler = dirs[f].to_track_quat('-Z', 'Y').to_euler()
    cam.data.lens = lens[f]


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else 'check'
    if mode == 'check':
        pos, dirs, lens, T = build_path()
        diagnostics(pos, dirs)
        bpy.ops.wm.open_mainfile(filepath=os.path.join(HERE, 'tempel_event.blend'))
        R.set_event(True)
        bpy.context.view_layer.update()
        for t, d, ob in clearance(pos):
            print('CLEAR %.1fs %.2fm %s' % (t, d, ob))
        print('NEAR people', people_near_path(pos))
        return
    if mode == 'video':
        frames = sorted(f for f in os.listdir(os.path.join(OUT, 'fly_frames')) if f.endswith('.png'))
        sc = bpy.context.scene
        sc.sequence_editor_create()
        step = int(sys.argv[2]) if len(sys.argv) > 2 else 1
        for i, f in enumerate(frames):
            s = sc.sequence_editor.strips.new_image('f%d' % i, os.path.join(OUT, 'fly_frames', f), 1, 1 + i * step) \
                if hasattr(sc.sequence_editor, 'strips') else \
                sc.sequence_editor.sequences.new_image('f%d' % i, os.path.join(OUT, 'fly_frames', f), 1, 1 + i * step)
            s.frame_final_duration = step
        sc.frame_start, sc.frame_end = 1, len(frames) * step
        sc.render.fps = FPS
        sc.render.resolution_x, sc.render.resolution_y = 480, 270
        sc.render.image_settings.file_format = 'FFMPEG'
        sc.render.ffmpeg.format = 'MPEG4'
        sc.render.ffmpeg.codec = 'H264'
        sc.render.ffmpeg.constant_rate_factor = 'HIGH'
        sc.render.filepath = os.path.join(OUT, 'flythrough.mp4')
        bpy.ops.render.render(animation=True)
        print('VIDEO', sc.render.filepath)
        return
    sc, cam, pos, dirs, lens = setup('stills' if mode == 'stills' else 'video')
    if mode == 'stills':
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 24
        d = os.path.join(OUT, 'fly_test')
        os.makedirs(d, exist_ok=True)
        for i in range(n):
            f = int(i * (len(pos) - 1) / (n - 1))
            place(cam, pos, dirs, lens, f)
            sc.frame_set(100 + f)
            sc.render.filepath = os.path.join(d, 'fly_%05d_%05.1fs.png' % (f, f / FPS))
            bpy.ops.render.render(write_still=True)
            print('STILL', f, flush=True)
    elif mode == 'frames':
        a, b = int(sys.argv[2]), int(sys.argv[3])
        step = int(sys.argv[4]) if len(sys.argv) > 4 else 1
        d = os.path.join(OUT, 'fly_frames')
        os.makedirs(d, exist_ok=True)
        for f in range(a, min(b, len(pos) - 1) + 1, step):
            dst = os.path.join(d, 'f_%05d.png' % f)
            if os.path.exists(dst):
                continue
            place(cam, pos, dirs, lens, f)
            sc.frame_set(100 + f)
            sc.render.filepath = dst
            bpy.ops.render.render(write_still=True)
            print('FRAME', f, flush=True)


if __name__ == '__main__':
    main()
