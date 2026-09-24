"""2D drawings (ground floor, upper floor, section A-A) from the shared params.

    python3 plans.py   -> *.pdf (vector, 1:100 on A2) and *.png next to this file
"""
import math
import os
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Polygon, Circle, FancyArrowPatch, Rectangle, Arc  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'model'))
import params as P  # noqa: E402

rad = math.radians
INK = '#2B2420'
POCHE = '#6E5A4B'
CLAY = '#E9DCCB'
WOOD = '#C9A57A'
NETC = '#9A8C78'
LIGHT = '#E8B04A'
A2 = (23.386, 16.535)
SCALE = 100.0   # 1:100


def pol(r, a):
    return (r * math.cos(rad(a)), r * math.sin(rad(a)))


def arc_pts(r, a0, a1, n=None):
    n = n or max(2, int(abs(a1 - a0) / 1.0) + 1)
    return [pol(r, a0 + (a1 - a0) * i / (n - 1)) for i in range(n)]


def sector_poly(r0, r1, a0, a1):
    return arc_pts(r1, a0, a1) + arc_pts(r0, a1, a0)


def sheet(xmin, xmax, ymin, ymax, title, subtitle):
    fig = plt.figure(figsize=A2)
    w_in = (xmax - xmin) * 1000 / SCALE / 25.4
    h_in = (ymax - ymin) * 1000 / SCALE / 25.4
    left = 1.0 / A2[0]
    bottom = (A2[1] - h_in) / 2 / A2[1]
    ax = fig.add_axes([left, bottom, w_in / A2[0], h_in / A2[1]])
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    ax.set_aspect('equal')
    ax.axis('off')
    # title block
    tx = left + w_in / A2[0] + 0.02
    tx = max(tx, 0.64)
    fig.text(tx + 0.02, 0.93, title, fontsize=24, color=INK, weight='bold', va='top')
    fig.text(tx + 0.02, 0.885, subtitle, fontsize=12, color=INK, va='top', linespacing=1.5)
    fig.text(tx + 0.02, 0.045, 'Tempel – seminar building, concept v0.1\nScale 1:100 on A2 · dimensions in metres\n'
             'Not for construction: structure and net to be verified\nby a structural engineer and a net maker.',
             fontsize=8.5, color='#6B5E55', va='bottom', linespacing=1.5)
    return fig, ax, tx


def poly(ax, pts, fc=POCHE, ec=INK, lw=0.6, z=2, **kw):
    ax.add_patch(Polygon(pts, closed=True, fc=fc, ec=ec, lw=lw, zorder=z, **kw))


def ring_wall_plan(ax, r0, r1, gaps, fc=POCHE):
    """gaps: list of (a0, a1) angular gaps"""
    cuts = sorted([0.0, 360.0] + [g for gp in gaps for g in gp])
    for a0, a1 in zip(cuts[:-1], cuts[1:]):
        am = (a0 + a1) / 2
        if any(g0 < am < g1 for g0, g1 in gaps) or a1 - a0 < 1e-6:
            continue
        poly(ax, sector_poly(r0, r1, a0, a1), fc=fc)


def seg_wall(ax, p0, p1, t, fc=POCHE, lw=0.6, z=2):
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    L = math.hypot(dx, dy)
    nx, ny = -dy / L * t / 2, dx / L * t / 2
    poly(ax, [(p0[0] + nx, p0[1] + ny), (p1[0] + nx, p1[1] + ny), (p1[0] - nx, p1[1] - ny),
              (p0[0] - nx, p0[1] - ny)], fc=fc, lw=lw, z=z)


def circle(ax, r, **kw):
    kw.setdefault('fill', False)
    ax.add_patch(Circle((0, 0), r, **kw))


def north_arrow(ax, x, y, s=1.2):
    ax.add_patch(Polygon([(x, y + s), (x - s * 0.35, y - s * 0.5), (x, y - s * 0.2)], fc=INK, ec=INK, lw=0.5))
    ax.add_patch(Polygon([(x, y + s), (x + s * 0.35, y - s * 0.5), (x, y - s * 0.2)], fc='white', ec=INK, lw=0.5))
    ax.text(x, y + s * 1.25, 'N', ha='center', va='bottom', fontsize=11, weight='bold', color=INK)


def scale_bar(ax, x, y):
    for i in range(5):
        ax.add_patch(Rectangle((x + i, y), 1, 0.18, fc=INK if i % 2 == 0 else 'white', ec=INK, lw=0.5))
    ax.text(x, y - 0.25, '0', fontsize=7, ha='center', va='top')
    ax.text(x + 5, y - 0.25, '5 m', fontsize=7, ha='center', va='top')


def label(ax, x, y, s, size=8, **kw):
    kw.setdefault('ha', 'center')
    kw.setdefault('va', 'center')
    kw.setdefault('color', INK)
    ax.text(x, y, s, fontsize=size, zorder=10, **kw)


def dim_radial(ax, a, r0, r1, text, off=0.0, size=7):
    p0, p1 = pol(r0, a), pol(r1, a)
    ax.annotate('', xy=p1, xytext=p0, arrowprops=dict(arrowstyle='<|-|>', lw=0.5, color=INK,
                                                       mutation_scale=6), zorder=9)
    m = pol((r0 + r1) / 2, a)
    ax.text(m[0], m[1], text, fontsize=size, color=INK, ha='center', va='center', zorder=10,
            rotation=(a + 90) % 180 - 90 if True else 0,
            bbox=dict(fc='white', ec='none', pad=0.6, alpha=0.85))


def opening_angles(a, w, r=None):
    r = r or (P.R_IN + P.R_OUT) / 2
    da = math.degrees(w / 2 / r)
    return a - da, a + da


RC = P.front_corner_radius()
S_A0 = P.partition_angle(P.STAIR_SLOT)
S_A1 = P.partition_angle(P.STAIR_SLOT + 1)
SA = P.slot_center(P.STAIR_SLOT)


def to_world(k_angle, u, v):
    a = rad(k_angle)
    return (u * math.cos(a) - v * math.sin(a), u * math.sin(a) + v * math.cos(a))


def HWp(theta, r):
    return to_world(SA, P.HELIX_U + r * math.cos(rad(theta)), r * math.sin(rad(theta)))


S_ = P.HELIX_STEP_DEG
TH0 = 180.0 - (P.STAIR_RISERS - 1) * S_
TH_UF0 = 180.0
TH_UF1 = TH_UF0 + 2 * S_
TH_TOP = TH_UF1 + (P.TERRACE_RISERS - 1) * S_


