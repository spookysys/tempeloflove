"""Pfingstfestival ZEGG 2027 - about 80 realistic people for the event views.

    python3 humans/build_crowd.py            -> model/tempel_event.blend

People are MakeHuman characters generated with MPFB (body, skin, eyes, hair, clothes, skeleton);
poses come from the MakeHuman pose library, and contact between people (hands on backs,
shoulders, arms around each other) is added with IK on the arms. Every person is then dropped
onto what is under them (floor, mattresses, net, stair, other people), so bodies rest on
each other instead of floating or intersecting.
Everyone is dressed; closeness is shown as embrace, close dancing, lying together, cuddle puddles.
"""
import math
import os
import random
import sys

import bpy
from mathutils import Euler, Matrix, Vector
import bmesh
from mathutils.bvhtree import BVHTree

HUM = os.path.dirname(os.path.abspath(__file__))
MODEL = os.path.dirname(HUM)
sys.path.insert(0, HUM)
sys.path.insert(0, MODEL)
import mh_lib as H  # noqa: E402  (enables MPFB + BVH importer)
import params as P  # noqa: E402

rad = math.radians
bpy.ops.wm.open_mainfile(filepath=os.path.join(MODEL, 'tempel.blend'))
SC = bpy.context.scene
EVC = bpy.data.collections['event']
EVC.hide_viewport = False
CROWD = bpy.data.collections.new('crowd')
EVC.children.link(CROWD)


def pol(r, a, z=0.0):
    return Vector((r * math.cos(rad(a)), r * math.sin(rad(a)), z))


def Rz(a):
    return Matrix.Rotation(rad(a), 3, 'Z')


# ---------------------------------------------------------------------------
# the net carries a lot of people tonight: it sags further (net mesh follows)
# ---------------------------------------------------------------------------
NET_EXTRA = 0.22
for ob in bpy.data.objects:
    if ob.type == 'MESH' and ob.name in ('net', 'net_ropes'):
        mw = ob.matrix_world
        mi = mw.inverted()
        for v in ob.data.vertices:
            w = mw @ v.co
            r = math.hypot(w.x, w.y)
            if r < P.RING_BEAM_IN and w.z > 3.0:
                w.z -= NET_EXTRA * (1 - (r / P.RING_BEAM_IN) ** 2)
                v.co = mi @ w


# ---------------------------------------------------------------------------
# static surfaces people can rest on (world-space BVH)
# ---------------------------------------------------------------------------
SKIP = ('tree', 'pine', 'birch', 'vine', 'leaf', 'leaves', 'plant', 'hanging', 'green', 'dome', 'glass',
        'curtain', 'sheer', 'canopy', 'lantern', 'light', 'volume', 'shoji', 'cord', 'rope_central', 'sail',
        'meadow', 'forest', 'path', 'ivy', 'ev_speaker', 'hall_zafu', 'hall_round', 'rose', 'gp_', 'scan_',
        'lib_', 'proto')


def world_bvh(objs):
    dg = bpy.context.evaluated_depsgraph_get()
    verts, polys = [], []
    for ob in objs:
        ev = ob.evaluated_get(dg)
        try:
            me = ev.to_mesh()
        except RuntimeError:
            continue
        o = len(verts)
        mw = ob.matrix_world
        verts += [mw @ v.co for v in me.vertices]
        polys += [[o + i for i in p.vertices] for p in me.polygons]
        ev.to_mesh_clear()
    return BVHTree.FromPolygons(verts, polys) if polys else None


def _static_objects():
    out = []
    for ob in SC.objects:
        if ob.type != 'MESH' or any(s in ob.name.lower() for s in SKIP):
            continue
        if ob.users_collection and ob.users_collection[0].name in ('variant_central_rope', 'people'):
            continue
        bb = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
        # distance from the building axis to the nearest point of the bounding box (not to its corners:
        # the floor and the roof deck have all corners far out but cover the centre)
        nx = max(min(v.x for v in bb), 0.0, -max(v.x for v in bb))
        ny = max(min(v.y for v in bb), 0.0, -max(v.y for v in bb))
        if min(v.z for v in bb) > 8.0 or math.hypot(nx, ny) > 10.5:
            continue
        out.append(ob)
    return out


STATIC = world_bvh(_static_objects())
print('static BVH ready')

# ---------------------------------------------------------------------------
# wardrobe, skins, hair
# ---------------------------------------------------------------------------
FLOW_F = [('mindfront_kimono',), ('mindfront_kimono', 'elvs_retro_girly_shorts1'), ('mindfront_kimono', 'toigo_harem_pants'),
          ('elvs_goddess_dress1',), ('elvs_goddess_dress2',), ('elvs_goddess_dress3',), ('elvs_goddess_dress5',),
          ('elvs_goddess_dress7',), ('elvs_fringe_hippy_dress',), ('elvs_halter_dress_long',),
          ('toigo_long_full_skirt', 'toigo_camisole_top'), ('toigo_harem_pants', 'toigo_keyhole_tank_top'),
          ('elvs_sarong_cover_up', 'punkduck_tube_top'), ('toigo_dress_with_tiered_skirt',),
          ('elvs_double_handkerchief_halter_dress',), ('elvs_gored_midi_skirt', 'elvs_ladies_tank1'),
          ('toigo_tiered_skirt', 'punkduck_off-shoulder_long-sleeve_top'), ('mindfront_f_dress_03',),
          ('toigo_halter_dress_midi',), ('punkduck_retro_polka_dot_skirt', 'punkduck_spaghetti_strap_tank_top')]
FLOW_M = [('mindfront_kimono', 'toigo_harem_pants'), ('mindfront_kimono',), ('mindfront_kimono', 'elvs_gored_elephant_pants'),
          ('toigo_harem_pants', 'elvs_male_boho_top1'), ('toigo_harem_pants', 'elvs_male_tankshirt1'),
          ('elvs_gored_elephant_pants', 'elvs_male_athletic_tank1'), ('toigo_harem_pants',),
          ('elvs_gored_elephant_pants', 'mindfront_kimono'), ('mindfront_male_trousers_1', 'elvs_male_muscle_shirt1'),
          ('wdg_mycenaean_tunic',), ('drednicolson_asymmetric_tunic_and_sash',),
          ('elvs_male_trouser_short_1', 'elvs_male_boho_top1'), ('toigo_wool_pants', 'elvs_crude_t-shirt_male'),
          ('elvs_sarong_cover_up', 'elvs_male_tankshirt1')]
# a few theatric / kinky looks
CRAZY = [('punkduck_black_mini_skirt', 'toigo_bodice-style_top', 'punkduck_lace-choker', 'scailman_gogo_platform_boots',
          'culturalibre_heroine_mask_1'),
         ('elvs_fringe_leather_dress', 'learning_slave_collar_chain', 'toigo_stiletto_booties'),
         ('punkduck_black_cocktail_dress', 'punkduck_lace-choker', 'culturalibre_heroine_mask_1'),
         ('elvs_disco_pants_double_ruffles', 'elvs_goth_statement_necklace1'),
         ('mindfront_ballet_dress_the_swan', 'punkduck_brass_circlet_crown'),
         ('toigo_harem_pants', 'jaldmic_ankh_collar', 'culturalibre_hero_mask_1'),
         ('toigo_turtleneck_halter_top', 'punkduck_black_mini_skirt', 'grinsegold_female_pirate_boots'),
         ('punkduck_evening_gown', 'elvs_m_facial_jewel_array1', 'punkduck_lace-choker')]
BOTTOMS = ['toigo_harem_pants', 'elvs_gored_elephant_pants', 'toigo_long_full_skirt', 'elvs_sarong_cover_up',
           'toigo_tiered_skirt', 'elvs_gored_midi_skirt', 'mindfront_female_trousers_1', 'elvs_retro_girly_shorts1',
           'cortu_jeans_shorts', 'toigo_wool_pants', 'punkduck_black_mini_skirt']
TOPS_F = ['toigo_camisole_top', 'punkduck_tube_top', 'punkduck_off-shoulder_long-sleeve_top', 'elvs_ladies_tank1',
          'punkduck_sleeveless_crop_top', 'elvs_ruffle_sleeve_peasant_blouse_1', 'toigo_keyhole_tank_top',
          'punkduck_lace_up_blouse', 'mindfront_knitted_sweater_01', None]
TOPS_M = ['elvs_male_boho_top1', 'elvs_male_tankshirt1', 'elvs_male_athletic_tank1', 'mindfront_tank_top_01',
          'mindfront_kimono', None]
# small adornments on bare skin (tantric / festival)
JEWEL_F = ['elvs_heart_belly_jewel', 'elvs_stars_belly_circlet', 'elvs_braided_anklet1', 'elvs_pearl_anklet_1',
           'elvs_multi_bangle_bracelet1', 'elvs_twisty_hoops1', 'punkduck_brass_circlet_crown', 'elvs_bangle_bracelet1']
JEWEL_M = ['culturalibre_leather_bracelet', 'elvs_braided_anklet1', 'culturalibre_cl_spiral_bracelets',
           'punkduck_necklace_native_american_fashion_']
KIMONO = ('mindfront_kimono',)
# most of the clothes already off: bare chests, loose pants and wraps, camisoles, slips
UNDIES_F = [('mindfront_kimono', 'elvs_retro_girly_shorts1'), ('toigo_camisole_top', 'elvs_retro_girly_shorts1'), ('elvs_crochet_baby_doll',),
            ('punkduck_tube_top', 'elvs_sarong_cover_up'), ('mindfront_cardigan_long_open_front', 'elvs_retro_girly_shorts1'),
            ('punkduck_spaghetti_strap_tank_top', 'elvs_retro_girly_shorts1'), ('punkduck_tube_dress',),
            ('toigo_camisole_top', 'toigo_harem_pants')]
UNDIES_M = [('mindfront_kimono', 'toigo_harem_pants'), ('toigo_harem_pants', 'elvs_male_tankshirt1'),
            ('elvs_gored_elephant_pants', 'mindfront_tank_top_01'), ('elvs_sarong_cover_up',),
            ('mindfront_male_trousers_1', 'elvs_male_boho_top1'), ('toigo_harem_pants',)]
TOPLESS_F = [('toigo_harem_pants',), ('elvs_gored_elephant_pants',), ('toigo_long_full_skirt',),
             ('elvs_gored_midi_skirt',), ('toigo_tiered_skirt',)]
LINGERIE_F = [('elvs_crochet_baby_doll',), ('toigo_bodice-style_top', 'elvs_retro_girly_shorts1', 'punkduck_lace-choker'),
              ('punkduck_tube_top', 'elvs_retro_girly_shorts1'), ('toigo_camisole_top', 'elvs_retro_girly_shorts1')]
LINGERIE_TONES = [(0.0, 0.2, 0.25), (0.98, 1.4, 0.45), (0.85, 1.2, 0.5), (0.08, 0.6, 1.1), (0.0, 0.0, 0.2)]
UNDRESS = [0.0]      # share of people in the current zone who have taken most of their clothes off

HAIR_F = ['elvs_lady_hippy_hair', 'long01', 'braid01', 'elvs_braid_bun', 'elvs_wavy_bob', 'punkduck_alpha7_curly',
          'punkduck_alpha7_long', 'elvs_island_princess_hair', 'o4saken_curly01', 'ponytail01', 'elvs_micky_afro',
          'elvs_french_braid_variation', 'rehmanpolanski_hair_bun_brown', 'toigo_curled_under_bob', 'bob02',
          'elvs_katherine_hair', 'elvs_hazel_hair', 'o4saken_long01', 'sonntag78_blond_with_headband',
          'elvs_short_side_do', 'afro01', 'elvs_braided_rows']
HAIR_M = ['short02', 'short04', 'cortu_short_messy_hair', 'elvs_grump_hair', 'afro01', 'long01', 'ponytail01',
          'elvs_maxwell_hair', 'culturalibre_hair_05', 'short03', 'elvs_keylth_hair', 'elvs_micky_afro', '']

RACES = {'caucasian': dict(caucasian=0.9, african=0.03, asian=0.07),
         'african': dict(caucasian=0.1, african=0.85, asian=0.05),
         'asian': dict(caucasian=0.1, african=0.02, asian=0.88),
         'mixed': dict(caucasian=0.45, african=0.35, asian=0.2)}


