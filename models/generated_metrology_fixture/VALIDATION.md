# Generated Fixture Validation Record

Primary artifact: `fixture.step`

The STEP was generated from `fixture.py`, which loads `program.json` and uses
the build123d/cadpy refinement backend. The canonical reference execution is in
`execution.json`.

## Deterministic inspection

- assembly: 18 faces, 30 edges;
- bounding box minimum: `[-60, -40, 0]` mm;
- bounding box maximum: `[60, 40, 32]` mm;
- bounding box size: `[120, 80, 32]` mm;
- one assembly root and four leaf occurrences;
- `base` occurrence frame: `[0, 0, 0]` mm;
- `locator_a` occurrence frame: `[-40, -10, 14.5]` mm;
- `locator_b` occurrence frame: `[40, -10, 14.5]` mm;
- `reference_post` occurrence frame: `[0, 15, 19.5]` mm;
- measured locator X separation: 80 mm;
- measured base bottom/top separation: 10 mm;
- locator/reference lower faces: Z=7 mm, yielding 3 mm insertion through the
  base top at Z=10 mm.

These frames exactly match the four occurrence poses in the canonical program.

## Visual inspection

The ISO, top, front and opposite-ISO snapshots in `review/` were inspected.
They show the intended three-post layout, two equal-height locator pins, taller
reference post, rectangular base and all three underside through-bores. No
detached occurrence or unintended solid was observed.

## Evidence boundary

This record validates canonical-to-STEP structure, dimensions and visible
placement. It does not certify load capacity, press-fit retention, machining
tolerance, surface finish, wear, thermal drift or real metrology accuracy.
