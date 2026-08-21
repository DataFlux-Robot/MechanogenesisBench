# Canonical Mechanism IR 0.3

## Purpose

The canonical mechanism IR is the semantic spine shared by product execution
and benchmark evaluation. It describes what a mechanism and a construction
transition mean before choosing a CAD kernel, GPU solver or robot runtime.
Backends may refine this meaning; they may not silently replace it.

Version 0.3 is a deliberately bounded but closed vertical fragment. It covers
fixed-point quantities, axis-aligned constructive geometry, rigid datum-based
assembly, inventory-backed subtractive manufacturing, component consumption
and calibration-derived capability. It is the first persistent layer of the
large Mechanogenesis Engine, not a claim of complete multiphysics.

## Canonical objects

| Object | Canonical meaning in 0.3 |
| --- | --- |
| `WorldSpec` | Materials, physical inventory, machine envelopes, bounded disturbances and the baseline capability |
| `ShapeNode` | Labeled `box`, `cylinder`, `difference` or disjoint `union` geometry |
| `PartSpec` | Geometry, material, inventory provenance and local datums |
| `AssemblySpec` | Occurrences, root frame and a rigid mate tree |
| `MechanismProgram` | Content-addressed parts, assemblies and an ordered construction/calibration program |
| `WorldState` | Remaining inventory, constructed parts, assemblies, capabilities and monotone sequence number; valid states can become the exact parent of another program |
| `ExecutionReceipt` | Operation hash, parent/child world hashes, material balances, time, energy and semantic facts |

Quantities are integers with units in field names: `_um`, `_mdeg`, `_mg`,
`_us` and `_mj`. This avoids platform-dependent floating point in identity,
lineage and conservation decisions. Positions are signed; dimensions,
resources and tolerances are nonnegative or positive as declared.

## Geometry invariants

- All labels in one CSG tree are unique.
- Boxes and cylinders have positive dimensions.
- A subtraction cutter's conservative AABB must be contained by the base.
- Subtraction cutters must have pairwise disjoint AABBs in the reference
  fragment, so interval volume accounting does not double-count removal.
- Union children must have pairwise disjoint AABBs for the same reason.
- Remaining conservative volume must be positive.
- Cylinder volume uses rational lower/upper bounds on π; geometry-derived mass
  therefore remains an explicit interval until a conservative endpoint is
  selected.

These restrictions are reference semantics, not the final geometry language.
A future exact B-rep/SDF fragment may admit overlaps by supplying proof
obligations that preserve topology and volume bounds.

## Assembly and manufacturing invariants

- Every occurrence resolves to one declared part.
- Every non-root occurrence has exactly one rigid parent in version 0.3.
- Both mate datums must coincide within the declared integer tolerance.
- The reference interpreter currently rejects non-identity occurrence and
  datum rotations; rotation fields already exist for compatible extensions.
- A generated part must fit both its stock and machine envelopes and respect
  the machine's minimum feature bound; the requested process must appear in
  the machine's declared operation set.
- A purchased component must match declared provenance, material, geometry
  mass interval and available quantity.
- Every receipt closes material exactly:
  `input + reserve_draw = output + waste`.
- Receipts form an unbroken world-hash chain; an operation cannot mutate the
  world without producing a new bound receipt.
- `machine_part` must cite a same-machine process capability and records its
  absolute error bound on the constructed part.
- `qualify_process` can create a child process capability only when fixture
  error plus bounded transfer error is strictly below the parent process bound.

## Trust boundary

`ReferenceInterpreter` is the normative executable semantics for this
fragment. `cad_backend` compiles the same program to build123d/STEP for
geometric inspection. The STEP file is a refinement artifact and does not
decide inventory, error, capability or promotion semantics.

Lean proves that local mass closure composes globally, conservative
subtraction cannot create part mass, an empty receipt sequence cannot change a
world, and larger disturbance terms cannot reduce the stated error bound. The
proofs are conditional on the IR facts supplied to them; physical fidelity is
an empirical refinement obligation.

## Extension rule

New contact, compliant, thermal, electrical, machining or control semantics
must extend these identities through a versioned schema migration. Each
extension needs a reference case, adversarial rejection case, preservation
lemma and explicit refinement/calibration boundary. Adapter-only semantics are
not accepted into the canonical kernel.
