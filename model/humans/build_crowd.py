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
        'meadow', 'forest', 'path', 'ivy', 'ev_speaker', 'hall_zafu', 'hall_round')


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
        if min(v.z for v in bb) > 8.0 or min(math.hypot(v.x, v.y) for v in bb) > 10.5:
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
        w = {'flow': 0.30, 'mix': 0.25, 'lungi': 0.12 if sex < 0.5 else 0.07, 'crazy': 0.08,
             'undress': 0.10 + 0.35 * UNDRESS[0]}
        u = rnd.random() * sum(w.values())
        for k_, v_ in w.items():
            if u < v_:
                kind = k_
                break
            u -= v_
        if kind == 'undress':
            kind = 'lingerie' if (sex < 0.5 and rnd.random() < 0.5) else 'undies'
            if sex < 0.5 and UNDRESS[0] <= 0.2 and rnd.random() < 0.6:
                kind = 'topless'                 # dancing topless (dance areas)
    if outfit is None:
        if kind == 'mix':                    # own combination of a bottom, maybe a top, maybe a kimono over it
            bottom = rnd.choice(BOTTOMS)
            top = rnd.choice(TOPS_F if sex < 0.5 else TOPS_M)
            outfit = tuple(x for x in (bottom, top, 'mindfront_kimono' if rnd.random() < 0.25 else None) if x)
            kind = 'flow'
        if kind == 'lungi':                  # lungis / sarongs tied in different ways
            outfit = tuple(x for x in rnd.choice(LUNGI_F if sex < 0.5 else LUNGI_M) if x)
    if outfit is None:
        pool = {'crazy': CRAZY, 'organiser': [KIMONO], 'naked': [()],
                'undies': UNDIES_F if sex < 0.5 else UNDIES_M, 'lingerie': LINGERIE_F,
                'topless': TOPLESS_F}.get(kind)
        if pool is None:
            pool = FLOW_F if (sex < 0.5 or rnd.random() < 0.08) else FLOW_M
        outfit = rnd.choice(pool)
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
    dress_up(rig, fab)
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


def reach_to(rig, side, target, chain=4):
    """Put the hand (wrist bone) of `side` ('L'/'R') on a world point, IK over the arm."""
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


def lying(pname, x, y, head, how, z0, on=(), kind='flow', tilt=0.0, **kw):
    r = new_person(kind, **kw)
    pose(r, pname)
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
    a = standing(a_pose, *(c - f * d + s * l).xy, face, kinds[0], z0)
    b = standing(b_pose, *(c + f * d - s * l).xy, face + 180, kinds[1], z0)
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
    pose(r, pname)
    lie(r, 0, 0, head_away + 180, how)
    bpy.context.view_layer.update()
    hd = bone_w(r, 'head')
    r.location.x += p.x - hd.x + d.x * 0.02
    r.location.y += p.y - hd.y + d.y * 0.02
    drop(r, z0, on=(partner,) + tuple(extra_on))
    return r


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
b1 = lying('sohh_posing4', -2.2, 1.5, 110, 'back', MF_Z)                             # hand behind head, looking up
b2 = lying('elvs_yoga_cobra_pose_1', -1.6, 1.95, 300, 'front', MF_Z)
reach_to(b2, 'L', bone_w(b1, 'spine02', (0, -0.12, 0)))
standing('callharvey3d_sittingfloorstretch2', 2.6, -0.4, 170, z0=MF_Z)              # leaning back, looking up
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
standing('callharvey3d_lotus', -2.4, -1.0, 20, z0=net_z(-2.4, -1.0))
lying('elvs_yoga_cobra_pose_1', -0.2, 2.5, 90, 'front', net_z(-0.2, 2.5))            # looking down through the mesh
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
    blur_move(r, mv, face)
    DANCERS.append(r)
    return r


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
        reach_to(ra, sa, m - u * 0.075)
        reach_to(rb, sb, m + u * 0.075)
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

