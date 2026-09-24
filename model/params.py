"""Shared dimensions for the Tempel building concept (metres, degrees).

Everything in the 3D model and in the 2D drawings is derived from these
numbers, so a change here propagates to both.
+Y = north, +X = east, Z up. Hall finished floor = 0.00.
"""
import math

# --- overall -----------------------------------------------------------
# Octagonal outside, round inside. R_OUT / R_IN are the *apothems* of the
# octagon (20.00 m across the flats, 21.65 m across the corners).
R_OUT = 10.00          # outer face of the outer wall (across flats / 2)
WALL_T = 0.45          # timber-frame wall: clay plaster, wood fibre, larch cladding
R_IN = R_OUT - WALL_T  # 9.55 inner face (apothem)

N_SLOTS = 8            # 7 rooms + 1 stair segment; one octagon face per segment
SLOT_DEG = 360.0 / N_SLOTS
SLOT0_DEG = 90.0       # slot 0 is centred on north
STAIR_SLOT = 1         # segment centred at 135 deg (NW)
ENTRY_SLOT = 0         # hall entrance from the annex, north face
GARDEN_SLOT = 4        # garden doors, south face


def slot_center(k):
    return SLOT0_DEG + k * SLOT_DEG


def partition_angle(k):
    """Angle of the partition wall between slot k-1 and slot k (= octagon corner)."""
    return slot_center(k) - SLOT_DEG / 2


def octo_r(a_deg, apothem=None):
    """Distance from the centre to the octagon (given apothem) at angle a."""
    apothem = R_OUT if apothem is None else apothem
    k = round((a_deg - SLOT0_DEG) / SLOT_DEG)
    return apothem / math.cos(math.radians(a_deg - slot_center(k)))


def face_half(apothem):
    """Half length of an octagon face at the given apothem."""
    return apothem * math.tan(math.radians(SLOT_DEG / 2))


# --- levels -------------------------------------------------------------
FFL_GF = 0.00
FFL_UF = 4.14          # 22 risers x 188 mm (v0.7: +18 cm for a higher hall)
SLAB_T = 0.40          # upper-floor build-up (boards, screed w/ UFH, acoustic, CLT)
CEIL_GF = FFL_UF - SLAB_T          # 3.56 underside of upper floor
BEAM_D = 0.22                      # radial glulam beams visible below ceiling
BEAM_W = 0.16
N_BEAMS = 16
CLEAR_UF = 2.60
CEIL_UF = FFL_UF + CLEAR_UF        # 6.56
ROOF_T = 0.45

# --- net and its edge -----------------------------------------------------
R_NET = 3.90           # usable net, 7.80 m
PAD_W = 0.40
R_PAD_OUT = R_NET + PAD_W          # 4.25 -> opening 8.50 m
RING_BEAM_IN = 4.25    # steel box ring beam (500x300) clad in timber, net anchored to inner face
RING_BEAM_OUT = 4.55
RING_BEAM_TOP = 4.04
RING_BEAM_BOT = 3.52
PAD_T = 0.12
Z_NET_EDGE = 4.02      # net level at the anchor
NET_SAG_REST = 0.15    # pre-tensioned, unloaded
NET_SAG_MAX = 0.90     # design sag with a crowd (to be confirmed by net maker)
N_NET_RADIAL = 16
NET_RING_RADII = (0.30, 1.30, 2.60)
NET_MESH = 0.045       # 45 mm mesh


def net_z(r, sag=NET_SAG_REST):
    r = min(r, RING_BEAM_IN)
    return Z_NET_EDGE - sag * (1 - (r / RING_BEAM_IN) ** 2)


# --- pillars -------------------------------------------------------------
N_PILLARS = 4          # steel tube 219 mm inside a round timber casing
R_PILLAR = 4.40
PILLAR_D = 0.30
PILLAR0_DEG = 67.5     # on four of the room-partition lines (every 90 deg)

# --- walkway and rooms ------------------------------------------------------
WALK_W = 1.25
APOTHEM_FRONT = R_PAD_OUT + WALK_W + 0.05   # 5.40 room fronts (decagon)
FRONT_T = 0.12
PART_T = 0.16          # acoustic partitions between rooms
DOOR_H = 2.20
POST = 0.14


def front_corner_radius():
    return APOTHEM_FRONT / math.cos(math.radians(SLOT_DEG / 2))


# --- stair: half-turn (U), hall -> upper floor only; the roof terrace is reached by the
# external stair. 22 risers x 188 mm, going 260 mm (DIN 18065: 2R+G = 636 mm)
STAIR_RISERS = 22
STAIR_RISE = FFL_UF / STAIR_RISERS    # 0.188
STAIR_GOING_U = 0.26
STAIR_GOING = STAIR_GOING_U
STAIR_FLIGHT_W = 1.20
# v0.9: one straight flight along the NW wall (circumferential), open to the hall
STAIR_GOING_T = 0.27                  # 2R+G = 646 mm
STAIR_FLIGHT_W_T = 1.50
STAIR_T0 = -3.72                      # first riser, face-local t on the stair face
TERRACE_Z = 7.28                      # finished deck of the roof terrace
TERRACE_RISERS = 17
TERRACE_RISE = (TERRACE_Z - FFL_UF) / TERRACE_RISERS  # 0.185 (external stair)

