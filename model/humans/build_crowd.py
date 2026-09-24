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
FLOW_F = [('elvs_goddess_dress1',), ('elvs_goddess_dress2',), ('elvs_goddess_dress3',), ('elvs_goddess_dress5',),
          ('elvs_goddess_dress7',), ('elvs_fringe_hippy_dress',), ('elvs_halter_dress_long',),
          ('toigo_long_full_skirt', 'toigo_camisole_top'), ('toigo_harem_pants', 'toigo_keyhole_tank_top'),
          ('elvs_sarong_cover_up', 'punkduck_tube_top'), ('toigo_dress_with_tiered_skirt',),
          ('elvs_double_handkerchief_halter_dress',), ('elvs_gored_midi_skirt', 'elvs_ladies_tank1'),
          ('toigo_tiered_skirt', 'punkduck_off-shoulder_long-sleeve_top'), ('mindfront_f_dress_03',),
          ('toigo_halter_dress_midi',), ('punkduck_retro_polka_dot_skirt', 'punkduck_spaghetti_strap_tank_top')]
FLOW_M = [('toigo_harem_pants', 'elvs_male_boho_top1'), ('toigo_harem_pants', 'elvs_male_tankshirt1'),
          ('elvs_gored_elephant_pants', 'elvs_male_athletic_tank1'), ('toigo_harem_pants',),
          ('elvs_gored_elephant_pants',), ('mindfront_male_trousers_1', 'elvs_male_muscle_shirt1'),
          ('wdg_mycenaean_tunic',), ('drednicolson_asymmetric_tunic_and_sash',),
          ('elvs_male_trouser_short_1', 'elvs_male_boho_top1'), ('toigo_wool_pants', 'elvs_crude_t-shirt_male'),
          ('elvs_sarong_cover_up', 'elvs_male_tankshirt1')]
CRAZY = [('elvs_disco_pants_double_ruffles', 'elvs_disco_top_1_butterfly'), ('punkduck_figure_skating_dress',),
         ('mindfront_ballet_dress_the_swan',), ('skalldyrssuppe_tube_top_funky_colors', 'elvs_disco_mini_skirt'),
         ('elvs_fringe_leather_dress',), ('elvs_fashion_stylized_qipoa',), ('elvs_disco_pants_single_ruffles',
                                                                            'punkduck_high_neck_crop_top'),
         ('elvs_frilled_party_dress',)]
KIMONO = ('mindfront_kimono',)
# most of the clothes already off: bare chests, loose pants and wraps, camisoles, slips
UNDIES_F = [('toigo_camisole_top', 'elvs_retro_girly_shorts1'), ('elvs_crochet_baby_doll',),
            ('punkduck_tube_top', 'elvs_sarong_cover_up'), ('mindfront_cardigan_long_open_front', 'elvs_retro_girly_shorts1'),
            ('punkduck_spaghetti_strap_tank_top', 'elvs_retro_girly_shorts1'), ('punkduck_tube_dress',),
            ('toigo_camisole_top', 'toigo_harem_pants')]
UNDIES_M = [('toigo_harem_pants',), ('elvs_gored_elephant_pants',), ('elvs_sarong_cover_up',),
            ('mindfront_male_trousers_1',), ('toigo_wool_pants',)]
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


N = [0]


def new_person(kind='flow', sex=None, years=None, race=None, outfit=None, seed=None):
    """Generate one dressed person. kind: flow | crazy | organiser."""
    N[0] += 1
    rnd = random.Random(1000 + N[0] if seed is None else seed)
    sex = rnd.choice([0.0, 0.05, 0.1, 0.9, 0.95, 1.0, 0.0, 1.0]) if sex is None else sex
    years = rnd.choice([24, 27, 29, 31, 34, 37, 41, 45, 49, 53, 58, 63, 68]) if years is None else years
    race = race or rnd.choice(['caucasian'] * 6 + ['african', 'asian', 'mixed', 'caucasian'])
    if kind == 'flow' and rnd.random() < UNDRESS[0]:
        kind = 'undies'
    if outfit is None:
        pool = {'crazy': CRAZY, 'organiser': [KIMONO], 'naked': [()],
                'undies': UNDIES_F if sex < 0.5 else UNDIES_M}.get(kind)
        if pool is None:
            pool = FLOW_F if (sex < 0.5 or rnd.random() < 0.08) else FLOW_M
        outfit = rnd.choice(pool)
    if sex < 0.5:
        hair = rnd.choice(HAIR_F)
    else:
        hair = rnd.choice(HAIR_M)
    ph = dict(gender=sex, age=0.5 + (years - 25) / 130.0, muscle=rnd.uniform(0.35, 0.65),
              weight=rnd.uniform(0.35, 0.7), height=rnd.uniform(0.35, 0.65), proportions=rnd.uniform(0.4, 0.7),
              cupsize=rnd.uniform(0.3, 0.7), firmness=rnd.uniform(0.3, 0.7), race=RACES[race])
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
    return rig


def body_of(rig):
    return bpy.data.objects[rig['body']]


def pose(rig, name):
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
lying('standing04', -0.4, -2.7, 320, 'back', MF_Z)
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
lying('elvs_yoga_star_pose_1', 2.4, 1.6, 30, 'back', net_z(2.4, 1.6))
print('net done', N[0])

