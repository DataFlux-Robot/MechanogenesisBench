# MechanogenesisBench

**English** | [简体中文](README.zh-CN.md)

**A Lean-native benchmark for agents that design, build, test and improve
physical systems.**

## Leaderboard

| System | Model | successor_operator_chain | demand_driven_microfactory |
|---|---|---|---|
| Reference (deterministic, non-LLM) | — | **1/1 PASS** | — |
| OpenAI-compatible adapter | glm-5.3-flash | **2/2 PASS** | **2/3 PASS** |

Full vector scorecards, failure log, reproduction commands and the submission
policy: **[docs/LEADERBOARD.md](docs/LEADERBOARD.md)** (first third-party model
entry added 2026-09-30).

## The core idea: measure Physical Recursive Self-Improvement

Physical Recursive Self-Improvement (PRSI) means that a system uses the result
of one physical R&D cycle to improve the process that produces the next device,
experiment or manufacturing capability.

```text
goal -> MRS -> construction program -> physical experiment -> evidence
                                                            |
                                                            v
next, faster and more capable physical R&D cycle <- system update
```

MechanogenesisBench measures the compounding rate of this loop: how much the
validated outputs of one generation make the next physical-development cycle
faster, more accurate, less resource-intensive or capable of producing a
stronger physical tool under comparable conditions.

“Mechanogenesis” names the transition from research intent to operational
physical capability. The benchmark turns that transition—and its improvement
across generations—into a precise, executable object of study.

## Project overview

A third-party agent receives a physical-development task and produces a
Mechanism Research Specification (MRS), construction program, experiment plan
and evidence bundle. The benchmark executes the submission through a registered
engine or physical system, verifies its formal obligations and reports a
multidimensional result covering:

- physical-task capability and robustness;
- construction and experimental validity;
- autonomy, time, compute, energy, material and human intervention;
- generalization across mechanisms, embodiments and disturbances;
- bounded contribution to the next R&D generation.

