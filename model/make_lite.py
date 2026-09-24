"""Light version of the model for walking around on a weak laptop (Blender 4.5 LTS / 5.x).

    python3 make_lite.py        -> model/tempel_lite.blend

Only the building: no people, no event layer, no variant; forest thinned to the trees near the
building, climbing plants and trees simplified, smoothing only at render time, small lanterns
without shadows. Real-time EEVEE set up, a walk camera at eye height, cameras at all rendering
viewpoints, instructions and a quality switch inside the file (Text Editor).
"""
import math
import os
import sys

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import params as P  # noqa: E402
import render as R  # noqa: E402

bpy.ops.wm.open_mainfile(filepath=os.path.join(HERE, 'tempel.blend'))
sc = bpy.context.scene


def drop_collection(name):
    c = bpy.data.collections.get(name)
    if not c:
        return
    for sub in list(c.children_recursive):
        for o in list(sub.objects):
            bpy.data.objects.remove(o)
        bpy.data.collections.remove(sub)
    for o in list(c.objects):
        bpy.data.objects.remove(o)
    bpy.data.collections.remove(c)


for n in ('people', 'event', 'variant_central_rope', 'crowd'):
    drop_collection(n)

# forest: only trees within 32 m, simplified
for o in list(bpy.data.objects):
    if o.type != 'MESH':
        continue
    low = o.name.lower()
    far = Vector((o.matrix_world.translation.x, o.matrix_world.translation.y)).length
    if any(k in low for k in ('pine', 'tree_', 'birch')):
        if far > 32:
            bpy.data.objects.remove(o)
            continue
        m = o.modifiers.new('lite', 'DECIMATE')
        m.ratio = 0.35
    elif 'leaves' in low or 'vine' in low or 'hanging' in low:
        m = o.modifiers.new('lite', 'DECIMATE')
        m.ratio = 0.45

# bake the simplification into the meshes (smaller file, less memory when opening)
dg = bpy.context.evaluated_depsgraph_get()
for o in list(bpy.data.objects):
    if o.type == 'MESH' and o.modifiers.get('lite'):
        me = bpy.data.meshes.new_from_object(o.evaluated_get(dg))
        old = o.data
        o.modifiers.clear()
        o.data = me
        if old.users == 0:
            bpy.data.meshes.remove(old)

# smoothing only when rendering
for o in bpy.data.objects:
    for m in getattr(o, 'modifiers', []):
        if m.type == 'SUBSURF':
            m.levels = 0

# lights: shadows only for the sun and the bigger lights
for o in bpy.data.objects:
    if o.type == 'LIGHT' and o.data.type != 'SUN':
        if o.get('lantern_power', o.data.energy) < 30:
            o.data.use_shadow = False

# look: daylight sky + sun, lanterns off (see the switch for evening)
v = R.VIEWS['02_hall_wide']
R.setup_world('day', *v['sun'])
R.set_night(0.0)
R.set_variant(False) if bpy.data.collections.get('variant_central_rope') else None
bpy.data.objects.get('beam_volume') and bpy.data.objects.remove(bpy.data.objects['beam_volume'])

# cameras at all rendering viewpoints + a walk camera at eye height by the entrance
cams = bpy.data.collections.new('cameras')
sc.collection.children.link(cams)
for name, vv in R.VIEWS.items():
    if vv.get('event') or vv.get('variant'):
        continue
    cam = bpy.data.objects.new('CAM_' + name, bpy.data.cameras.new('CAM_' + name))
    cam.location = vv['loc']
    cam.rotation_euler = (vv['tgt'] - vv['loc']).to_track_quat('-Z', 'Y').to_euler()
    cam.data.lens = vv['lens']
    cam.data.clip_start = 0.05
    cams.objects.link(cam)
walk = bpy.data.objects.new('CAM_walk', bpy.data.cameras.new('CAM_walk'))
a = P.slot_center(P.ENTRY_SLOT)
walk.location = R.pol(P.R_IN - 1.2, a, 1.65)
walk.rotation_euler = (Vector((0, 0, 1.6)) - walk.location).to_track_quat('-Z', 'Y').to_euler()
walk.data.lens = 20
walk.data.clip_start = 0.05
cams.objects.link(walk)
sc.camera = walk
old = bpy.data.objects.get('CAM')
if old:
    bpy.data.objects.remove(old)