def skin_for(sex, years, race, rnd):
    age = 'young' if years < 36 else ('middleage' if years < 58 else 'old')
    g = 'female' if sex < 0.5 else 'male'
    base = {'caucasian': 'caucasian', 'african': 'african', 'asian': 'asian', 'mixed': 'african'}[race]
    opts = ['%s_%s_%s' % (age, base, g)]
    if race == 'caucasian' and age == 'young':
        opts += (['toigo_light_skin_female_freckles', 'toigo_light_skin_female_ginger', 'skalldyrssuppe_creamy_female',
                  'flower-angel_red_head_skin', 'young_caucasian_female2'] if g == 'female' else
                 ['toigo_light_skin_male_freckles', 'toigo_light_skin_male_bronze', 'young_caucasian_male2'])
    if race == 'caucasian' and age != 'young':
        opts += ['onlytheghosts_middle_aged_eurasian_female'] if g == 'female' else []
    if race == 'asian' and g == 'female' and age == 'young':
        opts += ['cutoff3d_indian_female_skin', 'onlytheghosts_young_eurasian_female']
    return rnd.choice(opts)


# ---------------------------------------------------------------------------
# fabrics: lungis (check, batik, ikat), sequins / glitter
# ---------------------------------------------------------------------------
def _hex(h):
    h = h.lstrip('#')
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple([(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4) for x in c] + [1.0])


LUNGI_PAL = [('#1F2E6B', '#F2EEE3', '#B3202A'), ('#1D5B3A', '#E8C547', '#141414'), ('#6B1420', '#D9A441', '#F3E9D2'),
             ('#1E8C8C', '#E75A8C', '#1A2340'), ('#D9661E', '#5B2A6E', '#E8B43A'), ('#3A2A1E', '#C9A77C', '#8C2F1E'),
             ('#2B6CB0', '#F5F0E6', '#F2C14E'), ('#8E3B8E', '#F2B5D4', '#2E1A47')]
SPARKLE_PAL = ['#D4AF37', '#C0C0C8', '#C2185B', '#1CA3A3', '#B87333', '#7B3FB5', '#E6C7A8']


def fabric(name, style, rnd):
    m = bpy.data.materials.new(name)
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    bs = nt.nodes.new('ShaderNodeBsdfPrincipled')
    nt.links.new(bs.outputs[0], out.inputs[0])
    uv = nt.nodes.new('ShaderNodeTexCoord').outputs['UV']
    L = nt.links.new
    if style == 'sequin':
        col = _hex(rnd.choice(SPARKLE_PAL))
        vo = nt.nodes.new('ShaderNodeTexVoronoi')
        vo.inputs['Scale'].default_value = 520.0
        L(uv, vo.inputs['Vector'])
        hs = nt.nodes.new('ShaderNodeHueSaturation')
        hs.inputs['Color'].default_value = col
        L(vo.outputs['Color'], hs.inputs['Value'])          # each sequin catches the light differently
        hs.inputs['Hue'].default_value = 0.5
        mr = nt.nodes.new('ShaderNodeMapRange')
        mr.inputs['To Min'].default_value = 0.55
        mr.inputs['To Max'].default_value = 1.35
        L(vo.outputs['Distance'], mr.inputs['Value'])
        L(mr.outputs[0], hs.inputs['Value'])
        L(hs.outputs[0], bs.inputs['Base Color'])
        bs.inputs['Metallic'].default_value = 0.95
        bs.inputs['Roughness'].default_value = 0.18
        bump = nt.nodes.new('ShaderNodeBump')
        bump.inputs['Strength'].default_value = 0.6
        L(vo.outputs['Distance'], bump.inputs['Height'])
        L(bump.outputs[0], bs.inputs['Normal'])
        return m
    if style == 'chiffon':                                # thin, light-through fabric in warm colours
        col = _hex(rnd.choice(['#E3A23A', '#F0B45A', '#C8553D', '#D98C8C', '#F28C6B', '#8E2A3A', '#D4A548', '#F5C89A',
                               '#B8402E', '#E9B7A1']))
        bs.inputs['Base Color'].default_value = col
        bs.inputs['Roughness'].default_value = 0.55
        bs.inputs['Sheen Weight'].default_value = 0.8
        bs.inputs['Sheen Tint'].default_value = col
        bs.inputs['Transmission Weight'].default_value = 0.35
        bs.inputs['Alpha'].default_value = 0.82
        nz = nt.nodes.new('ShaderNodeTexNoise')           # faint weave / fold variation
        nz.inputs['Scale'].default_value = 30
        L(uv, nz.inputs['Vector'])
        mx = nt.nodes.new('ShaderNodeMix')
        mx.data_type = 'RGBA'
        mx.blend_type = 'OVERLAY'
        mx.inputs[0].default_value = 0.15
        mx.inputs[6].default_value = col
        L(nz.outputs['Color'], mx.inputs[7])
        L(mx.outputs[2], bs.inputs['Base Color'])
        return m
    if style == 'velvet':                                 # plain velvet in a strong colour
        bs.inputs['Base Color'].default_value = _hex(rnd.choice(['#6B1E5A', '#1F3F8C', '#0F6B5C', '#B3261E', '#E0A21A',
                                                                 '#2A1A3A', '#D25A8C', '#101010', '#F2E6D8']))
        bs.inputs['Roughness'].default_value = 0.8
        bs.inputs['Sheen Weight'].default_value = 1.0
        bs.inputs['Sheen Roughness'].default_value = 0.3
        return m
    if style == 'rainbow':                                # rainbow gradient
        mp = nt.nodes.new('ShaderNodeMapping')
        mp.inputs['Scale'].default_value = (1, 3, 1)
        L(uv, mp.inputs['Vector'])
        sep = nt.nodes.new('ShaderNodeSeparateXYZ')
        L(mp.outputs[0], sep.inputs[0])
        hsv = nt.nodes.new('ShaderNodeCombineColor')
        hsv.mode = 'HSV'
        L(sep.outputs['Y'], hsv.inputs[0])
        hsv.inputs[1].default_value = 0.75
        hsv.inputs[2].default_value = 0.8
        L(hsv.outputs[0], bs.inputs['Base Color'])
        bs.inputs['Roughness'].default_value = 0.5
        bs.inputs['Sheen Weight'].default_value = 0.6
        return m
    if style == 'snake':                                  # snake skin: scales with a slight sheen
        pal = rnd.choice([('#C9B48A', '#5A4630'), ('#6E8B4A', '#1F2A14'), ('#B8B8B8', '#161616'), ('#8A2B3A', '#1A0B0E')])
        mp = nt.nodes.new('ShaderNodeMapping')
        mp.inputs['Scale'].default_value = (140, 90, 1)
        L(uv, mp.inputs['Vector'])
        vo = nt.nodes.new('ShaderNodeTexVoronoi')
        vo.feature = 'DISTANCE_TO_EDGE'
        L(mp.outputs[0], vo.inputs['Vector'])
        nz = nt.nodes.new('ShaderNodeTexNoise')
        nz.inputs['Scale'].default_value = 4
        L(uv, nz.inputs['Vector'])
        r_ = nt.nodes.new('ShaderNodeValToRGB')
        cr = r_.color_ramp
        cr.elements[0].position, cr.elements[0].color = 0.35, _hex(pal[1])
        cr.elements[1].position, cr.elements[1].color = 0.65, _hex(pal[0])
        L(nz.outputs['Fac'], r_.inputs['Fac'])
        mx = nt.nodes.new('ShaderNodeMix')
        mx.data_type = 'RGBA'
        mx.blend_type = 'MULTIPLY'
        mx.inputs[0].default_value = 0.6
        L(r_.outputs[0], mx.inputs[6])
        edge = nt.nodes.new('ShaderNodeValToRGB')
        edge.color_ramp.elements[0].position = 0.0
        edge.color_ramp.elements[0].color = (0.1, 0.1, 0.1, 1)
        edge.color_ramp.elements[1].position = 0.08
        L(vo.outputs['Distance'], edge.inputs['Fac'])
        L(edge.outputs[0], mx.inputs[7])
        L(mx.outputs[2], bs.inputs['Base Color'])
        bs.inputs['Roughness'].default_value = 0.3
        bs.inputs['Coat Weight'].default_value = 0.4
        bump = nt.nodes.new('ShaderNodeBump')
        bump.inputs['Strength'].default_value = 0.5
        L(vo.outputs['Distance'], bump.inputs['Height'])
        L(bump.outputs[0], bs.inputs['Normal'])
        return m
    furry = style.startswith('fur_')
    style = style.replace('fur_', '')
    if style in ('leopard', 'zebra', 'tiger'):
        bs.inputs['Roughness'].default_value = 0.55
        bs.inputs['Sheen Weight'].default_value = 0.6
        mp = nt.nodes.new('ShaderNodeMapping')
        L(uv, mp.inputs['Vector'])
        base = _hex(rnd.choice({'leopard': ['#C8964E', '#D9B47A', '#B5793A', '#E7D3B0'],
                                'zebra': ['#F2EEE6', '#E9E1D0'], 'tiger': ['#D9772A', '#E08A2E']}[style]))
        dark = _hex(rnd.choice(['#1A1410', '#2B1B12', '#3A2416']))
        if style == 'leopard':                            # rosettes: voronoi rings with a lighter centre
            mp.inputs['Scale'].default_value = (22, 22, 1)
            vo = nt.nodes.new('ShaderNodeTexVoronoi')
            vo.inputs['Randomness'].default_value = 0.9
            L(mp.outputs[0], vo.inputs['Vector'])
            nz = nt.nodes.new('ShaderNodeTexNoise')
            nz.inputs['Scale'].default_value = 60
            L(mp.outputs[0], nz.inputs['Vector'])
            mix_ = nt.nodes.new('ShaderNodeMath')
            mix_.operation = 'ADD'
            L(vo.outputs['Distance'], mix_.inputs[0])
            mm = nt.nodes.new('ShaderNodeMath')
            mm.operation = 'MULTIPLY'
            mm.inputs[1].default_value = 0.15
            L(nz.outputs['Fac'], mm.inputs[0])
            L(mm.outputs[0], mix_.inputs[1])
            r_ = nt.nodes.new('ShaderNodeValToRGB')
            cr = r_.color_ramp
            cr.elements[0].position, cr.elements[0].color = 0.22, tuple(x * 0.8 for x in base[:3]) + (1,)
            cr.elements[1].position, cr.elements[1].color = 0.3, dark
            e_ = cr.elements.new(0.42)
            e_.color = base
            L(mix_.outputs[0], r_.inputs['Fac'])
        else:                                             # stripes: distorted wave bands
            mp.inputs['Scale'].default_value = (1, 1, 1)
            w_ = nt.nodes.new('ShaderNodeTexWave')
            w_.wave_type = 'BANDS'
            w_.inputs['Scale'].default_value = 9 if style == 'zebra' else 6
            w_.inputs['Distortion'].default_value = 9 if style == 'zebra' else 14
            w_.inputs['Detail'].default_value = 3
            L(mp.outputs[0], w_.inputs['Vector'])
            r_ = nt.nodes.new('ShaderNodeValToRGB')
            cr = r_.color_ramp
            cr.interpolation = 'EASE'
            cr.elements[0].position, cr.elements[0].color = 0.45 if style == 'zebra' else 0.62, dark
            cr.elements[1].position, cr.elements[1].color = 0.52 if style == 'zebra' else 0.7, base
            L(w_.outputs['Fac'], r_.inputs['Fac'])
        L(r_.outputs[0], bs.inputs['Base Color'])
        if furry:                                         # plush faux fur: soft sheen + fine fibre bump
            bs.inputs['Roughness'].default_value = 1.0
            bs.inputs['Sheen Weight'].default_value = 1.0
            bs.inputs['Sheen Roughness'].default_value = 0.6
            fz = nt.nodes.new('ShaderNodeTexNoise')
            fz.inputs['Scale'].default_value = 900
            fz.inputs['Detail'].default_value = 8
            L(uv, fz.inputs['Vector'])
            fb = nt.nodes.new('ShaderNodeBump')
            fb.inputs['Strength'].default_value = 0.8
            L(fz.outputs['Fac'], fb.inputs['Height'])
            L(fb.outputs[0], bs.inputs['Normal'])
        return m
    a, b, c = [_hex(h) for h in rnd.choice(LUNGI_PAL)]
    bs.inputs['Roughness'].default_value = 0.65
    bs.inputs['Sheen Weight'].default_value = 0.5
    mp = nt.nodes.new('ShaderNodeMapping')
    L(uv, mp.inputs['Vector'])
    if style == 'check':                                  # madras / lungi check
        sc_ = rnd.uniform(9, 16)
        mp.inputs['Scale'].default_value = (sc_, sc_, 1)
        mix = None
        cols = []
        for ax in ('X', 'Y'):
            w = nt.nodes.new('ShaderNodeTexWave')
            w.wave_type = 'BANDS'
            w.bands_direction = ax
            w.inputs['Scale'].default_value = 1.0
            L(mp.outputs[0], w.inputs['Vector'])
            r_ = nt.nodes.new('ShaderNodeValToRGB')
            r_.color_ramp.interpolation = 'CONSTANT'
            r_.color_ramp.elements[0].position = 0.0
            r_.color_ramp.elements[1].position = 0.62
            L(w.outputs['Fac'], r_.inputs['Fac'])
            cols.append(r_)
        m1 = nt.nodes.new('ShaderNodeMix')
        m1.data_type = 'RGBA'
        L(cols[0].outputs[0], m1.inputs[0])
        m1.inputs[6].default_value = a
        m1.inputs[7].default_value = b
        m2 = nt.nodes.new('ShaderNodeMix')
        m2.data_type = 'RGBA'
        m2.blend_type = 'MULTIPLY'
        m2.inputs[0].default_value = 0.55
        L(m1.outputs[2], m2.inputs[6])
        mx = nt.nodes.new('ShaderNodeMix')
        mx.data_type = 'RGBA'
        L(cols[1].outputs[0], mx.inputs[0])
        mx.inputs[6].default_value = (1, 1, 1, 1)
        mx.inputs[7].default_value = c
        L(mx.outputs[2], m2.inputs[7])
        L(m2.outputs[2], bs.inputs['Base Color'])
    else:                                                 # batik / ikat
        if style == 'ikat':
            mp.inputs['Scale'].default_value = (3.0, 28.0, 1)
        else:
            mp.inputs['Scale'].default_value = (7.0, 7.0, 1)
        n = nt.nodes.new('ShaderNodeTexNoise')
        n.inputs['Scale'].default_value = 2.5 if style == 'ikat' else 1.5
        n.inputs['Detail'].default_value = 6
        n.inputs['Distortion'].default_value = 1.5 if style == 'batik' else 0.3
        L(mp.outputs[0], n.inputs['Vector'])
        r_ = nt.nodes.new('ShaderNodeValToRGB')
        cr = r_.color_ramp
        cr.elements[0].position, cr.elements[0].color = 0.35, a
        cr.elements[1].position, cr.elements[1].color = 0.5, b
        e = cr.elements.new(0.62)
        e.color = c
        L(n.outputs['Fac'], r_.inputs['Fac'])
        L(r_.outputs[0], bs.inputs['Base Color'])
    return m


