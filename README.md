# Tempel – a new Blue Saloon for ZEGG, concept v0.7

A concept model, plans, a section and renderings for ZEGG's new temple of love (a successor to the Blue Saloon) in Bad
Belzig, Brandenburg. It is for community members and guests alike:
- seminars (Liebe Tanzen, temple retreats, the love school and young love school),
- erotic parties and temples,
- quiet sensual or sexual meetings, alone, in pairs or in groups,
- overnight stays during seminars. The outside is octagonal and in timber. The inside is round, with
a walkable net under a glass dome, a ring of small rooms, and a sun terrace on the roof.

This is a concept for discussion only. The structure and the net need to be checked by a structural engineer and a
specialist net maker, and the fire strategy by a fire engineer (Brandschutzplaner).

## What's here

| Folder | Content |
|---|---|
| `model/tempel.blend` | Full model (Blender 5.0) with materials, lights, people; cameras are set by `render.py` |
| `model/tempel.glb` | The same model as glTF (without the forest). Opens in Windows 3D Viewer, macOS Preview, SketchUp, Rhino, or https://gltf-viewer.donmccurdy.com. Flat colours only |
| `drawings/*.pdf` | Ground floor, upper floor, roof terrace, section A–A (vector, 1:100 on A2), step-free access options; PNG previews next to them |
| `renders/*.jpg` | Renderings (Cycles, 1600×900) |
| `model/params.py` | **All dimensions in one place**; the model and the drawings are both generated from it |
| `model/build_model.py`, `render.py`, `export_glb.py`, `drawings/plans.py` | Scripts to rebuild everything |

Rebuild: `pip install bpy matplotlib pillow`, then
`cd model && python3 build_model.py && python3 export_glb.py && python3 render.py` and `python3 ../drawings/plans.py`.

## What changed in v0.7: dimensions fine-tuned (within 15 %)

| | Before | Now | Why |
|---|---|---|---|
| Upper floor level | +3.96 | **+4.14** | The hall is 3.74 m clear, 3.52 m under the beams (was 3.34 m). That suits 290 m², dance and parties better, and leaves ≥ 1.2 m under the sagging net. The stairs have 22 risers of 188 mm, still within DIN 18065 |
| Walkway | 1.10 m | **1.25 m** | Room to pass people sitting on the pad and sliding doors, also at parties |
| Padded edge | 35 cm | **40 cm** | More margin for a head falling backwards; the usable net stays Ø 7.80 (opening Ø 8.60) |
| Dome | Ø 11.20, rise 2.60 m | **Ø 11.60, rise 2.90 m** | It still covers the wider walkway; it's more generous and sheds rain and snow better |
| Group shower | ≈ 1.0 × 3.0 m | **≈ 1.7 × 3.3 m** | Fits several people at once |
| Rooms | ≈ 24 m², 4.1 m deep | ≈ 23 m², 3.8 m deep | A side effect of the wider walkway |
| Heights above | terrace +7.10, dome top +10.15 | terrace +7.28, dome top +10.63 | Everything above the upper floor moves up |

## What changed in v0.6

| Feedback | Change |
|---|---|
| Keep the annex (simpler) | A **small annex on the north face** only (≈ 45 m², 5 m deep): foyer with coat benches, rails and shoe space; a **ground-floor WC**; a tech room (ventilation, heat-pump controls). The entrance door and canopy are on its outer face, on the axis of the hall door. The bathroom upstairs stays |
| Nice ceiling lights + indirect light on the walls | **Hall:** 7 large paper disc pendants (Ø 1.1 m) hung between the beams round the periphery; a continuous **timber light ledge** above the windows with a hidden warm LED strip washing the clay wall and ceiling (indirect); **clay wall shells** in the corners that throw light up and down the wall. **Rooms:** 2 clay wall shells each (indirect), plus the paper pendant and floor lantern. All warm white (about 2700 K) and dimmable. See `14_hall_evening` |

## What changed in v0.5

