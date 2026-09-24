# Tempel – seminar building at ZEGG, concept v0.3

A concept model, plans, a section and renderings for a two-storey seminar building for workshops on love, intimacy
and sexuality at ZEGG in Bad Belzig, Brandenburg. The outside is octagonal and in timber. The inside is round, with
a walkable net under a glass dome, a ring of small rooms, and a sun terrace on the roof.

This is a concept for discussion only. The structure and the net need to be checked by a structural engineer and a
specialist net maker, and the fire strategy by a fire engineer (Brandschutzplaner).

## What's here

| Folder | Content |
|---|---|
| `model/tempel.blend` | Full model (Blender 5.0) with materials, lights, people; cameras are set by `render.py` |
| `model/tempel.glb` | The same model as glTF (without the forest). Opens in Windows 3D Viewer, macOS Preview, SketchUp, Rhino, or https://gltf-viewer.donmccurdy.com. Flat colours only |
| `drawings/*.pdf` | Ground floor, upper floor, roof terrace, section A–A: vector, 1:100 on A2 (PNG previews next to them) |
| `renders/*.jpg` | Renderings (Cycles, 1600×900) |
| `model/params.py` | **All dimensions in one place**; the model and the drawings are both generated from it |
| `model/build_model.py`, `render.py`, `export_glb.py`, `drawings/plans.py` | Scripts to rebuild everything |

Rebuild: `pip install bpy matplotlib pillow`, then
`cd model && python3 build_model.py && python3 export_glb.py && python3 render.py` and `python3 ../drawings/plans.py`.

## What changed in v0.3 (your feedback)

| Feedback | Change |
|---|---|
| Octagonal outside, round inside | Octagon, 20.00 m across the flats (21.65 m across the corners). Net, pad, walkway, dome and sliding doors stay as they were. There are now **7 rooms + 1 stair segment**, so every room has one straight outer wall |
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
| Hall | ≈ 290 m², clear height 3.56 m (3.34 m under the beams); 4 columns on Ø 8.70 m |
| Upper floor | +3.96. Net: opening Ø 8.50, usable Ø 7.80. Padded edge 0.35 m. Walkway 1.10 m |
| Rooms | 7 × ≈ 24 m²: 4.5 m wide at the door, 7.9 m at the outer wall, 4.1 m deep, 2.60 m high |
| Dome | Ø 11.20, rise 2.60 m, on a 45 cm upstand (base +7.55, top +10.15), 20 glulam ribs, crown ring with vent |
| Roof terrace | Deck +7.10; railing 1.20 m, or 1.80 m privacy screen on the south faces |
| Stair | Spiral around a timber trunk, Ø 3.3 m, treads 1.45 m wide; hall → upper floor 22 × 180 mm, → terrace 17 × 185 mm, going 264 mm on the walking line |
| External stair | On the NW face: ground → upper floor → terrace, 1.20 m wide flights, 180 / 185 × 270 mm |
| Annex | On the N + NE faces, 6.2 m deep: entrance/foyer, 2 changing rooms with 3 showers each, WCs (incl. accessible), cleaning store, tech |

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
- a WC and shower on the upper floor (now in the stair segment),
- an accessible WC (in the annex),
- probably a lift or other step-free access to at least part of the upper floor. There is no lift yet.

## Other decisions (unchanged from v0.2, please review)

- **Net**: 16 radial ropes, 3 ring ropes, an edge rope, 45 mm fine mesh, and tensioners under the removable pad.
  Pre-sag is 0.15 m. At an assumed 0.9 m sag under a crowd, there is still at least 1.1 m above a 1.9 m person below.
- **Central-rope variant**: hidden in the model. The rope hangs from a steel spider in the crown ring, never from the
  glass (see `08_variant_central_rope`). I'd keep the clear version.
- **Dome over the walkway**: yes (Ø 11.20), so the walkway and the doors get daylight.
- **Sliding doors**: three shoji-type panels per room: *closed*, *half open* (1.4 m) or *open* (2.9 m).
- **Annex**: people arrive at its east end, change and shower, and enter the hall on the north axis. Nobody undressed
  is visible from outside.
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
| `06c_exterior_stair_side` | The north-west side: external stair and annex |
| `09_roof_terrace` | The sun deck: daybeds, sails, privacy screen, dome |
| `10_spiral_stair` | The spiral stair in its glass drum, seen from the hall |
| `07_walkway_evening` | The walkway in the evening, lanterns glowing through the doors |
| `08_variant_central_rope` | View 01 with the single central rope, for comparison |
