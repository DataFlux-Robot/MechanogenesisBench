# Lean-Sovereign Mechanogenesis Kernel 0.2 (MechanogenesisBench 0.6)

## Sovereignty rule

Lean is the authoritative language for canonical physical state, evidence,
refinement and promotion. Python, GPU solvers and devices remain execution
backends, but no backend output can change a promoted world unless it crosses
the Lean checker:

$$
W \xrightarrow[\mathcal A]{P,E,C} W'
$$

where $P$ is the program, $E$ the observations/receipts, $C$ the certificate
and $\mathcal A$ the explicit assumption ledger. A separately produced
evaluator decision $D$ must name the same parent and child world hashes.
Sovereignty means:

$$
\boxed{\text{No promoted world transition or decision without Lean acceptance.}}
$$

It does not mean that physical reality is derivable from mathematics. Lean
proves consequences of recorded model/calibration assumptions; experiments are
still required to justify those assumptions.

## Kernel modules

The authoritative import surface is
`formal/lean/Mechanogenesis/SovereignKernel.lean`:

```text
Mechanogenesis/Kernel/
├── Quantity.lean             fixed-point dimensions and scale compatibility
├── Frame.lean                canonical frame identity
├── World.lean                world, inventory and capability identity
├── Digest.lean               canonical SHA-256 syntax
├── AssumptionLedger.lean     explicit empirical/model assumptions
├── Evidence.lean             evidence tiers and observation receipts
├── RefinementContract.lean   proof-producing external backend interface
├── PhysicalTransition.lean   lineage, mass, sequence and resource semantics
├── Promotion.lean            non-aggregated promotion gate
├── CanonicalIR.lean          Lean-owned lowered mechanism language
├── MetrologyRefinement.lean  proof-checked metrology error contract
└── FixtureCertificate.lean   composed certificate ABI/checker
```

The kernel contains no project-declared `axiom` or `sorry`. `#print axioms`
audits the central theorems; Lean may report its standard logical foundations
such as quotient soundness, propositional extensionality or classical choice.
These must not be confused with declaring a simulator physically correct.

## External refinement contract

Every numerical/device backend is represented by:

```lean
structure RefinementContract (Input Output Certificate) where
  trustClass : TrustClass
  precondition : Input → Prop
  postcondition : Input → Output → Prop
  check : Input → Output → Certificate → Bool
  checkerSound :
    check input output certificate = true →
    precondition input → postcondition input output
```

The implementation may run outside Lean. Only the checker and its soundness
theorem belong to the trusted semantics. Four trust classes are defined:

1. `kernelVerified`;
2. `certificateChecked`;
3. `empiricallyCalibrated`;
4. `advisory`.

LLM proposals are advisory until lowered through a stronger contract.

## Fixture certificate ABI

The Python reference interpreter is the first `certificateChecked` backend. It
emits a content-addressed certificate containing:

- sovereign semantics and backend identifiers;
- Gθ strategy hash, support size and attempted candidates;
- world specification, parent world, program and child world hashes;
- sequence before/after;
- every operation receipt and exact material balance;
- total time and energy;
- a required assumption ledger.
- a Lean-native canonical program manifest;
- exactly one bound metrology refinement certificate per calibration operation.

## Canonical program boundary

`CanonicalIR.lean` owns the accepted lowered language for the current fixture
fragment. Its manifest contains flattened but topology-preserving shape trees,
materials, inventory, machines, parts, assemblies, occurrences, rigid mates
and typed records for exactly five operations:

```text
machine_part | consume_component | assemble | calibrate | qualify_process
```

The checker rejects unknown operations, malformed primitive/composite shapes,
duplicate identities, missing parent shapes, depth-inconsistent or disconnected
shape cycles, non-canonical child indices, mismatched part-source inventory,
unknown part/material/inventory/machine/assembly references, invalid
calibration roles and non-contiguous operation indices. Unused operation fields
must have their canonical zero value, preventing multiple encodings of the same
instruction. The sovereign composition additionally requires every canonical
operation hash to equal the corresponding transition-receipt operation hash.

Python currently performs the deterministic surface-program-to-manifest codec.
The trusted evaluator independently regenerates the complete certificate and
compares it byte-for-byte with the submitted object. Therefore Python remains
in the codec TCB, but it no longer chooses what the lowered language means.
Generating this ABI directly from Lean remains the next trust reduction.

## First physical refinement module

`MetrologyRefinement.lean` checks a calibration receipt against:

$$
e_{angular}=\left\lceil
\frac{2c_{radial}s_{workpiece}}{d_{locator}}
\right\rceil,
$$

