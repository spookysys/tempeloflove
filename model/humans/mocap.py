"""CMU motion capture (ASF/AMC) -> poses on the MPFB 'default' skeleton.

The ASF/AMC files are read directly (forward kinematics), then the MakeHuman bones are aimed
along the recorded body segments (direction retargeting, parents first). A pose can be keyed at
two moments a fraction of a second apart, which gives real motion blur in Cycles.
Data: CMU Graphics Lab Motion Capture Database, http://mocap.cs.cmu.edu (free for all uses).
"""
import math
import os

import numpy as np
from mathutils import Euler, Matrix, Vector

CMU = os.environ.get('CMU_DIR', os.path.join(os.environ.get('TEMPEL_ASSETS', os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.assets')), 'cmu'))


def _rot(ax, order='XYZ'):
    """Rotation matrix for ASF axis / AMC angles (degrees), applied x then y then z."""
    return np.array(Euler([math.radians(a) for a in ax], 'XYZ').to_matrix())


class Skeleton:
    def __init__(self, asf):
        self.bones = {}
        self.children = {'root': []}
        self.root_order = ['TX', 'TY', 'TZ', 'RX', 'RY', 'RZ']
        txt = open(asf).read()
        sect = txt.split(':bonedata')[1].split(':hierarchy')
        for blk in sect[0].split('begin')[1:]:
            b = {}
            for line in blk.split('end')[0].strip().split('\n'):
                p = line.split()
                if not p:
                    continue
                if p[0] == 'name':
                    b['name'] = p[1]
                elif p[0] == 'direction':
                    b['dir'] = np.array([float(x) for x in p[1:4]])
                elif p[0] == 'length':
                    b['len'] = float(p[1])
                elif p[0] == 'axis':
                    b['C'] = _rot([float(x) for x in p[1:4]])
                elif p[0] == 'dof':
                    b['dof'] = [d.lower() for d in p[1:]]
            b.setdefault('dof', [])
            self.bones[b['name']] = b
        for line in sect[1].split('begin')[1].split('end')[0].strip().split('\n'):
            p = line.split()
            if p:
                self.children.setdefault(p[0], []).extend(p[1:])
        self.parent = {c: p for p, cs in self.children.items() for c in cs}

    def fk(self, frame):
        """frame: dict bone -> values. Returns dict bone -> end position (Y up, ASF units)."""
        out = {}
        rv = frame['root']
        pos = np.array(rv[0:3])
        Rr = _rot(rv[3:6])
        out['root'] = pos
        stack = [('root', Rr, pos)]
        while stack:
            name, Rp, start = stack.pop()
            for c in self.children.get(name, []):
                b = self.bones[c]
                ang = [0.0, 0.0, 0.0]
                for d, v in zip(b['dof'], frame.get(c, [])):
                    if d in ('rx', 'ry', 'rz'):
                        ang['xyz'.index(d[1])] = v
                C = b['C']
                L = Rp @ C @ _rot(ang) @ C.T
                end = start + b['len'] * (L @ b['dir'])
                out[c] = end
                stack.append((c, L, end))
        return out


def read_amc(path):
    frames, cur = [], None
    for line in open(path):
        line = line.strip()
        if not line or line[0] in '#:':
            continue
        if line.isdigit():
            cur = {}
            frames.append(cur)
            continue
        p = line.split()
        cur[p[0]] = [float(x) for x in p[1:]]
    return frames


_SK = {}


def clip(name):
    """name like '05_02' -> (skeleton, frames)."""
    subj = name.split('_')[0]
    if subj not in _SK:
        _SK[subj] = Skeleton(os.path.join(CMU, subj + '.asf'))
    return _SK[subj], read_amc(os.path.join(CMU, name + '.amc'))


def joints(name, f, frames_cache={}):
    """World joint positions (Z up, metres, not yet de-yawed) of clip `name` at frame f."""
    if name not in frames_cache:
        frames_cache[name] = clip(name)
    sk, fr = frames_cache[name]
    f = max(0, min(len(fr) - 1, f))
    j = sk.fk(fr[f])
    s = 0.0254 / 0.45                      # ASF units (length 0.45 -> inches) to metres
    return {k: Vector((v[0] * s, -v[2] * s, v[1] * s)) for k, v in j.items()}, len(fr)


# MPFB default-rig bone -> (start joint, end joint) of the recorded segment
SEG = {
    'spine05': ('root', 'lowerback'), 'spine04': ('root', 'lowerback'),
    'spine03': ('lowerback', 'upperback'), 'spine02': ('upperback', 'thorax'),
    'spine01': ('upperback', 'thorax'),
    'neck01': ('thorax', 'upperneck'), 'neck02': ('thorax', 'upperneck'), 'neck03': ('lowerneck', 'upperneck'),
    'head': ('upperneck', 'head'),
}
for s_, m_ in (('L', 'l'), ('R', 'r')):
    SEG.update({
        'clavicle.' + s_: ('thorax', m_ + 'clavicle'),
        'upperarm01.' + s_: (m_ + 'clavicle', m_ + 'humerus'), 'upperarm02.' + s_: (m_ + 'clavicle', m_ + 'humerus'),
        'lowerarm01.' + s_: (m_ + 'humerus', m_ + 'radius'), 'lowerarm02.' + s_: (m_ + 'humerus', m_ + 'radius'),
        'wrist.' + s_: (m_ + 'radius', m_ + 'hand'),
        'upperleg01.' + s_: (m_ + 'hipjoint', m_ + 'femur'), 'upperleg02.' + s_: (m_ + 'hipjoint', m_ + 'femur'),
        'lowerleg01.' + s_: (m_ + 'femur', m_ + 'tibia'), 'lowerleg02.' + s_: (m_ + 'femur', m_ + 'tibia'),
        'foot.' + s_: (m_ + 'tibia', m_ + 'foot'),
    })
ORDER = ['spine05', 'spine04', 'spine03', 'spine02', 'spine01', 'neck01', 'neck02', 'neck03', 'head'] + \
    [b + s_ for s_ in ('.L', '.R') for b in ('clavicle', 'upperarm01', 'upperarm02', 'lowerarm01', 'lowerarm02',
                                             'wrist', 'upperleg01', 'upperleg02', 'lowerleg01', 'lowerleg02', 'foot')]


def pelvis_frame(j):
    x = (j['lhipjoint'] - j['rhipjoint']).normalized()          # subject's left
    up = j['lowerback'] - j['root']
    z = (up - x * up.dot(x)).normalized()
    y = z.cross(x)                                               # subject's back
    return Matrix((x, y, z)).transposed()


def yaw_of(j):
    """Heading of the pelvis (angle of the 'back' axis projected on the floor)."""
    y = pelvis_frame(j).col[1]
    return math.atan2(y.y, y.x)


def apply(rig, name, f, yaw0=None, update=None):
    """Pose `rig` (MPFB default skeleton, object transform ignored) like clip `name` at frame f.
    yaw0: heading to remove (so the dancer faces -Y); default: this frame's own heading."""
    import bpy
    update = update or (lambda: bpy.context.view_layer.update())
    j, n = joints(name, f)
    if yaw0 is None:
        yaw0 = yaw_of(j)
    R = Matrix.Rotation(-(yaw0 - math.pi / 2), 3, 'Z')          # back axis -> +Y (face -Y)
    j = {k: R @ v for k, v in j.items()}
    for pb in rig.pose.bones:
        pb.rotation_mode = 'QUATERNION'
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.location = (0, 0, 0)
    update()
    # pelvis / root orientation
    P = pelvis_frame(j).to_4x4()
    root = rig.pose.bones['root']
    h = root.head.copy()
    root.matrix = Matrix.Translation(h) @ P @ Matrix.Translation(-h) @ root.matrix
    update()
    for bn in ORDER:
        pb = rig.pose.bones.get(bn)
        if pb is None:
            continue
        a, b = SEG[bn]
        d = (j[b] - j[a])
        if d.length < 1e-6:
            continue
        cur = (pb.tail - pb.head)
        q = cur.rotation_difference(d.normalized()).to_matrix().to_4x4()
        hd = pb.head.copy()
        pb.matrix = Matrix.Translation(hd) @ q @ Matrix.Translation(-hd) @ pb.matrix
        update()
    return yaw0, j


def key_motion(rig, name, f, dt_frames=4):
    """Pose at frame f and key it, plus the pose dt_frames earlier (for motion blur).
    Also moves the rig object by the recorded root motion between the two frames.
    Returns the root displacement (in the de-yawed frame) from f-dt to f."""
    import bpy
    sc = bpy.context.scene
    yaw0, j1 = apply(rig, name, f)
    for pb in rig.pose.bones:
        pb.keyframe_insert('rotation_quaternion', frame=sc.frame_current)
    _, j0 = apply(rig, name, f - dt_frames, yaw0=yaw0)
    for pb in rig.pose.bones:
        pb.keyframe_insert('rotation_quaternion', frame=sc.frame_current - 1)
    apply(rig, name, f, yaw0=yaw0)
    return j1['root'] - j0['root']


def expressiveness(j, jprev):
    """How much a moment 'dances': arms out / up, legs lifted, torso bent or twisted, speed."""
    up = (j['lowerback'] - j['root']).normalized()
    s = 0.0
    for w, sh in (('lwrist', 'lclavicle'), ('rwrist', 'rclavicle')):
        v = j[w] - j[sh]
        s += max(0.0, v.dot(up) + 0.25) * 1.2            # hands up
        s += (v - up * v.dot(up)).length * 0.8          # hands out
    fz = min(j['lfoot'].z, j['rfoot'].z)
    s += abs(j['lfoot'].z - j['rfoot'].z) * 1.5         # a leg lifted
    s += (1 - up.z) * 1.5                               # torso bent
    s += sum((j[k] - jprev[k]).length for k in ('lwrist', 'rwrist', 'head', 'lfoot', 'rfoot')) * 3.0   # speed
    return s


def best_frames(name, k=4, step=10, dt=4, gap=150, lo=0.08, hi=0.95):
    """The k most expressive, well separated frames of a clip."""
    _, n = joints(name, 0)
    sc = []
    for f in range(int(n * lo), int(n * hi), step):
        j, _ = joints(name, f)
        jp, _ = joints(name, f - dt)
        sc.append((expressiveness(j, jp), f))
    sc.sort(reverse=True)
    out = []
    for s, f in sc:
        if all(abs(f - g) > gap for g in out):
            out.append(f)
        if len(out) >= k:
            break
    return out


def contact_frames(a, b, k=3, step=10, gap=150, near=0.22):
    """Frames of a two-person clip where the two touch (hands to hands / body) - with expressiveness."""
    _, n = joints(a, 0)
    sc = []
    for f in range(int(n * 0.05), int(n * 0.95), step):
        ja, _ = joints(a, f)
        jb, _ = joints(b, f)
        pa = [ja[x] for x in ('lwrist', 'rwrist', 'lhand', 'rhand')]
        pb = [jb[x] for x in ('lwrist', 'rwrist', 'lhand', 'rhand', 'thorax', 'lclavicle', 'rclavicle', 'lowerback')]
        d = min((p - q).length for p in pa for q in pb)
        d2 = min((p - q).length for p in [jb[x] for x in ('lwrist', 'rwrist')] for q in
                 [ja[x] for x in ('lwrist', 'rwrist', 'thorax', 'lclavicle', 'rclavicle', 'lowerback')])
        if min(d, d2) > near:
            continue
        jpa, _ = joints(a, f - 4)
        jpb, _ = joints(b, f - 4)
        sc.append((expressiveness(ja, jpa) + expressiveness(jb, jpb) - 4 * min(d, d2), f))
    sc.sort(reverse=True)
    out = []
    for s, f in sc:
        if all(abs(f - g) > gap for g in out):
            out.append(f)
        if len(out) >= k:
            break
    return out


def key_duet(ra, rb, a, b, f, dt=4):
    """Pose two partners from a two-person clip (shared heading = A's). Keys both for motion blur.
    Returns (offset of B's pelvis from A's pelvis, motion of A, motion of B) in A's de-yawed frame."""
    import bpy
    fc = bpy.context.scene.frame_current
    ja, _ = joints(a, f)
    yaw0 = yaw_of(ja)
    out = {}
    for rig, clip_ in ((ra, a), (rb, b)):
        _, j0 = apply(rig, clip_, f - dt, yaw0=yaw0)
        for pb in rig.pose.bones:
            pb.keyframe_insert('rotation_quaternion', frame=fc - 1)
        _, j1 = apply(rig, clip_, f, yaw0=yaw0)
        for pb in rig.pose.bones:
            pb.keyframe_insert('rotation_quaternion', frame=fc)
        out[clip_] = (j0, j1)
    (a0, a1), (b0, b1) = out[a], out[b]
    return b1['root'] - a1['root'], a1['root'] - a0['root'], b1['root'] - b0['root']


# ---------------------------------------------------------------------------
# poses reconstructed from photos (MediaPipe world landmarks) -> same retargeting
# ---------------------------------------------------------------------------
def photo_joints(world):
    """MediaPipe world landmarks (metres, Z up) -> the joint names used above."""
    W = [Vector(p) for p in world]
    mh = (W[23] + W[24]) / 2
    ms = (W[11] + W[12]) / 2
    nose = W[0]
    ears = (W[7] + W[8]) / 2
    j = {'root': mh, 'lhipjoint': W[23], 'rhipjoint': W[24],
         'lowerback': mh.lerp(ms, 0.3), 'upperback': mh.lerp(ms, 0.62), 'thorax': mh.lerp(ms, 0.9),
         'lowerneck': ms, 'upperneck': ms.lerp(ears, 0.6), 'head': ears + (ears - ms).normalized() * 0.12}
    for s_, (sh, el, wr, ix, hp, kn, an, ft) in (('l', (11, 13, 15, 19, 23, 25, 27, 31)), ('r', (12, 14, 16, 20, 24, 26, 28, 32))):
        j.update({s_ + 'clavicle': W[sh], s_ + 'humerus': W[el], s_ + 'radius': W[wr], s_ + 'hand': W[ix],
                  s_ + 'femur': W[kn], s_ + 'tibia': W[an], s_ + 'foot': W[ft]})
    return j


def apply_joints(rig, j, keep_yaw=False):
    """Pose `rig` from a joint dict (like apply(), without a clip). Faces -Y unless keep_yaw."""
    import bpy
    update = lambda: bpy.context.view_layer.update()  # noqa: E731
    yaw0 = yaw_of(j)
    R = Matrix.Identity(3) if keep_yaw else Matrix.Rotation(-(yaw0 - math.pi / 2), 3, 'Z')
    j = {k: R @ v for k, v in j.items()}
    for pb in rig.pose.bones:
        pb.rotation_mode = 'QUATERNION'
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.location = (0, 0, 0)
    update()
    P = pelvis_frame(j).to_4x4()
    root = rig.pose.bones['root']
    h = root.head.copy()
    root.matrix = Matrix.Translation(h) @ P @ Matrix.Translation(-h) @ root.matrix
    update()
    for bn in ORDER:
        pb = rig.pose.bones.get(bn)
        if pb is None:
            continue
        a, b = SEG[bn]
        d = (j[b] - j[a])
        if d.length < 1e-6:
            continue
        q = (pb.tail - pb.head).rotation_difference(d.normalized()).to_matrix().to_4x4()
        hd = pb.head.copy()
        pb.matrix = Matrix.Translation(hd) @ q @ Matrix.Translation(-hd) @ pb.matrix
        update()
    return yaw0, j


def spin_frames(name, k=3, window=40, gap=200):
    """Moments at the end of the fastest turns (body heading rotating quickly for ~1/3 s) - for flying skirts."""
    _, n = joints(name, 0)
    yaws = []
    for f in range(0, n, 4):
        j, _ = joints(name, f)
        yaws.append((f, yaw_of(j)))
    sc = []
    w = window // 4
    for i in range(w, len(yaws)):
        tot = 0.0
        for a in range(i - w, i):
            d = yaws[a + 1][1] - yaws[a][1]
            d = (d + math.pi) % (2 * math.pi) - math.pi
            tot += d
        sc.append((abs(tot), yaws[i][0]))
    sc.sort(reverse=True)
    out = []
    for s, f in sc:
        if all(abs(f - g) > gap for g in out):
            out.append(f)
        if len(out) >= k:
            break
    return out


# ---------------------------------------------------------------------------
# resting moments: recorded people lying, sitting on the floor / a chair, on all fours
# (found by scripts/tools/find_rest_moments.py -> rest_poses.json; nothing here is posed by hand)
# ---------------------------------------------------------------------------
REST_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rest_poses.json')
_REST = {}


def rest_moments(kind):
    """kind: lie_back | lie_side | lie_front | sit_floor | sit_high | all_fours -> [(clip, frame), ...]"""
    if not _REST:
        import json
        for m in json.load(open(REST_FILE)):
            _REST.setdefault(m['kind'], []).append((m['clip'], m['f']))
    return _REST.get(kind, [])


def mirror(j):
    """The same moment mirrored left <-> right (in a frame where x is sideways)."""
    out = {}
    for k, v in j.items():
        k2 = ('r' + k[1:]) if k[0] == 'l' and k[1:] in _SIDED else ('l' + k[1:]) if k[0] == 'r' and k[1:] in _SIDED \
            else k
        out[k2] = Vector((-v.x, v.y, v.z))
    return out


_SIDED = {'clavicle', 'humerus', 'radius', 'wrist', 'hand', 'fingers', 'thumb', 'hipjoint', 'femur', 'tibia', 'foot',
          'toes'}


def rest_joints(clip, f, kind, side=None):
    """Joints of a recorded resting moment, turned for apply_joints(keep_yaw=True):
    sitting: facing -Y (like a standing figure); lying / all fours: the head towards -Y, so that stand(face=a)
    points the head at angle a. side = side_r (front towards the figure's -X) or side_l (+X): mirrored if needed."""
    j, _ = joints(clip, f)
    if kind.startswith('sit'):
        yaw = yaw_of(j)
        R = Matrix.Rotation(-(yaw - math.pi / 2), 3, 'Z')
    else:
        h = j['head'] - j['root']
        R = Matrix.Rotation(-math.pi / 2 - math.atan2(h.y, h.x), 3, 'Z')
    j = {k: R @ v for k, v in j.items()}
    if side in ('side_r', 'side_l'):
        front = -pelvis_frame(j).col[1]
        if (front.x > 0) != (side == 'side_l'):
            j = mirror(j)
    return j
