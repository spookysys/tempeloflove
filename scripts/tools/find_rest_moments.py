"""Find resting moments in CMU motion capture: lying (on the back / side / front), sitting on
the floor, on a chair or bench, kneeling, on all fours.

Every frame of the listed clips is classified from the recorded joints (pelvis height above the floor, torso tilt,
which way the back faces, knees on the floor) and only still moments are kept (little movement around the frame).
Output: model/humans/rest_poses.json = [{clip, f, kind}], used by the crowd build for everyone lying or sitting.

    python3 scripts/tools/find_rest_moments.py
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, 'model', 'humans'))
import bpy  # noqa: E402,F401  (provides mathutils)
import mocap as MC  # noqa: E402

CLIPS = ['139_16', '139_17', '139_18', '140_01', '140_02', '140_03', '140_04', '140_08', '140_09',    # getting up
         '111_06', '111_07', '111_08', '111_12', '111_21', '113_08', '114_02', '114_11',              # lie down / roll
         '82_05', '114_16', '75_20', '143_18', '142_13',                                              # sitting
         '111_03', '133_01', '133_02',                                                                # crawling
         '111_09', '111_10', '111_11', '113_15', '114_04', '114_05', '114_06', '13_04', '13_05', '13_06',
         '14_29', '14_30', '14_31', '86_09', '86_15', '143_19']                                       # chair, stool
STEP, WIN, GAP = 4, 12, 90          # sample every 4th frame; stillness over +-12 frames; moments >= 0.75 s apart


def classify(j, floor):
    h = j['root'].z - floor
    up = j['thorax'] - j['root']
    tilt = math.degrees(math.acos(max(-1, min(1, up.normalized().z))))
    knees = max(j['lfemur'].z, j['rfemur'].z) - floor
    if h < 0.32 and tilt > 62:
        back = MC.pelvis_frame(j).col[1]            # subject's back direction
        return 'lie_back' if back.z < -0.6 else 'lie_front' if back.z > 0.6 else 'lie_side'
    if h < 0.30 and tilt < 55:
        return 'sit_floor'
    hands = max(j['lhand'].z, j['rhand'].z) - floor
    if 0.3 < h < 0.85 and knees < 0.18 and hands < 0.18 and tilt > 50:
        return 'all_fours'
    if 0.35 < h < 0.80 and knees < 0.16 and tilt < 45:
        return 'kneel'
    feet = max(j['lfoot'].z, j['rfoot'].z) - floor
    thigh = [(j[s + 'femur'] - j[s + 'hipjoint']) for s in 'lr']
    if 0.3 < h < 0.75 and feet < 0.15 and tilt < 40 and all(abs(t.z) < 0.4 * t.length for t in thigh):
        return 'sit_high'
    return None


def motion(name, f, n):
    a, _ = MC.joints(name, max(0, f - WIN))
    b, _ = MC.joints(name, min(n - 1, f + WIN))
    return max((a[k] - b[k]).length for k in a)


def main():
    out = []
    for name in CLIPS:
        try:
            _, n = MC.joints(name, 0)
        except Exception as e:
            print('skip', name, e)
            continue
        fr = [MC.joints(name, f)[0] for f in range(0, n, STEP)]
        mins = sorted(min(v.z for v in j.values()) for j in fr)
        floor = mins[len(mins) // 20]                 # 5th percentile of the lowest joint = the floor
        cand = []
        for i, j in enumerate(fr):
            k = classify(j, floor)
            if k:
                cand.append((motion(name, i * STEP, n), i * STEP, k))
        cand.sort()
        picked = []
        for m, f, k in cand:
            if m > 0.12:                                # still: no joint moves more than 12 cm in 0.2 s
                break
            if all(abs(f - g) >= GAP for g, _ in picked):
                picked.append((f, k))
        picked.sort()
        print(name, n, 'frames:', ', '.join('%d %s' % p for p in picked) or '-')
        out += [dict(clip=name, f=f, kind=k) for f, k in picked]
    dst = os.path.join(REPO, 'model', 'humans', 'rest_poses.json')
    json.dump(out, open(dst, 'w'), indent=0)
    from collections import Counter
    print('REST', len(out), dict(Counter(o['kind'] for o in out)), '->', dst)


if __name__ == '__main__':
    main()
