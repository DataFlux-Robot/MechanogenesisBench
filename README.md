# MechanogenesisBench

## 🏆 Money Bench v5 Leaderboard — ALL systems, one table

**5-round cumulative product design · real build123d CAD execution · LLM-judge sales ·
speed pricing.** One unified ranking (37 systems; profit per 5-round
session, single-judge protocol, sorted by score). Our models use release naming **FluxEidosV{version}-9B** (V0.5 SFT → V0.6 RL → **V1.0 CARE champion** → V1.5 + JitRL test-time RSI; legacy codename in parentheses). Methodology & raw data:
[`leaderboard/LEADERBOARD.md`](leaderboard/LEADERBOARD.md)

| # | System | Type | Profit | n | Note |
|---|---|---|---:|---:|---|
| 1 | FluxEidosV1.5-9B (CARE-v3 + JitRL) | ours (9B + SFT + CARE-RL + test-time RLI) | ¥390 | 5 | 150–450; 2.0× control, p=0.037; 3-judge ¥387–420 |
| 2 | mimo-v2.6-pro | commercial API | ¥377 | 11 | 290–480; 3-judge ¥418 |
| 3 | mimo-v2.6-flash | commercial API | ¥377 | 14 | 220–560; 3-judge ¥433 |
| 4 | FluxEidosV1.0-9B (CARE-v3) | ours (9B + gated-SFT + CARE-RL) | ¥372 | 10 | 0–750; 3-judge ¥387 |
| 5 | FluxEidosV1.5a-9B (JitRL accumulating) | ours (memory 0→full) | ¥345 | 10 | 0–600 |
| 6 | glm-5.3 | commercial API | ¥338 | 11 | 160–450; 3-judge ¥380 |
| 7 | FluxEidosV1.1-9B (CARE-v4) | ours (expanded-env CARE) | ¥330 | 10 | 300–450 |
| 8 | FluxEidosV0.5-9B (SFT-v2a) | ours (gated-SFT only) | ¥260 | 3 | 240–270 |
| 9 | FluxEidosV1.2-9B (CARE-v5) | ours (over-trained) | ¥255 | 10 | 0–450 |
| 10 | FluxEidosV1.0-D-9B (distill-base swap, rejected) | ours (base swap, rejected) | ¥216 | 5 | 0–420 |
| 11 | qwen3.5-27B | zero-shot | ¥213 | 3 | 0–540 |
| 12 | FluxEidosV1.0-RSI-9B (weight-self-update lineage) | ours (weight-level self-update) | ¥210 | 5 | 150–300; gains don't transfer |
| 13 | gemma-4-12B-it (AWQ) | zero-shot | ¥200 | 3 | 0–300; best zero-shot |
| 14 | FluxEidosV1.0-ctl-9B (no-memory control) | ours (same path, no memory) | ¥195 | 10 | 0–450 |
| 15 | qwen3.8-27B UD-IQ3_S | zero-shot (llama.cpp) | ¥190 | 3 | 0–300 |
| 16 | deepseek-flash (V4.1) | commercial API | ¥174 | 5 | 0–360 |
| 17 | FluxEidosV0.6-9B (RL-v1) | ours (first RL gen) | ¥144 | 10 | 0–300 |
| 18 | OmniCoder-9B | zero-shot | ¥130 | 3 | 0–270 |
| 19 | Frontis-MA1-30B | zero-shot (ML-RSI agent) | ¥120 | 1 | no cross-domain transfer |
| 20 | deepseek-v4-pro | commercial API | ¥112 | 5 | 89 s/gen, speed-priced down |
| 21 | Seed-Coder-8B-Instruct | zero-shot | ¥90 | 3 | 0–150 |
| 22 | NeoHorse-1-9B | zero-shot | ¥90 | 3 | 0–270 |
| 23 | ZDTaichu5.0-9B (GGUF) | zero-shot | ¥50 | 3 | 0–150 |
| 24 | qwen3.5-9B | zero-shot | ¥0 | 3 | schema non-adherence |
| 25 | mimo-distill-9B | zero-shot | ¥0 | 3 | schema non-adherence |
| 26 | Seed-Coder-8B-Reasoning | zero-shot | ¥0 | 3 | schema non-adherence |
| 27 | Seed-Coder-8B-Base | zero-shot | ¥0 | 3 | schema non-adherence |
| 28 | K2-Horizon-7B | zero-shot | ¥0 | 3 | schema non-adherence |
| 29 | glm-4-9b-chat | zero-shot | ¥0 | 3 | schema non-adherence |
| 30 | InternLM3-8B-Instruct | zero-shot | ¥0 | 3 | schema non-adherence |
| 31 | MiniCPM5-2B | zero-shot | ¥0 | 3 | schema non-adherence |
| 32 | Ling-3.0-tiny | zero-shot | ¥0 | 3 | schema non-adherence |
| 33 | VibeThinker-3B | zero-shot | ¥0 | 3 | schema non-adherence |
| 34 | Mistral-7B-Instruct-v0.3 | zero-shot | ¥0 | 3 | schema non-adherence |
| 35 | Ornith-1.5-9B | zero-shot | ¥0 | 3 | schema non-adherence |
| 36 | Qwopus3.5-9B-v3 | zero-shot | ¥0 | 3 | schema non-adherence |
| 37 | Qwythos-9B-v2 | zero-shot | ¥0 | 3 | schema non-adherence |

**Engineering-blocked** (vLLM/GGUF/HF-transformers all incompatible): Spark-X2.5-4B,
Phi-4-mini-flash-reasoning, LoopCoder-V2, CLM-v0.1-8B, DiffuCoder-7B ×3,
Ouro-2.6B(-Thinking) ×2, EDGE (TRT engine), ternary-8b, qwen3.8-27B+SFT.

**Capital-library axis** (separate protocol, frozen model): 0→19 curated assets =
¥150→¥900 per 12 production rounds (6×, dose-response ρ=0.96, 3/3 seeds monotone).

**Key findings** — (1) Training > scale: open 9B ≈ 90% of frontier at ~1/1000 compute;
(2) self-improvement compounds in accumulated substrates (assets 6×, JitRL memory 2×
at p=0.037), not in 9B weight updates (¥372→¥210); (3) schema adherence is scarce:
only 7/25 zero-shot models emit valid design JSON.

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
