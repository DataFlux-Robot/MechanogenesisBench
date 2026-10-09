# Status and roadmap

**English** | [简体中文](STATUS_AND_ROADMAP.zh-CN.md)

Snapshot: 2026-09-02

## Current maturity

MechanogenesisBench is a developer preview, not a complete benchmark. The
current public slice can validate task packages, run an external process,
verify a content-addressed multi-generation submission, execute a trusted
evaluator and emit a vector score. It also contains a small Lean protocol
kernel and negative tests. The demand-driven microfactory slice now requires an
OpenAI-compatible model to emit the complete two-generation action: demand
beliefs, product specifications and capital plans for mechanical assembly, PCB
test and battery-calibration operators. Literal actions are executed without a
benchmark-side parameter search. Hidden demand truth and physical disturbances
measure calibration, product robustness and successor-operator advantage, and
accepted runs produce an executable Lean certificate binding the two operator
generations. The certificate also carries the task, evaluator, plan, product,
execution and construction-trace digests, so an independent replay can bind the
proved inequalities to the exact run bytes.

The present release is insufficient for fair third-party ranking because task
diversity is narrow, physical trials are not packaged as a reproducible public
suite, evaluator isolation is process-level only, and the new model adapter has
not yet been independently reproduced across organizations and model providers.

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
5. **Protocol examples cannot serve as competitive baselines.** The original
   reference system only checks the ABI and verifier. The generated-fixture
   task is a stronger reachability baseline, but one conformance family still
   cannot support a general model ranking.
6. **Demand, product and production must be coupled.** A useful machine-making
   task cannot score a product brief independently of whether the agent builds
   the fixtures, electronics test capability and calibration capacity needed
   to make the product and its successor. The current microfactory task couples
   all three, including exact operator inheritance.

## Executable demand-microfactory slice

The current two-generation simulation represents a low-speed mobility product
and three reusable production operators. It distinguishes four capabilities:

1. infer a five-attribute demand distribution from aggregate comparisons;
2. turn the belief into a physically feasible product and outcome forecast;
3. allocate finite capital to mechanical, PCB and battery production capacity;
4. update the demand belief after new evidence and reuse the exact manufactured
   operator bundle in the successor generation.

The reference run achieves two promotions, 100% held-out robustness, a demand
update gain of 697,856 ppm and a 117,524 ppm inherited-operator advantage. These
numbers validate reachability and the evaluator; they are not a third-party
model result. Its registered two-generation resource account is US$131,587.50,
121.36 kg of input material and 10.527 GJ; product BOM and operator materials
share one finite inventory. The next baseline campaign runs GLM-5.3-Flash in matched
history-enabled and stateless arms with complete request/response bytes.

The remaining realism gap is explicit: product physics is deterministic
simulation, aggregate preferences are synthetic, and the production cell has
three operator channels rather than a full industrial bill of process. M2/M4
will add multiple product families, supply disruptions, assembly routing,
inspection/rework, hardware metrology and authorized human outcome adapters.
Lean proves the finite certificate relation; the evidence tier records whether
the bound trace came from this simulator or a separately qualified instrument.

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
