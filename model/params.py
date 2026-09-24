"""Shared dimensions for the Tempel building concept (metres, degrees).

Everything in the 3D model and in the 2D drawings is derived from these
numbers, so a change here propagates to both.
+Y = north, +X = east, Z up. Hall finished floor = 0.00.
"""
import math

# --- overall -----------------------------------------------------------
R_OUT = 10.00          # outer face of outer wall (20 m diameter)
WALL_T = 0.45          # outer wall incl. insulation, clay plaster, cladding
R_IN = R_OUT - WALL_T  # 9.55 inner face of outer wall

N_SLOTS = 10           # 9 rooms + 1 stair slot on the upper floor
SLOT_DEG = 360.0 / N_SLOTS
SLOT0_DEG = 90.0       # slot 0 is centred on north
STAIR_SLOT = 1         # slot centred at 126 deg (NNW)
ENTRY_SLOT = 0         # hall entrance from the annex, centred at 90 deg (N)
GARDEN_SLOT = 5        # garden doors, centred at 270 deg (S)


def slot_center(k):
    return SLOT0_DEG + k * SLOT_DEG


def partition_angle(k):
    """Angle of the partition wall between slot k-1 and slot k."""
    return slot_center(k) - SLOT_DEG / 2


# --- levels -------------------------------------------------------------
FFL_GF = 0.00
FFL_UF = 3.96          # 22 risers x 180 mm
SLAB_T = 0.40          # upper-floor build-up (boards, screed w/ UFH, acoustic, CLT)
CEIL_GF = FFL_UF - SLAB_T          # 3.56 underside of upper floor
BEAM_D = 0.22                      # radial glulam beams visible below ceiling
BEAM_W = 0.16
N_BEAMS = 20
CLEAR_UF = 2.60
CEIL_UF = FFL_UF + CLEAR_UF        # 6.56
ROOF_T = 0.45

# --- net and its edge -----------------------------------------------------
R_NET = 3.90           # usable net, 7.80 m
PAD_W = 0.35
R_PAD_OUT = R_NET + PAD_W          # 4.25 -> opening 8.50 m
RING_BEAM_IN = 4.20    # glulam / steel ring beam, net anchored to inner face
RING_BEAM_OUT = 4.50
RING_BEAM_TOP = 3.86
RING_BEAM_BOT = 3.34
PAD_T = 0.12
Z_NET_EDGE = 3.84      # net level at the anchor
NET_SAG_REST = 0.15    # pre-tensioned, unloaded
NET_SAG_MAX = 0.90     # design sag with a crowd (to be confirmed by net maker)
N_NET_RADIAL = 16
NET_RING_RADII = (0.30, 1.30, 2.60)
NET_MESH = 0.045       # 45 mm mesh


def net_z(r, sag=NET_SAG_REST):
    r = min(r, RING_BEAM_IN)
    return Z_NET_EDGE - sag * (1 - (r / RING_BEAM_IN) ** 2)


# --- pillars -------------------------------------------------------------
N_PILLARS = 10
R_PILLAR = 4.35
PILLAR_D = 0.36

# --- walkway and rooms ------------------------------------------------------
WALK_W = 1.10
APOTHEM_FRONT = R_PAD_OUT + WALK_W + 0.05   # 5.40 room fronts (decagon)
FRONT_T = 0.12
PART_T = 0.16          # acoustic partitions between rooms
DOOR_H = 2.20
POST = 0.14


def front_corner_radius():
    return APOTHEM_FRONT / math.cos(math.radians(SLOT_DEG / 2))


# --- stair: helical, around a central wooden trunk, hall -> upper floor -> roof terrace
# One full turn per storey below, so you step on/off at the front of the slot on
# the hall floor and on the upper floor; the last 3/4 turn reaches the roof terrace.
STAIR_RISERS = 22                     # hall -> upper floor
STAIR_RISE = FFL_UF / STAIR_RISERS    # 0.180
HELIX_U = 7.75                        # centre, radial distance along the slot axis
HELIX_CORE_R = 0.20                   # central trunk
HELIX_R = 1.45                        # outer edge of treads (tread width 1.25 m)
HELIX_CAGE_R = 1.55                   # slatted larch screen around the stair
HELIX_STEP_DEG = 360.0 / STAIR_RISERS # 16.36 deg per step
HELIX_WALKLINE_R = 0.85
STAIR_GOING = math.radians(HELIX_STEP_DEG) * HELIX_WALKLINE_R   # 0.243 on the walking line
TERRACE_Z = 7.10                      # finished deck of the roof terrace
TERRACE_RISERS = 17
TERRACE_RISE = (TERRACE_Z - FFL_UF) / TERRACE_RISERS  # 0.185
STAIR_HOUSE_TOP = TERRACE_Z + 2.55    # roof of the little round stair house

# --- dome and roof ------------------------------------------------------
R_DOME = 5.60          # dome springs here: 11.2 m, covers net + walkway
DOME_BASE_Z = 7.55     # dome sits on a 45 cm upstand above the terrace (bench height)
DOME_RISE = 2.60
DOME_OCULUS_R = 0.60
N_DOME_RIBS = 20
ROOF_OVERHANG = 0.0    # no eave: the facade battens rise to form the terrace railing
ROOF_Z_IN = 7.00       # flat roof structure (falls in the build-up)
ROOF_Z_OUT = 7.00
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
GF_CLERESTORY = dict(w=1.80, sill=2.30, head=3.15)
UF_WINDOW = dict(w=1.60, sill=0.45, head=1.60)     # relative to FFL_UF
ENTRY_DOOR = dict(w=1.80, h=2.40)
GARDEN_DOOR = dict(w=2.40, h=2.40)

# --- annex (entrance, changing, showers, WC, tech) ----------------------------
ANNEX_A0, ANNEX_A1 = 55.0, 125.0
ANNEX_R_CORR = 11.50   # corridor band R_OUT..11.5
ANNEX_R_OUT = 16.00
ANNEX_H = 3.20