def harc(r, a0, a1, n=60):
    return [HWp(a0 + (a1 - a0) * i / (n - 1), r) for i in range(n)]


def stair_plan(ax, level):
    """Helical stair around a trunk. level: GF, UF or RF (roof)."""
    R0, R1, RC_ = P.HELIX_CORE_R, P.HELIX_R, P.HELIX_CAGE_R
    ax.add_patch(Polygon(harc(R1, 0, 360, 90), closed=True, fc='#F4EADC', ec=INK, lw=0.5, zorder=3))
    if level == 'GF':
        visible = [(TH0 + (k - 1) * S_, TH0 + k * S_) for k in range(1, 8)]
        above = [(TH0 + (k - 1) * S_, TH0 + k * S_) for k in range(8, P.STAIR_RISERS)]
        gaps = [(165, 232)]
        arrow = (TH0 + 0.3 * S_, TH0 + 6 * S_, 'UP')
    elif level == 'UF':
        ax.add_patch(Polygon([HWp(TH_UF0, R0)] + harc(R1, TH_UF0, TH_UF1, 12) + [HWp(TH_UF1, R0)],
                             closed=True, fc='#E7D6BE', ec=INK, lw=0.5, zorder=4))
        visible = [(TH_UF1 + (j - 1) * S_, TH_UF1 + j * S_) for j in range(1, 7)]
        above = [(TH_UF1 + (j - 1) * S_, TH_UF1 + j * S_) for j in range(7, P.TERRACE_RISERS)]
        gaps = [(150, 214)]
        arrow = (TH_UF1 + 0.3 * S_, TH_UF1 + 5 * S_, 'UP')
    else:
        visible = [(TH_UF1 + (j - 1) * S_, TH_UF1 + j * S_) for j in range(8, P.TERRACE_RISERS)]
        above = []
        gaps = []
        arrow = (TH_TOP - 0.3 * S_, TH_TOP - 5 * S_, 'DN')
        ax.add_patch(Polygon([HWp(TH_TOP, R0)] + harc(R1 + 0.08, TH_TOP, TH_TOP + 150, 30) +
                             [HWp(TH_TOP + 150, R0)], closed=True, fc='#E7D6BE', ec=INK, lw=0.5, zorder=4))
    for a0, a1 in visible:
        ax.plot(*zip(HWp(a0, R0), HWp(a0, R1)), color=INK, lw=0.45, zorder=5)
    for a0, a1 in above:
        ax.plot(*zip(HWp(a0, R0), HWp(a0, R1)), color='#9C8E80', lw=0.35, ls=(0, (2, 2)), zorder=5)
    # cut line
    if visible and above:
        a = visible[-1][1] - 4
        ax.plot(*zip(HWp(a, R0), HWp(a + 5, (R0 + R1) / 2), HWp(a - 2, R1)), color=INK, lw=0.8, zorder=6)
    ax.add_patch(Circle(HWp(0, 0), R0, fc=WOOD, ec=INK, lw=0.6, zorder=6))
    # slatted screen with openings
    cuts = sorted({0.0, 360.0} | {g for gp in gaps for g in gp})
    for a0, a1 in zip(cuts[:-1], cuts[1:]):
        if any(g0 < (a0 + a1) / 2 < g1 for g0, g1 in gaps):
            continue
        ax.plot(*zip(*harc(RC_, a0, a1, 40)), color='#8C6E50', lw=1.6, ls=(0, (0.8, 0.8)), zorder=5)
    # walking line + arrow
    a0, a1, t = arrow
    pts = harc(P.HELIX_WALKLINE_R, a0, a1, 20)
    ax.plot(*zip(*pts[:-1]), color=INK, lw=0.7, zorder=7)
    ax.annotate('', xy=pts[-1], xytext=pts[-3], arrowprops=dict(arrowstyle='-|>', lw=0.7, color=INK), zorder=7)
    p = HWp((a0 + a1) / 2, P.HELIX_WALKLINE_R + 0.45)
    label(ax, p[0], p[1], t, 6.5, weight='bold')