HEAD_HANDS = ('head', 'neck', 'jaw', 'eye', 'ear', 'nose', 'lip', 'mouth', 'cheek', 'brow', 'tongue', 'oris', 'temporalis',
              'levator', 'orbicularis', 'risorius', 'wrist', 'finger', 'thumb', 'metacarpal', 'toe', 'foot', 'special')
LEG_GROUPS = ('upperleg', 'lowerleg', 'pelvis')


def body_paint(body, mat, part='full'):
    """Skin-tight: a bodysuit (everything but head, hands, feet) or tights (legs) painted onto the body."""
    names = {g.index: g.name for g in body.vertex_groups}
    me = body.data
    dom = []
    for v in me.vertices:
        best = max(((g.weight, names.get(g.group, '')) for g in v.groups
                    if not names.get(g.group, '').startswith(('helper', 'joint', 'body', 'Left', 'Right', 'Mid'))),
                   default=(0, ''))
        dom.append(best[1])
    me.materials.append(mat)
    slot = len(me.materials) - 1
    for poly in me.polygons:
        gs = [dom[i] for i in poly.vertices]
        if part == 'legs':
            ok = all(any(g.startswith(k) for k in LEG_GROUPS) for g in gs)
        else:
            ok = all(g and not any(k in g for k in HEAD_HANDS) for g in gs)
        if ok:
            poly.material_index = slot


def dress_up(rig, fabrics_by_asset):
    for ob in rig.children:
        for asset, mat in fabrics_by_asset.items():
            if ob.name.endswith('.' + asset) or ob.name.endswith(asset):
                ob.data.materials.clear()
                ob.data.materials.append(mat)


LUNGI_F = [('elvs_sarong_cover_up',), ('elvs_sarong_cover_up',),                 # chest wrap
           ('elvs_halter_dress_long',), ('toigo_halter_dress_midi',),                 # tied at the neck
           ('elvs_double_handkerchief_halter_dress',),                                # handkerchief tie
           ('elvs_goddess_dress2',), ('elvs_goddess_dress5',),                        # one shoulder / toga tie
           ('punkduck_tube_dress',), ('elvs_halter_dress_knee_length',),              # strapless / knee length
           ('toigo_long_full_skirt', 'toigo_camisole_top'), ('elvs_gored_midi_skirt', 'punkduck_tube_top')]
LUNGI_M = [('toigo_long_full_skirt', 'elvs_male_boho_top1'), ('elvs_gored_midi_skirt', 'elvs_male_tankshirt1'),
           ('toigo_long_full_skirt', 'elvs_male_tankshirt1'), ('elvs_gored_midi_skirt', 'elvs_male_boho_top1'),
           ('toigo_long_full_skirt', 'mindfront_kimono'), ('elvs_gored_midi_skirt',)]
LUNGI_PIECES = ('toigo_long_full_skirt', 'elvs_gored_midi_skirt', 'elvs_sarong_cover_up', 'elvs_halter_dress_long',
                'toigo_halter_dress_midi', 'elvs_double_handkerchief_halter_dress', 'elvs_goddess_dress2',
                'elvs_goddess_dress5', 'punkduck_tube_dress', 'elvs_halter_dress_knee_length')
SPARKLE_PIECES = ('punkduck_tube_top', 'punkduck_sleeveless_crop_top', 'toigo_camisole_top', 'elvs_disco_top2',
                  'elvs_disco_top_1_butterfly', 'punkduck_figure_skating_dress', 'elvs_disco_mini_skirt',
                  'punkduck_black_mini_skirt', 'elvs_disco_pants_skinny', 'punkduck_tube_dress',
                  'elvs_goddess_dress1', 'elvs_goddess_dress3', 'toigo_bodice-style_top', 'elvs_halter_dress_tiered',
                  'punkduck_evening_gown', 'elvs_disco_pants_double_ruffles', 'elvs_disco_pants_single_ruffles')

N = [0]


def new_person(kind='flow', sex=None, years=None, race=None, outfit=None, seed=None):
    """Generate one dressed person. kind: flow | crazy | organiser."""
    N[0] += 1
    rnd = random.Random(1000 + N[0] if seed is None else seed)
    sex = rnd.choice([0.0, 0.05, 0.1, 0.9, 0.95, 1.0, 0.0, 1.0]) if sex is None else sex
    years = rnd.choice([21, 24, 27, 29, 31, 34, 37, 41, 45, 49, 53, 58, 63, 68, 72, 76]) if years is None else years
    race = race or rnd.choice(['caucasian'] * 16 + ['african', 'asian', 'mixed', 'mixed'])
    build = rnd.choice(['slim', 'average', 'full'])     # body diversity: slim / average / curvy, heavy, soft bellies
    if kind == 'flow':                       # everyone dresses how they feel: a balanced, individual mix
        w = {'flow': 0.27, 'mix': 0.22, 'everyday': 0.15, 'lungi': 0.12 if sex < 0.5 else 0.07, 'crazy': 0.08,
             'undress': 0.14 + 0.4 * UNDRESS[0], 'onesie': 0.07}
        u = rnd.random() * sum(w.values())
        for k_, v_ in w.items():
            if u < v_:
                kind = k_
                break
            u -= v_
        if kind == 'undress':
            kind = 'lingerie' if (sex < 0.5 and rnd.random() < 0.7) else 'undies'
            if sex < 0.5 and UNDRESS[0] <= 0.2 and rnd.random() < 0.6:
                kind = 'topless'                 # dancing topless (dance areas)
    if outfit is None:
        if kind == 'mix':                    # own combination of a bottom, maybe a top, maybe a kimono over it
            bottom = rnd.choice(BOTTOMS)
            top = rnd.choice(TOPS_F if sex < 0.5 else TOPS_M)
            outfit = tuple(x for x in (bottom, top, 'mindfront_kimono' if rnd.random() < 0.25 else None) if x)
            kind = 'flow'
        if kind == 'everyday':               # everyday and colourful (as on ZEGG's festival photos)
            if sex < 0.5:
                outfit = (rnd.choice(['punkduck_retro_polka_dot_skirt', 'toigo_tiered_skirt', 'elvs_gored_midi_skirt',
                                      'toigo_long_full_skirt', 'mindfront_female_trousers_1', 'cortu_cargo_pants']),
                          rnd.choice(['joepal_crude_t-shirt_female', 'toigo_basic_tucked_t-shirt',
                                      'elvs_ruffle_sleeve_peasant_blouse_1', 'ews_striped_shirt']))
            else:
                outfit = (rnd.choice(['mindfront_male_trousers_1', 'toigo_wool_pants', 'cortu_cargo_pants',
                                      'elvs_male_trouser_short_2']),
                          rnd.choice(['elvs_crude_t-shirt_male', 'namuhekam_male_polo_shirt', 'ews_striped_shirt',
                                      'elvs_male_shirt_untucked_bd1']))
            kind = 'mix'
        if kind == 'onesie':                 # body-tight onesie (painted on), maybe a kimono over it
            outfit = ('mindfront_kimono',) if rnd.random() < 0.3 else ()
        if kind == 'lungi':                  # lungis / sarongs tied in different ways
            outfit = tuple(x for x in rnd.choice(LUNGI_F if sex < 0.5 else LUNGI_M) if x)
    if outfit is None:
        pool = {'crazy': CRAZY, 'organiser': [KIMONO], 'naked': [()],
                'undies': UNDIES_F if sex < 0.5 else UNDIES_M, 'lingerie': LINGERIE_F,
                'topless': TOPLESS_F}.get(kind)
        if pool is None:
            pool = FLOW_F if (sex < 0.5 or rnd.random() < 0.08) else FLOW_M
        outfit = rnd.choice(pool)
        if kind == 'flow' and rnd.random() < 0.4:            # layered: a sheer over-layer
            layer = rnd.choice(['mindfront_kimono', 'mindfront_cardigan_long_open_front'] +
                               (['toigo_long_full_skirt'] if 'toigo_harem_pants' in outfit else []))
            if layer not in outfit:
                outfit = tuple(outfit) + (layer,)
        if kind in ('flow', 'undies', 'naked') and rnd.random() < 0.45:
            outfit = tuple(outfit) + (rnd.choice(JEWEL_F if sex < 0.5 else JEWEL_M),)
    if sex < 0.5:
        hair = rnd.choice(HAIR_F)
    else:
        hair = rnd.choice(HAIR_M)
    wt = {'slim': rnd.uniform(0.12, 0.35), 'average': rnd.uniform(0.4, 0.6), 'full': rnd.uniform(0.68, 1.0)}[build]
    ph = dict(gender=sex, age=0.5 + (years - 25) / 130.0, muscle=rnd.uniform(0.15, 0.85),
              weight=wt, height=rnd.uniform(0.1, 0.9), proportions=rnd.uniform(0.15, 0.85),
              cupsize=rnd.uniform(0.1, 0.95), firmness=rnd.uniform(0.15, 0.8), race=RACES[race])
    name = 'cr_%02d' % N[0]
    lc = bpy.context.view_layer.layer_collection.children['event'].children['crowd']
    bpy.context.view_layer.active_layer_collection = lc
    rig, body = H.make_person(name, ph, skin_for(sex, years, race, rnd), hair=hair,
                              eyebrows=rnd.choice(['eyebrow001', 'eyebrow006', 'eyebrow009', 'eyebrow010']),
                              clothes=outfit, subdiv=1)
    for ob in [rig] + list(rig.children_recursive):
        for c in list(ob.users_collection):
            if c != CROWD:
                c.objects.unlink(ob)
        if CROWD not in ob.users_collection:
            CROWD.objects.link(ob)
    rig['body'] = body.name
    if years >= 55:                          # grey hair with age
        for ob in rig.children:
            if ob.name.endswith(hair) and ob.active_material and hair:
                recolour(ob, 0.5, rnd.uniform(0.0, 0.25), rnd.uniform(1.2, 1.8))
    fab = {}
    for piece in outfit:
        if piece in LUNGI_PIECES and (kind == 'lungi' or rnd.random() < 0.3):
            fab[piece] = fabric('lungi_%s_%s' % (name, piece[:12]), rnd.choice(['check', 'check', 'batik', 'ikat']), rnd)
        elif piece in SPARKLE_PIECES and rnd.random() < (0.7 if kind == 'crazy' else 0.18):
            fab[piece] = fabric('sequin_%s_%s' % (name, piece[:12]), 'sequin', rnd)
    FLOWY = ('goddess', 'halter', 'long_full_skirt', 'tiered', 'kimono', 'cardigan', 'sarong', 'handkerchief',
             'camisole', 'peasant', 'off-shoulder', 'harem', 'elephant', 'midi', 'dress')
    for piece in outfit:
        if piece not in fab and kind in ('flow', 'mix') and any(k in piece for k in FLOWY) and rnd.random() < 0.5:
            fab[piece] = fabric('chiffon_%s_%s' % (name, piece[:12]), 'chiffon', rnd)
    for piece in outfit:
        if piece in fab or kind == 'organiser' or any(k in piece for k in (
                'shoe', 'boot', 'sandal', 'flat', 'ring', 'anklet', 'bracelet', 'bangle', 'necklace', 'choker',
                'collar', 'mask', 'crown', 'circlet', 'jewel', 'hoop', 'earring')):
            continue
        if rnd.random() < 0.13:
            fab[piece] = fabric('animal_%s_%s' % (name, piece[:12]), rnd.choice(['leopard', 'leopard', 'zebra', 'tiger']),
                                rnd)
    dress_up(rig, fab)
    # skin-tight looks: bodysuits for the wild / lingerie looks, animal-print tights under skirts and dresses
    if kind == 'onesie':
        body_paint(body, fabric('onesie_' + name, rnd.choice(['velvet', 'velvet', 'sequin', 'rainbow', 'snake', 'leopard',
                                                              'fur_leopard', 'zebra']), rnd), 'full')
    elif kind in ('crazy', 'lingerie') and rnd.random() < 0.35:
        body_paint(body, fabric('suit_' + name, rnd.choice(['snake', 'snake', 'leopard', 'zebra']), rnd), 'full')
    elif kind in ('flow', 'mix') and sex < 0.5 and rnd.random() < 0.12:
        body_paint(body, fabric('tights_' + name, rnd.choice(['leopard', 'snake', 'zebra', 'tiger']), rnd), 'legs')
    # plush faux-fur leopard on some kimonos / cardigans / dresses
    for ob in rig.children:
        if ob.type == 'MESH' and any(k in ob.name for k in ('kimono', 'cardigan', 'goddess', 'fringe')) and \
                kind != 'organiser' and rnd.random() < 0.15:
            ob.data.materials.clear()
            ob.data.materials.append(fabric('fur_' + name, 'fur_leopard', rnd))
    if kind in ('flow', 'mix') and rnd.random() < 0.45:  # colourful: shift the colours of the rest
        for ob in rig.children:
            if ob.type == 'MESH' and ob.active_material and not any(k in ob.name for k in (
                    'body', 'hair', 'eyebrow', 'eyelash', 'high-poly', 'kimono')) and \
                    not any(ob.name.endswith(k) for k in fab):
                recolour(ob, rnd.random(), rnd.uniform(1.0, 1.5), rnd.uniform(0.9, 1.2))
    if kind == 'lingerie':                   # deep lingerie tones
        tone = rnd.choice(LINGERIE_TONES)
        for ob in rig.children:
            if ob.type == 'MESH' and ob.active_material and not any(
                    k in ob.name for k in ('body', 'hair', 'eyebrow', 'eyelash', 'high-poly', 'choker')):
                recolour(ob, *tone)
    if kind != 'organiser':                  # guests' kimonos: each in its own colour
        for ob in rig.children:
            if 'kimono' in ob.name and ob.active_material:
                recolour(ob, rnd.random(), rnd.uniform(0.7, 1.3), rnd.uniform(0.8, 1.15))
    return rig


