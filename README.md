# Tempel – round seminar building, concept v0.1

A first 3D concept model, plans, a section and renderings for a round two-storey
seminar building with a walkable net under a glass dome.

This is a concept for discussion only. The structure and the net need to be checked by a structural engineer and a
specialist net maker, and fire, escape and accessibility rules need to be checked against local code.

## What's here

| Folder | Content |
|---|---|
| `model/tempel.blend` | Full model (Blender 5.0) with materials, lights, people, cameras set up by `render.py` |
| `model/tempel.glb` | Same model as glTF binary (opens in Windows 3D Viewer, macOS Preview/Reality, SketchUp, Rhino, three.js, https://gltf-viewer.donmccurdy.com). Flat colours; the net keeps its mesh texture |
| `drawings/*.pdf` | Ground floor, upper floor, section A–A: vector, 1:100 on A2 (PNG previews next to them) |
| `renders/*.jpg` | Renderings (Cycles, 1600×900) |
| `model/params.py` | **All dimensions in one place**; the model and the drawings are both generated from it |
| `model/build_model.py`, `render.py`, `export_glb.py`, `drawings/plans.py` | Scripts to rebuild everything |

Rebuild: `pip install bpy matplotlib pillow`, then
`cd model && python3 build_model.py && python3 export_glb.py && python3 render.py` and `python3 ../drawings/plans.py`.

## Key dimensions

| | |
|---|---|
| Outer diameter | 20.00 m (wall 45 cm: timber frame, wood-fibre insulation, clay plaster inside, lime render / larch battens outside) |
| Hall | Ø 19.1 m inside, ≈ 270 m² net area, clear height 3.56 m (3.34 m under the exposed beams) |
| Upper floor level | +3.96 (slab build-up 40 cm incl. underfloor heating and impact sound insulation) |
| Net | Opening Ø 8.50 m, usable net Ø 7.80 m, anchored at +3.84 |
| Padded edge | 35 cm wide, 12 cm high, 48 upholstered linen segments on the ring beam (removable for access to the tensioners) |
| Walkway | 1.10 m (widens to 1.38 m at the posts, because the room fronts are a straight-sided decagon) |
| Rooms | 9 rooms, ≈ 17 m² each, 3.4 m wide at the door, 5.9 m at the outer wall, 4.1 m deep, clear height 2.60 m |
| Dome | Ø 11.20 m, rise 2.60 m, top at +9.75, 20 curved glulam ribs, steel crown ring with vent |

## Decisions I made (please review)

**Pillars.** There are 10 tree pillars on a Ø 8.70 m ring, one at each room partition line. Each one branches into four
arms under the ring beam. From below they frame the light column like a circle of trees. There are no other pillars in
the hall: 20 radial glulam beams (16×22 cm visible) span about 5 m from the ring beam to the outer wall, so the rest of
the hall is column-free. The beams make a sunburst pattern on the ceiling.

**Net structure.** A closed ring beam 30×52 cm (drawn in glulam; a steel box section inside a timber cladding would also
work) sits on the pillars. It takes the inward pull of the net as ring compression. The net has 16 radial ropes, rope
rings at r = 0.3, 1.3 and 2.6 m, an edge rope, and 45 mm fine mesh between them. There is a turnbuckle tensioner at
each radial, under the pad. There is no central support. The net rests 15 cm below the edge. I assumed about 0.9 m sag
under a crowd, which still leaves at least 1.1 m above a 1.9 m person standing below (see section). The net maker has
to confirm this figure. A house rule of no jumping probably belongs with it.

**Central-rope variant.** It is modelled but hidden: a steel spider inside the dome's crown ring carries a single rope
down to the net centre. The rope hangs from the rib structure, never from the glass. See `renders/08_variant_central_rope.jpg`. With the rope, the net is flatter and the centre stays up, but the view
straight up is interrupted and the dome ribs and crown have to carry the load. I'd keep the clear version unless the net
maker needs the rope.

**Dome over the walkway: yes.** I made the dome Ø 11.20 m, so it also covers the walkway (to r = 5.60 m). Otherwise the
ring walkway would be a dark internal corridor. With the dome over it, the walkway and the room fronts get daylight, and
the translucent doors glow.

**Stair: a half-turn (U) stair fits; a straight flight doesn't.** Floor to floor is 3.96 m: 22 risers × 180 mm, going
265 mm. That is two flights of 11 risers, 1.10 m wide, with a 1.15 m landing at the outer wall. It needs 3.85 m of
radial depth, and the slot has 4.1 m. A straight flight would need about 5.6 m of going plus landings. The stair starts
at the hall side and arrives back at the walkway, so nobody has to cross a room. There is a store under the upper
flight.

**Sliding doors.** Each room front has three panels: an oak frame with a linen or paper-laminate infill (shoji-like,
translucent). One panel is fixed and two slide, giving *closed*, *half open* (1.1 m) or *open* (2.2 m). There is a
fixed translucent transom above the doors up to the ceiling. The renderings show a mix of open, half-open and closed
doors.

**Entrance, changing, showers, WC: a curved annex on the north side.** It is a single storey with a green roof and hugs
the round building from 55° to 125°. People arrive at its east end (foyer with shoes, coats and a tea corner), walk
along a warm corridor with two changing rooms (lockers and 3 showers each), WCs (2 + accessible) and a tech/store room,
and enter the hall through a double door on the north axis. This keeps the hall round and complete and keeps the wet
rooms out of it. People can undress and shower before entering, and nobody undressed is ever visible from outside.

**Windows and facade.**
- Ground floor: high clerestory windows (sill 2.30 m) in 7 bays, which bring light in with no view in. On the south
  axis there are glazed garden doors with a heavy linen curtain, for an optional private walled garden.
- Upper rooms: one low, wide window each (sill 0.45 m, so you see sky and trees while lying down), with an inside
  shutter or curtain.
- Facade: the ground floor is in warm lime/clay render on a stone plinth. The upper floor is wrapped in vertical larch
  battens that also run in front of the room windows as a privacy screen. From inside they cast striped sunlight
  (see render 04).
- Roof: green sedum roof with 80 cm eaves.

**Heating and comfort.**
- Low-temperature underfloor heating everywhere (heat pump), with floor surfaces at about 26–28 °C and air at about
  24–26 °C for people undressed. The hall and the room ring are zoned separately.
- Balanced ventilation with heat recovery. The vent in the dome crown doubles as a summer purge.
- Clay plaster buffers humidity and damps sound. The partitions are 16 cm acoustic walls.
- The dome needs solar-control glass and probably an interior textile shade for summer. Check overheating.

**People in the renderings.** You left this open. I used abstract, sculptural figures in warm clay tones. They show
scale, poses and how the spaces are used, without committing to clothed or nude, and without the uncanny look of cheap
3D people. For presentation images, real photographed people (or licensed photoreal 3D people) can be composited in
later in whatever state of dress you choose.

## Still open / needs a professional

- **Structure**: ring beam size, pillar sizing, net forces, dome ribs, and the central-rope variant if chosen.
- **Fire safety**: an upper floor with 9 rooms and a single stair will probably need a second escape route (e.g. an
  outside stair from one room, or rescue openings) and a fire-rated stair. This depends on local code and occupancy.
- **Accessibility**: there is no lift in this concept. A platform lift could replace part of the store under the stair,
  or sit in the annex with a link at upper level.
- **Upper-floor WC**: people in the rooms have to go down to the annex. One option is to convert one room into a
  WC + shower (leaving 8 rooms).
- **Acoustics** between rooms, and between the walkway and the hall through the net (sound travels freely through it).
- **Privacy from the dome**: only an issue if anything overlooks the roof. A shade textile solves it.

## Renderings

| File | View |
|---|---|
| `01_hall_up_through_net` | Hall floor, looking up through the net into the dome, sun beams |
| `02_hall_wide` | Wide view of the hall, pillars and the sunlit centre |
| `03_walkway` | On the walkway: doors open, half-open and closed, the net beside you |
| `04_room_to_net` | Inside a room, looking out through the half-open door to the net |
| `05_on_net_up` | Lying on the net, looking up into the dome |
| `06_exterior` | Exterior, raised view from the north-east with the entrance annex |
| `07_walkway_evening` | The walkway in the evening, lanterns glowing through the doors |
| `08_variant_central_rope` | View 01 with the single central rope, for comparison |
