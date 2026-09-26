#!/bin/sh
# Render the two fly-through films and the still renderings from the built scene (scripts/build_scene.sh).
#
#   scripts/render.sh lq|hq [empty|people|stills ...]      (default: all three)
#
#   lq: 480x270, 10 samples, every 2nd frame + motion interpolation   -> renders/flythrough_{empty,people}.mp4
#       stills: renders/*.jpg at 640 px, 24 samples (--quick)
#   hq: 1920x1080, 64 samples, every frame, full textures/subdivision  -> renders/flythrough_{empty,people}_hq.mp4
#       stills: renders/*.jpg at 1920 px, 256 samples
# Frame renders resume: frames already on disk (and newer than the scene) are skipped, so an interrupted run can simply be restarted.
# Override with FLY_RES=WxH FLY_SAMPLES=n FLY_STEP=n.
set -e
Q=${1:-lq}; shift || true
WHAT=${*:-empty people stills}
HERE=$(cd "$(dirname "$0")" && pwd)
REPO=$(dirname "$HERE")
export TEMPEL_ASSETS=${TEMPEL_ASSETS:-$REPO/.assets}
L=${TEMPEL_LOGS:-$REPO/logs}
mkdir -p "$L"
case $Q in
  lq) export FLY_RES=${FLY_RES:-480x270} FLY_SAMPLES=${FLY_SAMPLES:-10}; STEP=${FLY_STEP:-2}; SUF=; STILLS=--quick ;;
  hq) export FLY_RES=${FLY_RES:-1920x1080} FLY_SAMPLES=${FLY_SAMPLES:-64} FLY_HQ=1; STEP=${FLY_STEP:-1}; SUF=_hq; STILLS= ;;
  *) echo "usage: $0 lq|hq [empty|people|stills ...]"; exit 2 ;;
esac
cd "$REPO/model"
[ -f tempel_event.blend ] || { echo "no scene - run scripts/build_scene.sh"; exit 1; }

film() {  # film empty|people
  k=$1
  fr=fly_frames_$k$SUF
  # frames from an older scene build are thrown away (the rest resume)
  [ -d "../renders/$fr" ] && find "../renders/$fr" -name 'f_*.png' ! -newer tempel_event.blend -delete
  echo "== film $k ($Q, $FLY_RES, $FLY_SAMPLES samples, step $STEP) $(date -u +%H:%M:%S)"
  if [ "$k" = empty ]; then
    FLY_EMPTY=1 FLY_FRAMES=$fr nice -n 5 python3 flythrough.py frames 0 99999 "$STEP" > "$L/film_$k$SUF.log" 2>&1
  else
    FLY_BLEND=tempel_event.blend FLY_FRAMES=$fr nice -n 5 python3 flythrough.py frames 0 99999 "$STEP" \
      > "$L/film_$k$SUF.log" 2>&1
  fi || { echo "FAILED: see $L/film_$k$SUF.log"; tail -20 "$L/film_$k$SUF.log"; exit 1; }
  FLY_FRAMES=$fr FLY_VIDEO=flythrough_$k$SUF.mp4 python3 flythrough.py video "$STEP" >> "$L/film_$k$SUF.log" 2>&1
  echo "   -> renders/flythrough_$k$SUF.mp4"
}

for w in $WHAT; do
  case $w in
    empty|people) film "$w" ;;
    stills)
      echo "== stills ($Q) $(date -u +%H:%M:%S)"
      python3 render.py $STILLS > "$L/stills$SUF.log" 2>&1 || { echo "FAILED: see $L/stills$SUF.log"; exit 1; }
      echo "   -> renders/*.jpg" ;;
    *) echo "unknown: $w"; exit 2 ;;
  esac
done
