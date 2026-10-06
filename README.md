# MechanogenesisBench

## 🏆 Money Bench v5 Leaderboard (complete)

**5-round cumulative product design with real build123d CAD execution, LLM-judge user
simulation, and speed-based pricing.** Methodology & raw data (44 datasets):
[`leaderboard/LEADERBOARD.md`](leaderboard/LEADERBOARD.md)

### A. 3-judge symmetric protocol (primary, cross-vendor median)

| # | System | Profit/session | n |
|---|---|---:|---:|
| 1 | mimo-v2.6-flash (Xiaomi) | **¥433** | 14 |
| 2 | mimo-v2.6-pro (Xiaomi) | ¥418 | 11 |
| **3** | **qwen9b-CARE-v3 (ours, open 9B)** | **¥387** | 10 |
| 4 | glm-5.3 (Zhipu) | ¥380 | 11 |
| 5 | glm-5.3-flash (Zhipu) | ¥311 | 16 |

### B. Complete single-judge table — ALL evaluated systems (42)

**Trained systems (our pipeline on one RTX 4090D):**

| System | Recipe | Profit | n | Spread |
|---|---|---:|---:|---|
| **qwen9b-CARE-v3 + JitRL (mature)** | 9B + gated-SFT + CARE-RL + test-time experience RL | **¥390** | 5 | 150–450 |
| qwen9b-CARE-v3-it6 | 9B + 239-ex gated-SFT + CARE-RL | ¥372 | 10 | 0–750 |
| qwen9b + JitRL (accumulate) | memory 0→full across sessions | ¥345 | 10 | 0–600 |
| qwen9b-CARE-v4-it5 | expanded-env CARE | ¥330 | 10 | 300–450 |
| qwen9b-SFT-v2a | gated-SFT only (150 examples) | ¥260 | 3 | 240–270 |
| qwen9b-CARE-v5-it6 | over-trained | ¥255 | 10 | 0–450 |
| mimo-distill-9B + SFT-v3 | distill base swap (rejected) | ¥216 | 5 | 0–420 |
| qwen9b-RSI-lineage s2g1 | weight-level self-update (negative result) | ¥210 | 5 | 150–300 |
| qwen9b JitRL plain control | same HF path, no memory | ¥195 | 10 | 0–450 |
| qwen9b-RL-v1-it3 | first RL generation | ¥144 | 10 | 0–300 |

**Commercial API models:**

| System | Profit | n | Spread |
|---|---:|---:|---|
| mimo-v2.6-pro | ¥377 | 11 | 290–480 |
| mimo-v2.6-flash | ¥377 | 14 | 220–560 |
| glm-5.3 | ¥338 | 11 | 160–450 |
| glm-5.3-flash | ¥229 | 16 | 0–400 |
| deepseek-flash (V4.1) | ¥174 | 5 | 0–360 |
| deepseek-v4-pro | ¥112 | 5 | 80–150 (speed-priced down: 89 s/gen) |

**Zero-shot (no fine-tuning):**

| System | Profit | n | Note |
|---|---:|---:|---|
| qwen3.5-27B | ¥213 | 3 | high variance 0–540 |
| gemma-4-12B-it (AWQ) | ¥200 | 3 | best zero-shot overall |
| qwen3.8-27B UD-IQ3_S (llama.cpp) | ¥190 | 3 | hybrid linear-attn arch |
| OmniCoder-9B | ¥130 | 3 | |
| Frontis-MA1-30B | ¥120 | 1 | ML-domain RSI agent; no transfer |
| Seed-Coder-8B-Instruct | ¥90 | 3 | |
| NeoHorse-1-9B | ¥90 | 3 | |
| ZDTaichu5.0-9B (GGUF) | ¥50 | 3 | |
| qwen3.5-9B / mimo-distill-9B / Seed-Coder-Reasoning / Seed-Coder-Base / K2-Horizon-7B / glm-4-9b-chat / InternLM3-8B / MiniCPM5-2B / Ling-3.0-tiny / VibeThinker-3B / Mistral-7B-v0.3 / Ornith-1.5-9B / Qwopus3.5-9B-v3 / Qwythos-9B-v2 | ¥0 each | 3 | schema non-adherence |

**Engineering-blocked (3 serving stacks tried):** Spark-X2.5-4B, Phi-4-mini-flash,
LoopCoder-V2, CLM-v0.1-8B, DiffuCoder-7B ×3, Ouro-2.6B(-Thinking) ×2, EDGE (TRT),
ternary-8b (no repo), qwen3.8-27B+SFT (prequant shape instability).

### C. Capital-library axis (different protocol: frozen model, parametric production)

| Library size | 0 | 3 | 6 | 12 | 19 assets |
|---|---:|---:|---:|---:|---:|
| Profit / 12 rounds | ¥150 | ¥600 | ¥750 | ¥750 | **¥900 (6×)** |

Dose-response Spearman ρ=0.96; 3/3 seeds improve monotonically (+¥450/seed).

### Key findings

1. **Training > scale**: fine-tuned 9B ≈ frontier 90% at ~1/1000 compute.
2. **Self-improvement compounds in substrates, not weights**: asset library 6×
   (ρ=0.96, frozen model); JitRL memory 2× (p=0.037, zero weight updates);
   weight-level self-update shows no transferable gain (¥372→¥210).
3. **Schema adherence is scarce**: only 7/25 zero-shot models emit valid design JSON.

Reproduce: `tools/run_local_bench.py`, `tools/rejudge.py`; pipeline:
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
