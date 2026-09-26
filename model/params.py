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
STAIR_T0 = -4.02                      # first riser, face-local t on the stair face (top leaves a 1.5 m way out)
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
DAYBED_T = (-1.9, 1.9)            # daybed positions on each SUN_FACE (t), centred at n = 8.15

DOME_RING_OUT = R_DOME + 0.10    # outer edge of the dome upstand / start of the terrace deck


# --- event mattress groups: standard 1.40 x 2.00 mattresses, always flush (edge to edge) in a grid ---
MAT_W, MAT_L = 1.40, 2.00
INT_CANOPY = (225, 6.4, 2.4)       # intimacy zone canopy: face angle, distance from the centre, radius


def _fp(a, n, t):
    a = math.radians(a)
    return (n * math.cos(a) - t * math.sin(a), n * math.sin(a) + t * math.cos(a))


def mat_group(name):
    """[(x, y)], rz (deg), thickness of a mattress group; rz turns the 1.40 side onto its local x."""
    if name == 'field':            # Spielwiese under the net: pixelated circle 3 + 5 + 3
        cells = [(i * MAT_W, j * MAT_L) for j in (-1, 0, 1) for i in (range(-2, 3) if j == 0 else range(-1, 2))]
        return cells, 0.0, 0.16
    if name == 'cuddle':           # cuddle puddle (SE face): 2 x 2, long sides along the face
        return [_fp(315, n, t) for n in (6.6, 8.0) for t in (-1.6, 0.4)], 315.0, 0.18
    if name == 'intimate':         # under the canopy (SW face): 3 side by side, heads to the wall
        a, n0, _ = INT_CANOPY
        return [_fp(a, n0, t) for t in (-MAT_W, 0.0, MAT_W)], a + 90.0, 0.18
    if name == 'wrestle':          # wrestling / rough-and-tumble (W face): 2 x 2, long sides radial
        return [_fp(180, n, t) for n in (5.9, 7.9) for t in (-0.95, 0.45)], 270.0, 0.12
    raise KeyError(name)


# --- stair foot: seating tiers along the hall side of the flight -----------------------------------------
# Tier i (1..5, height i * STAIR_RISE) is the stair's i-th step under the flight; at the foot it flares a
# little towards the hall. The lowest TIER_ROWS tiers continue along the hall side of the flight as seat rows
# (TIER_DEPTH deep each, each row a bit shorter): a modest amphitheatre facing the hall, clear of the corner.
STAIR_N_FAN = 5
TIER_ROWS = 3
TIER_DEPTH = 0.40                     # seat depth per row
TIER_RUN = 2.0                        # how far the lowest row runs along the flight beyond the fan
TIER_STEP_BACK = 0.45                 # each row ends this much earlier


def _tier_dims(i, grow=0.0):
    n1 = R_IN - 0.02                                   # outer wall side of the flight
    n0 = R_IN - STAIR_FLIGHT_W_T                       # hall-side edge of the flight
    t_fan = STAIR_T0 + STAIR_N_FAN * STAIR_GOING_T
    d_s = 0.2 * (STAIR_N_FAN + 1 - i)                  # flare at the foot
    d = TIER_DEPTH * (TIER_ROWS + 1 - i) if i <= TIER_ROWS else 0.0
    t_start = STAIR_T0 + (i - 1) * STAIR_GOING_T - 0.2 * d_s - grow
    t_end = t_fan + TIER_RUN - TIER_STEP_BACK * (i - 1) + grow if d else t_fan + grow
    return n1 + grow, n0, t_fan, n0 - d_s - grow, n0 - d - grow, t_start, t_end


def stair_tier_outline(i, grow=0.0, r=0.3, seg=6):
    """Outline (n, t) of tier i in stair-face coordinates, hall-side corners rounded."""
    n1, n0, t_fan, n_s, n_in, t_start, t_end = _tier_dims(i, grow)
    n_top = n0 + grow

    def arc(cn, ct, a0, a1, rr):
        return [(cn + rr * math.cos(math.radians(a0 + (a1 - a0) * q / seg)),
                 ct + rr * math.sin(math.radians(a0 + (a1 - a0) * q / seg))) for q in range(seg + 1)]
    if n_in >= n_top - 1e-6:                           # a plain step: flare at the foot only
        rr = max(0.02, min(r, (n1 - n_s) / 3, (t_end - t_start) / 2 - 0.01))
        return ([(n1, t_start)] + arc(n_s + rr, t_start + rr, 270, 180, rr) +
                arc(n_s + rr, t_end - rr, 180, 90, rr) + [(n1, t_end)])
    t_a = max(t_fan - 0.5, t_start + 0.25)             # the tier widens between t_a and t_b
    t_b = max(t_a + 0.3, min(t_fan + 0.8, t_end - 0.3))
    r1 = max(0.02, min(r, (n0 - n_s) / 2 - 0.01, (t_a - t_start) / 2 - 0.01))
    r2 = max(0.02, min(r, (n_top - n_in) / 2 - 0.01, (t_end - t_b) / 2 - 0.01))
    pts = [(n1, t_start)]
    pts += arc(n_s + r1, t_start + r1, 270, 180, r1)
    pts += [(n_s, t_a)]
    pts += [(n_s + (n_in - n_s) * (3 * (q / 8) ** 2 - 2 * (q / 8) ** 3), t_a + (t_b - t_a) * q / 8)
            for q in range(1, 9)]                      # smooth widening
    pts += arc(n_in + r2, t_end - r2, 180, 90, r2)
    pts += arc(n_top - r2, t_end - r2, 90, 0, r2)
    pts += [(n_top, t_fan + grow), (n1, t_fan + grow)]
    return pts


def _inside(poly, n, t):
    c = False
    for k in range(len(poly)):
        (n_a, t_a), (n_b, t_b) = poly[k], poly[k - 1]
        if (t_a > t) != (t_b > t) and n < n_a + (t - t_a) * (n_b - n_a) / (t_b - t_a):
            c = not c
    return c


def stair_cushion_spots(width=0.36, step=0.5):
    """(tier, n, t) spots for seat cushions: on the exposed seat of that tier (inside it, not under the next
    tier up), wide enough, off the stair's walking line and clear of the north wall."""
    n0 = R_IN - STAIR_FLIGHT_W_T
    a = math.radians(slot_center(STAIR_SLOT - 1))
    b = math.radians(slot_center(STAIR_SLOT))
    out = []
    for i in range(1, STAIR_N_FAN + 1):
        me, up = stair_tier_outline(i), stair_tier_outline(i + 1) if i < STAIR_N_FAN else []
        ts = [t for _, t in me]
        t = min(ts) + 0.3
        while t < max(ts) - 0.3:
            run, best = [], []
            n = n0 - 2.0
            while n < n0 - 0.05:
                ok = _inside(me, n, t) and not (up and _inside(up, n, t))
                x, y = n * math.cos(b) - t * math.sin(b), n * math.sin(b) + t * math.cos(b)
                ok = ok and x * math.cos(a) + y * math.sin(a) < R_IN - 0.35
                if ok:
                    run.append(n)
                elif run:
                    best = max(best, run, key=len)
                    run = []
                n += 0.02
            best = max(best, run, key=len)
            if best and best[-1] - best[0] >= width:
                out.append((i, (best[0] + best[-1]) / 2, t))
            t += step
    return out
