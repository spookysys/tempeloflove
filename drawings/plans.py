"""2D drawings from the shared params: ground floor, upper floor, roof terrace, section A-A.

    python3 plans.py   -> *.pdf (vector, 1:100 on A2) and *.png next to this file
"""
import math
import os
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Polygon, Circle, Rectangle, Arc, FancyBboxPatch  # noqa: E402
import numpy as np  # noqa: E402

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
GLASS = '#5B7B8C'
GREEN = '#9DAA7A'
A2 = (23.386, 16.535)
SCALE = 100.0
FACE_OPEN = P.face_openings()
RC = P.front_corner_radius()
SA = P.slot_center(P.STAIR_SLOT)
ROOM_SLOTS = [k for k in range(P.N_SLOTS) if k != P.STAIR_SLOT]
ROOMS = [k for k in ROOM_SLOTS if k != P.BATH_SLOT]
DOOR_STATES = {0: 'closed', 2: 'open', 3: 'half', 4: 'closed', 5: 'open', 6: 'closed', 7: 'half'}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def pol(r, a):
    return (r * math.cos(rad(a)), r * math.sin(rad(a)))


def arc_pts(r, a0, a1, n=None):
    n = n or max(2, int(abs(a1 - a0) / 1.0) + 1)
    return [pol(r, a0 + (a1 - a0) * i / (n - 1)) for i in range(n)]


def FP(k, n, t):
    """face-local (n along the face normal, t along the face) -> plan x, y"""
    a = rad(P.slot_center(k))
    return (n * math.cos(a) - t * math.sin(a), n * math.sin(a) + t * math.cos(a))


def oct_pts(apo):
    return [pol(P.octo_r(P.partition_angle(k), apo), P.partition_angle(k)) for k in range(P.N_SLOTS)]


def to_world(k_angle, u, v):
    a = rad(k_angle)
    return (u * math.cos(a) - v * math.sin(a), u * math.sin(a) + v * math.cos(a))


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
    tx = max(left + w_in / A2[0] + 0.04, 0.66)
    fig.text(tx, 0.93, title, fontsize=24, color=INK, weight='bold', va='top')
    fig.text(tx, 0.885, subtitle, fontsize=12, color=INK, va='top', linespacing=1.5)
    fig.text(tx, 0.045, 'Tempel – seminar building at ZEGG, Bad Belzig · concept v0.3\n'
             'Scale 1:100 on A2 · dimensions in metres\n'
             'Not for construction: structure, net and fire safety to be\n'
             'verified by a structural engineer, a net maker and a fire engineer.',
             fontsize=9, color='#6B5E55', va='bottom', linespacing=1.5)
    return fig, ax, tx


def poly(ax, pts, fc=POCHE, ec=INK, lw=0.6, z=2, **kw):
    ax.add_patch(Polygon(pts, closed=True, fc=fc, ec=ec, lw=lw, zorder=z, **kw))


def seg_wall(ax, p0, p1, t, fc=POCHE, lw=0.6, z=2):
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    L = math.hypot(dx, dy)
    nx, ny = -dy / L * t / 2, dx / L * t / 2
    poly(ax, [(p0[0] + nx, p0[1] + ny), (p1[0] + nx, p1[1] + ny), (p1[0] - nx, p1[1] - ny),
              (p0[0] - nx, p0[1] - ny)], fc=fc, lw=lw, z=z)


def rect_face(ax, k, n0, n1, t0, t1, **kw):
    poly(ax, [FP(k, n0, t0), FP(k, n1, t0), FP(k, n1, t1), FP(k, n0, t1)], **kw)


def circle(ax, r, c=(0, 0), **kw):
    kw.setdefault('fill', False)
    ax.add_patch(Circle(c, r, **kw))


def label(ax, x, y, s, size=8, **kw):
    kw.setdefault('ha', 'center')
    kw.setdefault('va', 'center')
    kw.setdefault('color', INK)
    ax.text(x, y, s, fontsize=size, zorder=12, **kw)


def north_arrow(ax, x, y, s=1.2):
    ax.add_patch(Polygon([(x, y + s), (x - s * 0.35, y - s * 0.5), (x, y - s * 0.2)], fc=INK, ec=INK, lw=0.5))
    ax.add_patch(Polygon([(x, y + s), (x + s * 0.35, y - s * 0.5), (x, y - s * 0.2)], fc='white', ec=INK, lw=0.5))
    ax.text(x, y + s * 1.25, 'N', ha='center', va='bottom', fontsize=11, weight='bold', color=INK)


def scale_bar(ax, x, y):
    for i in range(5):
        ax.add_patch(Rectangle((x + i, y), 1, 0.18, fc=INK if i % 2 == 0 else 'white', ec=INK, lw=0.5))
    ax.text(x, y - 0.25, '0', fontsize=7, ha='center', va='top')
    ax.text(x + 5, y - 0.25, '5 m', fontsize=7, ha='center', va='top')


def dim(ax, p0, p1, text, size=7):
    ax.annotate('', xy=p1, xytext=p0, arrowprops=dict(arrowstyle='<|-|>', lw=0.5, color=INK, mutation_scale=6),
                zorder=11)
    m = ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2)
    ang = math.degrees(math.atan2(p1[1] - p0[1], p1[0] - p0[0]))
    ang = (ang + 90) % 180 - 90
    ax.text(m[0], m[1], text, fontsize=size, color=INK, ha='center', va='center', zorder=12, rotation=ang,
            bbox=dict(fc='white', ec='none', pad=0.6, alpha=0.9))


def fdim(ax, k, n0, t0, n1, t1, text, size=6.5, ext=None):
    """dimension in face-local coords; ext = (n or None, t or None) extension-line origin per end"""
    p0, p1 = FP(k, n0, t0), FP(k, n1, t1)
    if ext:
        for (n, t) in ((n0, t0), (n1, t1)):
            q = FP(k, ext[0] if ext[0] is not None else n, ext[1] if ext[1] is not None else t)
            ax.plot(*zip(q, FP(k, n, t)), color=INK, lw=0.3, zorder=11)
    dim(ax, p0, p1, text, size=size)


def chain(ax, k, t, stations, texts, size=6, ext_t=None):
    """radial dimension chain along face k at offset t through the n-stations"""
    for i in range(len(stations) - 1):
        dim(ax, FP(k, stations[i], t), FP(k, stations[i + 1], t), texts[i], size=size)
    for n in stations:
        ax.plot(*zip(FP(k, n, t - 0.18), FP(k, n, t + 0.18)), color=INK, lw=0.5, zorder=11)


def legend(fig, tx, y0, items):
    fig.text(tx, y0, 'Legend', fontsize=11, weight='bold', color=INK)
    for i, (t, st) in enumerate(items):
        y = y0 - 0.03 - i * 0.028
        st = dict(st)
        st.setdefault('ec', INK)
        fig.patches.append(Rectangle((tx, y), 0.016, 0.016, transform=fig.transFigure, lw=0.5, **st))
        fig.text(tx + 0.024, y + 0.003, t, fontsize=10, color=INK)


def octagon_wall(ax, zcut, faces=range(P.N_SLOTS)):
    """Outer wall cut at zcut: poché, gaps for openings cut there, dashed marks for openings above."""
    for k in faces:
        holes = [o for o in FACE_OPEN[k] if o[2] < zcut < o[3]]
        above = [o for o in FACE_OPEN[k] if zcut <= o[2] < zcut + 2.2]
        ts = sorted({h[0] for h in holes} | {h[1] for h in holes})
        bounds = [None] + ts + [None]
        for i in range(len(bounds) - 1):
            ta, tb = bounds[i], bounds[i + 1]
            lo = -99 if ta is None else ta
            hi = 99 if tb is None else tb
            if any(h[0] < (lo + hi) / 2 < h[1] for h in holes):
                continue
            ti0 = -P.face_half(P.R_IN) if ta is None else ta
            to0 = -P.face_half(P.R_OUT) if ta is None else ta
            ti1 = P.face_half(P.R_IN) if tb is None else tb
            to1 = P.face_half(P.R_OUT) if tb is None else tb
            poly(ax, [FP(k, P.R_IN, ti0), FP(k, P.R_OUT, to0), FP(k, P.R_OUT, to1), FP(k, P.R_IN, ti1)])
        for (t0, t1, zb, zt, kind) in holes:
            for tt in (t0, t1):
                ax.plot(*zip(FP(k, P.R_IN, tt), FP(k, P.R_OUT, tt)), color=INK, lw=0.5, zorder=5)
            if kind.startswith('window'):
                for n in (P.R_IN + 0.12, P.R_IN + 0.17):
                    ax.plot(*zip(FP(k, n, t0), FP(k, n, t1)), color=INK, lw=0.5, zorder=5)
                continue
            w = t1 - t0
            leaves = [(t0, 1), (t1, -1)] if kind in ('door_entry', 'door_garden') else [(t0, 1)]
            leaf = w / len(leaves)
            for tt, s in leaves:
                hinge = FP(k, P.R_IN, tt)
                tip = FP(k, P.R_IN - leaf, tt)
                end = FP(k, P.R_IN, tt + s * leaf)
                ax.plot(*zip(hinge, tip), color=INK, lw=0.8, zorder=5)
                a_tip = math.degrees(math.atan2(tip[1] - hinge[1], tip[0] - hinge[0]))
                a_end = math.degrees(math.atan2(end[1] - hinge[1], end[0] - hinge[0]))
                lo_, hi_ = sorted((a_tip, a_end))
                if hi_ - lo_ > 180:
                    lo_, hi_ = hi_, lo_ + 360
                ax.add_patch(Arc(hinge, 2 * leaf, 2 * leaf, theta1=lo_, theta2=hi_, color=INK, lw=0.4, zorder=5))
        for (t0, t1, zb, zt, kind) in above:
            ax.plot(*zip(FP(k, P.R_IN - 0.25, t0), FP(k, P.R_IN - 0.25, t1)), color=INK, lw=0.5,
                    ls=(0, (3, 2)), zorder=5)


# ---------------------------------------------------------------------------
# straight stair along the NW wall (hall -> upper floor), open to the hall
# ---------------------------------------------------------------------------
KS = P.STAIR_SLOT
G_T = P.STAIR_GOING_T
NS0 = P.R_IN - P.STAIR_FLIGHT_W_T
NS1 = P.R_IN - 0.02
T0S = P.STAIR_T0
NT_S = P.STAIR_RISERS - 1
T_TOPS = T0S + NT_S * G_T
T_VOID = T0S + 7 * G_T


