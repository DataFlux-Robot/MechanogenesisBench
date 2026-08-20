# MechanogenesisBench

MechanogenesisBench is the benchmark and evidence plane of the full
Mechanogenesis Engine product. It evaluates complete systems that generate a
research strategy, physical theory, construction program, experiment and
successor-manufacturing improvement—not models that merely answer mechanics
questions.

The governing episode is:

```text
Gθ -> MRS -> generated physical/construction program -> experiment
   -> independent evaluation -> physical-process promotion
   -> generator checkpoint fork -> next MRS generation
```

The benchmark never owns a separate toy definition of physics. Production
Mechanogenesis Engine implementations and benchmark submissions share the
Mechanogenesis task, world, evidence and receipt contracts. Named simulators
may be independent refinement/falsification backends; they do not define the
canonical world state.

## Current executable slice

Version `0.1.0` provides:

- a benchmark task-package standard;
- Fixed Engine, Open System and Recursive Learner tracks;
- G1–G5 guidance-withdrawal levels;
- a complete MRS bundle and two-generation submission ABI;
- exact integer material-ledger and process-lineage validation;
- independent task evaluator execution;
- fail-closed promotion, evidence-tier and resource-budget gates;
- a non-aggregated scorecard for capability, robustness, autonomy, time,
  budget and Recursive Research Credit;
- a clearly labelled `CONFORMANCE` calibration-tool-to-production-fixture
  reference episode;
- Lean 4 benchmark-protocol invariants.

It does **not** yet contain calibrated multi-physics or hardware evidence. A
passing sample proves protocol conformance, not physical RSI.

## Quick start

```bash
python -m pip install -e '.[dev]'
mbench task validate tasks/conformance/calibration_to_fixture
mbench run tasks/conformance/calibration_to_fixture \
  --system-command "python examples/reference_system.py" \
  --guidance G3 \
  --output runs/reference
mbench score runs/reference
pytest -q
```

## Repository map

```text
src/mechanogenesis_bench/   task/submission/evidence/runner/scoring kernel
tasks/                      canonical benchmark episodes
examples/                   reference system adapters
formal/lean/                machine-checked protocol invariants
docs/                       architecture, standard, scoring and roadmap
tests/                      fail-closed and end-to-end verification
```

Start with [Architecture](docs/ARCHITECTURE.md), then read the
[Task Standard](docs/TASK_STANDARD.md) and [Handoff](HANDOFF.md).

## Status and license

Private pre-release research and product repository. No public license is
granted at this stage.