# ---------------------------------------------------------------------------
def ground_floor():
    fig, ax, tx = sheet(-17.5, 17.5, -12.5, 17.5, 'Ground floor',
                        'Open hall, ≈ 270 m² net (Ø 19.1 m inside)\n'
                        'Clear height 3.56 m (3.34 m under the beams)\n'
                        '10 tree pillars on Ø 8.70 m carry the ring beam\n'
                        'around the net opening (Ø 8.50 m, above)\n'
                        'Annex: entrance, changing, showers, WC, tech\n'
                        'Underfloor heating throughout (see notes)')
    # site hint
    circle(ax, P.R_OUT + 0.6, ec='#B8AC98', lw=0.5, ls='-', zorder=1)
    # light spot (sun, 57 deg, from S): the net opening projected onto the floor
    off = P.Z_NET_EDGE / math.tan(rad(57))
    ax.add_patch(Circle((0, off), P.R_PAD_OUT, fc=LIGHT, ec='none', alpha=0.18, zorder=1))
    label(ax, 0, off + 2.6, 'sun spot, noon in summer\n(moves with the sun)', 6.5, color='#9A6B12',
          style='italic')
    # outer wall
    gaps = []
    ent = opening_angles(P.slot_center(P.ENTRY_SLOT), P.ENTRY_DOOR['w'])
    gar = opening_angles(P.slot_center(P.GARDEN_SLOT), P.GARDEN_DOOR['w'])
    gaps += [ent, gar]
    ring_wall_plan(ax, P.R_IN, P.R_OUT, gaps)
    # clerestory windows (above cut) dashed
    for k in range(P.N_SLOTS):
        if k in (P.ENTRY_SLOT, P.GARDEN_SLOT, P.STAIR_SLOT):
            continue
        a0, a1 = opening_angles(P.slot_center(k), P.GF_CLERESTORY['w'])
        pts = arc_pts(P.R_IN - 0.25, a0, a1)
        ax.plot(*zip(*pts), color=INK, lw=0.6, ls=(0, (3, 2)), zorder=5)
    a0, a1 = opening_angles(SA, 0.9)
    ax.plot(*zip(*arc_pts(P.R_IN - 0.25, a0, a1)), color=INK, lw=0.6, ls=(0, (3, 2)), zorder=5)
    # doors
    for (a0, a1), leaves in ((ent, 2), (gar, 2)):
        pts = arc_pts(P.R_IN + 0.12, a0, a1)
        ax.plot(*zip(*pts), color=INK, lw=1.2, zorder=5)
    # entry door swing (double, into the hall)
    ac = P.slot_center(P.ENTRY_SLOT)
    for s in (-1, 1):
        hinge = pol(P.R_IN, ac + s * math.degrees(P.ENTRY_DOOR['w'] / 2 / P.R_IN))
        ax.add_patch(Arc(hinge, 1.8, 1.8, theta1=(180 if s > 0 else 270), theta2=(270 if s > 0 else 360),
                         color=INK, lw=0.4, zorder=5))
    label(ax, *pol(P.R_IN - 1.6, ac), 'entrance\nfrom annex', 6.5)
    label(ax, *pol(P.R_IN - 1.4, P.slot_center(P.GARDEN_SLOT)), 'garden doors\n(curtain)', 6.5)
    # pillars
    for k in range(P.N_PILLARS):
        ax.add_patch(Circle(pol(P.R_PILLAR, P.partition_angle(k)), P.PILLAR_D / 2, fc=WOOD, ec=INK, lw=0.6, zorder=6))
    # above: ring beam, beams, net opening, dome (dashed)
    circle(ax, P.RING_BEAM_IN, ec=INK, lw=0.5, ls=(0, (6, 3)), zorder=4)
    circle(ax, P.RING_BEAM_OUT, ec=INK, lw=0.5, ls=(0, (6, 3)), zorder=4)
    for i in range(P.N_BEAMS):
        a = i * 360 / P.N_BEAMS
        p0, p1 = pol(P.RING_BEAM_OUT, a), pol(P.R_IN, a)
        ax.plot([p0[0], p1[0]], [p0[1], p1[1]], color='#8C7A6A', lw=0.35, ls=(0, (2, 3)), zorder=2)
    # rug + cushions
    circle(ax, 2.9, ec='#9C8A70', lw=0.5, zorder=3)
    for i in range(14):
        a = 360 * i / 14 + 8
        ax.add_patch(Circle(pol(2.45, a), 0.25, fc='#E9DCC6', ec='#9C8A70', lw=0.4, zorder=3))
    # benches
    for k in [3, 4, 6, 7, 8, 9]:
        a = P.slot_center(k)
        poly(ax, sector_poly(P.R_IN - 0.55, P.R_IN, a - 12, a + 12), fc='#F2E8DA', lw=0.4, z=3)
    # stair walls (both partitions from ground) + ground-floor front
    for k in (P.STAIR_SLOT, P.STAIR_SLOT + 1):
        a = P.partition_angle(k)
        seg_wall(ax, pol(RC, a), pol(P.R_IN, a), P.PART_T)
    stair_plan(ax, 'GF')
    p = to_world(SA, 5.05, 0.55)
    label(ax, p[0], p[1], 'spiral stair\nto upper floor\n+ roof terrace', 6)
    # labels
    label(ax, 0, -1.2, 'HALL', 13, weight='bold')
    label(ax, 0, -2.0, 'open floor under the net · wooden boards', 7)
    label(ax, *pol(6.9, 250), 'benches along the wall', 6.5, rotation=-20)
    label(ax, *pol(3.3, 200), 'tree pillar', 6.5)
    # annex
    A0, A1 = P.ANNEX_A0, P.ANNEX_A1
    RA, RB, RC_ = P.R_OUT, P.ANNEX_R_CORR, P.ANNEX_R_OUT
    T = 0.35
    poly(ax, sector_poly(RC_ - T, RC_, A0, A1))
    seg_wall(ax, pol(RA, A1 - 0.9), pol(RC_ - T, A1 - 0.9), T)
    door_c = 13.2
    seg_wall(ax, pol(RA, A0 + 0.9), pol(door_c - 1.0, A0 + 0.9), T)
    seg_wall(ax, pol(door_c + 1.0, A0 + 0.9), pol(RC_ - T, A0 + 0.9), T)
    ax.plot(*zip(pol(door_c - 1.0, A0 + 0.9), pol(door_c + 1.0, A0 + 0.9)), color=INK, lw=1.2, zorder=5)
    gaps_c = [(62, 66), (80, 84), (96, 100), (111.5, 114.5)]
    edges = [A0 + 1.2] + [g for gp in gaps_c for g in gp] + [A1 - 1.2]
    for i in range(0, len(edges), 2):
        poly(ax, sector_poly(RB, RB + 0.12, edges[i], edges[i + 1]), fc=POCHE)
    for a in (72, 90, 108, 116):
        seg_wall(ax, pol(RB + 0.12, a), pol(RC_ - T, a), 0.12)
    rm = (RB + RC_) / 2
    label(ax, *pol(rm - 0.3, 63.5), 'ENTRANCE\n& FOYER\nshoes, coats\ntea corner', 6.5)
    label(ax, *pol(rm, 81), 'CHANGING 1\nlockers\n+ 3 showers', 6.5)
    label(ax, *pol(rm, 99), 'CHANGING 2\nlockers\n+ 3 showers', 6.5)
    label(ax, *pol(rm, 112), 'WC\n(2 + acc.)', 6)
    label(ax, *pol(rm, 120.5), 'tech\nstore', 6)
    label(ax, *pol((RA + RB) / 2, 90), 'warm corridor · towels · benches', 6)
    # shower cubicles
    for ac in (81, 99):
        for i in range(3):
            a = ac - 5 + i * 4.5
            p = pol(RC_ - T - 0.55, a)
            ax.add_patch(Rectangle((p[0] - 0.45, p[1] - 0.45), 0.9, 0.9, angle=0, fc='#DDE6E6', ec=INK, lw=0.4,
                                   zorder=3, rotation_point='center', transform=ax.transData))
    # entrance arrow
    pe = pol(door_c, A0 - 4)
    ax.annotate('', xy=pol(door_c, A0 + 1), xytext=pe, arrowprops=dict(arrowstyle='-|>', lw=1.2, color=INK))
    label(ax, *pol(door_c, A0 - 6.5), 'main\nentrance', 7, weight='bold')
    # dimensions
    ax.annotate('', xy=(-P.R_OUT, -11.3), xytext=(P.R_OUT, -11.3),
                arrowprops=dict(arrowstyle='<|-|>', lw=0.5, color=INK, mutation_scale=6))
    label(ax, 0, -11.0, 'Ø 20.00 outside', 7.5)
    ax.plot([-P.R_OUT, -P.R_OUT], [-11.6, -1], color=INK, lw=0.3)
    ax.plot([P.R_OUT, P.R_OUT], [-11.6, -1], color=INK, lw=0.3)
    dim_radial(ax, 322, 0, P.R_PAD_OUT, 'net opening above Ø 8.50', size=6.5)
    dim_radial(ax, 158, 0, P.R_PILLAR, 'pillars on Ø 8.70', size=6.5)
    north_arrow(ax, 15.5, 13.8)
    scale_bar(ax, -17, -12.0)
    # section line A-A (N-S)
    for y0, y1, s in ((-12.2, -10.6, 'A'), (16.9, 17.3, 'A')):
        pass
    ax.plot([0.05, 0.05], [-12.3, -10.6], color=INK, lw=1.4)
    ax.plot([0.05, 0.05], [16.4, 17.4], color=INK, lw=1.4)
    label(ax, 0.8, -12.0, 'A', 10, weight='bold')
    label(ax, 0.8, 17.1, 'A', 10, weight='bold')
    # legend
    fig.text(tx + 0.02, 0.62, 'Legend', fontsize=10, weight='bold', color=INK)
    items = [('cut wall (clay / timber frame)', dict(fc=POCHE)), ('wooden pillar (tree)', dict(fc=WOOD)),
             ('above: ring beam / beams / windows', dict(fc='white', ls='--')),
             ('sun spot through dome + net', dict(fc=LIGHT, alpha=0.3))]
    for i, (t, st) in enumerate(items):
        y = 0.59 - i * 0.03
        fig.patches.append(Rectangle((tx + 0.02, y), 0.018, 0.018, transform=fig.transFigure, ec=INK, lw=0.5, **st))
        fig.text(tx + 0.045, y + 0.004, t, fontsize=10, color=INK)
    notes = ('Heating & comfort\n'
             '• Underfloor heating (low-temp., heat pump)\n   in hall, rooms, annex – floors ~26–28 °C\n'
             '• Air ~24–26 °C for undressed use; hall and\n   rooms zoned separately\n'
             '• Balanced ventilation with heat recovery,\n   dome vent at the crown for summer purge\n'
             '• Clay plaster buffers humidity and sound')
    fig.text(tx + 0.02, 0.44, notes, fontsize=10, color=INK, va='top', linespacing=1.45)
    return fig