def clip_halfplane(pts, k, lim):
    """Sutherland-Hodgman: keep the part of the polygon with (p . face-normal k) <= lim"""
    a = rad(P.slot_center(k))
    d = lambda q: q[0] * math.cos(a) + q[1] * math.sin(a) - lim   # noqa: E731
    out = []
    for i in range(len(pts)):
        p, q = pts[i], pts[(i + 1) % len(pts)]
        dp, dq = d(p), d(q)
        if dp <= 0:
            out.append(p)
        if (dp < 0) != (dq < 0) and dp != dq:
            s = dp / (dp - dq)
            out.append((p[0] + (q[0] - p[0]) * s, p[1] + (q[1] - p[1]) * s))
    return out


def stair_plan(ax, level):
    cut = 7 if level == 'GF' else None
    N_FAN = 5
    T_FAN = T0S + N_FAN * G_T
    for i in range(1, NT_S + 1):
        ta, tb = T0S + (i - 1) * G_T, T0S + i * G_T
        f = 1.6 * max(0.0, 1 - (i - 1) / N_FAN) ** 1.6
        above = level == 'GF' and i > cut
        if level == 'UF' and i < 8:
            continue
        if i <= N_FAN:                       # seating terraces: nested outlines reaching to the end of the fan
            if level == 'GF':
                pts = [FP(KS, NS0 - f, ta - 0.6 * f), FP(KS, NS1, ta - 0.6 * f), FP(KS, NS1, T_FAN),
                       FP(KS, NS0 - f, T_FAN)]
                poly(ax, clip_halfplane(pts, KS - 1, P.R_IN - 0.01), fc='#F1E6D6' if i % 2 else '#EADCC8',
                     ec=INK, lw=0.4, z=3 + i * 0.01)
            continue
        rect_face(ax, KS, NS0 + 0.02, NS1, ta, tb, fc='none' if above else WOOD,
                  ec='#9C8E80' if above else INK, lw=0.4, z=3.2, ls=(0, (2, 2)) if above else '-')
    if level == 'GF':
        # low clay bench under the floating flight, rope-net balustrade on the hall side
        rect_face(ax, KS, NS0 + 0.25, NS1, T_FAN, T_TOPS - 0.2, fc='#E6D6BF', ec=INK, lw=0.4, z=3.1)
        ax.plot(*zip(FP(KS, NS0 + 0.05, T_FAN + 0.13), FP(KS, NS0 + 0.05, T0S + cut * G_T)), color=NETC, lw=1.4,
                zorder=5)
    if level == 'GF':
        tc = T0S + cut * G_T
        ax.plot(*zip(FP(KS, NS0, tc), FP(KS, (NS0 + NS1) / 2, tc + 0.2), FP(KS, NS1, tc - 0.1)), color=INK,
                lw=0.8, zorder=6)
        ax.annotate('', xy=FP(KS, (NS0 + NS1) / 2, T0S + 4 * G_T), xytext=FP(KS, (NS0 + NS1) / 2, T0S + 0.1),
                    arrowprops=dict(arrowstyle='-|>', lw=0.8, color=INK), zorder=6)
        p = FP(KS, NS0 - 0.55, T0S + 0.4)
        label(ax, p[0], p[1], 'seating\nterraces', 5.5)
        p = FP(KS, NS0 + 0.95, T0S + 9.5 * G_T)
        label(ax, p[0], p[1], 'bench', 5.5)
        p = FP(KS, NS0 + 0.7, T0S + 1.2)
        label(ax, p[0], p[1], 'UP', 6.5, weight='bold')
    else:
        ax.annotate('', xy=FP(KS, (NS0 + NS1) / 2, T_VOID + 0.2), xytext=FP(KS, (NS0 + NS1) / 2, T_TOPS - 0.1),
                    arrowprops=dict(arrowstyle='-|>', lw=0.8, color=INK), zorder=6)
        p = FP(KS, (NS0 + NS1) / 2, T_TOPS - 1.0)
        label(ax, p[0], p[1], 'DN', 6.5, weight='bold')
        rect_face(ax, KS, NS0 - 0.12, NS0, T_VOID, T_TOPS, fc='#CDBFAF', lw=0.4, z=4)
        fr = P.APOTHEM_FRONT + P.FRONT_T
        rect_face(ax, KS, fr, NS0, -1.3, -1.18, fc=POCHE, lw=0.5, z=4)
        rect_face(ax, KS, NS0 - 0.12, NS0, T_VOID, -1.18, fc=POCHE, lw=0.5, z=4)
        rect_face(ax, KS, NS0 - 0.12, NS1, T_VOID - 0.12, T_VOID, fc=POCHE, lw=0.5, z=4)
        rect_face(ax, KS, fr - 0.12, fr, -P.face_half(fr) + 0.1, -2.35, fc=POCHE, lw=0.5, z=4)
        rect_face(ax, KS, fr - 0.12, fr, -1.45, -1.18, fc=POCHE, lw=0.5, z=4)
        rect_face(ax, KS, 6.2, 7.6, 1.55, 2.05, fc='#E6D6BF', lw=0.4, z=4)


# ---------------------------------------------------------------------------
# external stair on the stair-segment face
# ---------------------------------------------------------------------------
K_ = P.STAIR_SLOT
W_ = P.EXT_W
G_ = P.EXT_GOING
TL = P.EXT_T_LAND
N0, N1, N2 = P.R_OUT + 0.05, P.R_OUT + 0.05 + W_, P.R_OUT + 0.05 + 2 * W_
T_BOT = TL - (P.STAIR_RISERS - 1) * G_
T_TOP = TL - (P.TERRACE_RISERS - 1) * G_


def ext_stair(ax, level):
    fh = P.face_half(P.R_OUT) - 0.05
    solid = dict(fc='#EDE3D3', lw=0.5, z=4)
    dashed = dict(fc='none', lw=0.5, z=4, ls=(0, (3, 2)))
    if level == 'GF':
        n_cut = int((P.FFL_UF - 1.2) / P.STAIR_RISE)
        rect_face(ax, K_, N0, N1, T_BOT, TL - n_cut * G_, **solid)
        rect_face(ax, K_, N0, N1, TL - n_cut * G_, TL, **dashed)
        for i in range(n_cut, P.STAIR_RISERS):
            t = TL - i * G_
            ax.plot(*zip(FP(K_, N0, t), FP(K_, N1, t)), color=INK, lw=0.4, zorder=5)
        rect_face(ax, K_, N1, N2, T_TOP, TL, **dashed)
        rect_face(ax, K_, N0, N2, TL, fh, **dashed)
        p = FP(K_, (N0 + N1) / 2, T_BOT + 0.7)
        label(ax, p[0], p[1], 'UP', 6.5, weight='bold')
    elif level == 'UF':
        rect_face(ax, K_, N0, N2, TL, fh, fc='#E3D3BC', lw=0.6, z=4)
        rect_face(ax, K_, N0, N1, T_BOT, TL, **solid)
        for i in range(1, P.STAIR_RISERS):
            t = TL - i * G_
            ax.plot(*zip(FP(K_, N0, t), FP(K_, N1, t)), color=INK, lw=0.4, zorder=5)
        cut = TL - 6 * G_
        rect_face(ax, K_, N1, N2, cut, TL, **solid)
        rect_face(ax, K_, N1, N2, T_TOP, cut, **dashed)
        for j in range(1, 7):
            t = TL - j * G_
            ax.plot(*zip(FP(K_, N1, t), FP(K_, N2, t)), color=INK, lw=0.4, zorder=5)
        for (lab, n, t) in (('DN', (N0 + N1) / 2, TL - 1.2), ('UP', (N1 + N2) / 2, TL - 0.8)):
            p = FP(K_, n, t)
            label(ax, p[0], p[1], lab, 6.5, weight='bold')
        p = FP(K_, N2 + 1.0, TL - 1.0)
        label(ax, p[0], p[1], 'external stair\n(2nd escape route)', 6.5)
    else:
        rect_face(ax, K_, P.R_OUT - 0.02, N2, P.TERRACE_GATE[0] - 0.05, T_TOP, fc='#E3D3BC', lw=0.6, z=4)
        rect_face(ax, K_, N1, N2, T_TOP, TL, **solid)
        for j in range(1, P.TERRACE_RISERS):
            t = TL - j * G_
            ax.plot(*zip(FP(K_, N1, t), FP(K_, N2, t)), color=INK, lw=0.4, zorder=5)
        p = FP(K_, (N1 + N2) / 2, T_TOP + 0.9)
        label(ax, p[0], p[1], 'DN', 6.5, weight='bold')