# --- dome and roof ------------------------------------------------------
R_DOME = 5.80          # dome springs here: 11.6 m, covers net + walkway
DOME_BASE_Z = 7.73     # dome sits on a 45 cm upstand above the terrace (bench height)
DOME_RISE = 2.90
DOME_OCULUS_R = 0.60
N_DOME_RIBS = 20
ROOF_OVERHANG = 0.0    # no eave: the facade battens rise to form the terrace railing
ROOF_Z_IN = 7.18       # flat roof structure (falls in the build-up)
ROOF_Z_OUT = 7.18
R_TERRACE_OUT = R_OUT - 0.05
RAIL_H = 1.20          # guard height above the deck


def dome_sphere():
    a, h = R_DOME, DOME_RISE
    rs = (a * a + h * h) / (2 * h)
    zc = DOME_BASE_Z + h - rs
    return rs, zc


def dome_z(r):
    rs, zc = dome_sphere()
    return zc + math.sqrt(max(rs * rs - r * r, 0))


# --- openings ------------------------------------------------------------
GF_WINDOW = dict(w=2.10, sill=0.40, head=3.20)     # two per face
UF_WINDOW = dict(w=2.60, sill=0.45, head=2.10)     # relative to FFL_UF; fixed safety glass to 0.90
ENTRY_DOOR = dict(w=1.80, h=2.40)
GARDEN_DOOR = dict(w=3.00, h=2.60)
SKYLIGHT = dict(w=1.40, d=1.10, u=8.30)            # walk-on frosted glass in the terrace, per room

# --- annex (entrance, changing, showers, WC, tech) ----------------------------
# rectangular wing on the north face, x across, y outwards from the face
ANNEX_W = 12.00
ANNEX_D = 5.00
ANNEX_CORR = 1.50      # corridor along the building
ANNEX_H = 3.20

# --- external stair (2nd escape route) on the stair segment's face --------
EXT_W = 1.20           # flight width
EXT_GOING = 0.27
EXT_LANDING = 1.40


# --- openings in the octagon faces (face-local: t along the face, z) ---------
ANNEX_FACES = (0,)         # small annex on the N face: foyer + coats, WC, tech
BAR_FACE = 7               # NE face: tea / party bar, no ground-floor windows
BATH_SLOT = 0              # N room on the upper floor = shared bathroom (2 WC + group shower)
SUN_FACES = (3, 4, 5)      # SW, S, SE: daybeds + 1.80 m privacy screen on the terrace


def face_openings():
    """{face: [(t0, t1, z_bottom, z_top, kind)]} shared by the model and the drawings."""
    out = {k: [] for k in range(N_SLOTS)}
    uf = FFL_UF
    for k in range(N_SLOTS):
        if k == STAIR_SLOT:
            out[k] += [(2.30, 3.30, uf, uf + 2.20, 'door_ext_stair'),        # upper floor -> external stair
                       (-3.05, -2.25, uf + 1.45, uf + 2.10, 'window')]       # bathroom
            continue
        if k == ENTRY_SLOT:
            out[k].append((-ENTRY_DOOR['w'] / 2, ENTRY_DOOR['w'] / 2, 0.0, ENTRY_DOOR['h'], 'door_entry'))
            for tc in (() if k in ANNEX_FACES else (-2.75, 2.75)):
                out[k].append((tc - 0.65, tc + 0.65, GF_WINDOW['sill'] + 0.6, GF_WINDOW['head'], 'window_gf'))
        elif k == GARDEN_SLOT:
            w = GARDEN_DOOR['w']
            out[k] += [(-w / 2, w / 2, 0.0, GARDEN_DOOR['h'], 'door_garden'),
                       (-3.35, -2.05, GF_WINDOW['sill'], GF_WINDOW['head'], 'window_gf'),
                       (2.05, 3.35, GF_WINDOW['sill'], GF_WINDOW['head'], 'window_gf')]
        elif k not in ANNEX_FACES and k != BAR_FACE:
            w = GF_WINDOW['w']
            for tc in (-1.95, 1.95):
                out[k].append((tc - w / 2, tc + w / 2, GF_WINDOW['sill'], GF_WINDOW['head'], 'window_gf'))
        w = UF_WINDOW['w']
        out[k].append((-w / 2, w / 2, uf + UF_WINDOW['sill'], uf + UF_WINDOW['head'], 'window_uf'))
    return out

EXT_T_LAND = 2.10                 # external stair: upper-floor landing from here to the face end
TERRACE_GATE = (-3.55, -2.30)     # gate in the terrace railing to the external stair (face t range)
DAYBED_T = (-2.25, 2.25)          # daybed positions on each SUN_FACE (t), centred at n = 8.15

DOME_RING_OUT = R_DOME + 0.10    # outer edge of the dome upstand / start of the terrace deck