| Feedback | Change |
|---|---|
| Remove the annex; all essentials on the upper floor | The annex was removed (brought back in a smaller form in v0.6). Inside the hall door there is a heavy linen curtain for warmth and privacy |
| 2 WCs and a larger, all-gender shower for several people | The north room on the upper floor is now the **shared bathroom**: 2 WC cubicles, a walk-in **group shower** under the window with 3 shower heads and a tadelakt bench, a low curved privacy wall, 2 basins, a bench, and a skylight. That leaves **6 rooms**. See `13_bathroom` |
| Forget lift / ramp | Removed from the concept (note: German accessibility rules may still come up in the permit) |
| – | The small bathroom in the stair segment is now linen storage and laundry, plus space for the ventilation unit. The heat pump stands outside |

## What changed in v0.4

| Feedback | Change |
|---|---|
| Carved naked bodies: touch, embrace, being human among humans | **Not solved yet.** My first attempt stamped reliefs from the placeholder mannequins and looked bad, so it has been removed. The columns and the hall entrance are kept as plain timber, ready to be carved. See **Carvings** below |
| This is the new Blue Saloon, used for erotic parties and overnight stays | A **tea / party bar** in the hall (curved clay counter on the windowless NE wall). The rooms are planned for overnight use (fire rules below). **Signal lanterns** at every sliding door: lit = come in / ask, dark = private. This carries the "I choose contact or withdrawal" principle of the doors into the evening |
| ZEGG core values and awareness | An awareness / retreat place for the awareness team and anyone who needs quiet (it was in the annex; since v0.5 one of the rooms can serve as this during events). The spaces are graded: open net and hall → walkway → rooms with open / half / closed doors |

## What changed in v0.3

| Feedback | Change |
|---|---|
| Octagonal outside, round inside | Octagon, 20.00 m across the flats (21.65 m across the corners). Net, pad, walkway, dome and sliding doors stay as they were. There are now 8 segments (rooms + 1 stair segment), so every room has one straight outer wall (since v0.5: 6 rooms + bathroom) |
| Timber facade, big windows, bright | Vertical larch cladding. Large windows on 4 hall faces (2 × 2.10 × 2.60 m each, with deep window seats), 3 m garden doors to the south, 2.60 × 1.65 m windows in every room with sliding larch shutters |
| Climbing plants | Ivy and Virginia creeper on steel cables at the corners and between the windows, and on the external stair |
| Set at ZEGG | Clearing in a Scots-pine forest on sandy ground, sun angles for 52° N (about 61° at noon in June) |
| Terrace as a place to lie in the sun | Sun deck on the south side with 6 daybeds, 3 sun sails and a 1.80 m slatted privacy screen; loungers west and east; planters with grasses to the north; bench ring around the dome |
| Columns too dominant | Now **4 straight, slim columns**: a steel tube Ø 219 mm inside a round timber casing, Ø 30 cm outside. Previously 10 branching tree columns. See the structure notes below |
| Rooms looked like a hotel | An earthen sleeping nest with soft rounded edges under the window, a clay bench along one wall, sheepskins, layered textiles, a plant, lanterns and clay ceilings. No hotel furniture |
| Skylights in the rooms | A 1.40 × 1.10 m skylight over each nest: walk-on frosted glass set into the terrace, so there is light but no view in from above |

## Key dimensions

| | |
|---|---|
| Outside | Octagon 20.00 m across the flats; timber-frame wall 45 cm (clay plaster inside, wood fibre, larch outside) |
| Hall | ≈ 290 m², clear height 3.74 m (3.52 m under the beams); 4 columns on Ø 8.80 m |
| Upper floor | +4.14. Net: opening Ø 8.60, usable Ø 7.80. Padded edge 0.40 m. Walkway 1.25 m |
| Rooms | 6 × ≈ 23 m² (+ shared bathroom in the 7th): 4.6 m wide at the door, 7.9 m at the outer wall, 3.8 m deep, 2.60 m high |
| Dome | Ø 11.60, rise 2.90 m, on a 45 cm upstand (base +7.73, top +10.63), 20 glulam ribs, crown ring with vent |
| Roof terrace | Deck +7.28; railing 1.20 m, or 1.80 m privacy screen on the south faces |
| Stair | Spiral around a timber trunk, Ø 3.3 m, treads 1.45 m wide; hall → upper floor 22 × 188 mm, → terrace 17 × 185 mm, going 264 mm on the walking line |
| External stair | On the NW face: ground → upper floor → terrace, 1.20 m wide flights, 188 / 185 × 270 mm |
| Bathroom | North segment of the upper floor, ≈ 24 m²: 2 WCs, walk-in group shower, 2 basins, all gender |
| Annex | North face, 5 m deep: foyer + coats, WC, tech; entrance door with canopy |

