#!/bin/sh
# Everything from a fresh clone: assets -> scene -> renders.
#
#   scripts/run_all.sh [lq|hq]        (default lq)
#
# The scene (with cloth and ragdoll physics) is the same for both; lq / hq is the render quality.
set -e
Q=${1:-lq}
D=$(cd "$(dirname "$0")" && pwd)
"$D/fetch_assets.sh"
"$D/build_scene.sh"
"$D/render.sh" "$Q"
echo "all done ($Q): renders/"