# ---------------------------------------------------------------------------
DOOR_STATES = {2: 'open', 3: 'half', 4: 'closed', 5: 'open', 6: 'closed', 7: 'half',
               8: 'closed', 9: 'open', 0: 'half'}


def upper_floor():
    fig, ax, tx = sheet(-12.5, 12.5, -12.5, 12.5, 'Upper floor',
                        'From the centre outwards:\n'
                        '• Net Ø 7.80 usable (opening Ø 8.50)\n'
                        '• Padded edge 0.35 m on the ring beam\n'
                        '• Ring walkway 1.10 m (up to 1.38 m at the posts)\n'
                        '• 9 rooms, each ≈ 17 m², 3.4 m wide at the door,\n'
                        '   5.9 m at the outer wall, 4.1 m deep\n'
                        '• Spiral stair in the 10th slot, on up to the roof\n'
                        'Clear height in rooms 2.60 m')
    # dome above (dash-dot)
    circle(ax, P.R_DOME, ec='#5B7B8C', lw=0.7, ls='-.', zorder=7)
    label(ax, *pol(P.R_DOME + 0.0, 200), 'glass dome above, Ø 11.20', 6.5, color='#3F5D6C',
          rotation=-70, bbox=dict(fc='white', ec='none', pad=0.5))
    # outer wall with windows
    gaps = []
    for k in range(P.N_SLOTS):
        w = 0.9 if k == P.STAIR_SLOT else P.UF_WINDOW['w']
        gaps.append(opening_angles(P.slot_center(k), w))
    ring_wall_plan(ax, P.R_IN, P.R_OUT, gaps)
    for g in gaps:
        for rr in (P.R_IN + 0.13, P.R_IN + 0.17):
            ax.plot(*zip(*arc_pts(rr, *g)), color=INK, lw=0.4, zorder=5)
    # battens outside
    circle(ax, P.R_OUT + 0.07, ec='#8C6E50', lw=0.9, ls=(0, (0.6, 0.6)), zorder=3)
    # partitions
    for k in range(P.N_SLOTS):
        a = P.partition_angle(k)
        seg_wall(ax, pol(RC, a), pol(P.R_IN, a), P.PART_T)
        ax.add_patch(Rectangle((pol(RC, a)[0] - P.POST / 2, pol(RC, a)[1] - P.POST / 2), P.POST, P.POST,
                               fc=WOOD, ec=INK, lw=0.5, zorder=6))
    # room fronts (3 shoji panels)
    tan18 = math.tan(rad(18))
    half = P.APOTHEM_FRONT * tan18 - P.POST / 2 - 0.01
    L = 2 * half
    pw = L / 3 + 0.03
    for k in range(P.N_SLOTS):
        if k == P.STAIR_SLOT:
            continue
        a = P.slot_center(k)
        x = P.APOTHEM_FRONT + P.FRONT_T / 2
        state = DOOR_STATES[k]
        pos = {'closed': (0, 1), 'half': (-1, 0), 'open': (-1, -1)}[state]
        for i, (slot, off) in enumerate([(-1, 0.0), (pos[0], -0.045), (pos[1], -0.09)]):
            yc = slot * L / 3
            xc = x + off + 0.045
            p0 = to_world(a, xc, yc - pw / 2)
            p1 = to_world(a, xc, yc + pw / 2)
            seg_wall(ax, p0, p1, 0.035, fc=WOOD if i == 0 else '#F3E6CC', lw=0.5, z=6)
        # track line
        ax.plot(*zip(to_world(a, x + 0.1, -half), to_world(a, x + 0.1, half)), color=INK, lw=0.25, zorder=5)
        # furniture: mattress + floor cushions + table
        mx = 8.45
        c = [to_world(a, mx - 0.82, -1.02), to_world(a, mx + 0.82, -1.02), to_world(a, mx + 0.82, 1.02),
             to_world(a, mx - 0.82, 1.02)]
        poly(ax, c, fc='#F4EDE2', lw=0.4, z=3)
        ax.add_patch(Circle(to_world(a, 7.1, 0.05), 0.32, fc='#E3D2BA', ec=INK, lw=0.4, zorder=3))
        n = [1, 2, 3, 4, 5, 6, 7, 8, 9]
        idx = [kk for kk in range(P.N_SLOTS) if kk != P.STAIR_SLOT].index(k)
        label(ax, *to_world(a, 6.2, 0.0), 'R%d' % (idx + 1), 9, weight='bold')
        label(ax, *to_world(a, 5.85, 0.0), state, 5.5, color='#6B5E55', rotation=(a - 90 + 90) % 180 - 90)
    # walkway, pad, net
    poly(ax, [pol(P.R_PAD_OUT, a) for a in range(0, 360, 2)], fc='none', lw=0.5, z=4)
    ax.add_patch(Circle((0, 0), P.R_PAD_OUT, fc='#E7D9BF', ec=INK, lw=0.6, zorder=4))
    ax.add_patch(Circle((0, 0), P.R_NET, fc='white', ec=INK, lw=0.6, zorder=4))
    # net: rope pattern
    for j in range(P.N_NET_RADIAL):
        a = 360 * j / P.N_NET_RADIAL + 360 / P.N_NET_RADIAL / 2
        p0, p1 = pol(P.NET_RING_RADII[0], a), pol(P.R_NET, a)
        ax.plot([p0[0], p1[0]], [p0[1], p1[1]], color=NETC, lw=0.8, zorder=5)
    for rr in P.NET_RING_RADII:
        circle(ax, rr, ec=NETC, lw=0.8, zorder=5)
    # fine mesh (diagonal hatch, symbolic)
    import numpy as np
    s = 0.30
    for c in np.arange(-8, 8, s):
        for sign in (1, -1):
            xs = np.linspace(-P.R_NET, P.R_NET, 200)
            ys = sign * xs + c
            m = xs ** 2 + ys ** 2 < P.R_NET ** 2
            if m.any():
                ax.plot(xs[m], ys[m], color='#CFC5B5', lw=0.25, zorder=4.5)
    label(ax, 0, 0.65, 'NET', 13, weight='bold')
    label(ax, 0, -0.2, 'walkable, see-through\n45 mm mesh between\nradial + ring ropes', 6.5)
    label(ax, *pol(4.08, 245), 'padded edge', 5.5, rotation=-25)
    label(ax, *pol(4.85, 262), 'walkway', 6.5, rotation=-8)
    # stair
    for k in (P.STAIR_SLOT,):
        pass
    stair_plan(ax, 'UF')
    label(ax, *to_world(SA, 5.85, 0.0), 'stair landing', 5.5)
    label(ax, *to_world(SA, 8.2, 2.0), 'linen\nstore', 5.5, color='#6B5E55')
    # dims
    dim_radial(ax, 322, 0, P.R_NET, 'Ø 7.80 usable', size=6.5)
    dim_radial(ax, 338, P.R_PAD_OUT, P.APOTHEM_FRONT, '1.10', size=6)
    ax.annotate('', xy=(-P.R_OUT, -11.5), xytext=(P.R_OUT, -11.5),
                arrowprops=dict(arrowstyle='<|-|>', lw=0.5, color=INK, mutation_scale=6))
    label(ax, 0, -11.2, 'Ø 20.00', 7.5)
    north_arrow(ax, 11.3, 10.2)
    scale_bar(ax, -12.3, -12.2)
    notes = ('Rooms\n'
             '• Front: 3 shoji-type panels (oak frame, linen\n   or paper-laminate infill). One fixed, two sliding:\n'
             '   closed / half (1.1 m) / open (2.2 m)\n'
             '• One low window per room (sill 0.45 m, 1.6 m wide)\n'
             '   behind outside larch battens: light and air, no\n   view in; inside shutter or curtain\n'
             '• Acoustic partitions 160 mm, clay plaster\n'
             '• Floor mattress, cushions, lanterns, shelf niche\n\n'
             'Stair (hall -> upper floor -> roof terrace)\n'
             '• Helical stair around a wooden trunk, Ø 2.9 m,\n   treads 1.25 m wide, in a slatted larch screen\n'
             '• Exactly one turn per storey: 22 risers × 180 mm,\n   so you get on and off at the front of the slot\n'
             '• Going 243 mm on the walking line (r = 0.85 m)\n'
             '• Upper floor -> terrace: 17 risers × 185 mm\n'
             '• A straight flight (≈5.3 m) does not fit the 4.1 m\n   slot; a stacked U-stair leaves no room for\n   the roof exit next to the dome.')
    fig.text(tx + 0.02, 0.60, notes, fontsize=10, color=INK, va='top', linespacing=1.45)
    return fig


