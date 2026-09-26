#!/bin/sh
# Generate the whole scene from params.py + the downloaded assets (run scripts/fetch_assets.sh first).
#
#   scripts/build_scene.sh
#
# 1. building           model/build_model.py         -> model/tempel.blend
# 2. plants             model/plants.py              Poly Haven scans, roses, roof planters (packed into the file)
# 3. crowd              model/humans/build_crowd.py  -> model/tempel_event.blend
#      MakeHuman people (MPFB), poses from CMU mocap (dance, contact improvisation duets, walking),
#      poses measured from photos (photo_poses*.json), separation pass, then always:
#      cloth simulation of skirts, dresses, kimonos and lungis (humans/clothsim.py) and active ragdoll settling
#      of everyone lying, sitting or leaning (humans/ragdoll.py). Slow (many hours on 4 CPU cores) but it is what
#      makes the people look natural. The scene is the same for lq and hq renders.
# 4. small fixes         model/postfix.py             stair cushions, roof planters (both files)
# 5. checks             clashes, support (nobody floating), camera path clearance
# 6. drawings           drawings/plans.py            -> drawings/*.pdf / *.png
# Logs go to $TEMPEL_LOGS (default <repo>/logs). Each step stops the script on failure.
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
REPO=$(dirname "$HERE")
export TEMPEL_ASSETS=${TEMPEL_ASSETS:-$REPO/.assets}
export TEMPEL_TMP=${TEMPEL_TMP:-$REPO/.tmp}
L=${TEMPEL_LOGS:-$REPO/logs}
mkdir -p "$L" "$TEMPEL_TMP"
export CROWD_PHYSICS=1 CROWD_CLOTH=1
[ -d "$TEMPEL_ASSETS/cmu" ] || { echo "no assets in $TEMPEL_ASSETS - run scripts/fetch_assets.sh"; exit 1; }
cd "$REPO/model"

step() {  # step <name> <command...>: run, log, fail loudly
  n=$1; shift
  echo "== $n ($(date -u +%H:%M:%S))"
  if ! "$@" > "$L/$n.log" 2>&1; then
    echo "FAILED: $n - see $L/$n.log"; tail -20 "$L/$n.log"; exit 1
  fi
}

step 1_building python3 build_model.py
step 2_plants env PACK=1 python3 plants.py
grep -q "PLANTS saved" "$L/2_plants.log" || { echo "plants did not save"; exit 1; }
step 3_crowd python3 humans/build_crowd.py
step 4_postfix python3 postfix.py tempel.blend
step 4_postfix_event python3 postfix.py tempel_event.blend
step 5_clashes python3 check_clashes.py
step 5_clashes_event env CLASH_EVENT=1 python3 check_clashes.py
step 5_support python3 humans/check_support.py
step 5_path python3 flythrough.py check tempel_event.blend
step 6_drawings python3 ../drawings/plans.py

echo "== check summary"
for f in "$L"/5_*.log; do
  echo "-- $(basename "$f" .log): $(grep -c -E '^CLASH|^CLEAR|^BLOCKED|^SUPPORT .* floats' "$f" || true) findings"
  grep -h -E '^CLASH|^CLEAR|^BLOCKED|^NEAR|^SUPPORT' "$f" | head -12 || true
done
echo "scene ready: model/tempel.blend (empty), model/tempel_event.blend (with people)"