# ---------------------------------------------------------------------------
def ground_floor():
    fig, ax, tx = sheet(-13.0, 16.5, -12.0, 18.0, 'Ground floor',
                        'Open hall ≈ 290 m², octagon 20.00 m across the flats\n'
                        'Clear height 3.74 m (3.52 m under the beams)\n'
                        'Only 4 slim columns (steel core Ø 219 in a Ø 30 cm\n'
                        'timber casing) carry the ring beam around the net\n'
                        'Big windows with deep window seats, garden doors\n'
                        'to the south, tea / party bar on the NE wall\n'
                        'Small annex on the north face: foyer with coats,\n'
                        'WC, tech. Showers + 2 WCs upstairs.\n'
                        'Light: paper pendants, indirect uplight ledge\n'
                        'above the windows, clay wall shells')
    ax.add_patch(Polygon(oct_pts(P.R_OUT + 0.6), closed=True, fc='none', ec='#B8AC98', lw=0.5, zorder=1))
    off = P.Z_NET_EDGE / math.tan(rad(61))
    ax.add_patch(Circle((0, off), P.R_PAD_OUT, fc=LIGHT, ec='none', alpha=0.18, zorder=1))
    label(ax, 0, off + 2.7, 'sun spot, noon in June\n(moves with the sun)', 6.5, color='#9A6B12', style='italic')
    octagon_wall(ax, 1.2)
    for k in range(P.N_SLOTS):
        for (t0, t1, zb, zt, kind) in FACE_OPEN[k]:
            if kind == 'window_gf':
                rect_face(ax, k, P.R_IN - 0.58, P.R_IN, t0 - 0.15, t1 + 0.15, fc='#F2E8DA', lw=0.4, z=3)
    for i in range(P.N_PILLARS):
        ax.add_patch(Circle(pol(P.R_PILLAR, P.PILLAR0_DEG + 90 * i), P.PILLAR_D / 2, fc=WOOD, ec=INK, lw=0.6,
                            zorder=6))
    for r in (P.RING_BEAM_IN, P.RING_BEAM_OUT):
        circle(ax, r, ec=INK, lw=0.5, ls=(0, (6, 3)), zorder=4)
    for i in range(P.N_BEAMS):
        a = i * 360 / P.N_BEAMS + 360 / P.N_BEAMS / 2
        p0, p1 = pol(P.RING_BEAM_OUT, a), pol(P.octo_r(a, P.R_IN), a)
        ax.plot([p0[0], p1[0]], [p0[1], p1[1]], color='#8C7A6A', lw=0.35, ls=(0, (2, 3)), zorder=2)
    circle(ax, 2.9, ec='#9C8A70', lw=0.5, zorder=3)
    for i in range(14):
        ax.add_patch(Circle(pol(2.45, 360 * i / 14 + 8), 0.25, fc='#E9DCC6', ec='#9C8A70', lw=0.4, zorder=3))
    stair_plan(ax, 'GF')
    ext_stair(ax, 'GF')
    p = FP(KS, NS0 - 1.3, -0.5)
    label(ax, p[0], p[1], 'open stair to the\nupper floor (1.50 m)', 6)
    p = FP(KS, NS0 + 0.75, T0S + 15 * G_T)
    label(ax, p[0], p[1], 'store', 5.5)
    # small annex on the north face: foyer + coats, WC, tech
    KE = P.ENTRY_SLOT
    AO = P.R_OUT + P.ANNEX_D
    T = 0.35
    for ta, tb in ((None, -3.9), (-2.2, -0.9), (0.9, 2.2), (3.9, None)):
        ti0 = -P.face_half(AO - T) if ta is None else ta
        to0 = -P.face_half(AO) if ta is None else ta
        ti1 = P.face_half(AO - T) if tb is None else tb
        to1 = P.face_half(AO) if tb is None else tb
        poly(ax, [FP(KE, AO - T, ti0), FP(KE, AO, to0), FP(KE, AO, to1), FP(KE, AO - T, ti1)])
    for t0, t1 in ((-3.9, -2.2), (2.2, 3.9)):
        for n in (AO - 0.15, AO - 0.2):
            ax.plot(*zip(FP(KE, n, t0), FP(KE, n, t1)), color=INK, lw=0.5, zorder=5)
    for a, side in ((P.partition_angle(KE), 1), (P.partition_angle(KE + 1), -1)):
        off = pol(T / 2, a + 90 * side)
        p0, p1 = pol(P.octo_r(a, P.R_OUT), a), pol(P.octo_r(a, AO - T), a)
        seg_wall(ax, (p0[0] + off[0], p0[1] + off[1]), (p1[0] + off[0], p1[1] + off[1]), T)
    for tt in (-2.6, 2.6):
        seg_wall(ax, FP(KE, P.R_OUT, tt), FP(KE, P.R_OUT + 3.1, tt), 0.12)
        seg_wall(ax, FP(KE, P.R_OUT + 4.0, tt), FP(KE, AO - T, tt), 0.12)
        rect_face(ax, KE, P.R_OUT + 1.3, P.R_OUT + 3.3, tt * 0.9 - 0.22, tt * 0.9 + 0.22, fc='#F2E8DA', lw=0.4, z=3)
    rect_face(ax, KE, AO, AO + 1.8, -1.8, 1.8, fc='none', lw=0.5, z=2, ls=(0, (3, 2)))
    ax.plot(*zip(FP(KE, P.R_IN - 0.6, -1.3), FP(KE, P.R_IN - 0.6, 1.3)), color=INK, lw=0.8, ls=(0, (1, 1)), zorder=6)
    for (n, t, txt, sz) in ((P.R_OUT + 2.5, 0, 'FOYER\ncoats, shoes', 7), (P.R_OUT + 2.6, -3.35, 'WC', 7),
                            (P.R_OUT + 2.6, 3.35, 'tech', 7), (AO + 1.1, 0, 'canopy', 6.5),
                            (AO + 2.9, 0, 'MAIN ENTRANCE', 8), (P.R_IN - 1.05, 0, 'curtain', 6.5)):
        p = FP(KE, n, t)
        label(ax, p[0], p[1], txt, sz, weight='bold' if txt.startswith('MAIN') else 'normal')
    # lighting: paper disc pendants + uplight ledge (indirect) + clay wall shells
    for i in range(8):
        if i == P.STAIR_SLOT:
            continue
        ax.add_patch(Circle(pol(7.0, P.slot_center(i) + 11.25), 0.55, fc='none', ec='#B07A2A', lw=0.7,
                            ls=(0, (2, 1.5)), zorder=6))
    p = pol(7.0, P.slot_center(5) + 11.25)
    label(ax, p[0], p[1] - 0.85, 'paper pendant', 6, color='#8A5A1A')
    # tea / party bar    # tea / party bar
    se = []
    for i in range(48):
        th = 2 * math.pi * i / 48
        c_, s_ = math.cos(th), math.sin(th)
        x = 1.9 * math.copysign(abs(c_) ** (2 / 2.2), c_)
        y = 0.38 * math.copysign(abs(s_) ** (2 / 2.2), s_)
        se.append(FP(7, P.R_IN - 1.25 + y, x + 0.6))
    poly(ax, se, fc='#E6D6BF', lw=0.6, z=4)
    p = FP(7, P.R_IN - 2.1, 0.6)
    label(ax, p[0], p[1], 'tea / party bar', 6.5, rotation=-45)
    label(ax, 0, -1.2, 'HALL', 14, weight='bold')
    label(ax, 0, -2.0, 'open floor under the net · oak boards', 7)
    p = FP(3, P.R_IN - 1.2, 0)
    label(ax, p[0], p[1], 'window seats', 6.5, rotation=-45)
    p = pol(3.4, 250)
    label(ax, p[0], p[1], 'column', 6.5)
    rect_face(ax, 4, P.R_OUT + 0.6, P.R_OUT + 4.35, -3.4, 3.8, fc='#EFE5D6', lw=0.4, z=1)
    p = FP(4, P.R_OUT + 2.5, 0.2)
    label(ax, p[0], p[1], 'garden deck', 7)
    ax.annotate('', xy=(-P.R_OUT, -11.3), xytext=(P.R_OUT, -11.3),
                arrowprops=dict(arrowstyle='<|-|>', lw=0.5, color=INK, mutation_scale=6))
    label(ax, 0, -11.0, '20.00 across the flats (21.65 across the corners)', 7.5)
    for x in (-P.R_OUT, P.R_OUT):
        ax.plot([x, x], [-11.6, -1], color=INK, lw=0.3)
    dim(ax, (0, 0), pol(P.R_PILLAR, 337.5), 'columns on Ø 8.80', size=6.5)
    # dimensions: east face (windows, face), garden doors, entrance, annex, hall inside
    fh = P.face_half(P.R_OUT)
    ts = [-fh, -3.0, -0.9, 0.9, 3.0, fh]
    for i in range(len(ts) - 1):
        fdim(ax, 6, P.R_OUT + 0.4, ts[i], P.R_OUT + 0.4, ts[i + 1], '%.2f' % (ts[i + 1] - ts[i]), 6,
             ext=(P.R_OUT, None))
    fdim(ax, 6, P.R_OUT + 1.1, -fh, P.R_OUT + 1.1, fh, '%.2f face' % (2 * fh), 6.5, ext=(P.R_OUT + 0.4, None))
    p = FP(6, P.R_OUT + 0.75, 0)
    label(ax, p[0], p[1], 'windows, sill 0.40, head 3.20', 5.5, rotation=90)
    fdim(ax, 4, P.R_IN - 0.75, -1.5, P.R_IN - 0.75, 1.5, '3.00 garden doors', 6)
    fdim(ax, KE, P.R_OUT + 0.35, -0.9, P.R_OUT + 0.35, 0.9, '1.80', 6)
    fha = P.face_half(AO)
    fdim(ax, KE, AO + 0.4, -fha, AO + 0.4, fha, '%.2f annex' % (2 * fha), 6, ext=(AO, None))
    fdim(ax, KE, P.R_OUT, -fha - 0.6, AO, -fha - 0.6, '%.2f' % P.ANNEX_D, 6.5)
    dim(ax, (-P.R_IN, 3.6), (P.R_IN, 3.6), '%.2f inside, across the flats' % (2 * P.R_IN), 6.5)
    chain(ax, 2, -3.55, [P.R_IN, P.R_OUT], ['%.2f' % P.WALL_T], 5.5)
    north_arrow(ax, 15.0, 15.8)
    scale_bar(ax, -12.8, -11.8)
    ax.plot([0.05, 0.05], [-11.9, -10.6], color=INK, lw=1.4)
    ax.plot([0.05, 0.05], [17.0, 17.8], color=INK, lw=1.4)
    label(ax, 0.8, -11.6, 'A', 10, weight='bold')
    label(ax, 0.8, 17.5, 'A', 10, weight='bold')
    legend(fig, tx, 0.60, [('cut wall (timber frame, clay inside, larch outside)', dict(fc=POCHE)),
                           ('timber column', dict(fc=WOOD)),
                           ('above: ring beam, beams, stair, windows', dict(fc='white', ls='--')),
                           ('sun spot through dome + net', dict(fc=LIGHT, alpha=0.3))])
    fig.text(tx, 0.41, 'Heating & comfort\n'
             '• Underfloor heating in hall and rooms, fed by ZEGG\'s\n   wood-chip district heating – floors ~26–28 °C\n'
             '• Balanced ventilation with heat recovery; vent in the\n   dome crown for smoke + summer purge\n'
             '• Clay plaster buffers humidity and sound\n'
             '• Outside shading on dome and big windows\n   (summer overheating, GEG / DIN 4108-2)',
             fontsize=10, color=INK, va='top', linespacing=1.45)
    return fig


