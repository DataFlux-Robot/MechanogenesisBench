# MechanogenesisBench Handoff

## Mission and repository

Private GitHub repository:
`git@ssh.github.com:ExuberantWitness/MechanogenesisBench.git` over SSH port 443.

Mechanogenesis Engine is intended to be a large, native physical invention and
simulation product. MechanogenesisBench is its benchmark/evidence plane using
the same canonical semantics. Do not turn the project into a Newton wrapper, a
fixed-parts combinatorial toy or a benchmark-only physics definition.

The first recursive commercial task is: a manufacturing unit autonomously
designs and makes a tooling/metrology artifact that improves the ability to
make the next generation.

## Research thesis

Current-task reward cannot identify which research trajectory improves the
future research generator. CG-MRSG estimates Recursive Research Credit through
isolated generator forks: start parent and candidate generator checkpoints from
the same parent, held-out future-task distribution and budget, then compare
future productive research time/cost.

Recursive promotion requires four independent conditions:

1. reachability: the construction can execute from the promoted physical state;
2. causal attribution: improvement is assigned through isolated forks;
3. reliable discrimination: confidence bounds and hidden interventions separate
   child from parent by a positive margin;
4. positive net value: improvement remains after resource cost.

The executable chain is:

```text
Gθ -> MRS -> generated mechanism/construction program -> physical experiment
   -> independent promotion -> isolated future-task forks -> Gθ update
```

An MRS contains a task-specific language, semantics, compiler, compiler
certificate, theory portfolio, construction program, experiment program,
evaluator contract and generator update proposal. These may result in PID, MPC,
search, neural models, LLM agents or newly invented representations; they are
not a fixed plug-in catalog.

## What exists now

- Python 3.11 task/submission/evaluation schemas and CLI.
- Three tracks and G1–G5 guidance withdrawal.
- Content-addressed nine-object MRS bundles.
- Separate process and world lineages.
- Exact integer material closure.
- Task/evaluator/artifact hash binding and evidence ceilings.
- Fail-closed promotion and Recursive Research Credit gates.
- Non-aggregated score vector.
- A two-generation `CONFORMANCE` reference task and canned system.
- Lean-checked bounded-promotion, reward-insufficiency and isolation lemmas.
- Adversarial unit tests and CI.
- Canonical Mechanism IR 0.3 with fixed-point quantities, labeled axis-aligned
  CSG, parts/datums, rigid assembly, materials, inventory and machines.
- A deterministic reference interpreter for machining, component consumption,
  assembly and calibration with per-operation world/material/resource receipts.
- A generated-metrology-fixture task whose baseline synthesizes and executes
  240 mechanism programs instead of selecting a canned part.
- Independent hidden-case re-execution of the stored construction-program MRS
  object, plus a generated labeled STEP assembly and four visual review views.
- Lean-checked local-to-global mass closure, subtractive no-creation,
  receipt-chain and error-bound monotonicity lemmas.
- Stateful `execute_from_state` semantics and machine-process capabilities.
- A two-generation `recursive_fixture_process` task that executes the strict
  physical chain `S0 fixture -> P1 qualified process -> S1 successor fixture`.
- A Lean theorem showing that strict process-error improvement plus
  non-worsening local artifact error implies strict successor absolute-error
  improvement.
- Gθ/MRS runtime 0.1: `ResearchRequest -> StrategyProposer ->
  FixtureResearchStrategy -> trusted compiler -> canonical program -> MRS`.
- A deterministic physics-prior proposer and a real OpenAI-compatible LLM
  proposer behind the same JSON-only, fail-closed strategy boundary.
- Strategy-generated task symbols, ordered candidate support, hard execution
  budget, multi-world hypotheses and robust experiment gate. The reference
  strategy reaches the current task's robust candidate in one execution rather
  than exhaustive execution of 240 candidates.
- Independent evaluators now reconstruct the submitted strategy and rerun its
  strategy-to-program mapping for both the one- and two-generation tasks.
- An executable support ablation: short-baseline/large-clearance support has no
  feasible candidate and fails under the same compiler/interpreter.
- `experiments/gtheta_phase_boundary.py` also shows a nominal 200 μm candidate
  being rejected only after grounded span/disturbance model expansion.
- Lean theorems for the exact feasible-support/budget phase boundary, monotone
  contraction under grounded world expansion, strict candidate removal by a
  separating model, and compiler-soundness certificate transfer.
- Lean Sovereign Kernel 0.1 is now the authority for the executable fixture
  slice's quantities/identity, assumptions/evidence, external refinement
  contracts, physical-transition accounting and promotion semantics.
- Every Gθ-produced compiler-certificate MRS object contains exact
  strategy/program/world hashes, receipt lineage, material/resource accounting
  and explicit model assumptions. Both fixture evaluators require the compiled
  `sovereignCheck` executable and fail closed.
- Accepted evaluator decisions additionally cross `promotionCheck`, which
  binds the decision to the same parent/child world hashes and checks positive
  margin, strict bounded-error improvement, net value, robustness and evidence
  tier. The central Lean theorem returns accounting validity, explicit
  assumptions, world binding and strict improvement.

Run:

```bash
python -m pip install -e '.[dev]'
lake build sovereignCheck promotionCheck
mbench task validate tasks/conformance/calibration_to_fixture
mbench run tasks/conformance/calibration_to_fixture \
  --system-command "python examples/reference_system.py" \
  --guidance G3 --output runs/reference
pytest -q
lean formal/lean/BenchmarkProtocol.lean
lean formal/lean/MechanismIR.lean
lean formal/lean/GTheta.lean

mbench run tasks/conformance/generated_metrology_fixture \
  --system-command "python examples/generated_fixture_search_system.py" \
  --guidance G5 --output runs/generated-fixture

mbench run tasks/conformance/recursive_fixture_process \
  --system-command "python examples/recursive_fixture_process_system.py" \
  --guidance G5 --output runs/recursive-fixture
```

## Lessons already incorporated

- Process state and physical world state are different identities; track both.
- A digest without an available content-addressed object is not an MRS asset.
- Private evaluator data must be version-bound without exposing it in the
  public package digest.
- Rejected attempts are evidence but do not advance lineage.
- “Faster” needs a vector denominator and prospective future tasks; current
  episode reward is not recursive credit.
- Formal verification certifies conditional protocol implications, not world
  model fidelity or universal physical RSI.
- External solvers must refine/falsify canonical semantics, not own it through
  adapters.
- Component source geometry must be centered in its own local frame; occurrence
  poses then remain identical across the reference interpreter and STEP
  assembly. An earlier mixed local/world origin representation caused visible
  occurrence-frame drift and was rejected during CAD inspection.
- The generated reference post contributes its own bore-clearance term; a
  measurement reference that does not affect the error budget is semantically
  decorative and should not pass review.
- Local tool accuracy and absolute process accuracy are distinct. Treating
  them as one number makes bootstrapping circular. IR 0.3 lets machine relative
  repeatability support the first local fixture while that fixture subsequently
  reduces the larger absolute setup bound.
- A physical descendant must cite the contributed process capability in its
  actual construction instruction. Merely observing that both artifacts exist
  is not a recursive causal chain.
- A transition certificate and improvement claim must be identity-bound. An
  earlier theorem allowed an independently accepted claim beside a valid
  transition; it was logically true but too weak for causal promotion. Version
  0.5 replaces it with a parent/child-world-bound promotion envelope.

## Current limitations

This is now a real generative geometry/manufacturing and generated-research
strategy vertical slice, but not yet the large multiphysics Mechanogenesis
Engine. An LLM can generate the current strategy schema, but the trusted
compiler accepts only one fixture topology and three parameter semantics. This
is bounded task-language generation, not unrestricted language or algorithm
invention. Rigid/contact force, tolerances, strength, surface finish, wear and
thermal drift are not simulated. The sample remains explicitly
conformance-only. Resource fields other than observed wall time are declared,
not independently metered. Host process execution is not secure against a
hostile submission. Confidence intervals and physical calibration are
delegated to each trusted task evaluator.

The two-generation task proves only a bounded reference-model
physical-contribution witness. Gθ now generates and binds both research
strategies, but both strategies target the same trusted topology/compiler
fragment and deterministic reference proposer. No learned checkpoint update,
isolated generator fork or hardware calibration establishes Recursive Research
Credit or the 800/10 µm machine bounds and 10 µm transfer bound.

Lean sovereignty here is operational but bounded: no current fixture
promotion bypasses its two checkers, yet the reference physical equations and
hidden evaluator bounds remain explicit empirical/model assumptions. Lean does
not establish that those machine parameters describe hardware.

## Next implementation sequence

1. Move canonical IR structures and lowering judgments into Lean, beginning
   with general frame composition, stable topology identity, intervals and
   uncertainty; generate/validate the Python ABI from that source.
2. Define the first proof-producing geometry/contact/metrology refinement
   contract, including residual and calibrated-regime certificates.
3. Extend IR 0.3 with stable B-rep/SDF views, experiment bytecode and custody
   signatures.
4. Add native collision/contact, fit, tolerance, metrology and machining-force
   semantics, keeping the current interpreter as the oracle-sized fragment.
5. Expand Gθ beyond the present parameter-language fragment: allow generation
   of different topology grammars, compiler sketches and experiment bytecode,
   but require trusted lowering/certificates before canonical execution.
6. Specify solver refinement contracts and add one optimized native backend;
   use Newton/other engines only for cross-validation and falsification.
7. Implement the full multi-world model population,
   interventional separability policy and executable MRS search.
8. Add genuine isolated checkpoint forks across hidden future task suites and
   statistically powered Recursive Research Credit.
9. Containerize untrusted submissions and independently meter compute, energy,
   materials and human intervention.
10. Connect a bounded manufacturing workcell; advance from conformance to
   simulation and hardware evidence only as calibration justifies.

Read `docs/MECHANOGENESIS_ENGINE_SPEC.md` and
`docs/CANONICAL_MECHANISM_IR.md` before changing architecture,
`docs/REFERENCE_INTERPRETER.md` before extending execution,
`docs/PHYSICAL_CONTRIBUTION_CHAIN.md` before changing recursive process
semantics, `docs/GTHETA_MRS_RUNTIME.md` before changing the research generator,
`docs/LEAN_SOVEREIGN_KERNEL.md` before adding any solver/device backend,
`docs/TASK_STANDARD.md` before adding tasks, and `PROOF_PACKAGE.md` before
strengthening any theoretical claim.