## Structure: how few columns?

The ring beam around the net carries:
- the net and the people on it,
- the inner half of the upper floor,
- the dome,
- part of the roof terrace.

That is roughly 1,500 kN in service (about 2,000 kN design load). The net's inward pull puts the closed ring into
compression, which is uncritical. What decides the number of columns is the ring beam's **bending and torsion**
between them.

| Columns | Span of the ring | Ring beam | Load per column |
|---|---|---|---|
| 6 | ≈ 4.6 m | steel box ≈ 400 × 300 | ≈ 330 kN |
| **4 (drawn)** | ≈ 6.8 m | steel box ≈ 500 × 300 | ≈ 400–500 kN |
| 3 | ≈ 7.5 m | very heavy; torsion and net vibration become a problem | not recommended |

With 4 columns the load per column is easy for a Ø 219 steel tube. The heavier ring is still only about 52 cm deep, so
it fits the existing edge. The radial glulam beams span to the outer wall, so the rest of the hall stays column-free.
The timber casing also gives the steel the fire protection it needs. The structural engineer must confirm all of this,
including how the net and the gallery feel underfoot (vibration).

## German regulations: fire safety, windows (Brandenburg, BbgBO)

You asked whether the design meets German rules. **v0.2 did not. v0.3 is designed to be approvable in principle**,
but it needs a fire-safety concept (Brandschutzkonzept) by a specialist. Several points are exceptions (Abweichungen)
that need compensating measures.

**Classification**
- Building class 3: the top floor with rooms is under 7 m, and the total area is over 400 m².
- **With overnight stays and more than 12 beds, it is a special building (Sonderbau), specifically a Beherbergungsstätte.**
  It also becomes a Sonderbau if a room is meant for more than 100 people. Above 200 visitors the assembly-building rule
  (Versammlungsstättenverordnung) applies too.

**Two built escape routes from the upper floor and the terrace.** The Beherbergungsstätten rules require both routes to
be structural; fire-brigade ladders do not count.
1. The **spiral stair as the necessary stair**:
   - Its going on the walking line is 264 mm, which meets the DIN 18065 minimum of 260 mm. It was enlarged for this.
   - It stands in **its own enclosure**: a fire-rated glass drum. The doors are held open on magnets and close in a fire.
   - It has an exit straight outside at the bottom and a smoke vent in the stair house at the top.
   - Open point: whether the authority accepts a spiral stair as a necessary stair in a Beherbergungsstätte.
2. The **external stair on the NW face** is the second route, from the terrace via the upper floor to the ground. The
   wall behind it has no room windows, only the doors; it may need to be fire-rated.

**Open void through the net.** Hall and upper floor are open to each other through the net, about 580 m² over two
storeys. The standard allowance is 400 m² over two storeys, so this is an **exception** (Abweichung). Typical
compensating measures:
- a fire alarm system (Brandmeldeanlage),
- smoke extraction through the dome crown and the stair house,
- a flame-retardant net and textiles (class B-s1,d0 / B1),
- emergency lighting.

**Construction.** Building class 3 allows timber construction with fire-retardant (feuerhemmend, F30) load-bearing
parts and floors. The Sonderbau rules may ask for more.

**Windows.**
- Daylight: every room needs window area of at least 1/8 of its floor area, about 3 m² for 24 m². The new
  2.60 × 1.65 m window plus the skylight easily meets this; the old 1.60 m window was too small.
