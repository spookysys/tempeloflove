"""Download the Pfingstfestival / Sommercamp / Silvester albums of ZEGG's own Flickr accounts
(flickr.com/photos/zegg and flickr.com/photos/zegg2) as LOCAL pose and look references.

Approved by ZEGG for this project. The photos stay in /tmp (never committed, never rendered);
only reconstructed pose numbers (humans/photo_poses_zegg.json) go into the model.

    python3 model/humans/fetch_zegg_flickr.py
"""
import html
import json
import os
import re
import subprocess

OUT = '/tmp/claude-0/mh/zegg'
UA = 'Mozilla/5.0'


def get(url):
    return subprocess.run(['curl', '-sSL', '-m', '40', '-A', UA, url], capture_output=True, text=True,
                          errors='ignore').stdout


os.makedirs(OUT, exist_ok=True)
urls = {}
for acc in ('zegg', 'zegg2'):
    albums = dict(re.findall(r'href="/photos/%s/albums/(\d+)" title="([^"]+)"' % acc,
                             get('https://www.flickr.com/photos/%s/albums' % acc)))
    for aid, title in albums.items():
        title = html.unescape(title)
        if not re.search(r'Pfingst|Sommercamp|Silvester', title) or 'Food' in title:
            continue
        for page in range(1, 6):
            h = get('https://www.flickr.com/photos/%s/albums/%s/page%d' % (acc, aid, page))
            new = [f for f in set(re.findall(r'live\.staticflickr\.com/(\d+/\d+_[0-9a-f]+)_[a-z]\.jpg', h))
                   if f not in urls]
            for f in new:
                urls[f] = title
            if not new:
                break
        print(title, sum(1 for v in urls.values() if v == title), flush=True)
json.dump(urls, open(os.path.join(OUT, 'urls.json'), 'w'), indent=1)
for i, (f, title) in enumerate(sorted(urls.items())):
    dst = os.path.join(OUT, f.replace('/', '_') + '.jpg')
    if os.path.exists(dst) and os.path.getsize(dst) > 5000:
        continue
    for suffix in ('_b', '_c', '_z', ''):             # not every size exists for every photo
        subprocess.run(['curl', '-sSL', '-m', '60', '-A', UA, '-o', dst,
                        'https://live.staticflickr.com/%s%s.jpg' % (f, suffix)])
        if os.path.getsize(dst) > 5000 and open(dst, 'rb').read(2) == b'\xff\xd8':
            break
print('downloaded', len(urls), 'photos to', OUT)
