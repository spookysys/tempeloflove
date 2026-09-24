"""Renders the views from tempel.blend with Cycles (CPU).

    python3 render.py [view ...] [--quick] [--res 1920] [--samples 256]
"""
import argparse
import math
import os
import sys

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import params as P  # noqa: E402

OUT = os.path.join(os.path.dirname(HERE), 'renders')
rad = math.radians


def pol(r, a, z=0.0):
    return Vector((r * math.cos(rad(a)), r * math.sin(rad(a)), z))


def room_local(k, x, y, z):
    a = rad(P.slot_center(k))
    return Vector((x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a), z))


UF = P.FFL_UF
VIEWS = {
    # name: camera loc, target, lens, sun (azimuth deg, math convention: 0=E, 90=N; elevation), mode
    '01_hall_up_through_net': dict(
        loc=Vector((1.5, -1.6, 0.35)), tgt=Vector((-0.2, 0.6, 9.0)), lens=15,
        sun=(-100, 57), mode='day', volume=0.016, exposure=0.2, roll=0),
    '02_hall_wide': dict(
        loc=pol(8.7, 292, 1.45), tgt=Vector((-1.2, 2.2, 1.35)), lens=17,
        sun=(-80, 47), mode='day', volume=0.02, exposure=1.8),
    '03_walkway': dict(
        loc=pol(4.95, 236, UF + 1.58), tgt=pol(4.75, 292, UF + 1.05), lens=18,
        sun=(-60, 50), mode='day', volume=0.0, exposure=0.5),
    '04_room_to_net': dict(
        loc=room_local(3, 8.75, -0.85, UF + 1.0), tgt=room_local(3, 5.2, 0.75, UF + 0.85), lens=19,
        sun=(197, 20), mode='day', volume=0.0, exposure=2.3),
    '05_on_net_up': dict(
        loc=Vector((2.3, 1.6, P.net_z(2.8) + 0.30)), tgt=Vector((-2.0, -1.4, 6.4)), lens=14,
        sun=(-95, 58), mode='day', volume=0.004, exposure=0.1),
    '06_exterior': dict(
        loc=pol(33.0, 18, 13.5), tgt=Vector((0, 1.5, 3.2)), lens=32,
        sun=(-40, 38), mode='day', volume=0.0, exposure=0.0),
    '07_walkway_evening': dict(
        loc=pol(4.95, 236, UF + 1.58), tgt=pol(4.75, 292, UF + 1.05), lens=18,
        sun=(-60, 50), mode='night', volume=0.0, exposure=-0.2),
    '08_variant_central_rope': dict(
        loc=Vector((1.5, -1.6, 0.35)), tgt=Vector((-0.2, 0.6, 9.0)), lens=15,
        sun=(-100, 57), mode='day', volume=0.016, exposure=0.2, variant=True),
}


def setup_world(mode, sun_az, sun_el):
    sc = bpy.context.scene
    w = bpy.data.worlds.get('sky') or bpy.data.worlds.new('sky')
    sc.world = w
    nt = w.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputWorld')
    bg = nt.nodes.new('ShaderNodeBackground')
    nt.links.new(bg.outputs[0], out.inputs[0])
    if mode == 'day':
        sky = nt.nodes.new('ShaderNodeTexSky')
        sky.sky_type = 'MULTIPLE_SCATTERING'
        sky.sun_disc = False
        sky.sun_elevation = rad(sun_el)
        sky.sun_rotation = rad(90 - sun_az)     # blender: rotation around Z from +Y clockwise?
        sky.altitude = 200
        sky.air_density = 1.0
        sky.aerosol_density = 1.2
        nt.links.new(sky.outputs[0], bg.inputs[0])
        bg.inputs[1].default_value = 0.35
    else:
        bg.inputs[0].default_value = (0.010, 0.016, 0.035, 1)
        bg.inputs[1].default_value = 1.0
    # sun lamp
    sun = bpy.data.objects.get('SUN')
    if sun is None:
        li = bpy.data.lights.new('SUN', 'SUN')
        sun = bpy.data.objects.new('SUN', li)
        sc.collection.objects.link(sun)
    sun.data.angle = rad(0.55)
    sun.data.color = (1.0, 0.93, 0.83)
    d = Vector((math.cos(rad(sun_el)) * math.cos(rad(sun_az)),
                math.cos(rad(sun_el)) * math.sin(rad(sun_az)), math.sin(rad(sun_el))))
    sun.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
    sun.data.energy = 4.2 if mode == 'day' else 0.0
    sun.hide_render = mode != 'day'
    # moon-ish fill for night
    return sun