def room_furniture(ax, k):
    a = P.slot_center(k)

    def se(cx, cy, rx, ry, n=2.4, rot=0.0, N=60):
        pts = []
        cr, sr = math.cos(rad(rot)), math.sin(rad(rot))
        for i in range(N):
            t = 2 * math.pi * i / N
            c, s = math.cos(t), math.sin(t)
            x = rx * math.copysign(abs(c) ** (2 / n), c)
            y = ry * math.copysign(abs(s) ** (2 / n), s)
            pts.append(to_world(a, cx + x * cr - y * sr, cy + x * sr + y * cr))
        return pts
    poly(ax, se(8.55, 0, 1.2, 1.6), fc='#E6D6BF', lw=0.5, z=3)
    poly(ax, se(8.55, 0, 1.07, 1.46, n=2.6), fc='#F4EDE2', lw=0.4, z=3)
    wa = -P.SLOT_DEG / 2
    e = P.PART_T / 2 / math.cos(rad(P.SLOT_DEG / 2))
    wd = (math.cos(rad(wa)), math.sin(rad(wa)))
    wn = (math.sin(rad(-wa)), math.cos(rad(-wa)))
    c0 = (wd[0] * 7.0 + wn[0] * (e + 0.34), wd[1] * 7.0 + wn[1] * (e + 0.34))
    poly(ax, se(c0[0], c0[1], 0.95, 0.30, n=2.2, rot=wa), fc='#E6D6BF', lw=0.5, z=3)
    ax.add_patch(Circle(to_world(a, 9.05, 3.05), 0.28, fc=GREEN, ec=INK, lw=0.4, zorder=3))
    s0, s1 = P.SKYLIGHT['u'] - P.SKYLIGHT['d'] / 2, P.SKYLIGHT['u'] + P.SKYLIGHT['d'] / 2
    w = P.SKYLIGHT['w'] / 2
    poly(ax, [to_world(a, s0, -w), to_world(a, s1, -w), to_world(a, s1, w), to_world(a, s0, w)], fc='none',
         lw=0.6, z=6, ls=(0, (4, 2)), ec=GLASS)


def bathroom_plan(ax, k):
    """Bathing room: WCs with own doors at the front corners, rain showers, warm bench, aftercare nook."""
    a = P.slot_center(k)
    ht = math.tan(rad(P.SLOT_DEG / 2))
    e = P.PART_T / 2 / math.cos(rad(P.SLOT_DEG / 2))

    def yw(x):
        return x * ht - e
    W = lambda x, y: to_world(a, x, y)  # noqa: E731
    x0 = P.APOTHEM_FRONT + P.FRONT_T
    XW, YW = 7.35, 1.05
    for s_ in (-1, 1):
        seg_wall(ax, W(x0, s_ * YW), W(XW, s_ * YW), 0.1)
        seg_wall(ax, W(XW, s_ * YW), W(XW, s_ * yw(XW)), 0.1)
        poly(ax, [W(XW - 0.55, s_ * 1.4), W(XW - 0.05, s_ * 1.4), W(XW - 0.05, s_ * 1.8), W(XW - 0.55, s_ * 1.8)],
             fc='white', lw=0.5, z=4)
        p = W(6.35, s_ * 1.75)
        label(ax, p[0], p[1], 'WC', 6.5)
    poly(ax, [W(7.9, -2.4), W(P.R_IN, -2.4), W(P.R_IN, 0.9), W(7.9, 0.9)], fc='#E4ECEC', lw=0.4, z=3,
         ls=(0, (3, 2)))
    for yy in (-1.9, -0.75, 0.4):
        poly(ax, [W(8.38, yy - 0.17), W(8.72, yy - 0.17), W(8.72, yy + 0.17), W(8.38, yy + 0.17)], fc='none',
             lw=0.4, z=5)
    poly(ax, [W(9.06, -2.6), W(P.R_IN, -2.6), W(P.R_IN, 0.9), W(9.06, 0.9)], fc='#E6D6BF', lw=0.4, z=4)
    p = W(8.45, -1.3)
    label(ax, p[0], p[1], 'rain\nshowers', 6.5)
    poly(ax, [W(7.65, 1.02), W(9.25, 1.02), W(9.25, 1.18), W(7.65, 1.18)], fc='#E6D6BF', lw=0.4, z=4)
    poly(ax, [W(8.4, 1.4), W(9.5, 1.4), W(9.5, 3.2), W(8.4, 3.2)], fc='#E6D6BF', lw=0.4, z=4)
    p = W(8.1, 2.3)
    label(ax, p[0], p[1], 'after-\ncare', 6.5)
    poly(ax, [W(5.95, YW - 0.05), W(7.2, YW - 0.05), W(7.2, YW - 0.55), W(5.95, YW - 0.55)], fc=WOOD, lw=0.4, z=4)
    p = W(6.6, -0.1)
    label(ax, p[0], p[1], 'BATH', 7.5, weight='bold')


def upper_floor():
    fig, ax, tx = sheet(-13.0, 15.5, -12.3, 12.7, 'Upper floor',
                        'From the centre outwards:\n'
                        '• Net Ø 7.80 usable (opening Ø 8.60)\n'
                        '• Padded edge 0.40 m on the ring beam\n'
                        '• Ring walkway 1.25 m (up to 1.75 m at the posts)\n'
                        '• 6 rooms, each ≈ 23 m²: 4.6 m wide at the door,\n'
                        '   7.9 m at the straight outer wall, 3.8 m deep\n'
                        '• Shared bathroom (north): 2 WCs, walk-in group\n'
                        '   shower, 2 basins – all gender\n'
                        '• Stair segment: stair, linen / laundry, tea,\n'
                        '   door to the external stair\n'
                        'Clear height in rooms 2.60 m')
    circle(ax, P.R_DOME, ec=GLASS, lw=0.7, ls='-.', zorder=7)
    octagon_wall(ax, P.FFL_UF + 1.2)
    for k in ROOM_SLOTS:
        rect_face(ax, k, P.R_OUT + 0.05, P.R_OUT + 0.10, -P.UF_WINDOW['w'] - 0.3, P.UF_WINDOW['w'] + 0.3,
                  fc='#B08D69', lw=0.3, z=3)
    for k in range(P.N_SLOTS):
        pa = P.partition_angle(k)
        seg_wall(ax, pol(RC, pa), pol(P.octo_r(pa, P.R_IN), pa), P.PART_T)
        c = pol(RC, pa)
        ax.add_patch(Rectangle((c[0] - P.POST / 2, c[1] - P.POST / 2), P.POST, P.POST, fc=WOOD, ec=INK, lw=0.5,
                               zorder=6))
    half = P.APOTHEM_FRONT * math.tan(rad(P.SLOT_DEG / 2)) - P.POST / 2 - 0.01
    L = 2 * half
    pw = L / 3 + 0.03
    for idx, k in enumerate(ROOM_SLOTS):
        a = P.slot_center(k)
        x = P.APOTHEM_FRONT + P.FRONT_T / 2
        state = DOOR_STATES[k]
        pos = {'closed': (0, 1), 'half': (-1, 0), 'open': (-1, -1)}[state]
        for i, (slot, off) in enumerate([(-1, 0.0), (pos[0], -0.045), (pos[1], -0.09)]):
            yc = slot * L / 3
            xc = x + off + 0.045
            seg_wall(ax, to_world(a, xc, yc - pw / 2), to_world(a, xc, yc + pw / 2), 0.035,
                     fc=WOOD if i == 0 else '#F3E6CC', lw=0.5, z=6)
        if k == P.BATH_SLOT:
            bathroom_plan(ax, k)
        else:
            room_furniture(ax, k)
            p = to_world(a, 6.3, 1.2)
            label(ax, p[0], p[1], 'R%d' % (ROOMS.index(k) + 1), 10, weight='bold')
        p = to_world(a, 5.85, 0.0)
        label(ax, p[0], p[1], state, 5.5, color='#6B5E55', rotation=(a + 90) % 180 - 90)
    ax.add_patch(Circle((0, 0), P.R_PAD_OUT, fc='#E7D9BF', ec=INK, lw=0.6, zorder=4))
    ax.add_patch(Circle((0, 0), P.R_NET, fc='white', ec=INK, lw=0.6, zorder=4))
    for j in range(P.N_NET_RADIAL):
        a = 360 * j / P.N_NET_RADIAL + 360 / P.N_NET_RADIAL / 2
        p0, p1 = pol(P.NET_RING_RADII[0], a), pol(P.R_NET, a)
        ax.plot([p0[0], p1[0]], [p0[1], p1[1]], color=NETC, lw=0.8, zorder=5)
    for rr in P.NET_RING_RADII:
        circle(ax, rr, ec=NETC, lw=0.8, zorder=5)
    for c in np.arange(-8, 8, 0.30):
        for sign in (1, -1):
            xs = np.linspace(-P.R_NET, P.R_NET, 200)
            ys = sign * xs + c
            m = xs ** 2 + ys ** 2 < P.R_NET ** 2
            if m.any():
                ax.plot(xs[m], ys[m], color='#CFC5B5', lw=0.25, zorder=4.5)
    label(ax, 0, 0.65, 'NET', 13, weight='bold')
    label(ax, 0, -0.2, 'walkable, see-through\n45 mm mesh between\nradial + ring ropes', 6.5)
    p = pol(4.85, 262)
    label(ax, p[0], p[1], 'walkway', 6.5, rotation=-8)
    stair_plan(ax, 'UF')
    ext_stair(ax, 'UF')
    p = FP(KS, 7.0, -2.2)
    label(ax, p[0], p[1], 'linen /\nlaundry', 5.5)
    p = FP(KS, 8.8, 2.9)
    label(ax, p[0], p[1], 'landing ->\nroof stair', 5.5)
    p = FP(KS, 6.9, 1.2)
    label(ax, p[0], p[1], 'tea', 5.5)
    dim(ax, (0, 0), pol(P.R_NET, 322), 'Ø 7.80 usable', size=6.5)
    # dimensions through R3 (south): radial chain, door front, window, face
    ht = math.tan(rad(P.SLOT_DEG / 2))
    e = P.PART_T / 2 / math.cos(rad(P.SLOT_DEG / 2))
    fr = P.APOTHEM_FRONT + P.FRONT_T
    chain(ax, 4, -2.1, [P.R_NET, P.R_PAD_OUT, P.APOTHEM_FRONT, P.R_IN, P.R_OUT],
          ['%.2f' % (P.R_PAD_OUT - P.R_NET), '%.2f' % (P.APOTHEM_FRONT - P.R_PAD_OUT),
           '%.2f (clear %.2f)' % (P.R_IN - P.APOTHEM_FRONT, P.R_IN - fr), '%.2f' % P.WALL_T], 5.5)
    wf = fr * ht - e
    fdim(ax, 4, fr + 0.3, -wf, fr + 0.3, wf, '%.2f door front' % (2 * wf), 6)
    fh = P.face_half(P.R_OUT)
    ww = P.UF_WINDOW['w'] / 2
    for (t0, t1) in ((-fh, -ww), (-ww, ww), (ww, fh)):
        fdim(ax, 4, P.R_OUT + 0.45, t0, P.R_OUT + 0.45, t1, '%.2f' % (t1 - t0), 6, ext=(P.R_OUT, None))
    ax.annotate('', xy=(-P.R_OUT, -11.8), xytext=(P.R_OUT, -11.8),
                arrowprops=dict(arrowstyle='<|-|>', lw=0.5, color=INK, mutation_scale=6))
    label(ax, 0, -11.5, '20.00 across the flats', 7.5)
    north_arrow(ax, 14.0, 10.6)
    scale_bar(ax, -12.8, -12.1)
    fig.text(tx, 0.58, 'Rooms (6 × ≈ 23 m², for 1–3 people, also overnight)\n'
             '• Front: 3 shoji-type panels (oak frame, linen / paper\n   infill): closed / half (1.4 m) / open (2.9 m);\n'
             '   a small signal lantern by each door: lit = welcome /\n   ask, dark = private\n'
             '• Earthen sleeping nest under the window, clay bench,\n   sheepskins, lanterns, plants – no hotel furniture\n'
             '• Big window 2.60 × 1.65 m (sill 0.45 m, fixed safety\n   glass up to 0.90 m), sliding larch shutters outside;\n'
             '   the opening part is a rescue window (≥ 0.90 × 1.20 m)\n'
             '• Skylight 1.40 × 1.10 m over the nest: walk-on frosted\n   glass in the terrace (light, no view in)\n'
             '• Acoustic partitions 160 mm, clay plaster\n\n'
             'Stairs\n'
             '• Inside: one flight along the NW wall, open to the hall,\n   22 × 188 mm, going 270 mm, 1.50 m wide; floating oak\n'
             '   treads, rope-net balustrade, seating terraces at the\n   bottom, a long clay bench under the flight\n'
             '• Outside (NW face): ground -> upper floor -> roof\n   terrace; 2nd escape route and the only way up\n'
             '   to the terrace',
             fontsize=10, color=INK, va='top', linespacing=1.4)
    return fig


