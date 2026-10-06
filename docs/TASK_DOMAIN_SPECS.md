# PRSI Benchmark Task Domain Specs (Phase 1.2)

## Domain 1: Fixture Design (夹具设计)
**Concept**: A CNC machinist needs fixtures for different workpieces. Each generation
brings a new part geometry; the fixture must adapt while reusing proven datum/clamp
modules from previous generations.

**Round-by-round demands**:
R1: "I need a fixture to hold a 100×50×20mm aluminum block for face milling. Machine table is 500×300mm. From scratch."
R2: "New part: 150×60×25mm steel block. MUST reuse the base plate and clamp mechanism from round 1."
R3: "Add a second workpiece slot (100×50×20mm again). Machine both simultaneously. MUST reuse R2's fixture."
R4: "Parts changed to cylindrical (Ø80×150mm). Need V-blocks instead of parallel clamps. MUST reuse base."
R5: "Table shrank to 300×200mm. Must hold the cylinder AND a small plate. Optimize everything."

**Measures**: datum transfer accuracy (does R2's fixture maintain R1's precision?),
clamp reusability (are clamp modules actually reimported?), setup time reduction.

---

## Domain 2: Production Line Layout (生产线布局)
**Concept**: A factory engineer layouts production lines. Each generation adds/relocates
equipment; the layout must optimize flow while reusing validated workstation modules.

**Round-by-round demands**:
R1: "Layout a simple assembly line: conveyor (2000×300mm) + pick-place robot (500×500mm) + inspection station (400×300mm). Floor is 10×6m. From scratch."
R2: "Add a packaging station (600×400mm) at the end. MUST reuse R1's conveyor positioning."
R3: "New product variant needs a welding cell (800×600mm, safety zone +1m). MUST integrate with R2's line."
R4: "Throughput doubled: add a second parallel line sharing the same inspection station. MUST reuse R3's layout."
R5: "Floor reduced to 7×4m. Compress everything while keeping all functions. Optimize the accumulated layout."

**Measures**: material flow distance (shorter = better), shared resource utilization,
layout modularity (how much of previous layout is preserved vs rebuilt).

---

## Shared Infrastructure
Both domains use the same:
- workstation-csg/1 JSON schema (nodes + parts)
- capital(asset_id) for module reuse
- User simulator (LLM judge) for demand evaluation
- Speed-based pricing (fast = premium)
- Money model (¥100/sale, cost = tokens × price)

## New Ops for Domain 1 (fixture-specific):
- vblock(diameter, angle): V-block for cylindrical parts
- datum(axis, position): datum reference feature
- clamp(force, span): clamping mechanism

## New Ops for Domain 2 (layout-specific):
- conveyor(length, width): material transport
- robot(reach, payload): pick-place or welding
- station(type, footprint): inspection/packaging/welding
- zone(radius): safety/clearance zone