# real-time settings that a weak laptop can manage
sc.render.engine = 'BLENDER_EEVEE' if 'BLENDER_EEVEE' in [e.identifier for e in
                                                          bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items] \
    else 'BLENDER_EEVEE_NEXT'
ee = sc.eevee
for attr, val in (('taa_samples', 8), ('taa_render_samples', 32), ('use_shadows', True),
                  ('shadow_ray_count', 1), ('shadow_step_count', 4), ('use_raytracing', False),
                  ('use_volumetric_shadows', False), ('volumetric_tile_size', '16'),
                  ('use_gtao', True), ('shadow_resolution_scale', 0.5)):
    try:
        setattr(ee, attr, val)
    except (AttributeError, TypeError):
        pass
sc.render.resolution_x = 1280
sc.render.resolution_y = 720
sc.view_settings.view_transform = 'AgX'
sc.cycles.device = 'CPU'
sc.cycles.samples = 32
sc.cycles.use_denoising = True

# instructions + quality switch inside the file
txt = bpy.data.texts.new('README_walk')
txt.write("""TEMPEL - walking around on a laptop
====================================

Open this file with Blender 4.5 LTS or 5.x.

LOOK AROUND
- Move the mouse into the 3D view. Press  Numpad 0  to look through the active camera,
  or pick a viewpoint: Outliner > collection 'cameras' > click a CAM_... > Ctrl+Numpad 0.
- Viewport shading: press Z > 'Material Preview' (fast)  or  'Rendered' (nicer, slower).

WALK
- Shift + `  (the key left of 1)  starts Walk mode   (menu: View > Navigation > Walk Navigation)
- W A S D  walk,  mouse  look,  Q / E  down / up,  Shift = faster,  Alt = slower
- Tab      gravity on/off   (on: you walk on floors and the stairs, Space = jump)
- Left click  keep this view,  Right click / Esc  go back
- To walk 'as' the camera: first Numpad 0, then start Walk mode.

A NICE STILL IMAGE
- Text Editor: open 'quality_switch', set MODE at the top, then  Alt+P  (Run Script).
  MODE = 'FAST'   EEVEE, daylight (default)
  MODE = 'EVENING' EEVEE, lanterns and indirect light on, night sky
  MODE = 'NICE'   Cycles on the CPU, 32 samples + denoiser (1280x720: a few minutes)
- Then  F12  renders through the active camera.  Image > Save As  to keep it.

If the laptop struggles: stay in 'Material Preview', close other programs,
and in Edit > Preferences > Viewport set Anti-Aliasing to 'No Anti-Aliasing'.
""")
sw = bpy.data.texts.new('quality_switch')
sw.write('''MODE = 'FAST'          # 'FAST' | 'EVENING' | 'NICE'
import bpy
sc = bpy.context.scene
night = MODE == 'EVENING'
for o in bpy.data.objects:
    if o.type == 'LIGHT' and o.data.type != 'SUN':
        o.data.energy = o.get('lantern_power', 0.0) if night else 0.0
        o.hide_render = not night
        o.hide_viewport = not night
    if o.type == 'LIGHT' and o.data.type == 'SUN':
        o.data.energy = 0.0 if night else 4.2
for m in bpy.data.materials:
    if m.node_tree and 'LANTERN_EMISSION' in m.node_tree.nodes:
        m.node_tree.nodes['LANTERN_EMISSION'].inputs['Strength'].default_value = \\
            (3.0 if m.name.startswith('paper_lantern') else 0.0) if night else 0.0
w = sc.world.node_tree
bg = [n for n in w.nodes if n.type == 'BACKGROUND'][0]
bg.inputs[1].default_value = 0.02 if night else 0.35
sc.view_settings.exposure = -0.2 if night else 0.8
if MODE == 'NICE':
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.samples = 32
    sc.cycles.use_denoising = True
    for o in bpy.data.objects:
        for md in getattr(o, 'modifiers', []):
            if md.type == 'SUBSURF':
                md.render_levels = 1
else:
    engines = [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items]
    sc.render.engine = 'BLENDER_EEVEE' if 'BLENDER_EEVEE' in engines else 'BLENDER_EEVEE_NEXT'
print('quality switch:', MODE)
''')
sc.view_settings.exposure = 0.8

bpy.ops.file.pack_all()
out = os.path.join(HERE, 'tempel_lite.blend')
bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
polys = sum(len(o.data.polygons) for o in bpy.data.objects if o.type == 'MESH')
print('LITE saved', out, len(bpy.data.objects), 'objects', polys, 'base polys')
