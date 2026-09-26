#!/bin/sh
# Download everything the scene needs that is not in the repository (all free licences):
#   - Python: Blender 5.0.1 as a module (bpy), matplotlib, pillow, imageio-ffmpeg
#   - MPFB 2.0.17 (MakeHuman for Blender) + 33 MakeHuman community asset packs (CC0 / CC-BY)
#   - Poly Haven scans (CC0): pines, shrubs, fern, grasses, potted plants, money tree
#   - ambientCG leaf atlases (CC0) for the roses and trailing plants
#   - CMU Graphics Lab motion capture (free for all uses): dance, contact improvisation, walking, and people
#     lying down, sitting on the floor / a chair, crawling, getting up (the resting moments of the crowd)
#   - derived: the light twig-card pine (scripts/tools/twigtree.py)
# Everything lands in $TEMPEL_ASSETS (default: <repo>/.assets); MPFB goes into Blender's user extensions.
# Safe to re-run: finished downloads are skipped.
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
REPO=$(dirname "$HERE")
A=${TEMPEL_ASSETS:-$REPO/.assets}
mkdir -p "$A/ph" "$A/acg" "$A/cmu" "$A/downloads"
echo "assets -> $A"

echo "== python packages"
python3 -m pip install -q "bpy==5.0.1" matplotlib pillow imageio-ffmpeg numpy

echo "== MPFB + MakeHuman asset packs (~3 GB)"
python3 "$HERE/tools/install_mpfb.py" "$A/downloads"

echo "== Poly Haven scans"
python3 "$HERE/tools/fetch_polyhaven.py" "$A" \
  pine_tree_01 shrub_01 shrub_02 shrub_03 shrub_04 fern_02 grass_medium_01 grass_medium_02 \
  potted_plant_01 potted_plant_02 calathea_orbifolia_01 anthurium_botany_01 pachira_aquatica_01

echo "== ambientCG leaf atlases"
for s in LeafSet005 LeafSet017 LeafSet024; do
  if [ ! -f "$A/acg/$s/${s}_1K-JPG_Color.jpg" ]; then
    curl -sSL -m 300 -o "$A/downloads/$s.zip" "https://ambientcg.com/get?file=${s}_1K-JPG.zip"
    mkdir -p "$A/acg/$s" && python3 -c "import zipfile,sys; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])" \
      "$A/downloads/$s.zip" "$A/acg/$s"
    echo "got $s"
  fi
done

echo "== CMU motion capture"
CLIPS="05_02 05_03 05_04 05_05 05_06 05_07 05_08 05_09 05_10 05_11 05_12 05_13 05_14 05_15 05_16 05_17 05_18 05_19
05_20 111_05 111_21 113_04 141_12 16_15 16_16 18_03 18_04 18_05 18_06 19_03 19_04 19_05 19_06 22_01 22_02 22_03 22_08
23_01 23_02 23_03 23_08 35_01 35_02 49_09 49_10 49_11 49_12 49_13 49_14 49_15 49_16 49_17 49_18 49_19 49_20 49_22
55_01 55_02 60_01 60_02 60_03 60_04 60_05 60_06 60_07 60_08 60_09 60_10 61_01 61_02 61_03 61_04 61_05 61_06 61_07
61_08 61_09 61_10
139_16 139_17 139_18 140_01 140_02 140_03 140_04 140_08 140_09 111_03 111_06 111_07 111_08 111_09 111_10 111_11 111_12
111_21 113_08 113_15 114_02 114_04 114_05 114_06 114_11 114_16 82_05 75_20 143_18 133_01 133_02 13_04 13_05 13_06
14_30 14_31"
for c in $CLIPS; do
  s=${c%_*}
  [ -f "$A/cmu/$s.asf" ] || curl -sSfL -m 120 -o "$A/cmu/$s.asf" "http://mocap.cs.cmu.edu/subjects/$s/$s.asf"
  [ -f "$A/cmu/$c.amc" ] || curl -sSfL -m 300 -o "$A/cmu/$c.amc" "http://mocap.cs.cmu.edu/subjects/$s/$c.amc"
done
echo "cmu: $(ls "$A/cmu" | wc -l) files"

echo "== light twig-card pine"
[ -f "$A/ph/pine_tree_01_lod.blend" ] || python3 "$HERE/tools/twigtree.py" "$A"

echo "assets ready"