# ---------------------------------------------------------------------------
def section():
    fig, ax, tx = sheet(-12.5, 17.5, -1.5, 12.5, 'Section A–A',
                        'North–south through the centre\n(looking east)')
    rs, zc = P.dome_sphere()
    g = '#B8AC98'
    ax.plot([-15, 17.5], [-0.05, -0.05], color=INK, lw=1.0)
    ax.add_patch(Rectangle((-15, -1.0), 32.5, 0.95, fc='#EFE8DC', ec='none', zorder=0))

    def R(x0, z0, x1, z1, fc=POCHE, lw=0.6, zo=3, **kw):
        ax.add_patch(Rectangle((x0, z0), x1 - x0, z1 - z0, fc=fc, ec=INK, lw=lw, zorder=zo, **kw))

    # hall floor slab
    R(-P.R_OUT, -0.35, P.R_OUT, 0.0, fc='#CDBFAF')
    # outer walls (N = +y right, S = left). North: entry door 0..2.4 + UF window
    uw0, uw1 = P.FFL_UF + P.UF_WINDOW['sill'], P.FFL_UF + P.UF_WINDOW['head']
    for s in (-1, 1):
        x0, x1 = sorted((s * P.R_IN, s * P.R_OUT))
        R(x0, 2.4, x1, uw0)
        R(x0, uw1, x1, P.CEIL_UF)
        ax.plot([x0 + 0.15, x0 + 0.15], [uw0, uw1], color=INK, lw=0.4)
        ax.plot([x0 + 0.2, x0 + 0.2], [uw0, uw1], color=INK, lw=0.4)
        # battens
        xb = s * (P.R_OUT + 0.06)
        ax.plot([xb, xb], [P.FFL_UF - 0.25, P.TERRACE_Z + P.RAIL_H], color='#8C6E50', lw=1.2, ls=(0, (1, 0.5)))
        R(min(xb - 0.07 * s, xb + 0.07 * s), P.TERRACE_Z + P.RAIL_H, max(xb - 0.07 * s, xb + 0.07 * s),
          P.TERRACE_Z + P.RAIL_H + 0.06, fc=WOOD, lw=0.4)
    # slabs (upper floor) both sides
    for s in (-1, 1):
        x0, x1 = sorted((s * P.RING_BEAM_OUT, s * P.R_IN))
        R(x0, P.CEIL_GF, x1, P.FFL_UF, fc='#B79B7E')
        # beam in the cut plane (beams every 18 deg incl. 90/270)
        R(x0, P.CEIL_GF - P.BEAM_D, x1, P.CEIL_GF, fc=WOOD)
        # ring beam
        x0, x1 = sorted((s * P.RING_BEAM_IN, s * P.RING_BEAM_OUT))
        R(x0, P.RING_BEAM_BOT, x1, P.RING_BEAM_TOP, fc=WOOD)
        # pad
        x0, x1 = sorted((s * P.R_NET, s * P.R_PAD_OUT))
        ax.add_patch(matplotlib.patches.FancyBboxPatch((x0 + 0.02, P.RING_BEAM_TOP), x1 - x0 - 0.04, P.PAD_T,
                                                       boxstyle='round,pad=0,rounding_size=0.05',
                                                       fc='#E7D9BF', ec=INK, lw=0.6, zorder=4))
        # room front (shoji) at apothem
        xf = s * (P.APOTHEM_FRONT + 0.06)
        R(xf - 0.03, P.FFL_UF, xf + 0.03, P.FFL_UF + P.DOOR_H, fc='#F3E6CC')
        R(xf - 0.08, P.FFL_UF + P.DOOR_H, xf + 0.08, P.FFL_UF + P.DOOR_H + 0.12, fc=WOOD)
        R(xf - 0.01, P.FFL_UF + P.DOOR_H + 0.12, xf + 0.01, P.CEIL_UF, fc='#F3E6CC')
        # fascia + dome ring
        x0, x1 = sorted((s * (P.APOTHEM_FRONT - 0.05), s * (P.APOTHEM_FRONT + 0.2)))
        R(x0, P.CEIL_UF, x1, P.ROOF_Z_IN, fc=CLAY)
        x0, x1 = sorted((s * (P.APOTHEM_FRONT - 0.05), s * (P.R_DOME + 0.25)))
        R(x0, P.ROOF_Z_IN - 0.02, x1, P.DOME_BASE_Z + 0.02, fc=WOOD)
        # roof (sloped top)
        xa_, xb_ = s * (P.APOTHEM_FRONT + 0.05), s * (P.R_OUT + P.ROOF_OVERHANG)
        ax.add_patch(Polygon([(xa_, P.CEIL_UF), (xb_, P.CEIL_UF), (xb_, P.ROOF_Z_OUT), (xa_, P.ROOF_Z_IN)],
                             fc='#B79B7E', ec=INK, lw=0.6, zorder=3))
        x0, x1 = sorted((s * (P.R_DOME + 0.25), s * P.R_TERRACE_OUT))
        R(x0, P.ROOF_Z_IN, x1, P.TERRACE_Z, fc='#D8C09C', lw=0.5)
        x0, x1 = sorted((s * (P.R_DOME + 0.25), s * (P.R_DOME + 0.72)))
        R(x0, P.TERRACE_Z + 0.36, x1, P.TERRACE_Z + 0.44, fc=WOOD, lw=0.5)
        x0, x1 = sorted((s * (P.R_TERRACE_OUT - 0.55), s * (P.R_TERRACE_OUT - 0.05)))
        R(x0, P.TERRACE_Z, x1, P.TERRACE_Z + 0.5, fc='#7E5A3B', lw=0.5)
        # room furniture silhouettes
        xm = s * 8.45
        R(xm - 0.82, P.FFL_UF, xm + 0.82, P.FFL_UF + 0.32, fc='#F4EDE2', lw=0.4)
    # garden door S / entry door N
    for s, lab in ((-1, 'garden doors'), (1, 'entrance')):
        x0, x1 = sorted((s * P.R_IN, s * P.R_OUT))
        ax.plot([(x0 + x1) / 2] * 2, [0, 2.4], color=INK, lw=0.4)
        label(ax, s * (P.R_IN - 0.9), 1.2, lab, 6.5, rotation=90)
    # plinth
    for s in (-1, 1):
        x0, x1 = sorted((s * P.R_OUT, s * (P.R_OUT + 0.08)))
        R(x0, -0.05, x1, 0.35, fc='#8A8076', lw=0.4)
    # dome (glass arc + rib)
    import numpy as np
    th1 = math.asin(P.R_DOME / rs)
    th0 = math.asin(P.DOME_OCULUS_R / rs)
    for sgn in (-1, 1):
        th = np.linspace(th0, th1, 80)
        ax.plot(sgn * rs * np.sin(th), zc + rs * np.cos(th), color='#3F5D6C', lw=1.4, zorder=5)
        ax.plot(sgn * (rs - 0.2) * np.sin(th), zc + (rs - 0.2) * np.cos(th), color=WOOD, lw=2.0, zorder=4)
    zcr = P.dome_z(P.DOME_OCULUS_R)
    R(-P.DOME_OCULUS_R - 0.05, zcr - 0.2, -P.DOME_OCULUS_R + 0.1, zcr + 0.4, fc='#4B4036')
    R(P.DOME_OCULUS_R - 0.1, zcr - 0.2, P.DOME_OCULUS_R + 0.05, zcr + 0.4, fc='#4B4036')
    ax.plot([-P.DOME_OCULUS_R - 0.1, P.DOME_OCULUS_R + 0.1], [zcr + 0.44] * 2, color='#3F5D6C', lw=1.4)
    label(ax, 1.6, zcr + 0.55, 'crown ring + vent', 6.5, ha='left')
    label(ax, -6.9, P.TERRACE_Z + 0.75, 'bench on the\ndome upstand', 6, ha='right')
    # pillars beyond (elevation, light)
    for k in range(P.N_PILLARS):
        a = P.partition_angle(k)
        xk, yk = pol(P.R_PILLAR, a)
        if xk < 0:
            continue
        y = yk
        ax.add_patch(Polygon([(y - 0.2, 0), (y + 0.2, 0), (y + 0.17, 2.35), (y + 0.55 * abs(math.cos(rad(a))) + 0.1, P.RING_BEAM_BOT),
                              (y - 0.55 * abs(math.cos(rad(a))) - 0.1, P.RING_BEAM_BOT), (y - 0.17, 2.35)],
                             fc='#EADBC6', ec='#8C7A6A', lw=0.5, zorder=1))
    # net: rest + loaded sag
    xs = np.linspace(-P.RING_BEAM_IN, P.RING_BEAM_IN, 200)
    ax.plot(xs, [P.net_z(abs(x)) for x in xs], color=INK, lw=1.3, zorder=6)
    ax.plot(xs, [P.net_z(abs(x), P.NET_SAG_MAX) for x in xs], color='#A34A2A', lw=0.8, ls=(0, (4, 2)), zorder=6)
    zlow = P.Z_NET_EDGE - P.NET_SAG_MAX
    label(ax, 1.2, zlow - 0.3, 'loaded sag ≈ 0.90 (design, to confirm)', 6.5, color='#A34A2A', ha='left')
    # standing person under the net + clearance
    def person(x, z0, h=1.85, fc='#D9C2A8'):
        ax.add_patch(Circle((x, z0 + h - 0.12), 0.11, fc=fc, ec=INK, lw=0.4, zorder=7))
        ax.add_patch(matplotlib.patches.FancyBboxPatch((x - 0.2, z0), 0.4, h - 0.26, boxstyle='round,pad=0,rounding_size=0.12',
                                                       fc=fc, ec=INK, lw=0.4, zorder=7))
    person(-0.9, 0.0)
    ax.annotate('', xy=(-0.4, zlow), xytext=(-0.4, 1.85), arrowprops=dict(arrowstyle='<|-|>', lw=0.5, color=INK,
                                                                         mutation_scale=6), zorder=8)
    label(ax, -0.15, (zlow + 1.85) / 2, '≥ 1.1 m\nclear', 6.5, ha='left')
    # lying people on net
    for x in (0.6, 2.4):
        ax.add_patch(matplotlib.patches.FancyBboxPatch((x - 0.85, P.net_z(abs(x)) - 0.02), 1.7, 0.24,
                     boxstyle='round,pad=0,rounding_size=0.1', fc='#D9C2A8', ec=INK, lw=0.4, zorder=7))
    person(-7.6, P.FFL_UF, 1.8)
    person(7.6, P.TERRACE_Z, 1.8)
    label(ax, 8.6, P.TERRACE_Z + 1.6, 'roof terrace', 7.5, ha='left')
    # sun rays
    for x0 in (-3.3, -1.0, 1.3):
        el = rad(57)
        z1 = 11.5
        x1 = x0 - (z1 - 0) / math.tan(el) * -1
        ax.plot([x0 - (z1 / math.tan(el)), x0], [z1, 0], color=LIGHT, lw=1.0, ls=(0, (6, 3)), zorder=1, alpha=0.8)
    label(ax, -9.2, 11.6, 'sun, noon in summer (~57°)', 6.5, color='#9A6B12', ha='left')
    # variant rope
    ax.plot([0, 0], [P.Z_NET_EDGE - 0.05, zcr - 0.3], color='#5B7B8C', lw=0.9, ls=(0, (2, 2)), zorder=5)
    label(ax, 0.15, 6.3, 'variant: single rope from\nthe crown ring (not the glass)', 6.2, color='#3F5D6C', ha='left')
    # annex (north, right)
    RA, RB, RC_ = P.R_OUT, P.ANNEX_R_CORR, P.ANNEX_R_OUT
    R(RA, P.ANNEX_H, RC_ + 0.5, P.ANNEX_H + 0.35, fc='#B79B7E')
    ax.plot([RA, RC_ + 0.5], [P.ANNEX_H + 0.39] * 2, color='#6B7A3A', lw=2.2)
    R(RB, 0, RB + 0.12, P.ANNEX_H, fc=POCHE)
    R(RC_ - 0.35, 0, RC_, 2.1, fc=POCHE)
    R(RC_ - 0.35, 2.9, RC_, P.ANNEX_H, fc=POCHE)
    ax.plot([RC_ - 0.18] * 2, [2.1, 2.9], color=INK, lw=0.5)
    R(RA, -0.35, RC_, 0.0, fc='#CDBFAF')
    label(ax, (RA + RB) / 2, 1.6, 'corridor', 6.5, rotation=90)
    label(ax, (RB + RC_) / 2, 1.3, 'changing /\nshowers', 7)
    # labels rooms / hall
    label(ax, 7.7, P.FFL_UF + 1.9, 'room (R1)', 7.5)
    label(ax, -7.5, P.FFL_UF + 2.15, 'room (R5)', 7.5)
    label(ax, 5.0, 1.0, 'HALL', 10, weight='bold')
    label(ax, -4.85, P.FFL_UF + 1.5, 'walkway', 6.5, rotation=90)
    label(ax, 0, 8.1, 'glass dome Ø 11.20', 7, color='#3F5D6C')
    # levels
    levels = [(0.0, '±0.00 hall'), (P.CEIL_GF, '+3.56 ceiling hall'), (P.FFL_UF, '+3.96 upper floor'),
              (P.Z_NET_EDGE, '+3.84 net at edge'), (P.CEIL_UF, '+6.56 ceiling rooms'),
              (P.TERRACE_Z, '+7.10 roof terrace'), (P.DOME_BASE_Z, '+7.55 dome base'),
              (P.TERRACE_Z + P.RAIL_H, '+8.30 railing'), (P.DOME_BASE_Z + P.DOME_RISE, '+10.15 dome top')]
    for i, (z, t) in enumerate(levels):
        x = -12.3
        ax.plot([x, x + 0.6], [z, z], color=INK, lw=0.5)
        ax.add_patch(Polygon([(x + 0.3, z), (x + 0.15, z + 0.18), (x + 0.45, z + 0.18)], fc=INK, ec=INK, lw=0.3))
        dz = {'+3.84': -0.22, '+3.56': -0.2, '+3.96': 0.18, '+7.10': -0.15, '+7.55': 0.12}.get(t[:5], 0.1)
        label(ax, x + 0.7, z + dz, t, 6.5, ha='left')
    scale_bar(ax, 12.0, -1.2)
    notes = ('Net and structure (concept, to be verified)\n'
             '• Closed ring beam (glulam or steel box) on 10\n   tree pillars takes the inward pull of the net\n'
             '• 16 radial + 3 ring ropes, fine 45 mm mesh,\n   tensioners at every radial under the pad\n'
             '• No central support: middle, light and view clear\n'
             '• Net at +3.84 at the edge, 0.15 m pre-sag;\n   design sag under load ≈ 0.9 m leaves\n'
             '   ≥ 1.1 m above a 1.9 m person below\n'
             '• Variant: one rope from a steel spider in the\n   crown ring (dome structure, not glass) –\n'
             '   ribs + ring must then carry that load')
    fig.text(tx + 0.02, 0.80, notes, fontsize=10, color=INK, va='top', linespacing=1.45)
    return fig


