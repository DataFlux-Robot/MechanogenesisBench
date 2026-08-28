# Status and roadmap

Snapshot: 2026-08-28

## Current maturity

MechanogenesisBench is a developer preview, not a complete benchmark. The
current public slice can validate task packages, run an external process,
verify a content-addressed multi-generation submission, execute a trusted
evaluator and emit a vector score. It also contains a small Lean protocol
kernel and negative tests.

The present release is insufficient for fair third-party ranking because task
diversity is narrow, physical trials are not packaged as a reproducible public
suite, evaluator isolation is process-level only, and the reference submission
is a canned conformance fixture rather than a learned agent.

## Lessons incorporated from recent development

1. **Formal soundness is not algorithmic reachability.** A checker can prove
   that an accepted artifact satisfies a predicate without proving that an
   agent can generate such an artifact. The benchmark will report validity,
   reachability/execution and empirical performance as separate fields.
2. **A receipt is not the event it describes.** Future hardware tracks must
   bind sensor observations, calibration, custody, construction and evaluation
   to independently replayable evidence.
3. **Environment failures are first-class outcomes.** Dependency failure,
   OOM, timeout, parser failure, construction failure and experiment failure
   must remain distinguishable from scientific rejection.
4. **One feasible sample is not robustness.** Task-family breadth, fresh
   seeds, perturbations and held-out compositions are required before promotion
   to a benchmark claim.
5. **Protocol examples cannot serve as competitive baselines.** The current
   reference system only checks the ABI and verifier.

## Development plan

### M0 — Repository and governance boundary

- Maintain a clean benchmark-only public repository.
- Publish schema versioning, deprecation and disclosure policies.
- Select an explicit open-source/data license before stable release.
- Add contribution, security and evaluator-disclosure guidance.

Exit criterion: a clean clone contains no FLUXPRSI implementation, internal
training trace, credential or unbounded local artifact.

### M1 — Third-party agent contract

- Freeze the first versioned MRS/submission ABI.
- Add containerized system adapters and deterministic resource accounting.
- Specify network, filesystem, retry and human-intervention policies.
- Publish at least one non-canned open baseline that does not share evaluator
  implementation.

Exit criterion: two independently written agents complete the same public task
without repository-local imports.

### M2 — Task and failure coverage

- Expand beyond the current fixture-oriented conformance case to multiple
  mechanism, sensing, actuation, manufacturing and experimental-design families.
- Add parser, feasibility, construction, metrology and causal-attribution
  failure suites.
- Register held-out compositional splits and anti-shortcut negative controls.

Exit criterion: task-family and failure-stage coverage are measured and no
single hand-written strategy solves the full suite.

### M3 — Evaluator custody and reproducibility

- Separate public task material from sealed evaluator assets.
- Add signed task/evaluator manifests, deterministic replay and tamper checks.
- Replace process-only execution with a competition-grade isolation profile.
- Publish reference run bundles and reproducibility checks without revealing
  sealed targets.

Exit criterion: independent maintainers reproduce every released score and
negative control from immutable bundles.

### M4 — Physical evidence track

- Define metrology, sensor, calibration, uncertainty and chain-of-custody
  requirements per task family.
- Add simulator-to-independent-backend and hardware-in-the-loop qualification.
- Pilot real construction and experiment tasks with explicit human and material
  accounting.

Exit criterion: at least one task has repeatable, independently audited
hardware evidence; simulation and conformance remain visibly lower tiers.

### M5 — Bounded recursive track

- Require exact operator and checkpoint lineage across generations.
- Require every candidate claimed by posterior selection to have been executed
  under a frozen, matched sibling protocol.
- Separate update validity, weight-level effect, future-task contribution and
  physical contribution.
- Add negative controls for front-loaded resources, software subsidy, evaluator
  leakage, unchanged weights and unreachable accepted states.

Exit criterion: a finite recursive claim is emitted only when every edge has
both executable evidence and the required causal/physical qualification.

### M6 — Public benchmark release

- Run an external beta with multiple organizations and heterogeneous agents.
- Freeze task/evaluator versions and publish benchmark cards.
- Establish issue triage, result invalidation and leaderboard governance.

Exit criterion: stable release only after external reproduction and threat-model
review. Until then, repository results are development evidence, not a general
ranking of agent capability.