def recolour(ob, hue, sat, val):
    m = ob.active_material.copy()
    ob.active_material = m
    nt = m.node_tree
    for lk in list(nt.links):
        if lk.to_socket.name == 'Base Color' and lk.from_node.type == 'TEX_IMAGE':
            hs = nt.nodes.new('ShaderNodeHueSaturation')
            hs.inputs['Hue'].default_value = hue
            hs.inputs['Saturation'].default_value = sat
            hs.inputs['Value'].default_value = val
            src, dst = lk.from_socket, lk.to_socket
            nt.links.remove(lk)
            nt.links.new(src, hs.inputs['Color'])
            nt.links.new(hs.outputs['Color'], dst)
            return


def body_of(rig):
    return bpy.data.objects[rig['body']]


def pose(rig, name):
    rig['pose'] = name
    if name in ('standing01', 'standing02', 'standing03', 'standing04', 'standing05', 'standing06'):
        # instead of a stiff photo pose: an ordinary moment of recorded movement (asymmetric, relaxed limbs)
        import mocap as MC_
        rg = random.Random(hash(rig.name) & 0xffff)
        clip_ = rg.choice(['60_04', '61_04', '60_05', '61_05', '49_10', '49_16', '05_18', '55_02'])
        _, n = MC_.joints(clip_, 0)
        f = rg.randrange(int(n * 0.15), int(n * 0.85))
        rig['pose'] = '%s@%d' % (clip_, f)
        MC_.apply(rig, clip_, f)
        bpy.context.view_layer.update()
        return
    H.apply_pose(rig, name)
    bpy.context.view_layer.update()


# orientations ------------------------------------------------------------------------------------
# MakeHuman figures stand along +Z and face -Y.
def stand(rig, x, y, face):
    """Standing / sitting upright, facing the (math) angle `face`."""
    rig.rotation_euler = Euler((0, 0, rad(face + 90)), 'XYZ')
    rig.location = (x, y, rig.location.z)


def lie(rig, x, y, head, how='back', tilt=0.0):
    """Lying: how = back | front | side_r (faces head-90) | side_l (faces head+90); head = angle of head."""
    rx, ry, rzz = {'back': (-90, 0, head - 90), 'front': (90, 0, head + 90),
                   'side_r': (0, 90, head), 'side_l': (0, -90, head - 180)}[how]
    rig.rotation_euler = Euler((rad(rx + tilt), rad(ry), rad(rzz)), 'XYZ')
    rig.location = (x, y, rig.location.z)


def lean(rig, deg):
    """Lean forward (+) / backward (-) about the figure's own left-right axis."""
    e = rig.rotation_euler
    m = e.to_matrix() @ Matrix.Rotation(rad(deg), 3, 'X')
    rig.rotation_euler = m.to_euler('XYZ')


def eval_verts(rig, step=6):
    bpy.context.view_layer.update()
    b = body_of(rig)
    dg = bpy.context.evaluated_depsgraph_get()
    ev = b.evaluated_get(dg)
    me = ev.to_mesh()
    mw = b.matrix_world
    vs = [mw @ me.vertices[i].co for i in range(0, len(me.vertices), step)]
    ev.to_mesh_clear()
    return vs


def drop(rig, z0, on=(), sink=0.015, reach=1.3):
    """Put the person at level z0, then move them so they rest on what is under them."""
    rig.location.z = z0
    vs = eval_verts(rig)
    lowest = min(v.z for v in vs)
    rig.location.z += z0 + 0.3 - lowest            # start 30 cm above the target level
    vs = eval_verts(rig)
    trees = [STATIC] + ([world_bvh([body_of(o) for o in on])] if on else [])
    best = -1e9
    for v in vs:
        for t in trees:
            hit = t.ray_cast(Vector((v.x, v.y, z0 + reach)), Vector((0, 0, -1)), reach + 1.0)
            if hit[0] is not None and hit[0].z <= v.z + 0.35:
                best = max(best, hit[0].z - v.z)
    if best > -1e8:
        rig.location.z += best - sink
    bpy.context.view_layer.update()
    return rig


def bone_w(rig, bone, off=(0, 0, 0)):
    """World position of a posed bone head, plus an offset in the figure's frame
    (x = figure's left, y = figure's back, z = up along the figure)."""
    pb = rig.pose.bones[bone]
    return rig.matrix_world @ (pb.head + Vector(off))


def front(rig):
    return (rig.matrix_world.to_3x3() @ Vector((0, -1, 0))).normalized()


N_IK = [0]


def reach_to(rig, side, target, chain=4, max_reach=0.5):
    """Put the hand (wrist bone) of `side` ('L'/'R') on a world point, IK over the arm -
    only if it is within a comfortable, bent-arm reach of the shoulder (no stretched 'zombie' arms)."""
    sh = bone_w(rig, 'upperarm01.' + side)
    if (Vector(target) - sh).length > max_reach:
        return None
    N_IK[0] += 1
    e = bpy.data.objects.new('ik_%s_%d' % (rig.name, N_IK[0]), None)
    e.location = target
    e.empty_display_size = 0.03
    CROWD.objects.link(e)
    e.hide_render = True
    c = rig.pose.bones['wrist.' + side].constraints.new('IK')
    c.target = e
    c.chain_count = chain + 1
    c.use_tail = False
    return e


def foot_to(rig, side, target):
    """Put a foot on something (IK over the leg)."""
    N_IK[0] += 1
    e = bpy.data.objects.new('ikf_%s_%d' % (rig.name, N_IK[0]), None)
    e.location = target
    CROWD.objects.link(e)
    e.hide_render = True
    c = rig.pose.bones['foot.' + side].constraints.new('IK')
    c.target = e
    c.chain_count = 5
    c.use_tail = False
    return e


def on_back(partner, height='spine02', side=0.0, depth=0.13):
    """Point on the partner's back (for hands)."""
    return bone_w(partner, height, (side, depth, 0))


def on_shoulder(partner, side='L', up=0.06):
    return bone_w(partner, 'shoulder01.' + side, (0, 0.02, up))


# ---------------------------------------------------------------------------
# helpers for groups
# ---------------------------------------------------------------------------
def standing(pname, x, y, face, kind='flow', z0=0.0, **kw):
    r = new_person(kind, **kw)
    pose(r, pname)
    stand(r, x, y, face)
    drop(r, z0)
    return r


def pose_lying(r, pname, how):
    """A lying person: the recorded walking / swaying moments ('standing0x') would lie stiff as a plank,
    so they get a resting posture instead (knee up, hand on the belly, curled on the side...)."""
    if pname.startswith('standing'):
        import mocap as MC_
        kind_ = {'back': 'back', 'front': 'front'}.get(how, 'side')
        MC_.apply_joints(r, MC_.resting_joints(kind_, random.Random(hash(r.name) & 0xffff)))
        r['pose'] = 'resting_' + kind_
        bpy.context.view_layer.update()
    else:
        pose(r, pname)


def lying(pname, x, y, head, how, z0, on=(), kind='flow', tilt=0.0, **kw):
    r = new_person(kind, **kw)
    pose_lying(r, pname, how)
    lie(r, x, y, head, how, tilt)
    drop(r, z0, on=on)
    return r


def embrace_standing(x, y, face, z0=0.0, a_pose='standing02', b_pose='standing05', kinds=('flow', 'flow'),
                     kiss=False):
    """Close dance / embrace: A faces `face`, B faces A; heads pass each other (or meet: kiss)."""
    c = Vector((x, y, 0))
    f = Rz(face) @ Vector((1, 0, 0))
    s = Rz(face) @ Vector((0, 1, 0))
    d, l = (0.115, 0.025) if kiss else (0.13, 0.07)
    a = swayer(*(c - f * d + s * l).xy, face, kinds[0], z0)
    b = swayer(*(c + f * d - s * l).xy, face + 180, kinds[1], z0)
    reach_to(a, 'L', on_back(b, 'spine02', 0.1))
    reach_to(a, 'R', on_back(b, 'spine04', -0.1, 0.12))
    reach_to(b, 'L', on_back(a, 'spine01', 0.12, 0.1))
    reach_to(b, 'R', on_back(a, 'spine01', -0.12, 0.1))
    return a, b