def setup_volume(density):
    ob = bpy.data.objects.get('beam_volume')
    if density <= 0:
        if ob:
            ob.hide_render = True
        return
    if ob is None:
        bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=P.R_IN - 0.05, depth=P.DOME_BASE_Z + P.DOME_RISE,
                                            location=(0, 0, (P.DOME_BASE_Z + P.DOME_RISE) / 2 + 0.01))
        ob = bpy.context.active_object
        ob.name = 'beam_volume'
        m = bpy.data.materials.new('beam_volume')
        nt = m.node_tree
        nt.nodes.clear()
        out = nt.nodes.new('ShaderNodeOutputMaterial')
        v = nt.nodes.new('ShaderNodeVolumePrincipled')
        v.inputs['Color'].default_value = (1.0, 0.97, 0.92, 1)
        v.inputs['Anisotropy'].default_value = 0.55
        nt.links.new(v.outputs[0], out.inputs['Volume'])
        ob.data.materials.append(m)
        ob.visible_shadow = False
    ob.hide_render = False
    mat = ob.data.materials[0]
    mat.node_tree.nodes['Principled Volume'].inputs['Density'].default_value = density


def set_night(on):
    for ob in bpy.data.collections['night_lights'].objects:
        if ob.type == 'LIGHT':
            ob.data.energy = ob.get('lantern_power', 0.0) if on else 0.0
            ob.hide_render = not on
    for m in bpy.data.materials:
        if m.node_tree and 'LANTERN_EMISSION' in m.node_tree.nodes:
            s = 0.0
            if on and m.name.startswith('paper_lantern'):
                s = 3.0
            m.node_tree.nodes['LANTERN_EMISSION'].inputs['Strength'].default_value = s


def set_variant(on):
    bpy.data.collections['variant_central_rope'].hide_render = not on
    for n in ('net', 'net_ropes'):
        bpy.data.objects[n].hide_render = on


def camera(v):
    sc = bpy.context.scene
    cam = bpy.data.objects.get('CAM')
    if cam is None:
        cam = bpy.data.objects.new('CAM', bpy.data.cameras.new('CAM'))
        sc.collection.objects.link(cam)
    cam.location = v['loc']
    d = v['tgt'] - v['loc']
    cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    cam.data.lens = v['lens']
    cam.data.sensor_width = 36
    cam.data.clip_start = 0.05
    cam.data.clip_end = 500
    sc.camera = cam


def render(name, v, res, samples, quick):
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.samples = samples
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.adaptive_threshold = 0.03 if quick else 0.015
    sc.cycles.use_denoising = True
    sc.cycles.denoiser = 'OPENIMAGEDENOISE'
    sc.cycles.max_bounces = 10
    sc.cycles.diffuse_bounces = 4
    sc.cycles.glossy_bounces = 3
    sc.cycles.transmission_bounces = 6
    sc.cycles.transparent_max_bounces = 48
    sc.cycles.volume_bounces = 0
    sc.cycles.sample_clamp_indirect = 8.0
    sc.cycles.caustics_reflective = False
    sc.cycles.caustics_refractive = False
    sc.render.resolution_x = res
    sc.render.resolution_y = int(res * 9 / 16)
    sc.render.resolution_percentage = 100
    sc.view_settings.view_transform = 'AgX'
    sc.view_settings.look = 'AgX - Medium High Contrast'
    sc.view_settings.exposure = v.get('exposure', 0.0)
    sc.render.image_settings.file_format = 'PNG'
    setup_world(v['mode'], *v['sun'])
    setup_volume(v.get('volume', 0.0))
    set_night(v['mode'] == 'night')
    set_variant(v.get('variant', False))
    camera(v)
    path = os.path.join(OUT, ('quick_' if quick else '') + name + '.png')
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print('RENDERED', path, flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('views', nargs='*')
    ap.add_argument('--quick', action='store_true')
    ap.add_argument('--res', type=int, default=1920)
    ap.add_argument('--samples', type=int, default=256)
    a = ap.parse_args()
    bpy.ops.wm.open_mainfile(filepath=os.path.join(HERE, 'tempel.blend'))
    os.makedirs(OUT, exist_ok=True)
    names = a.views or list(VIEWS)
    for n in names:
        render(n, VIEWS[n], a.res if not a.quick else 640, a.samples if not a.quick else 24, a.quick)


if __name__ == '__main__':
    main()
