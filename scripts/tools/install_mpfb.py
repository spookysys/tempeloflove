"""Install MPFB (MakeHuman for Blender, GPL) as a Blender extension for the bpy module, plus the MakeHuman
community asset packs (CC0 / CC-BY) it uses: skins, hair, eyes, clothes, poses, rigs.

    python3 install_mpfb.py <download_dir>
"""
import os
import sys
import urllib.request
import zipfile

import bpy

MPFB_URL = ('https://extensions.blender.org/download/sha256:'
            '4f0a879d64a39bf646fbf5f53601ac678855da329d650617dca5737548239a87/add-on-mpfb-v2.0.17.zip'
            '?repository=%2Fapi%2Fv1%2Fextensions%2F&blender_version_min=4.2.0')
PACKS = ['makehuman_system_assets', 'makehuman_system_poses', 'system_hair_materials01',
         'skins01', 'skins02', 'skins03', 'hair01', 'hair02', 'hair03', 'eyebrows01', 'eyelashes01',
         'dress01', 'dress02', 'dress03', 'skirts01', 'skirts02', 'shirts01', 'shirts02', 'shirts03',
         'pants01', 'pants02', 'pants03', 'shoes01', 'shoes02', 'jewelry01', 'jewelry02', 'masks01', 'masks02',
         'poses01', 'poses02', 'poses03', 'poses04', 'poses05']
UA = {'User-Agent': 'tempeloflove-fetch/1.0'}


def download(url, path):
    if os.path.exists(path) and os.path.getsize(path) > 1000:
        return path
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=600) as r, open(path + '.part', 'wb') as f:
        while True:
            b = r.read(1 << 20)
            if not b:
                break
            f.write(b)
    os.replace(path + '.part', path)
    return path


def main(dl):
    os.makedirs(dl, exist_ok=True)
    ext = os.path.join(bpy.utils.user_resource('EXTENSIONS'), 'user_default', 'mpfb')
    if not os.path.exists(os.path.join(ext, 'blender_manifest.toml')):
        z = download(MPFB_URL, os.path.join(dl, 'mpfb-2.0.17.zip'))
        os.makedirs(ext, exist_ok=True)
        zipfile.ZipFile(z).extractall(ext)
        print('MPFB installed', ext)
    data = os.path.join(bpy.utils.extension_path_user('bl_ext.user_default.mpfb'), 'data')
    os.makedirs(data, exist_ok=True)
    for p in PACKS:
        if os.path.exists(os.path.join(data, 'packs', p + '.json')):
            continue
        for lic in ('cc0', 'ccby', 'cc-by'):
            url = 'https://files.makehumancommunity.org/asset_packs/%s/%s_%s.zip' % (p, p, lic)
            try:
                z = download(url, os.path.join(dl, '%s_%s.zip' % (p, lic)))
            except Exception:
                continue
            zipfile.ZipFile(z).extractall(data)
            print('pack', p, lic)
            break
        else:
            print('MISSING pack', p)


if __name__ == '__main__':
    main(sys.argv[-1])