def spoon(x, y, head, z0, pname='callharvey3d_sittingnatural', on=()):
    """Two people lying on their side, the one behind holding the one in front."""
    fdir = Rz(head - 90) @ Vector((1, 0, 0))
    back = lying(pname, x - fdir.x * 0.16, y - fdir.y * 0.16, head, 'side_r', z0, on=on)
    fr = lying(pname, x + fdir.x * 0.16, y + fdir.y * 0.16, head - 4, 'side_r', z0, on=on)
    reach_to(back, 'L', bone_w(fr, 'spine04', (0, -0.14, 0)))
    return back, fr


def face_to_face(x, y, head, z0, pa='standing02', pb='standing03', on=(), kiss=True):
    """Lying on their sides facing each other, holding each other, making out."""
    fdir = Rz(head - 90) @ Vector((1, 0, 0))
    d = 0.135 if kiss else 0.17
    a = lying(pa, x - fdir.x * d, y - fdir.y * d, head, 'side_r', z0, on=on)
    b = lying(pb, x + fdir.x * d, y + fdir.y * d, head + (4 if kiss else 0), 'side_l', z0, on=on)
    reach_to(a, 'L', on_back(b, 'spine03', 0.0, 0.12))
    reach_to(b, 'R', on_back(a, 'spine02', 0.0, 0.12))
    return a, b


def head_on(pname, partner, rest_bone, head_away, how, z0, extra_on=()):
    """Someone lying with the head resting on a partner (belly / thigh / lap)."""
    p = bone_w(partner, rest_bone)
    d = Rz(head_away) @ Vector((1, 0, 0))
    r = new_person()
    pose_lying(r, pname, how)
    lie(r, 0, 0, head_away + 180, how)
    bpy.context.view_layer.update()
    hd = bone_w(r, 'head')
    r.location.x += p.x - hd.x + d.x * 0.02
    r.location.y += p.y - hd.y + d.y * 0.02
    drop(r, z0, on=(partner,) + tuple(extra_on))
    return r


# blindfolds for everyone in the 'Blind' zone: a band of dark silk fitted round each head at eye level
def blindfold(rig, mat):
    body = next(c for c in rig.children_recursive if c.name.endswith('.body'))
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    e = body.evaluated_get(dg)
    me = e.to_mesh()
    pts = [e.matrix_world @ v.co for v in me.vertices]
    e.to_mesh_clear()
    hm = rig.matrix_world @ rig.pose.bones['head'].matrix
    up = (hm.to_3x3() @ Vector((0, 1, 0))).normalized()
    if 'eye.L' in rig.pose.bones and 'eye.R' in rig.pose.bones:
        eye = (bone_w(rig, 'eye.L') + bone_w(rig, 'eye.R')) / 2
    else:
        eye = hm.translation + up * 0.09
    base = hm.translation
    c = base + up * (eye - base).dot(up)                     # head axis at eye level
    fwd = (eye - c)
    fwd = (fwd - up * fwd.dot(up)).normalized() if fwd.length > 1e-4 else front(rig)
    side = up.cross(fwd).normalized()
    near = [p for p in pts if abs((p - c).dot(up)) < 0.03 and (p - c).length < 0.16]
    N_, rings = 48, []
    for i in range(N_):
        a = 2 * math.pi * i / N_
        d = fwd * math.cos(a) + side * math.sin(a)
        best = 0.07
        for p in near:
            q = p - c - up * (p - c).dot(up)
            if q.length > 1e-4 and q.normalized().dot(d) > 0.995:
                best = max(best, q.length)
        rings.append((d, best + (0.009 if math.cos(a) > 0.3 else 0.006)))
    bm = bmesh.new()
    rows = []
    for dz, dr in ((-0.021, 0.0), (0.021, 0.0), (0.021, -0.004), (-0.021, -0.004)):
        rows.append([bm.verts.new(c + d * (r + dr) + up * dz) for d, r in rings])
    for j in range(4):
        A, B = rows[j], rows[(j + 1) % 4]
        for i in range(N_):
            bm.faces.new((A[i], A[(i + 1) % N_], B[(i + 1) % N_], B[i]))
    me2 = bpy.data.meshes.new(rig.name + '.blindfold')
    bm.to_mesh(me2)
    bm.free()
    for f in me2.polygons:
        f.use_smooth = True
    me2.materials.append(mat)
    ob = bpy.data.objects.new(rig.name + '.blindfold', me2)
    for col in rig.users_collection:
        col.objects.link(ob)
    ob.parent = rig
    ob.parent_type = 'BONE'
    ob.parent_bone = 'head'
    ob.matrix_world = Matrix.Identity(4)
    return ob


def blindfold_mat():
    m = bpy.data.materials.get('blindfold_silk')
    if m is None:
        m = bpy.data.materials.new('blindfold_silk')
        m.use_nodes = True
        b = m.node_tree.nodes.get('Principled BSDF')
        b.inputs['Base Color'].default_value = (0.02, 0.012, 0.018, 1)
        b.inputs['Roughness'].default_value = 0.35
        b.inputs['Sheen Weight'].default_value = 0.8
    return m
# ---------------------------------------------------------------------------
# separation: nobody deep inside another person or inside furniture. Touching is fine (embraces, heads on
# bellies); limbs through torsos and bodies through mattresses / benches are not. People are moved apart
# horizontally (from each other) or along the surface normal (out of furniture), in a few rounds.
# ---------------------------------------------------------------------------
def _person_mesh(rig, dg, step=3):
    vs, polys = [], []
    for part in [rig] + list(rig.children_recursive):
        if part.type != 'MESH' or part.hide_render or not part.name.endswith('.body'):
            continue
        e = part.evaluated_get(dg)
        me = e.to_mesh()
        o = len(vs)
        vs += [e.matrix_world @ v.co for v in me.vertices]
        polys += [[o + i for i in p.vertices] for p in me.polygons]
        e.to_mesh_clear()
    return vs, polys


def _depth_into(pts, tree, lim=0.5):
    best, n = 0.0, 0
    for p in pts:
        loc, nrm, _, dist = tree.find_nearest(p, lim)
        if loc is not None and (p - loc).dot(nrm) < -0.002:
            n += 1
            best = max(best, dist)
    return best, n


def _shift(rig, d):
    rig.location += d
    for o in bpy.data.objects:
        if o.name.startswith(('ik_%s_' % rig.name, 'ikf_%s_' % rig.name)):
            o.location += d


def separate_people(rigs, rounds=4, tol_person=0.05, tol_static=0.04):
    from mathutils.bvhtree import BVHTree
    for rnd in range(rounds):
        bpy.context.view_layer.update()
        dg = bpy.context.evaluated_depsgraph_get()
        data = {}
        for r in rigs:
            vs, polys = _person_mesh(r, dg)
            if not vs:
                continue
            lo = Vector((min(v.x for v in vs), min(v.y for v in vs), min(v.z for v in vs)))
            hi = Vector((max(v.x for v in vs), max(v.y for v in vs), max(v.z for v in vs)))
            data[r] = (vs[::4], BVHTree.FromPolygons(vs, polys), lo, hi, sum(vs, Vector()) / len(vs))
        moves = {r: Vector() for r in data}
        count = 0
        items = list(data.items())
        for i in range(len(items)):
            ra, (pa, ta, la, ha, ca) = items[i]
            for rb, (pb, tb, lb, hb, cb) in items[i + 1:]:
                if any(ha[k] < lb[k] or hb[k] < la[k] for k in range(3)):
                    continue
                d = max(_depth_into(pa, tb)[0], _depth_into(pb, ta)[0])
                if d > tol_person:
                    v = Vector((ca.x - cb.x, ca.y - cb.y, 0))
                    v = v.normalized() if v.length > 1e-3 else Vector((1, 0, 0))
                    moves[ra] += v * (d / 2 + 0.01)
                    moves[rb] -= v * (d / 2 + 0.01)
                    count += 1
        for r, (pts, _, _, _, _) in data.items():             # out of furniture (floor, mattresses, benches)
            deep = []
            for p in pts:
                loc, nrm, _, dist = STATIC.find_nearest(p, 0.5)
                if loc is not None and (p - loc).dot(nrm) < -0.002 and dist > tol_static:
                    deep.append((dist, nrm))
            if len(deep) > 3:
                dist = max(x[0] for x in deep)
                nrm = sum((x[1] for x in deep), Vector()).normalized()
                moves[r] += nrm * min(dist + 0.01, 0.4)
                count += 1
        for r, m in moves.items():
            if m.length > 1e-4:
                _shift(r, m)
        print('separation round', rnd, count, 'fixes', flush=True)
        if not count:
            break


# test mode: CROWD_TEST=blind | field builds only that zone into $TEMPEL_TMP/<zone>_test.blend
_TEST = os.environ.get('CROWD_TEST')
if _TEST == 'cloth':                                   # three dancers in flowing clothes, cloth simulation on
    _src = open(os.path.abspath(__file__)).read()
    _a = _src.index('\nCLOTH = os.environ.get') + 1
    _b = _src.index('\nSWAY = [') + 1
    exec(compile(_src[_a:_b], 'cloth', 'exec'))
    CLOTH = True
    SC.frame_set(10)
    DANCERS, FR_CACHE = [], {}
    import mocap as MC  # noqa: F811

    def frames_of(clip, k=4):
        if clip not in FR_CACHE:
            FR_CACHE[clip] = MC.best_frames(clip, k)
        return FR_CACHE[clip]

    def blur_move(r, mv, face):
        pass
    for i_, clip_ in enumerate(('61_01', '05_06', '05_16')):
        p_ = pol(2.2, 200 + 40 * i_)
        dancer(clip_, i_, p_.x, p_.y, 20 + 60 * i_, kind='flow')
    os.makedirs(os.environ.get('TEMPEL_TMP', '/tmp/tempel'), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(os.environ.get('TEMPEL_TMP', '/tmp/tempel'), 'cloth_test.blend'),
                                compress=True)
    print('ZONE TEST saved cloth', [(r.name, [c.name for c in r.children][:6]) for r in DANCERS], flush=True)
    sys.exit(0)
if _TEST in ('blind', 'field'):
    _src = open(os.path.abspath(__file__)).read()
    _m = {'blind': ('\n# 5. intimate zone', '\n# 6. cuddle puddle'),
          'field': ('\n# 1. mattress field', '\n# 2. on the net')}[_TEST]
    _a = _src.index(_m[0]) + 1                           # headings at the start of a line only
    _b = _src.index(_m[1]) + 1
    BLIND = []
    exec(compile(_src[_a:_b], _TEST, 'exec'))
    separate_people([o for o in CROWD.objects if o.type == 'ARMATURE'])
    for r_ in BLIND:
        blindfold(r_, blindfold_mat())
    os.makedirs(os.environ.get('TEMPEL_TMP', '/tmp/tempel'), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(os.environ.get('TEMPEL_TMP', '/tmp/tempel'), '%s_test.blend' % _TEST), compress=True)
    print('ZONE TEST saved', _TEST, flush=True)
    sys.exit(0)

# ---------------------------------------------------------------------------
# 1. mattress field under the net (12): lying together, some looking up at the net
# ---------------------------------------------------------------------------
MF_Z = 0.17
UNDRESS[0] = 0.6
a1 = lying('elvs_yoga_star_pose_1', 0.3, 0.2, 60, 'back', MF_Z)                      # starfish, looking up
head_on('standing01', a1, 'spine04', 200, 'back', MF_Z)                              # head on a1's belly
lying('callharvey3d_sittingnatural', -0.55, 0.9, 150, 'side_r', MF_Z)                # curled up alongside
r = standing('callharvey3d_lotus', 1.2, 0.95, 225, z0=MF_Z)
reach_to(r, 'R', bone_w(a1, 'spine02', (0, -0.1, 0)))
spoon(-1.6, -0.6, 250, MF_Z)
face_to_face(0.9, -1.6, 15, MF_Z)
lying('sohh_posing4', -1.5, 1.8, 110, 'back', MF_Z)                                  # hand behind head, looking up
# lounging: one leaning back against the other, who holds them loosely
g1 = standing('callharvey3d_sittingfloorstretch2', -0.45, -2.45, 20, z0=MF_Z)
g2 = standing('callharvey3d_lotus', *(Vector((-0.45, -2.45, 0)) - Rz(20) @ Vector((0.42, 0, 0))).xy, 20, z0=MF_Z)
reach_to(g2, 'L', bone_w(g1, 'spine03', (0.12, -0.08, 0)))
print('field done', N[0])

