# Reference Interpreter and Generated Fixture

## Deterministic transition system

The reference interpreter loads a `WorldSpec`, verifies that a program names
its exact initial world hash, validates all geometry and assembly facts, then
executes five operation kinds:

1. `machine_part`: consume stock, construct a geometry-derived part, account
   for waste, machining time and energy;
2. `consume_component`: instantiate a provenance-bound purchased component;
3. `assemble`: consume available part status into a rigid assembly;
4. `calibrate`: derive local and absolute-frame metrology bounds from generated
   geometry, cited manufacturing process, repeatability and disturbance;
5. `qualify_process`: let an assembled fixture create a strictly better
   same-machine process capability under an explicit transfer bound.

Each operation hashes the pre-state and post-state. The result contains both a
process hash (the program identity) and a child world hash (the physical-state
identity). This prevents a source-code edit from being confused with a world
transition and prevents an alleged world change without a receipt.

The interpreter is intentionally simple and auditable. It models no forces,
press fits, wear, surface finish or thermal effects. Such effects must enter as
explicit future semantics or calibrated disturbance terms, not implied by a
successful conformance run.

As of version 0.6, the interpreter is a certificate-checked backend rather
than the owner of the lowered language. Every execution certificate embeds a
Lean canonical manifest and a metrology refinement certificate. The trusted
evaluator regenerates the whole object from the stored program and replayed
execution; Lean checks its operation/reference language, metrology arithmetic
and receipt binding before promotion.

## First autonomous generation task

`conformance.generated_metrology_fixture` exposes a bounded workcell, stock,
two locator pins, one reference post and a performance goal. The baseline does
not choose a fixture from a catalog. It synthesizes 240 complete mechanism
programs by varying base geometry, locator spacing, bore clearance and
reference location; it executes every syntactically and physically reachable
candidate and selects lexicographically by:

1. modeled worst-case error;
2. base material volume;
3. construction duration.

The selected program creates a 120 × 80 × 10 mm base, two 6 mm locators at an
80 mm baseline, 20 µm radial clearance and an 8 mm reference post at Y=15 mm.
Its public error model is:

$$
e_{worst}=c_l+c_r+
\left\lceil\frac{2c_l s}{d}\right\rceil+e_m+e_p+e_d,
$$

where $c_l$ is locator radial clearance, $c_r$ reference clearance, $s$ the
workpiece span, $d$ locator spacing, $e_m$ manufacturing repeatability,
$e_p$ probe repeatability, and $e_d$ the declared disturbance bound. The
selected public bound is 130 µm. Hidden cases
change span and add disturbance; all five currently remain within 200 µm.

The independent evaluator retrieves the actual construction-program MRS
object, re-parses and re-executes it, and binds the submitted process hash,
world hashes, receipts and artifact to that execution. It then applies hidden
interventions and the existing fail-closed gain, robustness and net-value
promotion gates.

## CAD refinement result

The same canonical program compiles to a labeled STEP assembly with four leaf
occurrences. Automated inspection found:

- bounding box: 120 × 80 × 32 mm;
- base bottom/top: Z=0 / Z=10 mm;
- locator axes: X=-40 and X=40 mm, hence 80 mm separation;
- locator/reference bottoms: Z=7 mm, hence 3 mm insertion into the base;
- reference post: Y=15 mm;
- three through-bores visible from the underside.

Four rendered review views are stored under
`models/generated_metrology_fixture/review/`. This establishes compiler and
artifact consistency for the selected case, not strength or tolerance
certification.

The stateful two-generation task is described in
[`PHYSICAL_CONTRIBUTION_CHAIN.md`](PHYSICAL_CONTRIBUTION_CHAIN.md).

## Reproduction

```bash
mengine search-fixture \
  tasks/conformance/generated_metrology_fixture/public/mechanism_world.json \
  tasks/conformance/generated_metrology_fixture/public/fixture_goal.json \
  --program-output /tmp/fixture-program.json \
  --execution-output /tmp/fixture-execution.json

mengine execute \
  tasks/conformance/generated_metrology_fixture/public/mechanism_world.json \
  /tmp/fixture-program.json

mbench run tasks/conformance/generated_metrology_fixture \
  --system-command "python examples/generated_fixture_search_system.py" \
  --guidance G5 --output runs/generated-fixture
```
