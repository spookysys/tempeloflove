#!/bin/sh
# Everything from a fresh clone: assets -> scene -> renders.
#
#   scripts/run_all.sh [lq|hq]        (default lq)
#
# The scene is built at the same quality as the render: hq also runs the ragdoll settling and the cloth simulation.
set -e
Q=${1:-lq}
D=$(cd "$(dirname "$0")" && pwd)
"$D/fetch_assets.sh"
"$D/build_scene.sh" "$Q"
"$D/render.sh" "$Q"
echo "all done ($Q): renders/"