# ---------------------------------------------------------------------------
# 2. on the net (10)
# ---------------------------------------------------------------------------
def net_z(x, y):
    r = math.hypot(x, y)
    return P.net_z(r) - NET_EXTRA * (1 - (min(r, P.RING_BEAM_IN) / P.RING_BEAM_IN) ** 2)


face_to_face(-1.0, 0.8, 30, net_z(-1.0, 0.8))
n1 = lying('standing01', 1.3, -0.4, 110, 'back', net_z(1.3, -0.4))
head_on('callharvey3d_sittingnatural', n1, 'spine04', 20, 'side_r', net_z(1.6, -0.1))
n3 = lying('callharvey3d_sittingnatural', 1.75, -1.0, 200, 'side_l', net_z(1.75, -1.0))
reach_to(n3, 'R', bone_w(n1, 'spine03', (0, -0.1, 0)))
spoon(0.1, -2.3, 80, net_z(0.1, -2.3))
lying('elvs_yoga_star_pose_1', 2.4, 1.6, 30, 'back', net_z(2.4, 1.6), kind='naked')
print('net done', N[0])

# ---------------------------------------------------------------------------
# 3. the dance: one field, from ecstatic dance near the musicians (north-east) through contact
#    improvisation (north-west / west) into slow closeness (canopy, cuddle corner) and stillness
#    under the net. Recorded dance movement (CMU motion capture), each person caught mid-movement
#    (motion blur); people drift counter-clockwise; hands find hands across groups.
# ---------------------------------------------------------------------------
UNDRESS[0] = 0.15
import mocap as MC  # noqa: E402
SC.frame_set(10)
DANCERS = []
FR_CACHE = {}


def frames_of(clip, k=4):
    if clip not in FR_CACHE:
        FR_CACHE[clip] = MC.best_frames(clip, k)
    return FR_CACHE[clip]


def blur_move(r, mv, face):
    """Key the rig's own travel between the two posed moments (for motion blur)."""
    d = Rz(face + 90) @ Vector((mv.x, mv.y, 0.0))
    loc = r.location.copy()
    r.keyframe_insert('location', frame=10)
    r.location = loc - d
    r.keyframe_insert('location', frame=9)
    r.location = loc


CLOTH = os.environ.get('CROWD_CLOTH', '0') == '1'
FLOWY = ('skirt', 'dress', 'kimono', 'lungi', 'robe', 'cape', 'sarong', 'chiffon', 'goddess', 'halter', 'wrap', 'shawl')


def cloth_pass(r, clip, f, face):
    """CROWD_CLOTH=1: the person moves through the last second of their recorded motion and their flowing
    garments are simulated as cloth (humans/clothsim.py: pinned at waist / shoulders, relative wind, soft
    air), then baked. Returns True if simulated (the lead-in replaces the motion-blur keys)."""
    if not CLOTH:
        return False
    import clothsim as CS
    garments = [c for c in r.children if c.type == 'MESH' and not c.name.endswith('.body') and
                (any(k in c.name.lower() for k in FLOWY) or
                 (c.active_material and c.active_material.name.lower().startswith(('chiffon', 'lungi'))))]
    if not garments:
        return False
    try:
        CS.simulate(r, body_of(r), garments, clip, f, face, tuple(r.location))
        bpy.context.scene.frame_set(10)
        return True
    except Exception as e:                              # never lose a long crowd build over one skirt
        print('cloth sim failed for', r.name, e, flush=True)
        return False


def dancer(clip, i, x, y, face, kind='flow', z0=0.0, lean_deg=0.0, **kw):
    fs = frames_of(clip)
    f = fs[i % len(fs)]
    r = new_person(kind, **kw)
    r['pose'] = '%s@%d' % (clip, f)
    mv = MC.key_motion(r, clip, f)
    stand(r, x, y, face)
    if lean_deg:
        lean(r, lean_deg)
    drop(r, z0)
    if not cloth_pass(r, clip, f, face):
        blur_move(r, mv, face)
    DANCERS.append(r)
    return r


SWAY = ['60_04', '61_04', '60_05', '61_05', '60_06', '61_06', '60_07', '61_07', '60_08', '61_08']
WALK = ['35_01', '35_02', '16_15', '16_16']


def moving(clips, x, y, face, kind='flow', z0=0.0, seed=0, **kw):
    """Someone upright in recorded motion at an ordinary moment (swaying, stepping, walking)."""
    rg = random.Random(seed or int(x * 1000 + y * 77))
    clip_ = rg.choice(clips)
    _, n = MC.joints(clip_, 0)
    f = rg.randrange(int(n * 0.15), int(n * 0.85))
    r = new_person(kind, **kw)
    r['pose'] = '%s@%d' % (clip_, f)
    mv = MC.key_motion(r, clip_, f)
    stand(r, x, y, face)
    drop(r, z0)
    if not cloth_pass(r, clip_, f, face):
        blur_move(r, mv, face)
    return r


def swayer(x, y, face, kind='flow', z0=0.0, **kw):
    return moving(SWAY, x, y, face, kind, z0, **kw)


def walker(x, y, face, kind='flow', z0=0.0, **kw):
    return moving(WALK, x, y, face, kind, z0, **kw)


def hand_pos(r, side):
    return bone_w(r, 'wrist.' + side) + (bone_w(r, 'wrist.' + side) - bone_w(r, 'lowerarm02.' + side)).normalized() * 0.07


def link_hands(ra, rb, maxd=0.45):
    """If a hand of A and a hand of B are near, let them meet (holding hands)."""
    best = None
    for sa in 'LR':
        for sb in 'LR':
            d = (hand_pos(ra, sa) - hand_pos(rb, sb)).length
            if best is None or d < best[0]:
                best = (d, sa, sb)
    if best and best[0] < maxd:
        d, sa, sb = best
        pa, pb = bone_w(ra, 'wrist.' + sa), bone_w(rb, 'wrist.' + sb)
        m = (pa + pb) / 2
        u = (pb - pa).normalized() if (pb - pa).length > 1e-4 else Vector((1, 0, 0))
        ta, tb = m - u * 0.075, m + u * 0.075
        if (ta - bone_w(ra, 'upperarm01.' + sa)).length > 0.5 or (tb - bone_w(rb, 'upperarm01.' + sb)).length > 0.5:
            return False                                   # too far apart to hold hands comfortably
        reach_to(ra, sa, ta)
        reach_to(rb, sb, tb)
        return True
    return False


def duet(a, b, f, x, y, face, kinds=('flow', 'flow'), z0=0.0):
    ra, rb = new_person(kinds[0]), new_person(kinds[1])
    ra['pose'], rb['pose'] = '%s@%d' % (a, f), '%s@%d' % (b, f)
    off, ma, mb = MC.key_duet(ra, rb, a, b, f)
    o = Rz(face + 90) @ Vector((off.x, off.y, 0))
    stand(ra, x - o.x / 2, y - o.y / 2, face)
    stand(rb, x + o.x / 2, y + o.y / 2, face)
    drop(ra, z0)
    drop(rb, z0)
    blur_move(ra, ma, face)
    blur_move(rb, mb, face)
    link_hands(ra, rb, 0.35)
    DANCERS.extend((ra, rb))
    return ra, rb


def drift(a):
    """Facing for someone drifting counter-clockwise at polar angle a (+ a little of their own)."""
    return a + 90 + random.Random(int(a * 7)).uniform(-50, 50)


SOLO = ['05_02', '05_03', '05_04', '05_06', '05_08', '05_11', '05_12', '05_18', '49_09', '49_12', '49_14',
        '49_22', '55_01', '55_02', '111_05', '113_04', '141_12', '49_18', '05_13', '05_16']

import json as _json  # noqa: E402
PHOTO = _json.load(open(os.path.join(HUM, 'photo_poses.json')))
if os.path.exists(os.path.join(HUM, 'photo_poses_zegg.json')):      # poses from ZEGG's own festival photos
    PHOTO += _json.load(open(os.path.join(HUM, 'photo_poses_zegg.json')))
PH_LOW = [i for i, p in enumerate(PHOTO) if p['kind'] == 'low']
PH_MID = [i for i, p in enumerate(PHOTO) if p['kind'] == 'mid']
PH_UP = [i for i, p in enumerate(PHOTO) if p['kind'] == 'upright']


def photo_person(idx, x, y, face, z0=0.0, kind='flow', on=()):
    """Someone in a pose reconstructed from a real photo of a jam / dance / cuddle puddle."""
    r = new_person(kind)
    r['pose'] = 'photo:%s#%d' % (PHOTO[idx]['photo'][:8], PHOTO[idx]['k'])
    MC.apply_joints(r, MC.photo_joints(PHOTO[idx]['world']))
    stand(r, x, y, face)
    drop(r, z0, on=on)
    return r


def photo_pair(photo, x, y, face, z0=0.0):
    """Two or three people exactly as they were together in one photo (relative placement from the image)."""
    ps = [p for p in PHOTO if p['photo'] == photo]
    s0 = sum(p['torso_m'] / max(p['torso_px'], 1) for p in ps) / len(ps)
    cx = sum(p['hip_px'][0] for p in ps) / len(ps)
    out = []
    for p in ps:
        idx = PHOTO.index(p)
        off = Rz(face + 90) @ Vector(((p['hip_px'][0] - cx) * s0, 0, 0))
        r = new_person()
        r['pose'] = 'photo:%s#%d' % (p['photo'][:8], p['k'])
        MC.apply_joints(r, MC.photo_joints(p['world']), keep_yaw=True)   # keep the photo's own facing
        stand(r, x + off.x, y + off.y, face)
        drop(r, z0, on=tuple(out))
        out.append(r)
    return out


def floor_body(x, y, head, z0=0.0, on=(), kind='flow'):
    rg_ = random.Random(int(x * 100 + y * 37))
    if rg_.random() < 0.75:                  # most people on the floor: real poses from photos
        return photo_person(rg_.choice(PH_LOW + PH_MID), x, y, head, z0, kind, on)
    """Someone on the floor: rolling, curled, spread out, rising (static library poses, laid down)."""
    choice = random.Random(int(x * 100 + y * 37)).choice(
        [('callharvey3d_sittingnatural', 'side_r'), ('callharvey3d_sittingnatural', 'side_l'),
         ('elvs_yoga_star_pose_1', 'back'), ('standing02', 'back'), ('elvs_yoga_cobra_pose_1', 'front'),
         ('callharvey3d_sittingfloor2', 'side_r'), ('sohh_posing4', 'back')])
    return lying(choice[0], x, y, head, choice[1], z0, on=on, kind=kind)


def roll_duet(x, y, head, z0=0.0, style=0):
    """Two people rolling on the floor with each other."""
    if style == 0:                           # one rolling over the other
        a = lying('callharvey3d_sittingnatural', x, y, head, 'side_l', z0)
        b = lying('elvs_yoga_star_pose_1', x + 0.05, y + 0.05, head + 80, 'back', z0, on=(a,))
    elif style == 1:                         # back to back
        fdir = Rz(head - 90) @ Vector((1, 0, 0))
        a = lying('callharvey3d_sittingnatural', x - fdir.x * 0.2, y - fdir.y * 0.2, head, 'side_l', z0)
        b = lying('callharvey3d_sittingnatural', x + fdir.x * 0.2, y + fdir.y * 0.2, head + 10, 'side_r', z0)
    else:                                    # lying across, head on the other's belly, a hand on the chest
        a = lying('standing02', x, y, head, 'back', z0)
        b = head_on('elvs_yoga_star_pose_1', a, 'spine04', head + 100, 'back', z0)
        reach_to(b, 'R', bone_w(a, 'spine02', (0, -0.12, 0)))
    return a, b


