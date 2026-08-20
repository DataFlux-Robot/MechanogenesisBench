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

Run:

```bash
python -m pip install -e '.[dev]'
mbench task validate tasks/conformance/calibration_to_fixture
mbench run tasks/conformance/calibration_to_fixture \
  --system-command "python examples/reference_system.py" \
  --guidance G3 --output runs/reference
pytest -q
lean formal/lean/BenchmarkProtocol.lean
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

## Current limitations

This is the benchmark protocol vertical slice, not yet the Mechanogenesis
multi-physics engine. The reference system is canned and the sample is explicitly
conformance-only. Resource fields other than observed wall time are declared,
not independently metered. Host process execution is not secure against a
hostile submission. Confidence intervals and physical calibration are delegated
to each trusted task evaluator.

## Next implementation sequence

1. Define the canonical mechanism IR: quantities, frames, topology, material,
   capability, interventions, construction/experiment bytecode and receipts.
2. Implement its deterministic reference interpreter plus schema/Lean
   preservation tests; migrate benchmark world files onto this IR.
3. Add generative geometry, assemblies, collision/contact, metrology and
   manufacturing-process semantics for real fixture generation.
4. Specify solver refinement contracts and add one optimized native backend;
   use Newton/other engines only for cross-validation and falsification.
5. Implement the LLM-centered Gθ runtime, multi-world model population,
   interventional separability policy and executable MRS search.
6. Add genuine isolated checkpoint forks across hidden future task suites and
   statistically powered Recursive Research Credit.
7. Containerize untrusted submissions and independently meter compute, energy,
   materials and human intervention.
8. Connect a bounded manufacturing workcell; advance from conformance to
   simulation and hardware evidence only as calibration justifies.

Read `docs/MECHANOGENESIS_ENGINE_SPEC.md` before changing architecture,
`docs/TASK_STANDARD.md` before adding tasks, and `PROOF_PACKAGE.md` before
strengthening any theoretical claim.