def roof_plan():
    fig, ax, tx = sheet(-13.0, 15.5, -12.3, 12.7, 'Roof terrace',
                        'Flat roof over the rooms as a sun terrace\n'
                        'around the dome, deck at +7.28\n'
                        '• South side (SW–S–SE): 6 daybeds, sun sails,\n'
                        '   1.80 m slatted privacy screen\n'
                        '• West / east: loungers; north / north-east: big floor\n'
                        '   mattresses in the shade, planters, grasses\n'
                        '• Dome on a 45 cm upstand = bench ring\n'
                        '• Frosted walk-on skylights over each room\n'
                        '• Reached by the external stair only: going up\n'
                        '   to the terrace means going outside anyway')
    poly(ax, oct_pts(P.R_OUT + 0.04), fc='#EFE5D6', lw=0.6, z=1)
    for k in range(P.N_SLOTS):
        hh = 1.80 if k in P.SUN_FACES else P.RAIL_H
        fh = P.face_half(P.R_OUT - 0.04)
        rect_face(ax, k, P.R_OUT - 0.10, P.R_OUT, -fh, fh, fc='#6E5440' if hh > 1.5 else '#B08D69', lw=0.3, z=3)
    for apo in np.arange(P.R_DOME + 0.6, P.R_OUT - 0.1, 0.4):
        poly(ax, oct_pts(apo), fc='none', ec='#DCCBB0', lw=0.3, z=2)
    ax.add_patch(Circle((0, 0), P.DOME_RING_OUT + 0.47, fc=WOOD, ec=INK, lw=0.5, zorder=4))
    ax.add_patch(Circle((0, 0), P.DOME_RING_OUT, fc='#C9A57A', ec=INK, lw=0.6, zorder=4))
    ax.add_patch(Circle((0, 0), P.R_DOME, fc='#DCE8EC', ec=GLASS, lw=0.8, zorder=5))
    for j in range(P.N_DOME_RIBS):
        a = 360 * j / P.N_DOME_RIBS
        p0, p1 = pol(P.DOME_OCULUS_R, a), pol(P.R_DOME, a)
        ax.plot([p0[0], p1[0]], [p0[1], p1[1]], color=WOOD, lw=1.0, zorder=6)
    for rr in (2.4, 4.1):
        circle(ax, rr, ec=WOOD, lw=0.6, zorder=6)
    ax.add_patch(Circle((0, 0), P.DOME_OCULUS_R + 0.05, fc='#4B4036', ec=INK, lw=0.5, zorder=7))
    label(ax, 0, 1.2, 'GLASS DOME', 11, weight='bold', color='#3F5D6C')
    label(ax, 0, -1.0, 'Ø 11.60 on a 45 cm upstand\nvent at the crown', 7, color='#3F5D6C')
    for k in ROOM_SLOTS:
        a = P.slot_center(k)
        s0, s1 = P.SKYLIGHT['u'] - P.SKYLIGHT['d'] / 2, P.SKYLIGHT['u'] + P.SKYLIGHT['d'] / 2
        w = P.SKYLIGHT['w'] / 2
        poly(ax, [to_world(a, s0, -w), to_world(a, s1, -w), to_world(a, s1, w), to_world(a, s0, w)],
             fc='#E4ECEC', ec=GLASS, lw=0.6, z=5)
    for k in P.SUN_FACES:
        for t in P.DAYBED_T:
            rect_face(ax, k, 8.15 - 1.05, 8.15 + 1.05, t - 1.02, t + 1.02, fc='#E8D9C0', lw=0.5, z=5)
            rect_face(ax, k, 8.95, 9.15, t - 0.9, t + 0.9, fc='#C98F6A', lw=0.3, z=6)
        A = FP(k, P.R_OUT - 0.25, -3.6)
        B = FP(k, P.R_OUT - 0.25, 3.6)
        C = FP(k, 6.55, 0.0)
        ax.add_patch(Polygon([A, B, C], closed=True, fc='none', ec='#9C8E80', lw=0.6, ls=(0, (5, 3)), zorder=7))
        for pnt in (A, B, C):
            ax.add_patch(Circle(pnt, 0.07, fc=INK, zorder=8))
    for k in (2, 6):
        for t in (-2.7, -1.0):
            rect_face(ax, k, 7.3, 8.7, t - 0.35, t + 0.35, fc='#E8D9C0', lw=0.4, z=5)
    for k in (7.5, 6.5):                                 # floor mattresses in the corners, clear of the skylights
        rect_face(ax, k, 7.2, 9.5, -1.15, 1.15, fc='#EFE2CC', lw=0.5, z=5)
        p = FP(k, 8.35, 0)
        label(ax, p[0], p[1], 'floor\nmattress', 5.5)
    for k in (0, 2, 6, 7):
        for t0, t1 in ((-3.6, -1.2), (1.2, 3.6)):
            rect_face(ax, k, P.R_OUT - 0.68, P.R_OUT - 0.12, t0, t1, fc=GREEN, lw=0.4, z=4)
    ext_stair(ax, 'RF')
    p = FP(K_, P.R_OUT - 0.55, sum(P.TERRACE_GATE) / 2)
    label(ax, p[0], p[1], 'gate', 6)
    p = FP(4, 6.95, 0)
    label(ax, p[0], p[1], 'SUN DECK', 11, weight='bold')
    p = FP(2, 7.0, -1.85)
    label(ax, p[0], p[1], 'loungers', 6.5, rotation=90)
    p = FP(0, 8.0, 0)
    label(ax, p[0], p[1], '', 6.5)
    p = FP(4, 10.7, 0)
    label(ax, p[0], p[1], 'privacy screen 1.80 m (SW–S–SE) · railing 1.20 m elsewhere', 6.5)
    # dimensions
    chain(ax, 6, 1.05, [P.R_DOME, P.DOME_RING_OUT + 0.47, P.R_OUT - 0.10],
          ['%.2f bench' % (P.DOME_RING_OUT + 0.47 - P.R_DOME), '%.2f deck' % (P.R_OUT - 0.10 - P.DOME_RING_OUT - 0.47)],
          5.5)
    for k in (7.5,):
        fdim(ax, k, 6.95, -1.15, 6.95, 1.15, '2.30', 5.5)
        fdim(ax, k, 7.2, 1.4, 9.5, 1.4, '2.30', 5.5)
    t = P.DAYBED_T[1]
    fdim(ax, 4, 6.85, t - 1.02, 6.85, t + 1.02, '%.2f' % 2.04, 5.5)
    fdim(ax, 4, 8.15 - 1.05, t + 1.3, 8.15 + 1.05, t + 1.3, '2.10', 5.5)
    fdim(ax, 5, P.R_OUT + 0.45, -P.face_half(P.R_OUT), P.R_OUT + 0.45, P.face_half(P.R_OUT),
         '%.2f face' % (2 * P.face_half(P.R_OUT)), 6, ext=(P.R_OUT, None))
    ax.annotate('', xy=(-P.R_OUT, -11.8), xytext=(P.R_OUT, -11.8),
                arrowprops=dict(arrowstyle='<|-|>', lw=0.5, color=INK, mutation_scale=6))
    label(ax, 0, -11.5, '20.00 across the flats', 7.5)
    north_arrow(ax, 14.0, 10.6)
    scale_bar(ax, -12.8, -12.1)
    fig.text(tx, 0.56, 'Notes\n'
             '• Walkable flat roof: imposed load ≈ 4 kN/m²,\n   falls to internal outlets, deck on pedestals\n'
             '• Skylights: walk-on laminated safety glass, frosted\n'
             '• Sun sails are demountable (winter, storms)\n'
             '• Annex keeps a green sedum roof (not walkable)',
             fontsize=10, color=INK, va='top', linespacing=1.45)
    return fig