def group(cx, cy, n_up, n_floor, spread, seed, clips=None, kinds=None, duet_clip=None):
    """A contact group: standing dancers turned towards each other, people on the floor among them,
    hands and weight connecting them. Returns the members."""
    rg = random.Random(seed)
    members, floor = [], []
    pts = []
    for i in range(n_up + n_floor):          # organic blob: golden-angle spiral with jitter
        rr = spread * math.sqrt((i + 0.5) / (n_up + n_floor))
        a = i * 137.5 + rg.uniform(-20, 20)
        pts.append(Vector((cx, cy, 0)) + Rz(a) @ Vector((rr, 0, 0)))
    rg.shuffle(pts)
    for i in range(n_floor):
        p = pts.pop()
        floor.append(floor_body(p.x, p.y, rg.uniform(0, 360), on=tuple(floor)))
    if duet_clip:
        p = pts.pop()
        pts.pop()
        a_, b_, k_ = duet_clip
        members += list(duet(a_, b_, MC.contact_frames(a_, b_, 3)[k_], p.x, p.y, rg.uniform(0, 360)))
    for i, p in enumerate(pts[:n_up - (2 if duet_clip else 0)]):
        toward = math.degrees(math.atan2(cy - p.y, cx - p.x))
        clip_ = (clips or SOLO)[rg.randrange(len(clips or SOLO))]
        kd = kinds[i % len(kinds)] if kinds else 'flow'
        if rg.random() < 0.4:                # someone bent over / kneeling / leaning, from a real photo
            members.append(photo_person(rg.choice(PH_MID + PH_UP), p.x, p.y, toward + rg.uniform(-45, 45), kind=kd))
        else:
            members.append(dancer(clip_, rg.randrange(4), p.x, p.y, toward + rg.uniform(-45, 45), kind=kd))
    # weight and touch: a hand on a neighbour's back / shoulder, or reaching down to someone on the floor
    for m in members:
        near = sorted((o for o in members + floor if o is not m), key=lambda o: (o.location - m.location).length)
        for o in near[:1]:
            dist = (o.location - m.location).length
            if o in floor and dist < 0.9:
                reach_to(m, rg.choice('LR'), bone_w(o, 'spine03', (0, -0.1, 0)))
            elif dist < 0.75 and rg.random() < 0.6:
                reach_to(m, rg.choice('LR'), on_back(o, 'spine02', rg.uniform(-0.1, 0.1), 0.12))
    return members + floor


# -- one large flowing group near the musicians (north-east): ecstatic, connected --
big = group(*pol(6.3, 55).xy, 8, 1, 2.2, 11, duet_clip=('60_01', '61_01', 0),
            kinds=['flow', 'crazy', 'naked', 'flow', 'lungi', 'undies', 'flow', 'crazy'])
# a couple dancing at the east side of it
p = pol(6.8, 5)
duet('60_03', '61_03', MC.contact_frames('60_03', '61_03', 3)[1], p.x, p.y, drift(5))
# walking hand in hand through the room, swinging arms
p = pol(4.6, 95)
duet('22_08', '23_08', MC.contact_frames('22_08', '23_08', 1)[0], p.x, p.y, 95 + 90)
print('big group done', N[0])

# -- a circle holding hands, leaning out, carrying each other's weight together --
def hand_circle(cx, cy, n, radius, clips, lean_out=9, seed=0):
    rg = random.Random(seed)
    ring = []
    for i in range(n):
        a = 360 * i / n + rg.uniform(-8, 8)
        p = Vector((cx, cy, 0)) + Rz(a) @ Vector((radius * rg.uniform(0.9, 1.1), 0, 0))
        r = dancer(clips[i % len(clips)], rg.randrange(4), p.x, p.y, a + 180 + rg.uniform(-15, 15),
                   lean_deg=-lean_out)
        ring.append(r)
    for i in range(n):
        a_, b_ = ring[i], ring[(i + 1) % n]
        pa, pb = bone_w(a_, 'wrist.L'), bone_w(b_, 'wrist.R')
        m = (pa + pb) / 2
        u = (pb - pa).normalized()
        reach_to(a_, 'L', m - u * 0.075)
        reach_to(b_, 'R', m + u * 0.075)
    return ring


hand_circle(*pol(7.7, 95).xy, 5, 0.85, ['49_10', '05_12', '49_16', '05_18', '55_02', '49_22'], seed=5)

# -- weight structure: one low on all fours, another propped on one hand with a foot on their back,
#    beside them two leaning into each other and a third leaning into both --
c = pol(7.9, 205)
s1 = standing('drednicolson_prostrate', c.x, c.y, 115, z0=0.0)
s2 = new_person()
pose(s2, 'elvs_pushups_1')
stand(s2, c.x + 0.9, c.y + 0.5, 200)
drop(s2, 0.0)
foot_to(s2, 'R', bone_w(s1, 'spine03', (0, 0.12, 0)))

# -- contact improvisation: quartet, quintet, sextet, duets turning into trios, rolling on the floor --
UNDRESS[0] = 0.35
p = pol(6.9, 150)
duet('18_03', '19_03', 519, p.x, p.y, 150 + 90)                          # counterbalance, hands held
group(*pol(6.5, 186).xy, 2, 2, 1.1, 23)                                 # a group half on the floor
# a trio: one on hands and knees, one lying across their back, a third reaching in
c = pol(4.9, 140)
t1 = standing('drednicolson_prostrate', c.x, c.y, 250)
t2 = new_person()
pose(t2, 'elvs_yoga_star_pose_1')
lie(t2, c.x, c.y, 340, 'back')
drop(t2, 0.0, on=(t1,))
t3 = dancer('49_12', 1, c.x + 0.7, c.y - 0.45, 120)
reach_to(t3, 'R', bone_w(t2, 'wrist.L'))
# pairs and trios exactly as photographed at contact jams
from collections import Counter as _C  # noqa: E402
_multi = [ph for ph, n in _C(p['photo'] for p in PHOTO).items() if n > 1]
for ph, (rr, ang) in zip(_multi, ((7.0, 128), (5.6, 172), (8.0, 112), (4.9, 208), (7.9, 188))):
    photo_pair(ph, *pol(rr, ang).xy, ang + 90)
# rolling with each other on the floor
roll_duet(*pol(8.0, 200).xy, 110, 0.0, style=0)
roll_duet(*pol(5.2, 200).xy, 20, 0.0, style=1)
print('contact done', N[0])

# -- dancing melting into cuddling (and back): standing and kissing -> sinking down -> lying together --
UNDRESS[0] = 0.4
p = pol(4.5, 300)
embrace_standing(p.x, p.y, 20, kiss=True)
p = pol(4.3, 272)
duet('22_03', '23_03', 110, p.x, p.y, 272 + 90, z0=0.0)                 # sinking to the knees together
# a standing trio making out, arms around each other
c = pol(5.0, 330)
tri = []
for i, pn in enumerate(('standing02', 'standing05', 'standing01')):
    q = c + Rz(120 * i + 30) @ Vector((0.21, 0, 0))
    tri.append(swayer(q.x, q.y, 120 * i + 30 + 180))
for i in range(3):
    reach_to(tri[i], 'L', on_back(tri[(i + 1) % 3], 'spine03', 0.0, 0.12))
    reach_to(tri[i], 'R', on_back(tri[(i + 2) % 3], 'spine01', 0.0, 0.1))
# getting up again from a cuddle: one already dancing, one rising, one still lying
c = pol(2.6, 5)                                  # on the east end of the mattress field
lying('standing02', c.x, c.y, 200, 'back', MF_Z)
standing('wolgade_sit_on_ground_01', c.x + 0.5, c.y - 0.45, 250, z0=MF_Z)
dancer('49_12', 2, *(c + Vector((1.0, 0.9, 0))).xy, 230)
UNDRESS[0] = 0.15

# -- dancing at the edge of the mattress field, reaching down to the people lying there --
for i, a in enumerate((150,)):
    p = pol(4.05, a)
    dancer(['49_22', '05_12', '49_14'][i], i, p.x, p.y, a + 180 + (i - 1) * 30, kind='flow')

# hands find hands: neighbours from different groups link up
DANCERS_ = [d for d in DANCERS if d.get('pose')]
rnd_ = random.Random(27)
for i, a_ in enumerate(DANCERS_):
    for b_ in DANCERS_[i + 1:]:
        if (a_.location - b_.location).length < 1.25 and rnd_.random() < 0.7:
            link_hands(a_, b_, 0.5)
print('dance done', N[0])

# ---------------------------------------------------------------------------
# 5. intimate zone under the linen canopy (south-west) (6)
UNDRESS[0] = 0.7
# ---------------------------------------------------------------------------
iz = P.INT_CANOPY[0]
# three mattresses side by side, long sides radial (params.mat_group), everyone blindfolded ('Blind'):
# two sitting face to face, exploring each other's faces with their hands; a couple spooning; one lying on
# their back, the other sitting beside them with a hand on their chest
m0, m1, m2 = [Vector((x, y, 0)) for x, y in P.mat_group('intimate')[0]]
rad_ = Rz(iz) @ Vector((1, 0, 0))                      # along the mattresses (towards the wall)
tan_ = Rz(iz + 90) @ Vector((1, 0, 0))                 # across them
MZ = 0.18
a0 = standing('callharvey3d_lotus', *(m0 + rad_ * 0.42).xy, iz + 180, z0=MZ)
b0 = standing('callharvey3d_lotus', *(m0 - rad_ * 0.42).xy, iz, z0=MZ)
reach_to(a0, 'R', bone_w(b0, 'head', (0.07, -0.08, 0.02)))
reach_to(b0, 'L', bone_w(a0, 'head', (-0.07, -0.08, 0.02)))
reach_to(b0, 'R', bone_w(a0, 'wrist.L'))


def centre_on(rigs, target):
    """move people (and their hand / foot targets) so their bodies' centre lies over target (xy)"""
    vs = [v for r in rigs for v in eval_verts(r)]
    c = sum(vs, Vector()) / len(vs)
    d = Vector((target.x - c.x, target.y - c.y, 0))
    for r in rigs:
        r.location += d
        for o in bpy.data.objects:
            if o.name.startswith(('ik_%s_' % r.name, 'ikf_%s_' % r.name)):
                o.location += d
    bpy.context.view_layer.update()


s1, s2 = spoon(m1.x, m1.y, iz, MZ)
centre_on([s1, s2], m1)
l2 = lying('standing02', m2.x, m2.y, iz, 'back', MZ)
centre_on([l2], m2 + tan_ * 0.25)
k2 = standing('wolgade_sit_on_ground_01', *(m2 - tan_ * 0.45 - rad_ * 0.1).xy, iz + 90, z0=MZ)
reach_to(k2, 'R', bone_w(l2, 'spine03', (0, -0.12, 0)))
BLIND = [a0, b0, s1, s2, l2, k2]

# ---------------------------------------------------------------------------
# 6. cuddle puddle (south-east) (5)
# ---------------------------------------------------------------------------
cz = 310
c0 = Vector((*[sum(v) / 4 for v in zip(*P.mat_group('cuddle')[0])], 0))    # centre of the 2 x 2 mattresses
k1 = lying('standing02', c0.x, c0.y, cz + 100, 'back', 0.18)
head_on('callharvey3d_sittingnatural', k1, 'spine03', cz - 30, 'side_r', 0.18)
k3 = lying('callharvey3d_sittingnatural', *(c0 + Rz(cz) @ Vector((0.0, -0.45, 0))).xy, cz + 100, 'side_l', 0.18)
reach_to(k3, 'R', bone_w(k1, 'spine02', (0, -0.1, 0)))
print('zones done', N[0])

# ---------------------------------------------------------------------------
# 7. bar, musician, organisers, stair seating steps, window seats (10)
UNDRESS[0] = 0.1
# ---------------------------------------------------------------------------
def FP(k, n, t, z=0.0):
    a = P.slot_center(k)
    return Vector((n * math.cos(rad(a)) - t * math.sin(rad(a)), n * math.sin(rad(a)) + t * math.cos(rad(a)), z))


