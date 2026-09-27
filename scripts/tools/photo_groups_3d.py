"""Reconstruct the people in a photo in 3D, together (Multi-HMR, SMPL-X): body shape, pose, and where each
person is relative to the others, so touching stays touching. Output per photo: a JSON with each person's
SMPL-X parameters, 3D joints (camera frame, metres) and 3D mesh vertices (subsampled) -- derived data only,
the photos themselves are never stored in the repository.

    python3 scripts/tools/photo_groups_3d.py OUT_DIR IMAGE [IMAGE ...]

Needs: $MULTIHMR_DIR (a clone of https://github.com/naver/multi-hmr with models/multiHMR/multiHMR_896_L.pt,
models/smpl_mean_params.npz and models/smplx/SMPLX_NEUTRAL.npz). Licences: Multi-HMR CC BY-NC-SA 4.0,
SMPL-X non-commercial; both used for this non-commercial concept study.
"""
import json
import math
import os
import sys
import types

import numpy as np
import torch
from PIL import Image, ImageOps

MHR = os.environ.get('MULTIHMR_DIR', os.path.join(os.environ.get('TEMPEL_ASSETS', os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.assets')), 'multi-hmr'))
os.chdir(MHR)
sys.path.insert(0, MHR)
stub = types.ModuleType('utils.render')              # rendering helpers (pyrender) are not needed here
for n in ('render_meshes', 'print_distance_on_image', 'render_side_views', 'create_scene'):
    setattr(stub, n, None)
stub.OPENCV_TO_OPENGL_CAMERA_CONVENTION = None
sys.modules['utils.render'] = stub
DINO = os.environ.get('DINOV2_DIR', os.path.join(os.path.dirname(MHR), 'dinov2'))   # git clone of facebookresearch/dinov2
_hub_load = torch.hub.load
torch.hub.load = lambda repo, name, **kw: _hub_load(DINO, name, source='local', pretrained=False)  # weights: checkpoint
from utils import normalize_rgb, get_focalLength_from_fieldOfView  # noqa: E402
from model import Model  # noqa: E402

DEV = torch.device('cpu')
torch.set_num_threads(max(1, os.cpu_count() - 1))


def load(name='multiHMR_896_L'):
    ckpt = torch.load(os.path.join('models', 'multiHMR', name + '.pt'), map_location=DEV, weights_only=False)
    kw = dict(vars(ckpt['args']))
    kw['type'] = ckpt['args'].train_return_type
    kw['img_size'] = ckpt['args'].img_size[0]
    m = Model(**kw).to(DEV)
    m.load_state_dict(ckpt['model_state_dict'], strict=False)
    m.eval()
    return m, kw['img_size']


def run(model, size, path, fov=60, thresh=float(os.environ.get('DET_THRESH', '0.3'))):
    im = Image.open(path).convert('RGB')
    small = ImageOps.contain(im, (size, size))
    pad = ImageOps.pad(small, size=(size, size))
    x = torch.from_numpy(normalize_rgb(np.asarray(pad))).unsqueeze(0).to(DEV)
    K = torch.eye(3)
    f = get_focalLength_from_fieldOfView(fov=fov, img_size=size)
    K[0, 0] = K[1, 1] = f
    K[0, 2] = K[1, 2] = size // 2
    with torch.no_grad():
        humans = model(x, is_training=False, nms_kernel_size=3, det_thresh=thresh, K=K.unsqueeze(0).to(DEV))
    out = []
    for h in humans:
        out.append({
            'score': float(h['scores']) if 'scores' in h else None,
            'transl': h['transl'].cpu().numpy().tolist(),
            'rotvec': h['rotvec'].cpu().numpy().tolist(),        # 53 x 3: global, body, jaw, eyes, hands
            'shape': h['shape'].cpu().numpy().tolist(),
            'j3d': h['j3d'].cpu().numpy().tolist(),              # camera frame (x right, y down, z forward)
            'v3d': h['v3d'].cpu().numpy()[::8].tolist(),          # every 8th vertex, for contact checks
        })
    return out


def run_tiled(model, size, path, grid=3, overlap=0.45, fov=60, thresh=float(os.environ.get('DET_THRESH', '0.3'))):
    """Crowded photos (cuddle puddles): people are small, so run on overlapping tiles, each with the camera of
    the WHOLE photo (focal length and principal point carried over into the tile), so that every detection lands
    in one common camera frame; then drop duplicates found in several tiles (pelvis within 0.35 m)."""
    im = Image.open(path).convert('RGB')
    W, H = im.size
    f_full = (max(W, H) / 2) / math.tan(math.radians(fov / 2))
    cx, cy = W / 2, H / 2
    tw, th = W / (grid - (grid - 1) * overlap), H / (grid - (grid - 1) * overlap)
    found = []
    for gy in range(grid):
        for gx in range(grid):
            x0, y0 = int(gx * tw * (1 - overlap)), int(gy * th * (1 - overlap))
            tile = im.crop((x0, y0, int(x0 + tw), int(y0 + th)))
            small = ImageOps.contain(tile, (size, size))
            s = small.width / tile.width
            px, py = (size - small.width) // 2, (size - small.height) // 2
            pad = ImageOps.pad(small, size=(size, size))
            x = torch.from_numpy(normalize_rgb(np.asarray(pad))).unsqueeze(0).to(DEV)
            K = torch.eye(3)
            K[0, 0] = K[1, 1] = f_full * s
            K[0, 2], K[1, 2] = s * (cx - x0) + px, s * (cy - y0) + py
            with torch.no_grad():
                humans = model(x, is_training=False, nms_kernel_size=3, det_thresh=thresh, K=K.unsqueeze(0).to(DEV))
            for h in humans:
                j = h['j3d'].cpu().numpy()
                # how central the person is in this tile (prefer detections away from tile borders)
                u = f_full * j[0, 0] / j[0, 2] + cx
                v = f_full * j[0, 1] / j[0, 2] + cy
                cen = -max(abs(u - (x0 + tw / 2)) / tw, abs(v - (y0 + th / 2)) / th)
                found.append((cen, {
                    'score': float(h['scores']) if 'scores' in h else None,
                    'transl': h['transl'].cpu().numpy().tolist(), 'rotvec': h['rotvec'].cpu().numpy().tolist(),
                    'shape': h['shape'].cpu().numpy().tolist(), 'j3d': j.tolist(),
                    'v3d': h['v3d'].cpu().numpy()[::8].tolist()}))
            print('  tile', gx, gy, len(humans), 'people', flush=True)
    found.sort(key=lambda t: -t[0])
    keep = []
    for _, p in found:
        pj = np.array(p['j3d'])[0]
        if all(np.linalg.norm(pj - np.array(q['j3d'])[0]) > 0.35 for q in keep):
            keep.append(p)
    return keep


def contacts(people, d=0.04):
    """Pairs of people whose surfaces come within d metres (who touches whom)."""
    res = []
    for i in range(len(people)):
        for j in range(i + 1, len(people)):
            a = np.array(people[i]['v3d'])
            b = np.array(people[j]['v3d'])
            dd = np.sqrt(((a[:, None, :] - b[None, :, :]) ** 2).sum(-1)).min()
            if dd < d:
                res.append((i, j, round(float(dd), 3)))
    return res


def main():
    out_dir = sys.argv[1]
    os.makedirs(out_dir, exist_ok=True)
    model, size = load()
    for p in sys.argv[2:]:
        grid = int(os.environ.get('TILES', '1'))
        pa = os.path.abspath(p) if not os.path.isabs(p) else p
        people = run_tiled(model, size, pa, grid) if grid > 1 else run(model, size, pa)
        c = contacts(people)
        name = os.path.splitext(os.path.basename(p))[0]
        json.dump({'photo': name, 'people': people, 'contacts': c}, open(os.path.join(out_dir, name + '.json'), 'w'))
        print('GROUP', name, len(people), 'people, contacts', c, flush=True)


if __name__ == '__main__':
    main()
