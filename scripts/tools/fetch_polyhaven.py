"""Download Poly Haven models (CC0) as 1k glTF with all their textures: <out>/ph/<asset>/<asset>_1k.gltf

    python3 fetch_polyhaven.py <out> asset [asset ...]
"""
import json
import os
import sys
import urllib.request

UA = {'User-Agent': 'tempeloflove-fetch/1.0'}


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
        return r.read()


def fetch(out, asset, res='1k'):
    d = os.path.join(out, 'ph', asset)
    target = os.path.join(d, '%s_%s.gltf' % (asset, res))
    if os.path.exists(target):
        print('have', asset)
        return
    files = json.loads(get('https://api.polyhaven.com/files/' + asset))
    g = files['gltf'][res]['gltf']
    os.makedirs(d, exist_ok=True)
    for rel, inc in g.get('include', {}).items():
        p = os.path.join(d, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        if not os.path.exists(p):
            open(p, 'wb').write(get(inc['url']))
    open(target, 'wb').write(get(g['url']))
    print('got', asset, len(g.get('include', {})), 'files')


if __name__ == '__main__':
    for a in sys.argv[2:]:
        fetch(sys.argv[1], a)