ab = P.slot_center(P.BAR_FACE)
bc = FP(P.BAR_FACE, P.R_IN - 2.2, 1.0)
x1 = swayer(bc.x, bc.y, ab + 150, kind='crazy')
fb = Rz(ab + 150) @ Vector((1, 0, 0))
x2 = swayer(bc.x - fb.x * 0.2, bc.y - fb.y * 0.2, ab + 150)                     # holding them from behind
reach_to(x2, 'L', bone_w(x1, 'spine04', (0.1, -0.12, 0)))
reach_to(x2, 'R', bone_w(x1, 'spine04', (-0.1, -0.12, 0)))
mc = FP(P.BAR_FACE, P.R_IN - 3.0, -2.4)
mu = standing('callharvey3d_lotus', mc.x, mc.y, ab + 180, z0=0.0, sex=1.0, years=46)
hp = Vector((mc.x + 0.3, mc.y - 0.3, 0.27))
reach_to(mu, 'L', hp + Vector((0.08, 0.05, 0)))
reach_to(mu, 'R', hp + Vector((-0.08, -0.05, 0)))
dc = FP(P.BAR_FACE, P.R_IN - 2.9, -3.3)
dr = standing('callharvey3d_sittinglegscrossed', dc.x, dc.y, ab + 160, z0=0.0)
drum_c = bone_w(dr, 'spine03') + front(dr) * 0.3 + Vector((0, 0, -0.15))
reach_to(dr, 'L', drum_c + Rz(ab + 160) @ Vector((0.0, 0.2, 0.05)))
reach_to(dr, 'R', drum_c + Rz(ab + 160) @ Vector((0.0, -0.15, 0.1)))
DRUM = (drum_c, ab + 160)
# organisers in kimonos with clipboards
CLIP = []
for i, (pos, face, z0) in enumerate(((FP(P.ENTRY_SLOT, P.R_IN - 1.6, 1.1), P.slot_center(P.ENTRY_SLOT) + 200, 0.0),
                                     (pol(5.0, 284), 284 + 180 - 30, P.FFL_UF))):
    o = walker(pos.x, pos.y, face, kind='organiser', z0=z0)
    cp = bone_w(o, 'spine02') + front(o) * 0.3 + Vector((0, 0, -0.1))
    reach_to(o, 'L', cp + Rz(face) @ Vector((0, 0.1, 0)))
    reach_to(o, 'R', cp + Rz(face) @ Vector((0, -0.1, 0.02)))
    CLIP.append((cp, face))
# stair seating steps
ks = P.STAIR_SLOT
for i, (tr, dn) in enumerate(()):  # (no one on the stair tonight)
    sp = FP(ks, P.R_IN - P.STAIR_FLIGHT_W_T + dn, P.STAIR_T0 + (tr - 0.5) * P.STAIR_GOING_T)
    standing('callharvey3d_sittingdefault', sp.x, sp.y, P.slot_center(ks) + 180, z0=tr * P.STAIR_RISE - 0.45)
# window seats
for i, a in enumerate(()):
    p = pol(P.R_IN - 0.45, a)
    standing(['anrico_sitting02', 'callharvey3d_sittinglegscrossed', 'anrico_sitting04'][i], p.x, p.y, a + 180,
             z0=0.1)
print('bar/stair done', N[0])

# ---------------------------------------------------------------------------
# 8. walkway (upper floor) (5)
# ---------------------------------------------------------------------------
UF = P.FFL_UF
pad = P.RING_BEAM_TOP + P.PAD_T
for i, a in enumerate((255, 330)):
    p = pol(4.12, a)
    standing(['callharvey3d_lotus', 'wolgade_sit_on_ground_01'][i], p.x, p.y, a + 180, z0=pad)   # on the pad
c = pol(4.75, 20)
u1 = swayer(*(c + Rz(20) @ Vector((0, 0.3, 0))).xy, 200, z0=UF, kind='crazy')
u2 = swayer(*(c - Rz(20) @ Vector((0, 0.3, 0))).xy, 200, z0=UF)
reach_to(u1, 'R', on_back(u2, 'spine03', 0.12, 0.12))
dancer('05_12', 0, *pol(5.0, 210).xy, 300, z0=UF)

# ---------------------------------------------------------------------------
# 9. rooms upstairs (open / half-open doors) (9)
UNDRESS[0] = 0.7
# ---------------------------------------------------------------------------
def room_pt(k, x, y):
    return Rz(P.slot_center(k)) @ Vector((x, y, 0))


NEST = UF + 0.47
p = room_pt(3, 8.45, 0.0)
spoon(p.x, p.y, P.slot_center(3), NEST)
k = 5
p = room_pt(k, 8.45, 0.0)
v1 = lying('standing02', p.x, p.y, P.slot_center(k) + 90, 'back', NEST)
head_on('callharvey3d_sittingnatural', v1, 'spine03', P.slot_center(k), 'side_r', NEST)
p = room_pt(7, 8.45, 0.0)
face_to_face(p.x, p.y, P.slot_center(7) + 90, NEST)
print('rooms done', N[0])

# ---------------------------------------------------------------------------
# 9b. roof terrace: the music only softly from below - people talk, stroll, hold hands, cuddle on the
#     daybeds, make out standing (couples and a trio), hug in groups
# ---------------------------------------------------------------------------
UNDRESS[0] = 0.3
TZ = P.TERRACE_Z
# a group talking (the one place where people chat) - turned towards each other, swaying
c = pol(7.3, 70, 0)
for i in range(4):
    q = c + Rz(90 * i + 20) @ Vector((0.55, 0, 0))
    swayer(q.x, q.y, 90 * i + 20 + 180, z0=TZ)
# strolling hand in hand along the terrace
p = pol(7.0, 25)
duet('22_08', '23_08', MC.contact_frames('22_08', '23_08', 1)[0], p.x, p.y, 25 + 90, z0=TZ)
p = pol(7.2, 115)
walker(p.x, p.y, 115 + 90, z0=TZ)
# making out standing: a couple, and a trio
p = pol(6.7, 165)
embrace_standing(p.x, p.y, 40, z0=TZ, kiss=True)
c = pol(7.4, 188)
tri2 = []
for i in range(3):
    q = c + Rz(120 * i + 10) @ Vector((0.21, 0, 0))
    tri2.append(swayer(q.x, q.y, 120 * i + 10 + 180, z0=TZ))
for i in range(3):
    reach_to(tri2[i], 'L', on_back(tri2[(i + 1) % 3], 'spine03', 0.0, 0.12))
    reach_to(tri2[i], 'R', on_back(tri2[(i + 2) % 3], 'spine01', 0.0, 0.1))
# a group hug of four
c = pol(7.0, 350)
hug = []
for i in range(4):
    q = c + Rz(90 * i) @ Vector((0.3, 0, 0))
    hug.append(swayer(q.x, q.y, 90 * i + 180, z0=TZ))
for i in range(4):
    reach_to(hug[i], 'L', on_back(hug[(i + 1) % 4], 'spine02', 0.0, 0.12))
    reach_to(hug[i], 'R', on_back(hug[(i + 3) % 4], 'spine02', 0.0, 0.12))
# cuddling on the daybeds (south faces): couples, and three together on one
DB = TZ + 0.51
for j, (k, t) in enumerate(((3, P.DAYBED_T[0]), (4, P.DAYBED_T[1]), (5, P.DAYBED_T[0]))):
    cpt = FP(k, 8.15, t)
    if j == 1:
        a_ = lying('standing02', cpt.x, cpt.y, P.slot_center(k), 'back', DB)
        head_on('callharvey3d_sittingnatural', a_, 'spine03', P.slot_center(k) + 100, 'side_r', DB)
        head_on('elvs_yoga_star_pose_1', a_, 'upperleg02.R', P.slot_center(k) - 60, 'back', DB)
    elif j == 0:
        face_to_face(cpt.x, cpt.y, P.slot_center(k) + 90, DB)
    else:
        spoon(cpt.x, cpt.y, P.slot_center(k) + 90, DB)
# on the floor mattresses of the shady side: a couple spooning, three lying together
FM = TZ + 0.22
p = FP(7.5, 8.35, 0.0)
spoon(p.x, p.y, P.slot_center(7.5) + 90, FM)
p = FP(6.5, 8.35, 0.0)
b_ = lying('standing02', p.x, p.y, P.slot_center(6.5) + 90, 'back', FM)
head_on('callharvey3d_sittingnatural', b_, 'spine03', P.slot_center(6.5) + 10, 'side_r', FM)
head_on('elvs_yoga_star_pose_1', b_, 'upperleg02.R', P.slot_center(6.5) - 170, 'back', FM)
# someone on the bench ring, leaning back against the dome, looking at the sky
p = pol(P.DOME_RING_OUT + 0.3, 215)
standing('callharvey3d_sittingfloorstretch2', p.x, p.y, 215, z0=TZ + 0.2)
print('roof done', N[0])

# ---------------------------------------------------------------------------
# 10. physics: everyone lying, sitting or resting on others settles under gravity and contact
#     (active ragdolls, see ragdoll.py); dancers keep their recorded movement
# ---------------------------------------------------------------------------
import ragdoll as RD  # noqa: E402

for r_ in BLIND:
    try:
        blindfold(r_, blindfold_mat())
    except Exception:                                   # never lose a long crowd build over an accessory
        import traceback
        traceback.print_exc()
print('blindfolds', len(BLIND), flush=True)

separate_people([o for o in CROWD.objects if o.type == 'ARMATURE'])

# checkpoint before the (slow) physics: the crowd as placed
EVC.hide_render = True
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(MODEL, 'tempel_event.blend'), compress=True, copy=True)
print('CHECKPOINT saved', flush=True)
EVC.hide_render = False
PHYSICS = os.environ.get('CROWD_PHYSICS', '0') == '1'


def _keyed(r):
    return bool(r.animation_data and r.animation_data.action)


STILL = [o for o in CROWD.objects if o.type == 'ARMATURE' and not _keyed(o)]
# small clusters (at most 5 people) of people close to each other - bigger groups are too slow to simulate
groups_, seen = [], set()
for r in STILL:
    if r.name in seen:
        continue
    g = [r]
    seen.add(r.name)
    near = sorted((b for b in STILL if b.name not in seen),
                  key=lambda b: (b.matrix_world.translation - r.matrix_world.translation).length)
    for b in near:
        if len(g) >= 5 or (b.matrix_world.translation - r.matrix_world.translation).length > 1.8:
            break
        g.append(b)
        seen.add(b.name)
    groups_.append(g)
SURF = [o for o in _static_objects() if o.type == 'MESH' and CROWD not in o.users_collection]


def _near(ob, pts, d=2.5):
    bb = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    lo = Vector((min(v.x for v in bb), min(v.y for v in bb), min(v.z for v in bb)))
    hi = Vector((max(v.x for v in bb), max(v.y for v in bb), max(v.z for v in bb)))
    return any(lo.x - d < p.x < hi.x + d and lo.y - d < p.y < hi.y + d and lo.z - d < p.z < hi.z + d for p in pts)


for gi, g in enumerate(groups_ if PHYSICS else []):
    pts = [r.matrix_world.translation for r in g]
    cols = [o for o in SURF if _near(o, pts) and len(o.data.polygons) < 60000]
    # dancers standing right next to the group are obstacles too (they stay as they are)
    import time as _t
    t0 = _t.time()
    RD.settle([(r, body_of(r), False) for r in g], cols, frames=30)
    print('settled group', gi + 1, '/', len(groups_), len(g), 'people', len(cols), 'surfaces',
          round(_t.time() - t0, 1), 's', flush=True)

# clipboards for the organisers
import bmesh  # noqa: E402
M_CB = bpy.data.materials.get('wood_dark_walnut')
for i, (cp, face) in enumerate(CLIP):
    bm = bmesh.new()
    M = Matrix.Translation(cp) @ Matrix.Rotation(rad(face + 90), 4, 'Z') @ Matrix.Rotation(rad(-50), 4, 'X') @ \
        Matrix.Diagonal((0.23, 0.012, 0.31, 1))
    bmesh.ops.create_cube(bm, size=1.0, matrix=M)
    me = bpy.data.meshes.new('clipboard_%d' % i)
    bm.to_mesh(me)
    ob = bpy.data.objects.new('clipboard_%d' % i, me)
    ob.data.materials.append(M_CB)
    CROWD.objects.link(ob)

# frame drum
bm = bmesh.new()
M = Matrix.Translation(DRUM[0]) @ Matrix.Rotation(rad(DRUM[1] + 90), 4, 'Z') @ Matrix.Rotation(rad(70), 4, 'X')
bmesh.ops.create_cone(bm, cap_ends=True, segments=48, radius1=0.24, radius2=0.24, depth=0.07, matrix=M)
me = bpy.data.meshes.new('frame_drum')
bm.to_mesh(me)
ob = bpy.data.objects.new('frame_drum', me)
ob.data.materials.append(bpy.data.materials.get('shoji_linen'))
CROWD.objects.link(ob)
# event layer hidden by default, as in tempel.blend (render.py switches it on for the event views)
EVC.hide_render = True
EVC.hide_viewport = True
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(MODEL, 'tempel_event.blend'), compress=True)
print('CROWD', N[0], 'people saved')