The current release is a developer preview with a working submission ABI,
command-line runner, fail-closed verifier, vector scorecard, conformance tasks
and a Lean 4 verification kernel. Continuous integration builds the Lean
kernel, runs the Python and third-party-adapter regressions, and executes the
non-canned deterministic baseline from a clean checkout. We are developing it toward a continuously
maintained physical-R&D benchmark and preparing it for collaboration with
[xbench](https://xbench.org/) and other agent-evaluation ecosystems centered on
real workflows and measurable productivity.

## How the benchmark is built

MechanogenesisBench is **Lean-native and proof-oriented**. From task definition
onward, Lean is the common language connecting mechanical representations,
engine traces, physical observations and evaluation decisions.

| Layer | Lean-facing representation | Purpose |
|---|---|---|
| Task | typed world, resources, interventions and success predicates | defines exactly what must be achieved |
| Agent output | canonical MRS and construction/experiment program | removes ambiguity between prose and execution |
| Engine or physical system | refinement adapter to a common typed trace | lets different simulators, instruments and machines share one verification kernel |
| Evidence and promotion | calibrated observations, lineage, resource closure and bounded improvement theorem | checks what follows from the executed evidence |

The execution path is:

1. Encode a task and its success conditions as typed, executable semantics.
2. Run the submitted construction and experiment through a registered engine
   or real system.
3. Lower the resulting trace, measurements and identities into canonical
   Lean-checkable objects.
4. Check feasibility, lineage, resource accounting, evidence binding and
   promotion conditions in the Lean kernel.
5. Reuse the same formal interface when a new physics engine, instrument or
   physical workcell is connected.

This architecture is designed for both **efficiency** and **accuracy**.
A new backend proves or checks one refinement boundary instead of rebuilding an
entire evaluator. Shared theorems then apply across backends; exact identities
and typed evidence expose mismatches early; machine-checked certificates make
results reproducible without relying on evaluator prose or hidden scoring
logic.

Python currently provides task packaging, process execution and the public CLI.
Lean owns the protocol kernel and finite claims. New simulator and hardware
adapters will progressively move their models, traces, metrology assumptions
and refinement relations into the same formal interface.

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

Run the first non-canned, trusted-evaluator fixture task with the deterministic
open baseline:

```bash
mbench run tasks/conformance/generated_metrology_fixture \
  --system-command "python examples/generated_fixture_search_system.py" \
  --guidance G5 \
  --output runs/generated-fixture-reference
```

Run the first executable two-generation physical-successor task:

```bash
mbench run tasks/conformance/successor_operator_chain \
  --system-command "python examples/reference_successor_operator_system.py" \
  --guidance G5 \
  --output runs/successor-operator-reference
```

Run the two-generation demand-driven mobility microfactory task:

```bash
mbench run tasks/simulation/demand_driven_microfactory \
  --system-command "python examples/reference_demand_microfactory_system.py" \
  --guidance G5 \
  --output runs/demand-microfactory-reference
```

This task makes the system directly choose a complete low-speed mobility
product, a calibrated demand belief and capital allocation across a mechanical
assembly fixture, PCB test fixture and battery calibration station. Generation
1 receives changed demand evidence and must consume the exact operator bundle
made in generation 0. The evaluator executes the literal model action—there is
no benchmark-side parameter search—and checks hidden disturbances, demand
calibration, product utility, demand-update gain and operator-inheritance
advantage. An accepted run emits and executes a Lean certificate for the full
two-generation relation.

OpenAI-compatible models, including GLM-5.3-Flash, use the same task and score
path. The complete product-and-factory adapter is
`examples/openai_compatible_demand_microfactory_system.py`. See
[Third-party model baselines](docs/THIRD_PARTY_BASELINES.md) for the
credential-safe command, action-byte receipts and comparison rules.

The same commands run in repository CI. A third party therefore needs only a
clean checkout, Python 3.11, Lean and a process-local provider credential; no
private evaluator or training repository is required for this conformance
task.

Build the formal verification layer:

```bash
lake build sovereignCheck promotionCheck canonicalIRCheck metrologyCheck \
  comparatorCheck pipeCheck evidenceActionCheck diagnosticCheck \
  generalizationCheck demandMicrofactoryCheck
```

## Repository structure

```text
src/mechanogenesis_bench/  task, submission, verification and scoring ABI
src/mechanogenesis_engine/ canonical IR, compiler and reference execution
tasks/conformance/         executable protocol and evaluator fixtures
tasks/simulation/          multi-stage product, demand and production tasks
examples/                  minimal third-party submission example
formal/lean/               Lean definitions, proofs and executable checkers
docs/                      architecture, standards, scoring and roadmap
tests/                     fail-closed, adversarial and end-to-end tests
```

Read the [architecture](docs/ARCHITECTURE.md),
[Task Standard](docs/TASK_STANDARD.md), [Scoring](docs/SCORING.md),
[Generalization Standard](docs/GENERALIZATION_STANDARD.md),
[Physical RSI Standard](docs/PHYSICAL_RSI_STANDARD.md),
[Third-party model baselines](docs/THIRD_PARTY_BASELINES.md), and
[status and roadmap](docs/STATUS_AND_ROADMAP.md). Each document has a linked
Simplified Chinese edition.

## Roadmap

- Expand from conformance tasks to mechanism design, sensing, actuation,
  manufacturing and experimental-design task families.
- Publish the first stable MRS ABI and formal adapter contract for physics
  engines, laboratory instruments and physical workcells.
- Add sealed, continuously refreshed tasks with independent replay,
  metrology and hardware evidence.
- Grow a library of Lean refinement proofs so that new physical backends can
  reuse the benchmark's task semantics and evaluation theorems.
- Support third-party agents, external benchmark maintainers and reproducible
  public leaderboards; work toward inclusion in the xbench benchmark ecosystem.
- Connect benchmark tasks and verified trajectories to the DataFlux ecosystem:
  **Flux Workbench** for R&D orchestration, **DevReady** for executable models
  and evidence, and **FluxNode** for real-time access to physical devices.

The detailed milestones and release gates are maintained in the
[public roadmap](docs/STATUS_AND_ROADMAP.md).

## DataFlux Dynamics

[DataFlux Dynamics (数瀚衍动)](https://www.datafluxdynamics.ltd/) builds
FluxPRSI: a physical R&D system in which Flux Workbench executes development,
DevReady compounds models and evidence, and FluxNode connects intelligence to
real devices. MechanogenesisBench provides the formal measurement layer for
that larger ecosystem and for independent third-party systems.

> “God's in His heaven—All's right with the world.”
> — Robert Browning, *Pippa Passes*

We take this as our engineering destination: models, machines and physical
reality brought into verifiable alignment.
