"""Extract a library of real body poses from photos (MediaPipe PoseLandmarker, CPU). Optional: the results are
committed (model/humans/photo_poses*.json); the photos themselves are not (third-party / private).
    python3 photo_poses.py <photo_dir> <out.json>   (POSE_MODEL = pose_landmarker_heavy.task from
    https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_heavy/float16/latest/pose_landmarker_heavy.task)"""
import os, json, math
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python as mpt
from mediapipe.tasks.python import vision
from PIL import Image
import sys
d = sys.argv[1]; fs = sorted(f for f in os.listdir(d) if f.endswith('.jpg') and os.path.getsize(os.path.join(d, f)) > 5000)
det = vision.PoseLandmarker.create_from_options(vision.PoseLandmarkerOptions(
    base_options=mpt.BaseOptions(model_asset_path=os.environ.get('POSE_MODEL', 'pose_landmarker_heavy.task')),
    num_poses=6, min_pose_detection_confidence=0.4, min_pose_presence_confidence=0.4))
def L(p, a, b): return float(np.linalg.norm(np.array(p[a]) - np.array(p[b])))
lib = []
for f in fs:
    try:
        im = Image.open(os.path.join(d, f)).convert('RGB')
    except Exception:
        continue
    W, H = im.size
    r = det.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=np.asarray(im)))
    for k, (l2, l3) in enumerate(zip(r.pose_landmarks, r.pose_world_landmarks)):
        vis = [p.visibility for p in l2]
        core = [11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28]
        if np.mean([vis[i] for i in core]) < 0.55:
            continue
        w = [(p.x, p.z, -p.y) for p in l3]          # metres, Z up, Y = depth
        # plausibility: left/right limb lengths similar, limbs not absurd
        ok = True
        for a, b, c, e in ((11, 13, 12, 14), (13, 15, 14, 16), (23, 25, 24, 26), (25, 27, 26, 28)):
            la, lb = L(w, a, b), L(w, c, e)
            if min(la, lb) < 0.12 or max(la, lb) / max(min(la, lb), 1e-3) > 1.6:
                ok = False
        if L(w, 11, 23) < 0.25 or not ok:
            continue
        hip2 = ((l2[23].x + l2[24].x) / 2 * W, (l2[23].y + l2[24].y) / 2 * H)
        sh2 = ((l2[11].x + l2[12].x) / 2 * W, (l2[11].y + l2[12].y) / 2 * H)
        torso_px = math.hypot(hip2[0] - sh2[0], hip2[1] - sh2[1])
        mh = (np.array(w[23]) + np.array(w[24])) / 2
        ms = (np.array(w[11]) + np.array(w[12])) / 2
        up = (ms - mh) / max(np.linalg.norm(ms - mh), 1e-6)
        lowest = min(p[2] for p in w)
        kind = 'upright' if up[2] > 0.75 and mh[2] - lowest > 0.7 else ('low' if mh[2] - lowest < 0.35 else 'mid')
        lib.append(dict(photo=f, k=k, world=w, vis=vis, hip_px=hip2, torso_px=torso_px, torso_m=float(np.linalg.norm(ms - mh)),
                        kind=kind, n_in_photo=len(r.pose_landmarks)))
json.dump(lib, open(sys.argv[2], 'w'))
from collections import Counter
print('POSES', len(lib), Counter(p['kind'] for p in lib), 'photos with 2+ good:', sum(1 for v in Counter(p['photo'] for p in lib).values() if v > 1))