- Rescue opening: the opening sash is at least 0.90 × 1.20 m, with the sill at most 1.20 m. The larch shutters slide,
  so they don't block it.
- Fall protection: a sill below about 0.80–0.90 m on the upper floor needs protection. The lower part up to 0.90 m is
  fixed laminated safety glass.
- Skylights in the terrace: walk-on laminated glass.
- Summer overheating: the dome and the big windows need outside shading (GEG / DIN 4108-2).

**Also needed for guests staying overnight:**
- smoke detectors / alarm in every room,
- WCs and a shower on the upper floor (the shared bathroom),
- accessibility (accessible WC, step-free access) will probably be raised by the authority; not included by your choice.

## Carvings

The idea stays: naked bodies, touch and embrace, carved into the timber, so that sexuality is present and welcome
without being the focus. The **4 column casings** (Ø 30 cm, 3.3 m high) and a **timber arch around the hall entrance**
are the natural places. Both are inside, so nothing is visible from outside.

Figures like these only work if they are really well drawn. That is a job for an artist, not for procedural 3D:
1. an artist (ideally from the community) draws the figures as a band per column and as an arch composition;
2. those drawings are carved by a woodcarver, or CNC-milled as low relief and hand-finished;
3. the drawings can then be put back into this model for renderings.

The model has a switch for this (`CARVINGS` in `build_model.py`), which maps height images onto the columns and the arch.

## Open questions for you

1. **Carvings:** who draws the figures (see **Carvings** above)?
2. **Sanitary capacity:** 3 WCs (1 down, 2 up) and one group shower. Enough for your events?
3. **Where do guests change for seminars in the hall?** The bathroom upstairs, or their rooms?

## Other decisions (unchanged from v0.2, please review)

- **Net**: 16 radial ropes, 3 ring ropes, an edge rope, 45 mm fine mesh, and tensioners under the removable pad.
  Pre-sag is 0.15 m. At an assumed 0.9 m sag under a crowd, there is still at least 1.1 m above a 1.9 m person below.
- **Central-rope variant**: hidden in the model. The rope hangs from a steel spider in the crown ring, never from the
  glass (see `08_variant_central_rope`). I'd keep the clear version.
- **Dome over the walkway**: yes (Ø 11.20), so the walkway and the doors get daylight.
- **Sliding doors**: three shoji-type panels per room: *closed*, *half open* (1.4 m) or *open* (2.9 m).
- **Entrance**: through the small annex on the north face (foyer, coats, WC), then through a curtain into the hall.
- **Heating**: low-temperature underfloor heating everywhere (floors about 26–28 °C, air about 24–26 °C), heat pump,
  and balanced ventilation with heat recovery. Clay plaster buffers humidity.
- **People in the renderings**: abstract, sculptural figures that show scale and use, without committing to a dress
  code.

## Renderings

| File | View |
|---|---|
| `01_hall_up_through_net` | Hall floor, looking up through the net into the dome, sun beams |
| `02_hall_wide` | The hall: 4 slim columns, big windows with seats, sunlit centre |
| `03_walkway` | The walkway: doors open, half-open and closed, the net beside you |
| `04_room_to_net` | Inside a room: sleeping nest, clay bench, skylight, looking out through the half-open door |
| `05_on_net_up` | Lying on the net, looking up into the dome |
| `06_exterior` | Aerial view from the south-west: octagon, climbing plants, sun deck, pine forest |
| `06b_exterior_eye_level` | Eye level from the south-east: garden doors and big windows |
| `06c_exterior_stair_side` | The north-west side: external stair and the small annex |
| `09_roof_terrace` | The sun deck: daybeds, sails, privacy screen, dome |
| `10_spiral_stair` | The spiral stair in its glass drum, seen from the hall |
| `13_bathroom` | The shared bathroom: group shower under the window, WCs, basins |
| `14_hall_evening` | The hall in the evening: paper pendants, indirect light ledge, clay wall shells |
| `07_walkway_evening` | The walkway in the evening, lanterns glowing through the doors |
| `08_variant_central_rope` | View 01 with the single central rope, for comparison |