# ---------------------------------------------------------------------------
# a single room, 1:25 (room R2, south-west, door half open)
# ---------------------------------------------------------------------------
def room_detail(k=3):
    S25 = 25.0
    fig = plt.figure(figsize=A2)
    L = lambda n, t: (-t, n)                                    # noqa: E731  local (n, t) -> plan, window on top
    xmin, xmax, ymin, ymax = -4.6, 4.6, 5.0, 10.9
    w_in = (xmax - xmin) * 1000 / S25 / 25.4
    h_in = (ymax - ymin) * 1000 / S25 / 25.4
    ax = fig.add_axes([0.8 / A2[0], (A2[1] - h_in) / 2 / A2[1], w_in / A2[0], h_in / A2[1]])
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    ax.set_aspect('equal')
    ax.axis('off')
    ht = math.tan(rad(P.SLOT_DEG / 2))
    e = P.PART_T / 2 / math.cos(rad(P.SLOT_DEG / 2))
    fr = P.APOTHEM_FRONT + P.FRONT_T
    R = P.R_IN

    def Lp(pts):
        return [L(n, t) for n, t in pts]

    def se(cx, cy, rx, ry, n=2.4, rot=0.0, N=72):
        out = []
        cr, sr = math.cos(rad(rot)), math.sin(rad(rot))
        for i in range(N):
            t_ = 2 * math.pi * i / N
            c, s_ = math.cos(t_), math.sin(t_)
            x = rx * math.copysign(abs(c) ** (2 / n), c)
            y = ry * math.copysign(abs(s_) ** (2 / n), s_)
            out.append(L(cx + x * cr - y * sr, cy + x * sr + y * cr))
        return out
    # floor (oak) and walls
    poly(ax, Lp([(fr, fr * ht - e), (R, R * ht - e), (R, -(R * ht - e)), (fr, -(fr * ht - e))]), fc='#F6EEE2',
         lw=0.0, z=1)
    fh = P.face_half(P.R_OUT)
    ww = P.UF_WINDOW['w'] / 2
    for t0, t1 in ((-fh, -ww), (ww, fh)):
        poly(ax, Lp([(R, t0), (P.R_OUT, t0), (P.R_OUT, t1), (R, t1)]), fc=POCHE, lw=0.6, z=5)
    poly(ax, Lp([(R + 0.18, -ww), (R + 0.24, -ww), (R + 0.24, ww), (R + 0.18, ww)]), fc='#DCE8EC', ec=GLASS,
         lw=0.6, z=5)
    poly(ax, Lp([(P.R_OUT + 0.02, -ww - 0.05), (P.R_OUT + 0.07, -ww - 0.05), (P.R_OUT + 0.07, ww + 0.05),
                 (P.R_OUT + 0.02, ww + 0.05)]), fc='#B08D69', lw=0.3, z=5)
    for sgn in (-1, 1):                                       # partitions (160 mm, clay plaster)
        pts = [(P.APOTHEM_FRONT, sgn * (P.APOTHEM_FRONT * ht - e)), (R, sgn * (R * ht - e)),
               (R, sgn * (R * ht + e)), (P.APOTHEM_FRONT, sgn * (P.APOTHEM_FRONT * ht + e))]
        poly(ax, Lp(pts), fc=POCHE, lw=0.6, z=5)
        c = L(P.APOTHEM_FRONT - 0.02, sgn * P.APOTHEM_FRONT * ht)
        ax.add_patch(Rectangle((c[0] - P.POST / 2, c[1] - P.POST / 2), P.POST, P.POST, fc=WOOD, ec=INK, lw=0.5,
                               zorder=6))
    # front: 3 sliding shoji panels (oak + linen), here half open; signal lantern
    half = P.APOTHEM_FRONT * ht - P.POST / 2 - 0.01
    Lw = 2 * half
    pw = Lw / 3 + 0.03
    for i, (slot, off) in enumerate([(-1, 0.0), (-1, -0.045), (0, -0.09)]):
        yc = slot * Lw / 3
        xc = P.APOTHEM_FRONT + P.FRONT_T / 2 + off + 0.045
        poly(ax, Lp([(xc - 0.02, yc - pw / 2), (xc + 0.02, yc - pw / 2), (xc + 0.02, yc + pw / 2),
                     (xc - 0.02, yc + pw / 2)]), fc=WOOD if i == 0 else '#F3E6CC', lw=0.5, z=6)
    ax.add_patch(Circle(L(P.APOTHEM_FRONT - 0.15, Lw / 2 - 0.2), 0.075, fc=LIGHT, ec=INK, lw=0.4, zorder=7))
    # sleeping nest under the window: earthen plinth + mattress, sheepskin
    poly(ax, se(8.55, 0, 1.2, 1.6), fc='#E6D6BF', lw=0.6, z=3)
    poly(ax, se(8.55, 0, 1.07, 1.46, n=2.6), fc='#FBF6EE', lw=0.5, z=3.1)
    poly(ax, se(8.1, -0.85, 0.45, 0.62, n=2.0, rot=20), fc='#EFE7DA', lw=0.3, z=3.2, ls=(0, (1, 1)))
    for yy in (-0.9, -0.3, 0.3, 0.9):                          # cushions against the wall
        poly(ax, se(9.25 - 0.05 * abs(yy), yy, 0.14, 0.26, n=2.4), fc='#D9A58A', lw=0.3, z=3.3)
    # cob bench with a curved back along the side wall
    wa = -P.SLOT_DEG / 2
    wd = (math.cos(rad(wa)), math.sin(rad(wa)))
    wn = (math.sin(rad(-wa)), math.cos(rad(-wa)))
    c0 = (wd[0] * 7.0 + wn[0] * (e + 0.34), wd[1] * 7.0 + wn[1] * (e + 0.34))
    cb = (wd[0] * 7.0 + wn[0] * (e + 0.07), wd[1] * 7.0 + wn[1] * (e + 0.07))
    poly(ax, se(c0[0], c0[1], 0.95, 0.30, n=2.2, rot=wa), fc='#E6D6BF', lw=0.5, z=3)
    poly(ax, se(cb[0], cb[1], 1.05, 0.09, n=2.0, rot=wa), fc='#D6C3A8', lw=0.4, z=3)
    # rug, tea tray, floor lantern, plant, pendant, curtain, sconces
    poly(ax, se(6.95, 0.55, 1.15, 1.0, n=2.0), fc='#EAD2BE', lw=0.3, z=2)
    ax.add_patch(Circle(L(7.25, -0.45), 0.27, fc=WOOD, ec=INK, lw=0.4, zorder=3))
    ax.add_patch(Circle(L(6.15, -1.65 if k % 2 else 1.65), 0.2, fc='#F7EBD2', ec=INK, lw=0.4, zorder=3))
    ax.add_patch(Circle(L(9.05, 3.05), 0.28, fc=GREEN, ec=INK, lw=0.4, zorder=3))
    ax.add_patch(Circle(L(7.0, 0.9), 0.3, fc='none', ec=LIGHT, lw=0.8, ls=(0, (2, 2)), zorder=6))
    ax.plot(*zip(L(R - 0.1, -ww - 0.05), L(R - 0.1, -ww + 0.5)), color='#C9B99E', lw=3, zorder=4)
    for sgn in (-1, 1):
        p0 = (8.3, sgn * (8.3 * ht - e - 0.05))
        ax.add_patch(Circle(L(*p0), 0.09, fc=LIGHT, ec=INK, lw=0.4, zorder=7))
    s0, s1 = P.SKYLIGHT['u'] - P.SKYLIGHT['d'] / 2, P.SKYLIGHT['u'] + P.SKYLIGHT['d'] / 2
    w = P.SKYLIGHT['w'] / 2
    poly(ax, Lp([(s0, -w), (s1, -w), (s1, w), (s0, w)]), fc='none', ec=GLASS, lw=0.8, z=8, ls=(0, (5, 3)))
    # walkway strip in front
    poly(ax, Lp([(5.0, -2.6), (P.APOTHEM_FRONT, -2.3), (P.APOTHEM_FRONT, 2.3), (5.0, 2.6)]), fc='#EFE5D6', lw=0.0,
         z=0.5)
    # labels
    for (n_, t_, txt, sz) in ((8.55, 0.2, 'sleeping nest 2.40 × 3.20\nclay plinth 0.30 high\nmattress 1.40 × 2.10', 7),
                              (7.0, -2.25, 'cob bench\nwith curved back', 6.5), (6.8, 0.6, 'rug', 6.5),
                              (7.25, -0.45, 'tea', 5.5), (9.05, 3.05, 'plant', 5), (6.15, -1.65, 'lamp', 4.5),
                              (5.25, 0.0, 'walkway', 7), (9.85, 0.0, 'window 2.60 × 1.65', 6.5),
                              (P.SKYLIGHT['u'] - 0.72, 1.35, 'skylight above\n1.40 × 1.10', 6)):
        x_, y_ = L(n_, t_)
        label(ax, x_, y_, txt, sz)
    x_, y_ = L(7.7, 1.9)
    label(ax, x_, y_, 'R2', 16, weight='bold')
    x_, y_ = L(5.45, -1.95)
    label(ax, x_, y_, 'signal lantern', 5.5)
    # dimensions
    wf = fr * ht - e
    wr = R * ht - e
    dim(ax, L(fr - 0.3, wf), L(fr - 0.3, -wf), '%.2f  (door front)' % (2 * wf), size=7.5)
    nO = P.R_OUT + 0.7
    dim(ax, L(nO, wr), L(nO, -wr), '%.2f  (outer wall, inside)' % (2 * wr), size=7.5)
    for sg in (-1, 1):
        ax.plot(*zip(L(R, sg * wr), L(nO + 0.05, sg * wr)), color=INK, lw=0.3, zorder=11)
        ax.plot(*zip(L(P.R_OUT, sg * ww), L(P.R_OUT + 0.3, sg * ww)), color=INK, lw=0.3, zorder=11)
        ax.plot(*zip(L(fr, sg * wf), L(fr - 0.35, sg * wf)), color=INK, lw=0.3, zorder=11)
    dim(ax, L(fr, 4.25), L(R, 4.25), '%.2f clear depth' % (R - fr), size=7.5)
    for n_ in (fr, R):
        ax.plot(*zip(L(n_, n_ * ht - e), L(n_, 4.35)), color=INK, lw=0.3, zorder=11)
    dim(ax, L(P.R_OUT + 0.25, ww), L(P.R_OUT + 0.25, -ww), '%.2f window' % (2 * ww), size=7)
    dim(ax, L(R, 3.2), L(P.R_OUT, 3.2), '%.2f' % P.WALL_T, size=6)
    x_, y_ = L(6.4, 6.4 * ht - e - 0.55)
    label(ax, x_, y_, 'partition 0.16', 5.5)
    area = ht * (R ** 2 - fr ** 2) - 2 * e * (R - fr)
    # scale bar 1 m
    for i in range(4):
        ax.add_patch(Rectangle((xmin + 0.2 + i * 0.25, ymin + 0.2), 0.25, 0.06, fc=INK if i % 2 == 0 else 'white',
                               ec=INK, lw=0.5))
    ax.text(xmin + 0.2, ymin + 0.14, '0', fontsize=7, ha='center', va='top')
    ax.text(xmin + 1.2, ymin + 0.14, '1 m', fontsize=7, ha='center', va='top')
    tx = 0.8 / A2[0] + w_in / A2[0] + 0.03
    fig.text(tx, 0.93, 'A small room – R2', fontsize=24, color=INK, weight='bold', va='top')
    fig.text(tx, 0.885,
             'Upper floor, south-west segment · scale 1:25 on A2\n'
             'Floor area ≈ %.1f m² · clear height 2.60 m\n'
             'For 1–3 people, to withdraw, rest, make love, sleep\n\n'
             'Front to the walkway\n'
             '• 3 sliding shoji panels (oak frame, linen / paper infill):\n'
             '   closed / half (as drawn, 1.4 m) / fully open (2.9 m)\n'
             '• Signal lantern by the door: lit = welcome / ask,\n   dark = private\n\n'
             'Inside\n'
             '• Sleeping nest under the window: earthen plinth\n'
             '   0.30 m, natural-latex mattress, sheepskin, cushions\n'
             '• Cob bench with a curved back along the side wall\n'
             '• Round wool rug, low tea tray, floor lantern, plant\n'
             '• Paper pendant, two clay wall sconces (dimmable)\n'
             '• Linen curtain at the window\n\n'
             'Light and air\n'
             '• Window 2.60 × 1.65 m, sill 0.45 m; fixed safety glass\n'
             '   up to 0.90 m, opening part = rescue window\n'
             '• Sliding larch shutters outside\n'
             '• Skylight 1.40 × 1.10 m over the nest (walk-on\n'
             '   frosted glass in the terrace above)\n\n'
             'Build\n'
             '• Partitions 160 mm timber frame + clay plaster,\n'
             '   acoustic infill; oak floor on the slab' % area,
             fontsize=11, color=INK, va='top', linespacing=1.5)
    fig.text(tx, 0.045, 'Tempel – seminar building at ZEGG, Bad Belzig · concept\n'
             'Scale 1:25 on A2 · dimensions in metres', fontsize=9, color='#6B5E55', va='bottom', linespacing=1.5)
    return fig


