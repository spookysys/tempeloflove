"""Step-free access to the upper floor and the roof terrace: three options side by side.

    python3 access_options.py  -> 05_step_free_access_options.pdf / .png
"""
import math
import os

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Polygon, Rectangle  # noqa: E402

import plans as D  # noqa: E402
from plans import P, FP, oct_pts, poly, label, INK, POCHE, WOOD, GREEN  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
RAMP = '#D9B77E'
SLOPE = 0.06                     # DIN 18040-1: max 6 %
RUN = 6.0                        # max run between landings
LAND = 1.5
L_UF = P.FFL_UF / SLOPE          # 66 m of sloped run
L_RF = P.TERRACE_Z / SLOPE       # 118 m
TOT_UF = L_UF + (math.ceil(L_UF / RUN) - 1) * LAND + 2 * LAND
TOT_RF = L_RF + (math.ceil(L_RF / RUN) - 1) * LAND + 2 * LAND


def base(ax, title):
    poly(ax, oct_pts(P.R_OUT), fc='#EFE5D6', lw=0.8, z=2)
    ax.add_patch(plt.Circle((0, 0), P.R_DOME, fc='#DCE8EC', ec=D.GLASS, lw=0.6, zorder=3))
    D.annex_plan(ax, labels=False)
    D.ext_stair(ax, 'UF')
    ax.set_xlim(-24, 24)
    ax.set_ylim(-20, 26)
    ax.set_aspect('equal')
    ax.axis('off')
    ax.set_title(title, fontsize=13, weight='bold', color=INK, loc='left')


fig = plt.figure(figsize=(23.386, 11.0))
fig.text(0.02, 0.965, 'Step-free access to the upper floor (+3.96) and the roof terrace (+7.10)',
         fontsize=20, weight='bold', color=INK, va='top')
fig.text(0.02, 0.925, 'DIN 18040-1 (public buildings): ramps max. 6 %%, a 1.50 m landing after every 6 m, clear width '
         '≥ 1.20 m, handrails both sides.  →  Ramp to the upper floor ≈ %.0f m long, to the roof ≈ %.0f m.'
         % (TOT_UF, TOT_RF), fontsize=12, color=INK, va='top')

# A: spiral ramp around the octagon
ax = fig.add_axes([0.01, 0.12, 0.32, 0.74])
base(ax, 'A  Ramp gallery wrapped around the building')
apo = P.R_OUT + 1.0
per_wrap = 8 * 2 * apo * math.tan(math.radians(22.5))
pts = []
n = 400
total_len = TOT_UF
for i in range(n + 1):
    s = total_len * i / n
    a = P.partition_angle(P.STAIR_SLOT) + 360 * s / per_wrap   # start at the NW corner, counter-clockwise
    shift = 1.9 * math.floor(s / per_wrap)                      # 2nd wrap drawn outside (it would stack above)
    r = P.octo_r(a, apo + shift)
    pts.append((r * math.cos(math.radians(a)), r * math.sin(math.radians(a))))
ax.plot(*zip(*pts), color='#A37A3F', lw=9, solid_capstyle='butt', zorder=1, alpha=0.8)
label(ax, 0, -17.8, 'to the upper floor: ≈ %.0f m ≈ %.1f times round the building\n'
      'to the roof: ≈ %.0f m ≈ %.1f times round (stacked 2 storeys high)' %
      (TOT_UF, TOT_UF / per_wrap, TOT_RF, TOT_RF / per_wrap), 10.5)
label(ax, 0, 22.6, '+ becomes a covered gallery / veranda\n– runs in front of every window, clashes with\n'
      'annex + external stair, very large and costly', 10)

# B: garden hill with switchbacks at the NW
ax = fig.add_axes([0.34, 0.12, 0.32, 0.74])
base(ax, 'B  Garden hill with switchback ramp')
lanes = math.ceil(TOT_UF / (RUN + LAND))
k = P.STAIR_SLOT
for i in range(lanes):
    n0 = P.R_OUT + 2.6 + 3.2 + i * 1.8
    q = [FP(k, n0, -3.6), FP(k, n0 + 1.5, -3.6), FP(k, n0 + 1.5, 3.9), FP(k, n0, 3.9)]
    ax.add_patch(Polygon(q, closed=True, fc=RAMP, ec=INK, lw=0.4, zorder=3))
