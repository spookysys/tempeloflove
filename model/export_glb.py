"""Exports tempel.glb (web / Windows 3D viewer / SketchUp / Rhino import).

Procedural Cycles materials are replaced with flat PBR colours on export;
the net keeps its alpha texture. Lights, helpers and the variant are left out.
"""
import os

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
bpy.ops.wm.open_mainfile(filepath=os.path.join(HERE, 'tempel.blend'))

for m in bpy.data.materials:
    if m.name == 'net_mesh' or 'vp_color' not in m:
        continue
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    p = nt.nodes.new('ShaderNodeBsdfPrincipled')
    c = list(m['vp_color'])
    p.inputs['Base Color'].default_value = (c[0], c[1], c[2], 1)
    p.inputs['Roughness'].default_value = 0.7
    a = float(m.get('vp_alpha', 1.0))
    if a < 1.0:
        p.inputs['Alpha'].default_value = a
    nt.links.new(p.outputs[0], out.inputs['Surface'])

skip = {'variant_central_rope', 'render_helpers', 'night_lights'}
for c in bpy.data.collections:
    if c.name in skip:
        for o in list(c.objects):
            bpy.data.objects.remove(o)
for o in list(bpy.data.objects):
    if o.type in ('LIGHT', 'CAMERA') or o.name.startswith(('tree_', 'pine_', 'birch_')) or o.name == 'site_meadow':
        bpy.data.objects.remove(o)

bpy.ops.export_scene.gltf(filepath=os.path.join(HERE, 'tempel.glb'), export_format='GLB',
                          export_apply=True, export_yup=True, export_lights=False, export_cameras=False)
print('exported')