# ---------------------------------------------------------------------------
def section():
    fig, ax, tx = sheet(-14.6, 17.8, -1.5, 12.5, 'Section A–A', 'North–south through the centre\n(looking east)')
    rs, zc = P.dome_sphere()
    ax.plot([-15, 17.5], [-0.05, -0.05], color=INK, lw=1.0)
    ax.add_patch(Rectangle((-15, -1.0), 32.5, 0.95, fc='#EFE8DC', ec='none', zorder=0))

    def R(x0, z0, x1, z1, fc=POCHE, lw=0.6, zo=3, **kw):
        x0, x1 = min(x0, x1), max(x0, x1)
        ax.add_patch(Rectangle((x0, z0), x1 - x0, z1 - z0, fc=fc, ec=INK, lw=lw, zorder=zo, **kw))

    def rbox(x0, z0, x1, z1, fc, r=0.08):
        x0, x1 = min(x0, x1), max(x0, x1)
        ax.add_patch(FancyBboxPatch((x0, z0), x1 - x0, z1 - z0, boxstyle='round,pad=0,rounding_size=%g' % r,
                                    fc=fc, ec=INK, lw=0.4, zorder=4))

    R(-P.R_OUT, -0.35, P.R_OUT, 0.0, fc='#CDBFAF')
    uw0, uw1 = P.FFL_UF + P.UF_WINDOW['sill'], P.FFL_UF + P.UF_WINDOW['head']
    s0, s1 = P.SKYLIGHT['u'] - P.SKYLIGHT['d'] / 2, P.SKYLIGHT['u'] + P.SKYLIGHT['d'] / 2
    for s, gf_top in ((-1, P.GARDEN_DOOR['h']), (1, P.ENTRY_DOOR['h'])):
        R(s * P.R_IN, gf_top, s * P.R_OUT, uw0)
        R(s * P.R_IN, uw1, s * P.R_OUT, P.CEIL_UF)
        for d in (0.12, 0.17):
            ax.plot([s * (P.R_IN + d)] * 2, [uw0, uw1], color=INK, lw=0.4)
            ax.plot([s * (P.R_IN + d)] * 2, [0, gf_top], color=INK, lw=0.4)
        ax.plot([s * P.R_IN, s * P.R_OUT], [P.FFL_UF + 0.9] * 2, color=INK, lw=0.4)
        R(s * P.RING_BEAM_OUT, P.CEIL_GF, s * P.R_IN, P.FFL_UF, fc='#B79B7E')
        R(s * P.RING_BEAM_IN, P.RING_BEAM_BOT, s * P.RING_BEAM_OUT, P.RING_BEAM_TOP, fc=WOOD)
        rbox(s * P.R_NET + 0.02 * s, P.RING_BEAM_TOP, s * P.R_PAD_OUT - 0.02 * s, P.RING_BEAM_TOP + P.PAD_T,
             '#E7D9BF', 0.05)
        xf = s * (P.APOTHEM_FRONT + 0.06)
        R(xf - 0.03, P.FFL_UF, xf + 0.03, P.FFL_UF + P.DOOR_H, fc='#F3E6CC')
        R(xf - 0.08, P.FFL_UF + P.DOOR_H, xf + 0.08, P.FFL_UF + P.DOOR_H + 0.12, fc=WOOD)
        R(xf - 0.01, P.FFL_UF + P.DOOR_H + 0.12, xf + 0.01, P.CEIL_UF, fc='#F3E6CC')
        R(s * (P.APOTHEM_FRONT - 0.05), P.CEIL_UF, s * (P.APOTHEM_FRONT + 0.2), P.ROOF_Z_IN, fc=CLAY)
        R(s * (P.APOTHEM_FRONT - 0.05), P.ROOF_Z_IN - 0.02, s * (P.DOME_RING_OUT), P.DOME_BASE_Z + 0.02, fc=WOOD)
        R(s * (P.APOTHEM_FRONT + 0.2), P.CEIL_UF, s * s0, P.ROOF_Z_IN, fc='#B79B7E')
        R(s * s1, P.CEIL_UF, s * P.R_OUT, P.ROOF_Z_IN, fc='#B79B7E')
        R(s * (P.DOME_RING_OUT), P.ROOF_Z_IN, s * s0, P.TERRACE_Z, fc='#D8C09C', lw=0.5)
        R(s * s1, P.ROOF_Z_IN, s * P.R_TERRACE_OUT, P.TERRACE_Z, fc='#D8C09C', lw=0.5)
        ax.plot([s * s0, s * s1], [P.TERRACE_Z - 0.03] * 2, color=GLASS, lw=1.6, zorder=6)
        ax.add_patch(Polygon([(s * s0, P.CEIL_UF), (s * s1, P.CEIL_UF), (s * (s1 - 0.3), P.FFL_UF + 0.5),
                              (s * (s0 - 0.6), P.FFL_UF + 0.5)], fc=LIGHT, alpha=0.14, ec='none', zorder=1))
        R(s * (P.DOME_RING_OUT), P.TERRACE_Z + 0.36, s * (P.DOME_RING_OUT + 0.47), P.TERRACE_Z + 0.44, fc=WOOD, lw=0.5)
        hh = 1.80 if s < 0 else P.RAIL_H
        R(s * (P.R_OUT - 0.07), P.TERRACE_Z, s * (P.R_OUT - 0.02), P.TERRACE_Z + hh, fc='#8C6E50', lw=0.4)
        R(s * (P.R_OUT - 0.1), P.TERRACE_Z + hh, s * (P.R_OUT + 0.02), P.TERRACE_Z + hh + 0.05, fc=WOOD, lw=0.4)
        if s < 0:
            rbox(s * 7.35, P.FFL_UF, s * 9.55, P.FFL_UF + 0.30, CLAY, 0.12)
            rbox(s * 7.48, P.FFL_UF + 0.30, s * 9.55, P.FFL_UF + 0.49, '#F4EDE2', 0.08)
        else:
            rbox(9.1, P.FFL_UF, 9.5, P.FFL_UF + 0.45, CLAY, 0.05)
            rbox(7.73, P.FFL_UF, 7.97, P.FFL_UF + 1.35, CLAY, 0.05)
        R(s * P.R_OUT, -0.05, s * (P.R_OUT + 0.06), 0.30, fc='#8A8076', lw=0.4)
    rbox(-9.2, P.TERRACE_Z, -7.1, P.TERRACE_Z + 0.5, '#E8D9C0', 0.06)
    ax.plot([-9.75, -6.55], [P.TERRACE_Z + 2.85, P.TERRACE_Z + 2.25], color='#9C8E80', lw=1.4)
    for x, zt in ((-9.75, P.TERRACE_Z + 3.0), (-6.55, P.TERRACE_Z + 2.35)):
        ax.plot([x, x], [P.TERRACE_Z, zt], color=INK, lw=0.8)
    label(ax, -8.2, P.TERRACE_Z + 3.25, 'sun sail', 6.5)
    label(ax, -(P.R_IN - 0.8), 1.3, 'garden doors', 6.5, rotation=90)
    label(ax, P.R_IN - 0.8, 1.2, 'entrance', 6.5, rotation=90)
    th1 = math.asin(P.R_DOME / rs)
    th0 = math.asin(P.DOME_OCULUS_R / rs)
    for sg in (-1, 1):
        th = np.linspace(th0, th1, 80)
        ax.plot(sg * rs * np.sin(th), zc + rs * np.cos(th), color=GLASS, lw=1.4, zorder=5)
        ax.plot(sg * (rs - 0.2) * np.sin(th), zc + (rs - 0.2) * np.cos(th), color=WOOD, lw=2.0, zorder=4)
    zcr = P.dome_z(P.DOME_OCULUS_R)
    R(-P.DOME_OCULUS_R - 0.05, zcr - 0.2, -P.DOME_OCULUS_R + 0.1, zcr + 0.4, fc='#4B4036')
    R(P.DOME_OCULUS_R - 0.1, zcr - 0.2, P.DOME_OCULUS_R + 0.05, zcr + 0.4, fc='#4B4036')
    ax.plot([-P.DOME_OCULUS_R - 0.1, P.DOME_OCULUS_R + 0.1], [zcr + 0.44] * 2, color=GLASS, lw=1.4)
    label(ax, 1.6, zcr + 0.55, 'crown ring + vent', 6.5, ha='left')
    for i in range(P.N_PILLARS):
        x, y = pol(P.R_PILLAR, P.PILLAR0_DEG + 90 * i)
        if x < 0:
            continue
        R(y - P.PILLAR_D / 2, 0, y + P.PILLAR_D / 2, P.RING_BEAM_BOT, fc='#EADBC6', lw=0.5, zo=1)
    xs = np.linspace(-P.RING_BEAM_IN, P.RING_BEAM_IN, 200)
    ax.plot(xs, [P.net_z(abs(x)) for x in xs], color=INK, lw=1.3, zorder=6)
    ax.plot(xs, [P.net_z(abs(x), P.NET_SAG_MAX) for x in xs], color='#A34A2A', lw=0.8, ls=(0, (4, 2)), zorder=6)
    zlow = P.Z_NET_EDGE - P.NET_SAG_MAX
    label(ax, 1.2, zlow - 0.3, 'loaded sag ≈ 0.90 (design, to confirm)', 6.5, color='#A34A2A', ha='left')

    def person(x, z0, h=1.85, fc='#D9C2A8'):
        ax.add_patch(Circle((x, z0 + h - 0.12), 0.11, fc=fc, ec=INK, lw=0.4, zorder=7))
        ax.add_patch(FancyBboxPatch((x - 0.2, z0), 0.4, h - 0.26, boxstyle='round,pad=0,rounding_size=0.12',
                                    fc=fc, ec=INK, lw=0.4, zorder=7))
    person(-0.9, 0.0)
    ax.annotate('', xy=(-0.4, zlow), xytext=(-0.4, 1.85), arrowprops=dict(arrowstyle='<|-|>', lw=0.5, color=INK,
                                                                         mutation_scale=6), zorder=8)
    label(ax, -0.15, (zlow + 1.85) / 2, '≥ 1.2 m\nclear', 6.5, ha='left')
    for x in (0.6, 2.4):
        ax.add_patch(FancyBboxPatch((x - 0.85, P.net_z(abs(x)) - 0.02), 1.7, 0.24,
                     boxstyle='round,pad=0,rounding_size=0.1', fc='#D9C2A8', ec=INK, lw=0.4, zorder=7))
    person(-6.4, P.FFL_UF, 1.8)
    person(7.6, P.TERRACE_Z, 1.8)
    for x0 in (-3.3, -1.0, 1.3):
        el = rad(61)
        ax.plot([x0 - 11.8 / math.tan(el), x0], [11.8, 0], color=LIGHT, lw=1.0, ls=(0, (6, 3)), zorder=1, alpha=0.8)
    label(ax, -9.6, 11.9, 'sun at noon in June (~61°, Bad Belzig 52° N)', 6.5, color='#9A6B12', ha='left')
    ax.plot([0, 0], [P.Z_NET_EDGE - 0.05, zcr - 0.3], color=GLASS, lw=0.9, ls=(0, (2, 2)), zorder=5)
    label(ax, 0.15, 6.3, 'variant: single rope from\nthe crown ring (not the glass)', 6.2, color='#3F5D6C', ha='left')
    AO_ = P.R_OUT + P.ANNEX_D
    R(P.R_OUT, P.ANNEX_H, AO_ + 0.45, P.ANNEX_H + 0.35, fc='#B79B7E')
    ax.plot([P.R_OUT, AO_ + 0.45], [P.ANNEX_H + 0.39] * 2, color='#6B7A3A', lw=2.2)
    R(AO_ - 0.35, 2.4, AO_, P.ANNEX_H, fc=POCHE)
    ax.plot([AO_ - 0.18] * 2, [0, 2.4], color=INK, lw=0.5)
    R(P.R_OUT, -0.35, AO_, 0.0, fc='#CDBFAF')
    R(AO_, 2.8, AO_ + 1.8, 2.92, fc=WOOD, lw=0.5)
    label(ax, (P.R_OUT + AO_) / 2, 1.3, 'foyer', 7)
    label(ax, AO_ + 1.0, 3.15, 'canopy', 6.5)
    label(ax, 7.4, P.FFL_UF + 1.9, 'bathroom (group shower)', 7.5)
    label(ax, -8.4, P.FFL_UF + 1.9, 'room R4', 7.5)
    label(ax, -8.3, P.CEIL_UF - 0.25, 'skylight', 6, color='#3F5D6C')
    label(ax, 5.0, 1.0, 'HALL', 10, weight='bold')
    label(ax, -4.85, P.FFL_UF + 1.5, 'walkway', 6.5, rotation=90)
    label(ax, 0, 8.6, 'glass dome Ø 11.60', 7, color='#3F5D6C')
    label(ax, 8.6, P.TERRACE_Z + 1.6, 'roof terrace', 7.5, ha='left')
    label(ax, -10.3, P.TERRACE_Z + 2.3, 'privacy screen 1.80', 6, ha='right')
    levels = [(0.0, '±0.00 hall', 0.1), (P.CEIL_GF, '+%.2f ceiling hall' % P.CEIL_GF, -0.2),
              (P.FFL_UF, '+%.2f upper floor' % P.FFL_UF, 0.18), (P.Z_NET_EDGE, '+%.2f net at edge' % P.Z_NET_EDGE, -0.22),
              (P.CEIL_UF, '+%.2f ceiling rooms' % P.CEIL_UF, 0.1), (P.TERRACE_Z, '+%.2f roof terrace' % P.TERRACE_Z, -0.15),
              (P.DOME_BASE_Z, '+%.2f dome base' % P.DOME_BASE_Z, 0.12),
              (P.TERRACE_Z + P.RAIL_H, '+%.2f railing' % (P.TERRACE_Z + P.RAIL_H), 0.1),
              (P.DOME_BASE_Z + P.DOME_RISE, '+%.2f dome top' % (P.DOME_BASE_Z + P.DOME_RISE), 0.1)]
    ly = -9.0
    for (z, t, dz) in sorted(levels):
        x = -14.4
        ax.plot([x, x + 0.6], [z, z], color=INK, lw=0.5)
        ax.add_patch(Polygon([(x + 0.3, z), (x + 0.15, z + 0.18), (x + 0.45, z + 0.18)], fc=INK, ec=INK, lw=0.3))
        ly = max(z + 0.1, ly + 0.36)
        if ly - z > 0.15:
            ax.plot([x + 0.6, x + 0.85], [z, ly], color=INK, lw=0.3)
        label(ax, x + 0.9, ly, t, 6.5, ha='left')
    # height dimensions: storeys (outside, north) and clear heights (inside)
    xs = 16.4
    zs = [0.0, P.FFL_UF, P.TERRACE_Z, P.DOME_BASE_Z + P.DOME_RISE]
    for i in range(len(zs) - 1):
        dim(ax, (xs, zs[i]), (xs, zs[i + 1]), '%.2f' % (zs[i + 1] - zs[i]), size=6.5)
    for z in zs:
        ax.plot([xs - 0.2, xs + 0.2], [z, z], color=INK, lw=0.5)
    dim(ax, (xs + 0.8, 0.0), (xs + 0.8, zs[-1]), '%.2f overall' % zs[-1], size=6.5)
    dim(ax, (7.3, 0.0), (7.3, P.CEIL_GF), '%.2f clear' % P.CEIL_GF, size=6.5)
    dim(ax, (-7.6, P.FFL_UF), (-7.6, P.CEIL_UF), '%.2f clear' % (P.CEIL_UF - P.FFL_UF), size=6.5)
    dim(ax, (-P.R_OUT, -0.9), (P.R_OUT, -0.9), '20.00', size=6.5)
    scale_bar(ax, 12.0, -1.2)
    fig.text(tx, 0.80, 'Net and structure (concept, to be verified)\n'
             '• Closed steel box ring beam (≈ 500 × 300, timber-clad)\n   on 4 columns takes the inward pull of the net\n'
             '• 4 columns: steel tube Ø 219 in a timber casing Ø 30 cm,\n'
             '   ≈ 400 kN each (6 columns would allow a lighter ring)\n'
             '• 16 radial + 3 ring ropes, fine 45 mm mesh,\n   tensioners at every radial under the pad\n'
             '• Net at +4.02 at the edge, 0.15 m pre-sag; design sag\n   ≈ 0.9 m leaves ≥ 1.2 m above a 1.9 m person\n'
             '• Variant: one rope from a steel spider in the crown\n   ring (dome structure, not glass)',
             fontsize=10, color=INK, va='top', linespacing=1.45)
    return fig


if __name__ == '__main__':
    for name, fn in (('01_ground_floor_plan', ground_floor), ('02_upper_floor_plan', upper_floor),
                     ('03_roof_terrace_plan', roof_plan), ('04_section_AA', section),
                     ('05_room_R2_1-25', room_detail)):
        f = fn()
        f.savefig(os.path.join(HERE, name + '.pdf'))
        f.savefig(os.path.join(HERE, name + '.png'), dpi=110)
        plt.close(f)
        print('wrote', name)
