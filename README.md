# MechanogenesisBench

## 🏆 Money Bench v5 Leaderboard

**5-round cumulative product design with real build123d CAD execution, LLM-judge user
simulation, and speed-based pricing.** Full methodology, 38-system results and all raw
data: [`leaderboard/LEADERBOARD.md`](leaderboard/LEADERBOARD.md)

### 3-judge symmetric protocol (primary)

| # | System | Profit/session | n |
|---|---|---:|---:|
| 1 | mimo-v2.6-flash | **¥433** | 14 |
| 2 | mimo-v2.6-pro | ¥418 | 11 |
| **3** | **qwen9b-CARE-v3 (ours, open 9B)** | **¥387** | 10 |
| 4 | glm-5.3 | ¥380 | 11 |
| 5 | glm-5.3-flash | ¥311 | 16 |

The best open 9B model reaches ~90% of the commercial frontier at ~1/1000 of the
training compute — and with **JitRL test-time self-improvement** it earns ¥390
(2.0× same-model control, Mann-Whitney p=0.037, zero weight updates).

### Key findings

1. **Training > scale**: fine-tuned 9B ≈ frontier 90%; 27B zero-shot ¥190–213 and a
   30B ML-RSI agent (¥120) land far below.
2. **Self-improvement compounds in accumulated substrates, not weights**:
   execution-verified asset library = 6× production profit (dose-response ρ=0.96,
   frozen model); JitRL experience memory = 2× steady-state profit (p=0.037);
   weight-level self-update at 9B shows no transferable gain (negative result, full
   ablations included).
3. **Schema adherence is scarce**: of 25 zero-shot models only 7 major-vendor
   2025+ instruct models emit valid design JSON.

Reproduce: `tools/run_local_bench.py`, `tools/rejudge.py`; training pipeline:
`tools/openrsi_sft_v2.py` → `tools/train_prsi_v2.py` → `tools/prsi_rl_loop.py`
→ `tools/jitrl_bench.py` → `tools/dual_loop_prsi.py`.

---


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

Version `0.6.0` provides:

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
- Lean 4 benchmark-protocol invariants;
- a fixed-point canonical mechanism IR with deterministic world transitions;
- axis-aligned generative CSG, rigid assembly, inventory-backed manufacturing
  and calibration semantics;
- an autonomous search task that generates and independently evaluates a real
  fixture program, plus a labeled STEP refinement and four review views;
- Lean 4 mass-closure, no-creation, receipt-chain and disturbance-monotonicity
  invariants for the reference fragment;
- state continuation and a two-generation physical-contribution task in which
  the first generated fixture qualifies the process that constructs its
  successor;
- a Lean theorem connecting strict process improvement and non-worsening local
  error to strict successor absolute-error improvement.
- an executable Gθ/MRS research layer with a strict generated-strategy schema,
  deterministic reference proposer and optional OpenAI-compatible LLM proposer;
- strategy-controlled candidate support, ordering, execution budget and
  multi-world robustness gates, independently replayed by trusted evaluators;
- a reachability ablation in which removing feasible candidates from generated
  support makes downstream selection fail;
- Lean-checked support/budget phase boundaries, grounded world-model
  contraction and conditional compiler-certificate transfer.
- a Lean Sovereign Kernel defining the authoritative transition, assumption,
  evidence, refinement and promotion semantics for the executable fixture
  slice;
- proof-carrying interpreter receipts plus `sovereignCheck` for transition
  certificates and `promotionCheck` for evaluator decisions bound to the exact
  parent/child worlds;
- a machine-checked theorem that Lean-accepted promotion implies valid
  accounting, explicit assumptions, world-bound credit and strictly lower
  bounded child error.
- a Lean-native canonical program manifest for the current geometry,
  assembly and manufacturing fragment, including rooted shape depth, closed
  operation kinds, cross-reference validation and operation-to-receipt binding;
- a first metrology refinement module that recomputes angular, worst-case and
  absolute-frame error bounds, covers every calibration operation and binds
  each result to its exact operation and receipt;
- independent evaluator regeneration of the entire sovereign certificate, so
  an internally valid manifest cannot be substituted for a different program.

It does **not** yet contain calibrated multi-physics or hardware evidence. A
passing sample proves protocol conformance, not physical RSI.

## Quick start

```bash
python -m pip install -e '.[dev]'
lake build sovereignCheck promotionCheck canonicalIRCheck metrologyCheck
mbench task validate tasks/conformance/calibration_to_fixture
mbench run tasks/conformance/calibration_to_fixture \
  --system-command "python examples/reference_system.py" \
  --guidance G3 \
  --output runs/reference
mbench score runs/reference
pytest -q
python experiments/gtheta_phase_boundary.py

mengine search-fixture \
  tasks/conformance/generated_metrology_fixture/public/mechanism_world.json \
  tasks/conformance/generated_metrology_fixture/public/fixture_goal.json \
  --program-output /tmp/fixture.json
mbench run tasks/conformance/generated_metrology_fixture \
  --system-command "python examples/generated_fixture_search_system.py" \
  --guidance G5 --output runs/generated-fixture
mbench run tasks/conformance/recursive_fixture_process \
  --system-command "python examples/recursive_fixture_process_system.py" \
  --guidance G5 --output runs/recursive-fixture
```

## Repository map

```text
src/mechanogenesis_bench/   task/submission/evidence/runner/scoring kernel
src/mechanogenesis_engine/  canonical IR, reference interpreter and generation
tasks/                      canonical benchmark episodes
examples/                   reference system adapters
experiments/                executable Gθ/support/model ablations
models/                     generated STEP artifacts and visual review evidence
formal/lean/                machine-checked protocol invariants
docs/                       architecture, standard, scoring and roadmap
tests/                      fail-closed and end-to-end verification
```

Start with [Architecture](docs/ARCHITECTURE.md), then read the
[Canonical Mechanism IR](docs/CANONICAL_MECHANISM_IR.md),
[Reference Interpreter](docs/REFERENCE_INTERPRETER.md),
[Physical-Contribution Chain](docs/PHYSICAL_CONTRIBUTION_CHAIN.md),
[Gθ/MRS Research Runtime](docs/GTHETA_MRS_RUNTIME.md),
[Lean Sovereign Kernel](docs/LEAN_SOVEREIGN_KERNEL.md),
[Task Standard](docs/TASK_STANDARD.md) and [Handoff](HANDOFF.md).

## Status and license

Private pre-release research and product repository. No public license is
granted at this stage.
