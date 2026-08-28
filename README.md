# MechanogenesisBench

MechanogenesisBench is a developer-preview benchmark for third-party agents
that propose, construct and test physical devices. It evaluates evidence and
process—not whether an agent can merely describe a plausible mechanism.

Our motivating view is that physical recursive self-improvement (PRSI) begins
only when intelligence can autonomously manufacture and validate devices, and
when the resulting physical capability can causally improve a later research
or manufacturing cycle. Textual self-revision, a CAD image or an endpoint
score alone is not physical recursion.

> **Status: incomplete developer preview.** The repository exposes a usable
> submission ABI, fail-closed verifier, vector scorecard, a small conformance
> task and machine-checked protocol invariants. Its present task coverage and
> physical validation are not sufficient for a complete benchmark or a public
> leaderboard. Interfaces may change before the first stable release.

## What this repository is

- A benchmark protocol for third-party agents.
- A task-package, submission and evaluator interface.
- A non-scalar scorecard covering capability, robustness, autonomy, resources
  and bounded recursive contribution.
- A strict evidence-tier boundary between conformance, simulation,
  independently checked simulation, hardware-in-the-loop and hardware.
- Lean 4 definitions and proofs for bounded protocol properties.
- A deliberately canned reference submission used only to test conformance.

## What this repository is not

- It is not FLUXPRSI and contains no FLUXPRSI training loop, model weights,
  weight-update policy, researcher implementation or internal experiment
  history.
- It is not a claim that PRSI has been achieved.
- It is not yet a competition-grade sandbox or a representative task suite.
- Lean acceptance proves the encoded finite protocol condition; it does not
  turn a simulator receipt into hardware evidence or prove that a learned
  policy can reach a successful update.

The clean boundary is intentional: benchmark participants should implement
their own agents against the public contract, while the evaluator remains
independent of any one system.

## Episode model

```text
agent -> MRS -> construction program -> execution/experiment -> evidence
      -> independent evaluator -> bounded promotion decision
      -> optional next-generation submission
```

An MRS is the submitted mechanism-research specification bundle. A recursive
claim additionally requires linked generations, exact lineage, evaluator-owned
evidence and positive resource-normalized downstream contribution. The current
repository tests only bounded, finite claims.

## Quick start

Requirements: Python 3.11+. Lean is optional for the Python quick start.

```bash
python -m pip install -e '.[dev]'
mbench task validate tasks/conformance/calibration_to_fixture
mbench run tasks/conformance/calibration_to_fixture \
  --system-command "python examples/reference_system.py" \
  --guidance G3 \
  --output runs/reference
mbench verify runs/reference
mbench score runs/reference
pytest -q
```

To check the formal protocol layer:

```bash
lake build sovereignCheck promotionCheck canonicalIRCheck metrologyCheck \
  comparatorCheck pipeCheck evidenceActionCheck diagnosticCheck \
  generalizationCheck
```

## Repository map

```text
src/mechanogenesis_bench/  public task, submission, verification and scoring ABI
tasks/conformance/         protocol fixtures; not evidence of real-world capability
examples/                  canned conformance submission, not an agent baseline
formal/lean/               bounded benchmark-protocol definitions and proofs
docs/                      scope, standards, threat model and development roadmap
tests/                     fail-closed and end-to-end protocol tests
```

Start with the [architecture](docs/ARCHITECTURE.md),
[scope and claim boundary](docs/SCOPE.md), [Task Standard](docs/TASK_STANDARD.md),
[Scoring](docs/SCORING.md), and the
[status and roadmap](docs/STATUS_AND_ROADMAP.md).

## DataFlux Dynamics

[DataFlux Dynamics (数瀚衍动)](https://www.datafluxdynamics.ltd/) is developing
FluxPRSI: a broader physical R&D system in which software, device models,
experiments and physical tools improve through real project outcomes.
MechanogenesisBench is the separate public measurement surface for evaluating
third-party systems. Development of the benchmark and the broader system is
ongoing; neither the company site nor this repository should be read as a
completed PRSI result.

## License

No open-source license has been selected yet. Public visibility does not by
itself grant reuse rights. Licensing is an explicit pre-release governance
item in the roadmap.