def floor_body(x, y, head, z0=0.0, on=(), kind='flow'):
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
        members.append(dancer(clip_, rg.randrange(4), p.x, p.y, toward + rg.uniform(-45, 45),
                              kind=(kinds[i % len(kinds)] if kinds else 'flow')))
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
big = group(*pol(6.3, 55).xy, 9, 2, 2.4, 11, duet_clip=('60_01', '61_01', 0),
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


hand_circle(*pol(7.7, 92).xy, 6, 0.95, ['49_10', '05_12', '49_16', '05_18', '55_02', '49_22'], seed=5)

# -- weight structure: one low on all fours, another propped on one hand with a foot on their back,
#    beside them two leaning into each other and a third leaning into both --
c = pol(7.9, 205)
s1 = standing('drednicolson_prostrate', c.x, c.y, 115, z0=0.0)
s2 = new_person()
pose(s2, 'elvs_pushups_1')
stand(s2, c.x + 0.9, c.y + 0.5, 200)
drop(s2, 0.0)
foot_to(s2, 'R', bone_w(s1, 'spine03', (0, 0.12, 0)))
c2 = pol(6.2, 222)
f_ = Rz(40) @ Vector((1, 0, 0))
l1 = standing('standing03', *(c2 - f_ * 0.4).xy, 40)
l2 = standing('standing06', *(c2 + f_ * 0.4).xy, 220)
for r_ in (l1, l2):
    lean(r_, 13)
    drop(r_, 0.0)
for a_, b_ in ((l1, l2), (l2, l1)):
    reach_to(a_, 'L', on_shoulder(b_, 'R'))
    reach_to(a_, 'R', on_shoulder(b_, 'L'))
side = Rz(40) @ Vector((0, 1, 0))
l3 = standing('callharvey3d_standingnatural', *(c2 + side * 0.45).xy, 40 + 180 + 90)
lean(l3, -12)
drop(l3, 0.0)
reach_to(l3, 'L', on_back(l1, 'spine02', 0.0, 0.12))
reach_to(l3, 'R', on_back(l2, 'spine02', 0.0, 0.12))

# -- contact improvisation: quartet, quintet, sextet, duets turning into trios, rolling on the floor --
UNDRESS[0] = 0.35
group(*pol(6.4, 118).xy, 3, 1, 1.0, 21)                                 # quartet
q5 = group(*pol(6.9, 150).xy, 2, 1, 1.0, 22, duet_clip=('18_03', '19_03', 0))   # quintet around a counterbalance
group(*pol(6.5, 186).xy, 3, 3, 1.4, 23)                                 # sextet, half of it on the floor
# a trio: one on hands and knees, one lying across their back, a third reaching in
c = pol(4.9, 140)
t1 = standing('drednicolson_prostrate', c.x, c.y, 250)
t2 = new_person()
pose(t2, 'elvs_yoga_star_pose_1')
lie(t2, c.x, c.y, 340, 'back')
drop(t2, 0.0, on=(t1,))
t3 = dancer('49_12', 1, c.x + 0.7, c.y - 0.45, 120)
reach_to(t3, 'R', bone_w(t2, 'wrist.L'))
# kneeling floor duet
p = pol(8.0, 170)
duet('22_03', '23_03', 560, p.x, p.y, 170 + 60, z0=0.12)
# rolling with each other on the floor
roll_duet(*pol(8.0, 200).xy, 110, 0.0, style=0)
roll_duet(*pol(5.2, 200).xy, 20, 0.0, style=1)
roll_duet(*pol(8.2, 128).xy, 250, 0.0, style=2)
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
    tri.append(standing(pn, q.x, q.y, 120 * i + 30 + 180))
for i in range(3):
    reach_to(tri[i], 'L', on_back(tri[(i + 1) % 3], 'spine03', 0.0, 0.12))
    reach_to(tri[i], 'R', on_back(tri[(i + 2) % 3], 'spine01', 0.0, 0.1))
# getting up again from a cuddle: one already dancing, one rising, one still lying
c = pol(3.3, 20)
lying('standing02', c.x, c.y, 200, 'back', MF_Z)
standing('wolgade_sit_on_ground_01', c.x + 0.5, c.y + 0.6, 250, z0=MF_Z)
dancer('49_12', 2, *(c + Vector((1.0, 0.9, 0))).xy, 230)
UNDRESS[0] = 0.15

# -- dancing at the edge of the mattress field, reaching down to the people lying there --
for i, a in enumerate((35, 150, 330)):
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
iz = 235
cc = pol(7.0, iz)
R_ = Rz(iz)
m0 = cc + R_ @ Vector((-0.72, -0.3, 0))
m1 = cc + R_ @ Vector((0.72, -0.3, 0))
m2 = cc + R_ @ Vector((0.0, 0.75, 0))
face_to_face(m0.x, m0.y, iz + 90, 0.18)
# a trio making out: two kissing, the third close behind one of them, a hand on the other
ta, tb = face_to_face(m1.x, m1.y, iz + 90, 0.18)
fdir = Rz(iz + 90 - 90) @ Vector((1, 0, 0))
tc = lying('callharvey3d_sittingnatural', m1.x - fdir.x * 0.42, m1.y - fdir.y * 0.42, iz + 94, 'side_r', 0.18)
reach_to(tc, 'L', bone_w(tb, 'spine03', (0, 0.1, 0)))
s1 = standing('callharvey3d_lotus', m2.x, m2.y, iz + 180, z0=0.18)
s2 = head_on('standing01', s1, 'pelvis.L', iz - 90, 'back', 0.18)
reach_to(s1, 'R', bone_w(s2, 'head', (0, 0, 0.08)))

# ---------------------------------------------------------------------------
# 6. cuddle puddle (south-east) (5)
# ---------------------------------------------------------------------------
cz = 310
c0 = pol(7.2, cz)
k1 = lying('standing02', c0.x, c0.y, cz + 100, 'back', 0.18)
head_on('callharvey3d_sittingnatural', k1, 'spine03', cz - 30, 'side_r', 0.18)
k3 = lying('callharvey3d_sittingnatural', *(c0 + Rz(cz) @ Vector((0.0, -0.45, 0))).xy, cz + 100, 'side_l', 0.18)
reach_to(k3, 'R', bone_w(k1, 'spine02', (0, -0.1, 0)))
c1 = pol(8.1, cz + 8)
k4 = standing('callharvey3d_sittingfloorstretch2', c1.x, c1.y, cz + 180, z0=0.18)
k5 = standing('callharvey3d_lotus', *(c1 + Rz(cz + 90) @ Vector((0.5, 0, 0))).xy, cz + 170, z0=0.18)
reach_to(k5, 'L', on_back(k4, 'spine02', 0, 0.12))
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
x1 = standing('mindfront_standing_holding_wine_glass', bc.x, bc.y, ab + 150, kind='crazy')
fb = Rz(ab + 150) @ Vector((1, 0, 0))
x2 = standing('standing02', bc.x - fb.x * 0.2, bc.y - fb.y * 0.2, ab + 150)       # holding them from behind
reach_to(x2, 'L', bone_w(x1, 'spine04', (0.1, -0.12, 0)))
reach_to(x2, 'R', bone_w(x1, 'spine04', (-0.1, -0.12, 0)))
standing('jjones_leaning_on_counter_hands_folded', *FP(P.BAR_FACE, P.R_IN - 1.25, 0.2).xy, ab + 180)
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
    o = standing('callharvey3d_standingatease', pos.x, pos.y, face, kind='organiser', z0=z0)
    cp = bone_w(o, 'spine02') + front(o) * 0.3 + Vector((0, 0, -0.1))
    reach_to(o, 'L', cp + Rz(face) @ Vector((0, 0.1, 0)))
    reach_to(o, 'R', cp + Rz(face) @ Vector((0, -0.1, 0.02)))
    CLIP.append((cp, face))
# stair seating steps
ks = P.STAIR_SLOT
for i, (tr, dn) in enumerate(((2, -0.8), (3, -0.1))):
    sp = FP(ks, P.R_IN - P.STAIR_FLIGHT_W_T + dn, P.STAIR_T0 + (tr - 0.5) * P.STAIR_GOING_T)
    standing('callharvey3d_sittingdefault', sp.x, sp.y, P.slot_center(ks) + 180, z0=tr * P.STAIR_RISE - 0.45)
# window seats
for i, a in enumerate((200,)):
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
    standing('callharvey3d_sittingdefault', p.x, p.y, a + 180, z0=pad - 0.45)          # on the pad, feet on the net
c = pol(4.75, 20)
u1 = standing('callharvey3d_standingnatural', *(c + Rz(20) @ Vector((0, 0.3, 0))).xy, 200, z0=UF, kind='crazy')
u2 = standing('standing04', *(c - Rz(20) @ Vector((0, 0.3, 0))).xy, 200, z0=UF)
reach_to(u1, 'R', on_back(u2, 'spine03', 0.12, 0.12))
standing('standing05', *pol(5.0, 210).xy, 300, z0=UF)

# ---------------------------------------------------------------------------
# 9. rooms upstairs (open / half-open doors) (9)
UNDRESS[0] = 0.7
# ---------------------------------------------------------------------------
def room_pt(k, x, y):
    return Rz(P.slot_center(k)) @ Vector((x, y, 0))


NEST = UF + 0.47
k = 2
a = P.slot_center(k)
r1 = standing('callharvey3d_lotus', *room_pt(k, 8.3, -0.45).xy, a + 90, z0=NEST)
r2 = standing('callharvey3d_sittinglegscrossed', *room_pt(k, 8.3, 0.45).xy, a - 90, z0=NEST)
reach_to(r1, 'L', bone_w(r2, 'wrist.R'))
p = room_pt(3, 8.45, 0.0)
spoon(p.x, p.y, P.slot_center(3), NEST)
k = 5
p = room_pt(k, 8.45, 0.0)
v1 = lying('standing02', p.x, p.y, P.slot_center(k) + 90, 'back', NEST)
head_on('callharvey3d_sittingnatural', v1, 'spine03', P.slot_center(k), 'side_r', NEST)
head_on('standing01', v1, 'upperleg02.L', P.slot_center(k) - 150, 'back', NEST)
p = room_pt(7, 8.45, 0.0)
face_to_face(p.x, p.y, P.slot_center(7) + 90, NEST)
print('rooms done', N[0])

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
