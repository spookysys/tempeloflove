"""The EXTENDED flyby: the basic one (flythrough.WAY_BASIC, unchanged) plus three short detours:

1. during the loop on the upper walkway: into a small room with open doors (slot 5) and out again;
2. into the bathing room on the upper floor (slot 0: rain showers under the skylight, bench, WC doors);
3. at the end, instead of the aerial pull-back: round the outside to the annex on the north face (entrance with
   canopy), in through the glass entrance, ending in the foyer (coat benches) facing the doors to the hall.

    FLY_PATH=extended python3 flythrough.py stills|frames ...
"""
import math

from mathutils import Vector

import params as P

UF, TZ = P.FFL_UF, P.TERRACE_Z


def pol(r, a, z=0.0):
    return Vector((r * math.cos(math.radians(a)), r * math.sin(math.radians(a)), z))


def FP(k, n, t, z=0.0):
    a = math.radians(P.slot_center(k))
    return Vector((n * math.cos(a) - t * math.sin(a), n * math.sin(a) + t * math.cos(a), z))


def _index(way, p):
    return next(i for i, w in enumerate(way) if (w[0] - p).length < 1e-6)


def extend(basic):
    way = list(basic)
    # 1. small room (slot 5, doors fully open: the opening is at t > -0.7), after the walkway point at 315 deg
    i = _index(way, pol(5.15, 315, UF + 1.72))
    k = 5
    room = [                              # the paper pendant hangs at n 7.0, t 0.9: camera low, looking down,
        (FP(k, 4.75, 0.8, UF + 1.6), FP(k, 7.6, 1.9, UF + 0.9), 0.5, 19),    # so the lamp stays above the frame
        (FP(k, 5.1, 1.6, UF + 1.5), FP(k, 8.0, 1.0, UF + 0.6), 0.5, 19),
        (FP(k, 6.4, 1.7, UF + 1.4), FP(k, 9.4, -0.4, UF + 0.5), 0.5, 18),    # in: bed, window, the forest
        (FP(k, 7.6, 1.6, UF + 1.35), FP(k, 8.6, -1.7, UF + 0.4), 0.45, 18),  # a slow look round
        (FP(k, 7.3, 1.8, UF + 1.4), FP(k, 6.2, -2.0, UF + 0.6), 0.3, 18),    # across the room
        (FP(k, 6.6, 1.8, UF + 1.5), FP(k, 4.0, 2.4, UF + 1.1), 0.4, 19),     # turning back to the door
        (FP(k, 5.0, 1.6, UF + 1.7), pol(2.6, 345 + 55, UF - 0.3), 0.7, 19),
    ]
    way[i + 1:i + 1] = room
    # 2. bathing room (slot 0), between the walkway points at 435 and 465 deg; the sliding door leaves t 0..0.75
    j = _index(way, pol(5.15, 435, UF + 1.72))
    k = P.BATH_SLOT
    bath = [                              # plan: showers mid-back, daybed nook at t > 0, long bench at t < 0
        (FP(k, 4.7, -1.0, UF + 1.7), FP(k, 7.5, 0.6, UF + 1.3), 0.6, 18),    # turning towards the door early
        (FP(k, 4.85, 0.35, UF + 1.68), FP(k, 8.0, 0.35, UF + 1.2), 0.45, 18),
        (FP(k, 5.6, 0.38, UF + 1.65), FP(k, 9.3, 0.0, UF + 1.0), 0.45, 17),   # through the half-open door
        (FP(k, 7.0, 0.3, UF + 1.62), FP(k, 9.4, -0.6, UF + 0.9), 0.4, 17),    # rain showers under the skylight
        (FP(k, 7.5, 0.0, UF + 1.6), FP(k, 8.9, 2.1, UF + 0.6), 0.3, 17, 2.5),      # the aftercare nook
        (FP(k, 7.6, -0.2, UF + 1.6), FP(k, 9.1, -1.9, UF + 0.6), 0.3, 17, 2.8),    # the warm bench under the window
        (FP(k, 7.4, 0.1, UF + 1.61), FP(k, 7.6, -3.0, UF + 1.0), 0.3, 17, 2.5),   # along the bench to its end
        (FP(k, 7.1, 0.3, UF + 1.62), FP(k, 5.4, -1.0, UF + 1.1), 0.3, 18, 2.5),    # turning back: the changing bench
        (FP(k, 6.3, 0.4, UF + 1.63), FP(k, 3.5, 0.6, UF + 1.4), 0.35, 18),    # back to the door
        (FP(k, 5.5, 0.4, UF + 1.66), FP(k, 3.0, 1.2, UF + 1.4), 0.45, 18),
        (FP(k, 4.8, 0.6, UF + 1.7), pol(2.6, 465 + 55, UF - 0.3), 0.7, 19),
    ]
    way[j + 1:j + 1] = bath
    # 3. annex: replace the final pull-back (the last three points) by a glide round to the north face
    e = _index(way, pol(11.8, 198, TZ + 3.2))
    k = P.ENTRY_SLOT                                       # FP(0, n, t) = (-t, n): n = y (north), t = -x
    annex = [
        (pol(12.5, 190, TZ + 3.0), Vector((0, 0, TZ)), 1.4, 22),
        (pol(17.0, 150, TZ + 2.0), pol(10, 110, 4.0), 2.2, 24),               # clear of the external stair
        (pol(21.0, 112, 5.0), FP(k, 12.5, 0.0, 1.5), 2.2, 24),
        (FP(k, 21.0, -3.0, 2.6), FP(k, 14.5, 0.0, 1.4), 1.6, 24),             # the annex: canopy, entrance
        (FP(k, 17.8, -0.6, 1.8), FP(k, 14.8, 0.0, 1.3), 0.9, 22),
        (FP(k, 15.9, 0.0, 1.66), FP(k, 12.0, 0.0, 1.4), 0.7, 20),             # under the canopy
        (FP(k, 14.2, 0.0, 1.65), FP(k, 12.3, 2.3, 0.9), 0.55, 18),            # in: coat benches and rails
        (FP(k, 13.3, 0.4, 1.63), FP(k, 11.2, -2.2, 1.0), 0.4, 18),            # ending across the foyer: bench,
        (FP(k, 13.0, 0.9, 1.62), FP(k, 10.4, -1.0, 1.1), 0.3, 18),            # coats, the doors to the hall
    ]
    way[e:] = annex
    return way


def open_annex_doors():
    """Event evening: the glass double doors of the annex entrance stand open (the camera passes through)."""
    import bpy
    g = bpy.data.objects.get('annex_glass')
    if g:
        me = g.data
        mw = g.matrix_world
        import bmesh
        bm = bmesh.new()
        bm.from_mesh(me)
        door = [f for f in bm.faces if abs((mw @ f.calc_center_median()).x) < 1.0]      # the leaf pair at t ~ 0
        bmesh.ops.delete(bm, geom=door, context='FACES')
        bm.to_mesh(me)
        bm.free()
    f = bpy.data.objects.get('annex_entrance_frame')
    if f:
        import bmesh
        bm = bmesh.new()
        bm.from_mesh(f.data)
        mw = f.matrix_world
        post = [v for v in bm.verts if abs((mw @ v.co).x) < 0.08 and (mw @ v.co).z < 2.35]   # centre post
        bmesh.ops.delete(bm, geom=post, context='VERTS')
        bm.to_mesh(f.data)
        bm.free()
