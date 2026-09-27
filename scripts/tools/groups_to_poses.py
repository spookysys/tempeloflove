"""3D photo groups (photo_groups_3d.py output) -> model/humans/photo_groups.json for the crowd build.

For every photo: drop duplicate detections, find the clusters of people who touch (contacts), level the floor
(up = the torsos of people standing; else the plane through everyone's lowest points), put the cluster's
centre at the origin with the floor at z = 0, and store each person's joints under the mocap names used by
humans/mocap.py (metres; x right, y away from the camera, z up). Only these joint positions are stored.

    python3 scripts/tools/groups_to_poses.py GROUPS_DIR LABELS.json
LABELS.json: {"<photo name>": "<short label>", ...} (only the photos listed are used)
"""
import json
import os
import sys

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(REPO, 'model', 'humans', 'photo_groups.json')
# SMPL-X joint index -> mocap joint name (humans/mocap.py SEG)
J = {'root': 0, 'lhipjoint': 1, 'rhipjoint': 2, 'lowerback': 3, 'upperback': 6, 'thorax': 9, 'lowerneck': 12,
     'lfemur': 4, 'rfemur': 5, 'ltibia': 7, 'rtibia': 8, 'lfoot': 10, 'rfoot': 11,
     'lclavicle': 16, 'rclavicle': 17, 'lhumerus': 18, 'rhumerus': 19, 'lradius': 20, 'rradius': 21,
     'lhand': 28, 'rhand': 43}


def to_world(p):
    """camera frame (x right, y down, z forward) -> (x right, y forward, z up)"""
    p = np.asarray(p)
    return np.stack([p[..., 0], p[..., 2], -p[..., 1]], -1)


def joints_of(person):
    j = to_world(np.array(person['j3d']))
    d = {k: j[i] for k, i in J.items()}
    d['upperneck'] = j[12] + (j[15] - j[12]) * 0.5
    d['head'] = j[15] + (j[15] - j[12]) * 0.35
    return d


def up_vector(people):
    ups = []
    for p in people:
        j = joints_of(p)
        t = j['lowerneck'] - j['root']
        legs = j['root'] - (j['ltibia'] + j['rtibia']) / 2
        if np.linalg.norm(legs) > 0.7 and np.dot(t, legs) > 0.8 * np.linalg.norm(t) * np.linalg.norm(legs):
            ups.append(t / np.linalg.norm(t))                    # standing upright
    if ups:
        u = np.mean(ups, 0)
        return u / np.linalg.norm(u)
    low = []
    for p in people:
        v = to_world(np.array(p['v3d']))
        low.append(v[np.argsort(v[:, 2])[:25]])
    pts = np.concatenate(low)
    c = pts.mean(0)
    n = np.linalg.svd(pts - c)[2][-1]
    return n if n[2] > 0 else -n


def rot_to(u, target=np.array([0, 0, 1.0])):
    v = np.cross(u, target)
    s, c = np.linalg.norm(v), np.dot(u, target)
    if s < 1e-8:
        return np.eye(3)
    vx = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + vx + vx @ vx * ((1 - c) / s ** 2)


def clusters(n, contacts):
    parent = list(range(n))

    def f(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    for a, b, _ in contacts:
        parent[f(a)] = f(b)
    groups = {}
    for i in range(n):
        groups.setdefault(f(i), []).append(i)
    return [g for g in groups.values() if len(g) > 1]


def onto_floor(people, iters=4, lying=0.13):
    """Floor scenes (cuddle puddles) seen from above: depth from a single image is unreliable, but everyone lies
    on one floor. Fit the floor plane through everyone's lowest points, then slide each person along their own
    line of sight (camera at the origin) until their lowest points rest on that plane; refit and repeat."""
    ppl = [dict(p) for p in people]
    for _ in range(iters):
        low = []
        for p in ppl:
            v = np.array(p['v3d'])
            low.append(v[np.argsort(-v[:, 1])[:30]])          # camera y points down: lowest = largest y
        pts = np.concatenate(low)
        c = pts.mean(0)
        n = np.linalg.svd(pts - c)[2][-1]
        if n[1] < 0:
            n = -n                                            # normal points down (towards the floor)
        d = float(n @ c)
        for p in ppl:
            v = np.array(p['v3d'])
            j = np.array(p['j3d'])
            base = v[np.argsort(-v[:, 1])[:30]].mean(0)       # the person's own floor contact
            # scale s so that s * base lies on the plane: n . (s * base) = d  (moving along the camera ray)
            s_ = d / float(n @ base) if abs(float(n @ base)) > 1e-6 else 1.0
            s_ = min(max(s_, 0.6), 1.6)
            shift = base * (s_ - 1.0)
            p['v3d'] = (v + shift).tolist()
            p['j3d'] = (j + shift).tolist()
    return ppl


def contacts_of(people, d=0.06):
    res = []
    vs = [np.array(p['v3d']) for p in people]
    for i in range(len(vs)):
        for k in range(i + 1, len(vs)):
            dd = np.sqrt(((vs[i][:, None, :] - vs[k][None, :, :]) ** 2).sum(-1)).min()
            if dd < d:
                res.append((i, k, float(dd)))
    return res


def main():
    gdir, labels = sys.argv[1], json.load(open(sys.argv[2]))
    out = []
    for name, label in labels.items():
        d = json.load(open(os.path.join(gdir, name + '.json')))
        ppl = d['people']
        mode = ''
        if isinstance(label, dict):
            label, mode = label['label'], label.get('mode', '')
        if mode == 'floor':                                    # cuddle puddle: onto one floor, contacts anew
            ppl = onto_floor(ppl)
            d['contacts'] = contacts_of(ppl, 0.08)
        pel = [to_world(np.array(p['j3d'])[0]) for p in ppl]
        dup = sum(1 for i in range(len(ppl)) for k in range(i + 1, len(ppl)) if np.linalg.norm(pel[i] - pel[k]) < 0.15)
        if dup > 1:
            print('skip (duplicate detections)', name)
            continue
        for ci, members in enumerate(clusters(len(ppl), d['contacts'])):
            if len(members) > 16:
                continue
            sub = [ppl[i] for i in members]
            R = rot_to(up_vector(sub))
            js = [{k: R @ v for k, v in joints_of(p).items()} for p in sub]
            low = min(min(float(np.min((R @ to_world(np.array(p['v3d'])).T).T[:, 2])) for p in sub), 1e9)
            ctr = np.mean([j['root'] for j in js], 0)
            ctr[2] = low
            people = [{k: [round(float(x), 4) for x in (v - ctr)] for k, v in j.items()} for j in js]
            heights = [j['root'][2] - low for j in js]
            kind = 'standing' if np.mean(heights) > 0.75 else 'sitting' if np.mean(heights) > 0.3 else 'lying'
            out.append({'id': '%s_%d' % (label, ci), 'kind': kind, 'n': len(people), 'people': people})
            print('GROUP', out[-1]['id'], kind, len(people), 'people')
    json.dump(out, open(OUT, 'w'), indent=0)
    print('->', OUT, len(out), 'groups')


if __name__ == '__main__':
    main()