hill = [FP(k, P.R_OUT + 5.4, -4.8), FP(k, P.R_OUT + 6.0 + lanes * 1.8, -4.8),
        FP(k, P.R_OUT + 6.0 + lanes * 1.8, 5.1), FP(k, P.R_OUT + 5.4, 5.1)]
ax.add_patch(Polygon(hill, closed=True, fc=GREEN, ec=INK, lw=0.6, alpha=0.6, zorder=2))
br = [FP(k, P.R_OUT + 2.45, 2.2), FP(k, P.R_OUT + 5.8, 2.2), FP(k, P.R_OUT + 5.8, 3.9), FP(k, P.R_OUT + 2.45, 3.9)]
ax.add_patch(Polygon(br, closed=True, fc=WOOD, ec=INK, lw=0.6, zorder=4))
p = FP(k, P.R_OUT + 8 + lanes * 0.9, -9.5)
ax.set_xlim(-36, 16)
ax.set_ylim(-20, 32)
label(ax, p[0], p[1], '%d switchbacks\n≈ %.0f m ramp\non a 4 m high\nplanted earth hill' % (lanes, TOT_UF), 10)
label(ax, 0, -17.8, 'footprint ≈ 10 × %.0f m next to the house; reaches the upper floor only\n'
      '(the roof needs another ≈ %.0f m)' % (lanes * 1.8 + 1.5, TOT_RF - TOT_UF), 10.5)
label(ax, 0, 22.6, '+ could be a garden amphitheatre / sun slope\n– huge earthworks, only makes sense if the\n'
      'site already slopes', 10)

# C: platform lift at the external stair
ax = fig.add_axes([0.67, 0.12, 0.32, 0.74])
base(ax, 'C  Platform lift in the external stair tower')
q = [FP(k, P.R_OUT + 2.5, 2.2), FP(k, P.R_OUT + 4.3, 2.2), FP(k, P.R_OUT + 4.3, 4.1), FP(k, P.R_OUT + 2.5, 4.1)]
ax.add_patch(Polygon(q, closed=True, fc='#7F9AA6', ec=INK, lw=0.8, zorder=5))
p = FP(k, P.R_OUT + 3.4, 3.15)
label(ax, p[0], p[1], 'lift', 9, color='white', weight='bold')
bridge = [FP(k, P.R_OUT - 0.05, 2.3), FP(k, P.R_OUT + 2.5, 2.3), FP(k, P.R_OUT + 2.5, 3.9), FP(k, P.R_OUT - 0.05, 3.9)]
ax.add_patch(Polygon(bridge, closed=True, fc='none', ec=INK, lw=0.8, ls=(0, (3, 2)), zorder=5))
p = FP(k, P.R_OUT + 9.5, -3.0)
label(ax, p[0], p[1], 'vertical platform lift\n1.6 × 1.9 m shaft\n3 stops: garden, upper floor\nlanding, terrace (bridge)', 10)
label(ax, 0, -17.8, 'no machine room, no pit; clad in larch with climbing\nplants as part of the external stair', 10.5)
label(ax, 0, 22.6, '+ smallest, reaches all three levels, cheapest\n– still a machine (service contract), '
      'slow (0.15 m/s)', 10)

fig.text(0.02, 0.035, 'Rough costs, order of magnitude only, to be checked with quotes: '
         'A) ≈ 150 m² of timber/steel ramp with railings and foundations, easily €150–300k;  '
         'B) earthworks, retaining edges, ramps, bridge – similar or more;  '
         'C) platform lift for 3 stops ≈ €40–70k plus maintenance.',
         fontsize=11, color='#6B5E55')
fig.savefig(os.path.join(HERE, '05_step_free_access_options.pdf'))
fig.savefig(os.path.join(HERE, '05_step_free_access_options.png'), dpi=90)
print('wrote access options', round(TOT_UF), round(TOT_RF))
