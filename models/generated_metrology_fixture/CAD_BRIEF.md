# CAD Brief — Generated Metrology Fixture

- Model: generated calibration/measurement fixture assembly.
- Task type: new parametric assembly generated from canonical mechanism IR.
- Units: canonical micrometres; STEP backend converts to millimetres.
- Coordinate convention: base footprint centred on XY; base bottom datum at
  `Z=0`; positive Z points out of the fixture.
- Selected base: 120 × 80 × 10 mm aluminum model.
- Functional geometry: two 6 mm locator pins in generated clearance bores and
  one 8 mm probe-reference post; three parts are inserted 3 mm into the base.
- Selected locator spacing: 80 mm.
- Selected modeled radial bore clearance: 0.02 mm.
- Selected modeled reference-post clearance: 0.02 mm.
- Selected public worst-case metrology bound: 0.12 mm, including locator and
  reference clearances, angular amplification, probe repeatability and the
  declared disturbance bound.
- Positioning: base is fixed root; each pin/post has a source-level rigid mate
  between its mount datum and generated base seat datum.
- Primary paths: `program.json`, `fixture.py`, `fixture.step`.
- Validation targets: four labeled assembly occurrences, 120 × 80 mm base,
  base bottom at Z=0, two locator axes 80 mm apart, 3 mm insert depth, reference
  post at the selected generated Y offset, closed positive-volume solids,
  canonical material closure and modeled worst-case error no more than 0.2 mm.
- Assumptions: the task world supplies calibrated component envelopes and mass;
  modeled materials are not strength-certified; press-fit/contact force,
  fastener retention, surface finish and thermal drift are outside reference
  semantics 0.2.