$$
e_{worst}=c_{radial}+c_{reference}+e_{angular}
+e_{manufacturing}+e_{probe}+e_{disturbance},
$$

and $e_{absolute}=e_{source\ process}+e_{worst}$. The certificate is bound to
the canonical calibration operation, its workpiece-span parameter and its exact
parent/child receipt hashes. Duplicate certificates are rejected, and every
canonical `calibrate` operation must be covered. Lean proves that every accepted
bound contains the declared disturbance term and that the absolute bound cannot
be smaller than its source-process term.

This proves formula/accounting fidelity, not calibration truth. Geometry-role
binding, additive error composition and input calibration fidelity remain
explicit assumption identifiers at the conformance tier.

The evaluator wraps this immutable certificate with a promotion decision
containing the artifact hash, the same parent/child world hashes, conservative
parent/child error bounds, required improvement, net value, robustness result
and evidence tier. Together with the benchmark's artifact-to-world binding,
this prevents an improvement measured on one world transition from being
credited to another.

Kernel acceptance checks:

```text
schema/semantics binding
∧ digest syntax
∧ 0 < attempts ≤ generated support
∧ required assumptions present
∧ consecutive receipt indices
∧ parent → ... → child lineage
∧ canonical_operation_hashes = receipt_operation_hashes
∧ exact material closure for every receipt
∧ every calibration operation has one bound metrology certificate
∧ sequence_after = sequence_before + receipt_count
∧ duration/energy totals equal receipt sums
```

The required assumptions in Sovereign Kernel 0.2 are:

- `fixed_point_arithmetic`;
- `hash_identity`;
- `reference_model_fidelity`;
- `geometry_role_binding`;
- `additive_error_budget`;
- `calibration_parameter_fidelity`.

The last assumption prevents the present conformance model from being
misrepresented as hardware truth.

## Central theorem

`checked_certificate_allows_only_accounted_strict_promotion` proves:

$$
\operatorname{PromotionCheck}(C,D)=\mathrm{true}
\Rightarrow
\operatorname{ValidAccounting}(C)
\land \operatorname{AssumptionsExplicit}(C)
\land \operatorname{CanonicalIRValid}(C)
\land \operatorname{MetrologyRefinementValid}(C)
\land \operatorname{BoundTo}(D,C)
\land e_{child}<e_{parent}
\land \operatorname{NetValuePositive}(D)
\land \operatorname{RobustnessPassed}(D)
\land \operatorname{EvidenceBound}(D,C).
$$

The theorem does not prove the assumption ledger true. A future hardware
backend must replace or strengthen assumptions with calibration receipts,
signatures and experimentally justified bounds.

## Executing the checker

```bash
lake build sovereignCheck promotionCheck canonicalIRCheck metrologyCheck
.lake/build/bin/sovereignCheck certificate.json
.lake/build/bin/promotionCheck promotion-envelope.json
.lake/build/bin/canonicalIRCheck canonical-program.json
.lake/build/bin/metrologyCheck metrology-certificate.json
python -m mechanogenesis_engine.cli verify-certificate certificate.json
python -m mechanogenesis_engine.cli verify-promotion promotion-envelope.json
python -m mechanogenesis_engine.cli verify-canonical-ir canonical-program.json
python -m mechanogenesis_engine.cli verify-metrology metrology-certificate.json
```

Both conformance fixture evaluators require both Lean executables. If either is
missing, if the transition certificate is rejected, or if the evaluation is
not bound to that certificate's world pair, the generation cannot be promoted.

## Adding a new solver or device

A backend is not integrated by writing an adapter alone. It must add:

1. canonical input/output definitions;
2. a bounded valid regime and assumptions;
3. a pure certificate checker;
4. a Lean soundness theorem for the exact postcondition;
5. adversarial accepted/rejected certificate fixtures;
6. an evidence ceiling appropriate to calibration;
7. independent evaluator replay or custody verification.

Newton, FEM, collision, thermal, learned-world-model and hardware modules can
all use this interface. They cannot alter the world-state semantics or promote
their own outputs by assertion.

## Current boundary

Version 0.2 makes Lean operationally sovereign over lowered IR well-formedness,
transition accounting, bounded metrology formulas and promotion in the fixture
vertical slice. It does not yet compute B-rep/SDF geometry, mass/fit/contact
physics, numerical solver residuals, sensor signatures or calibrated hardware
semantics. The Python codec is independently replayed but not yet generated
from Lean; that remaining TCB boundary is explicit.