def roof_plan():
    fig, ax, tx = sheet(-12.5, 12.5, -12.5, 12.5, 'Roof terrace',
                        'Flat roof over the room ring as a round terrace\n'
                        'around the dome, deck at +7.10\n'
                        '• Deck 4.1 m wide (bench ring to railing)\n'
                        '• Railing 1.20 m: the facade battens continue\n'
                        '   up and get a timber handrail\n'
                        '• Dome on a 45 cm upstand = bench height,\n'
                        '   keeps feet off the glass\n'
                        '• Round stair house with a door on each side:\n'
                        '   you walk through it to go all the way round')
    ax.add_patch(Circle((0, 0), P.R_OUT + 0.1, fc='#EFE5D6', ec=INK, lw=0.6, zorder=1))
    circle(ax, P.R_OUT + 0.07, ec='#8C6E50', lw=2.2, ls=(0, (0.6, 0.6)), zorder=3)
    circle(ax, P.R_TERRACE_OUT, ec=INK, lw=0.5, zorder=3)
    # deck boards (rings)
    for rr in [P.R_DOME + 0.25 + 0.36 * i for i in range(12)]:
        if rr < P.R_TERRACE_OUT:
            circle(ax, rr, ec='#CDB89A', lw=0.3, zorder=2)
    # bench ring + upstand
    a0, a1 = SA + 19, SA + 341
    poly(ax, sector_poly(P.R_DOME + 0.25, P.R_DOME + 0.72, a0, a1), fc=WOOD, lw=0.5, z=4)
    ax.add_patch(Circle((0, 0), P.R_DOME + 0.25, fc='#C9A57A', ec=INK, lw=0.6, zorder=4))
    # dome glass + ribs
    ax.add_patch(Circle((0, 0), P.R_DOME, fc='#DCE8EC', ec='#3F5D6C', lw=0.8, zorder=5))
    for j in range(P.N_DOME_RIBS):
        a = 360 * j / P.N_DOME_RIBS
        p0, p1 = pol(P.DOME_OCULUS_R, a), pol(P.R_DOME, a)
        ax.plot([p0[0], p1[0]], [p0[1], p1[1]], color=WOOD, lw=1.0, zorder=6)
    for rr in (2.4, 4.1):
        circle(ax, rr, ec=WOOD, lw=0.6, zorder=6)
    ax.add_patch(Circle((0, 0), P.DOME_OCULUS_R + 0.05, fc='#4B4036', ec=INK, lw=0.5, zorder=7))
    label(ax, 0, 1.2, 'GLASS DOME', 11, weight='bold', color='#3F5D6C')
    label(ax, 0, 0.35 - 1.3, 'Ø 11.20, on a 45 cm upstand\nvent at the crown', 7, color='#3F5D6C')
    # planters
    for k in range(P.N_SLOTS):
        if k == P.STAIR_SLOT:
            continue
        a = P.slot_center(k)
        poly(ax, sector_poly(P.R_TERRACE_OUT - 0.55, P.R_TERRACE_OUT - 0.05, a - 7, a + 7), fc='#9DAA7A', lw=0.4, z=4)
    # stair house
    stair_plan(ax, 'RF')
    DOORS = [(119, 143), (226, 250)]
    cuts = sorted({0.0, 360.0} | {a for d in DOORS for a in d})
    for a0, a1 in zip(cuts[:-1], cuts[1:]):
        if any(d0 < (a0 + a1) / 2 < d1 for d0, d1 in DOORS):
            continue
        ax.add_patch(Polygon(harc(P.HELIX_CAGE_R + 0.16, a0, a1, 30) + harc(P.HELIX_CAGE_R + 0.02, a1, a0, 30),
                             closed=True, fc=POCHE, ec=INK, lw=0.5, zorder=8))
    for d0, d1 in DOORS:
        ax.plot(*zip(*harc(P.HELIX_CAGE_R + 0.09, d0, d1, 12)), color=INK, lw=1.2, zorder=8)
        p = HWp((d0 + d1) / 2, P.HELIX_CAGE_R + 0.7)
        label(ax, p[0], p[1], 'door', 6.5)
    p = HWp(0, 2.35)
    label(ax, p[0], p[1], 'stair house\n(roof +9.65)', 6.5)
    label(ax, *pol(7.9, 250), 'TERRACE', 11, weight='bold', rotation=-20)
    label(ax, *pol(7.9, 30), 'timber deck', 7, rotation=-60)
    label(ax, *pol(6.35, 300), 'bench', 6.5, rotation=30)
    label(ax, *pol(9.35, 342), 'planters,\ngrasses', 6, rotation=-18)
    label(ax, *pol(11.0, 300), 'railing 1.20 m (larch battens)', 6.5, rotation=30)
    ax.set_ylim(-12.5, 12.5)
    dim_radial(ax, 322, P.R_DOME + 0.72, P.R_TERRACE_OUT, 'deck ≈ 3.2', size=6)
    north_arrow(ax, 11.3, 10.2)
    scale_bar(ax, -12.3, -12.2)
    notes = ('Notes\n'
             '• Roof built as a walkable flat roof: loads for people\n   (≈ 4 kN/m²), falls to internal outlets, deck on pedestals\n'
             '• Railing is see-through at an angle only; raise to\n   ≈ 1.8 m (or add screens) if people want to sunbathe\n   undressed without being seen from further away\n'
             '• Stair house doubles as rain shelter; lantern inside\n'
             '• Annex keeps its green (sedum) roof, not walkable')
    fig.text(tx + 0.02, 0.60, notes, fontsize=10, color=INK, va='top', linespacing=1.45)
    return fig


if __name__ == '__main__':
    for name, fn in (('01_ground_floor_plan', ground_floor), ('02_upper_floor_plan', upper_floor),
                     ('03_roof_terrace_plan', roof_plan), ('04_section_AA', section)):
        f = fn()
        f.savefig(os.path.join(HERE, name + '.pdf'))
        f.savefig(os.path.join(HERE, name + '.png'), dpi=110)
        plt.close(f)
        print('wrote', name)