# ---------------------------------------------------------------------------
UNDRESS[0] = 0.15
# 3. dance floor, north half of the hall (contact improvisation, solos, close dancing) (18)
# ---------------------------------------------------------------------------
# trio: one on hands and knees, one lying across their back, a third reaching in
c = pol(6.0, 70)
t1 = standing('drednicolson_prostrate', c.x, c.y, 160)
t2 = new_person()
pose(t2, 'elvs_yoga_star_pose_1')
lie(t2, c.x, c.y, 250, 'back')
drop(t2, 0.0, on=(t1,))
t3 = standing('punkduck_hand_on_shoulder_02', c.x - 0.75, c.y - 0.5, 40)
reach_to(t3, 'R', bone_w(t2, 'wrist.L'))
# counterbalance pair: leaning into each other's shoulders
c = pol(5.6, 105)
f = Rz(20) @ Vector((1, 0, 0))
p1 = standing('standing03', *(c - f * 0.42).xy, 20)
p2 = standing('standing06', *(c + f * 0.42).xy, 200)
lean(p1, 14)
lean(p2, 14)
drop(p1, 0.0)
drop(p2, 0.0)
for a_, b_ in ((p1, p2), (p2, p1)):
    reach_to(a_, 'L', on_shoulder(b_, 'R'))
    reach_to(a_, 'R', on_shoulder(b_, 'L'))
# back to back, leaning on each other
c = pol(7.0, 130)
q1 = standing('callharvey3d_standingnatural', *(c + Rz(40) @ Vector((0.17, 0, 0))).xy, 40)
q2 = standing('elvs_epic_haute_couture_1', *(c - Rz(40) @ Vector((0.17, 0, 0))).xy, 220)
lean(q1, -6)
lean(q2, -6)
drop(q1, 0.0)
drop(q2, 0.0)
# close dancing couples
embrace_standing(*pol(5.2, 40).xy, 130, kiss=True)
embrace_standing(*pol(7.4, 95).xy, 300, a_pose='standing04', b_pose='standing01')
# group hug of three
c = pol(6.3, 150)
g = []
for i, pn in enumerate(('standing01', 'standing02', 'standing05')):
    p = c + Rz(120 * i) @ Vector((0.32, 0, 0))
    g.append(standing(pn, p.x, p.y, 120 * i + 180))
for i in range(3):
    reach_to(g[i], 'L', on_back(g[(i + 1) % 3], 'spine02', 0.0, 0.12))
    reach_to(g[i], 'R', on_back(g[(i + 2) % 3], 'spine02', 0.0, 0.12))
# solos
standing('spreadcore_arms_up_pose_001', *pol(4.9, 75).xy, 240, kind='crazy')
standing('sohh_posing5', *pol(7.8, 60).xy, 200, kind='crazy')
standing('anrico_standing11', *pol(4.8, 140).xy, 320, kind='naked')
jump = standing('callharvey3d_archer_leap', *pol(6.6, 20).xy, 110, kind='crazy')
jump.location.z += 0.22
standing('elvs_yoga_triangle_pose_1', *pol(8.0, 160).xy, 30, kind='undies')
standing('sohh_posing4', *pol(6.9, 45).xy, 250, kind='naked')
print('dance done', N[0])

# ---------------------------------------------------------------------------
# 4. wrestling mats (west) (4)
UNDRESS[0] = 0.5
# ---------------------------------------------------------------------------
wz = 178
c = pol(7.2, wz - 3)
w1 = standing('sweetan008_sitting-pose', c.x, c.y - 0.4, 90, z0=0.12)
w2 = standing('sweetan008_sitting-pose', c.x, c.y + 0.4, 270, z0=0.12)
for a_, b_ in ((w1, w2), (w2, w1)):
    reach_to(a_, 'L', on_shoulder(b_, 'R'))
    reach_to(a_, 'R', on_shoulder(b_, 'L'))
c = pol(6.9, wz + 7)
w3 = lying('elvs_yoga_cobra_pose_1', c.x, c.y, 90, 'front', 0.12)
w4 = standing('xhado84_sitting_floor_3', c.x + 0.55, c.y - 0.1, 180, z0=0.12)
reach_to(w4, 'R', on_back(w3, 'spine03', 0, 0.12))
reach_to(w4, 'L', on_back(w3, 'spine05', 0.05, 0.12))

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
spoon(m1.x, m1.y, iz + 90, 0.18)
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
x1 = standing('mindfront_standing_holding_wine_glass', bc.x, bc.y, ab + 150)
x2 = standing('punkduck_hand_on_shoulder_01', bc.x + 0.45, bc.y - 0.55, ab + 200)
reach_to(x2, 'R', on_shoulder(x1, 'L'))
standing('jjones_leaning_on_counter_hands_folded', *FP(P.BAR_FACE, P.R_IN - 1.25, 0.2).xy, ab + 180)
mc = FP(P.BAR_FACE, P.R_IN - 3.0, -2.4)
mu = standing('callharvey3d_lotus', mc.x, mc.y, ab + 180, z0=0.0, sex=1.0, years=46)
hp = Vector((mc.x + 0.3, mc.y - 0.3, 0.27))
reach_to(mu, 'L', hp + Vector((0.08, 0.05, 0)))
reach_to(mu, 'R', hp + Vector((-0.08, -0.05, 0)))
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
for i, a in enumerate((200, 235, 20)):
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
c = pol(4.75, 300)
u1 = standing('callharvey3d_standingnatural', *(c + Rz(300) @ Vector((0, 0.3, 0))).xy, 120, z0=UF)
u2 = standing('standing04', *(c - Rz(300) @ Vector((0, 0.3, 0))).xy, 120, z0=UF)
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

# event layer hidden by default, as in tempel.blend (render.py switches it on for the event views)
EVC.hide_render = True
EVC.hide_viewport = True
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(MODEL, 'tempel_event.blend'), compress=True)
print('CROWD', N[0], 'people saved')
