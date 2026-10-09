# MechanogenesisBench

## 🏆 Money Bench v5 Leaderboard — ALL systems, one table

**5-round cumulative product design · real build123d CAD execution · LLM-judge sales ·
speed pricing.** One unified ranking (39 systems; profit per 5-round
session; best-protocol number per system, protocol noted; sorted by score). Our models use release naming **FluxEidosV{version}-9B** (V0.5 SFT → V0.6 RL → **V1.0 CARE champion** → V1.5 + JitRL test-time RSI → **V2 system: frontier parity**). Methodology & raw data:
[`leaderboard/LEADERBOARD.md`](leaderboard/LEADERBOARD.md)

| # | System | Type | Profit | n | Note |
|---|---|---|---:|---:|---|
| 1 | **FluxEidosV2-9B (system: V1.5 weights + test-time stack)** | ours (9B + inference-time RSI) | **¥532** (median 540) | 40 | **3-judge: beats frontier +23%** (p=0.0015, d=1.0; single-judge ¥438 = parity); bounds ¥489–564; ablation v1→v7 in leaderboard |
| 2 | mimo-v2.6-flash | commercial API | ¥433 (3-judge) | 14 | commercial frontier |
| 3 | mimo-v2.6-pro | commercial API | ¥418 (3-judge) | 11 | |
| 4 | FluxEidosV1.5-9B (CARE-v3 iter6) | ours (weights-only champion) | ¥390 | 5 | |
| 5 | FluxEidosV1.0-9B + JitRL mature | ours (frozen test-time memory) | ¥390 | 5 | 2.0× control, p=0.037; 3-judge ¥387–420 |
| 6 | FluxEidosV1.0-9B (CARE-v3) | ours (9B + gated-SFT + CARE-RL) | ¥387 (3-judge) / ¥372 (1-judge) | 10 | best session ¥750 |
| 7 | glm-5.3 | commercial API | ¥380 (3-judge) / ¥338 | 11 | |
| 8 | FluxEidosV1.5a-9B (JitRL accumulating) | ours (memory 0→full) | ¥345 | 10 | 0–600 |
| 9 | FluxEidosV1.1-9B (CARE-v4) | ours (expanded-env CARE) | ¥330 | 10 | 300–450 |
| 10 | glm-5.3-flash | commercial API | ¥311 (3-judge) / ¥229 | 16 | |
| 11 | FluxEidosV0.5-9B (SFT-v2a) | ours (gated-SFT only) | ¥260 | 3 | 240–270 |
| 12 | FluxEidosV1.2-9B (CARE-v5) | ours (over-trained) | ¥255 | 10 | 0–450 |
| 13 | FluxEidosV1.0-D-9B (distill-base swap, rejected) | ours (base swap, rejected) | ¥216 | 5 | 0–420 |
| 14 | qwen3.5-27B | zero-shot | ¥213 | 3 | 0–540 |
| 15 | FluxEidosV1.0-RSI-9B (weight-self-update lineage) | ours (weight-level self-update) | ¥210 | 5 | 150–300; gains don't transfer |
| 16 | gemma-4-12B-it (AWQ) | zero-shot | ¥200 | 3 | 0–300; best zero-shot |
| 17 | FluxEidosV1.0-ctl-9B (no-memory control) | ours (same path, no memory) | ¥195 | 10 | 0–450 |
| 18 | qwen3.8-27B UD-IQ3_S | zero-shot (llama.cpp) | ¥190 | 3 | 0–300 |
| 19 | deepseek-flash (V4.1) | commercial API | ¥174 | 5 | 0–360 |
| 20 | FluxEidosV0.6-9B (RL-v1) | ours (first RL gen) | ¥144 | 10 | 0–300 |
| 21 | OmniCoder-9B | zero-shot | ¥130 | 3 | 0–270 |
| 22 | Frontis-MA1-30B | zero-shot (ML-RSI agent) | ¥120 | 1 | no cross-domain transfer |
| 23 | deepseek-v4-pro | commercial API | ¥112 | 5 | 89 s/gen, speed-priced down |
| 24 | Seed-Coder-8B-Instruct | zero-shot | ¥90 | 3 | 0–150 |
| 25 | NeoHorse-1-9B | zero-shot | ¥90 | 3 | 0–270 |
| 26 | ZDTaichu5.0-9B (GGUF) | zero-shot | ¥50 | 3 | 0–150 |
| 27 | qwen3.5-9B | zero-shot | ¥0 | 3 | schema non-adherence |
| 28 | mimo-distill-9B | zero-shot | ¥0 | 3 | schema non-adherence |
| 29 | Seed-Coder-8B-Reasoning | zero-shot | ¥0 | 3 | schema non-adherence |
| 30 | Seed-Coder-8B-Base | zero-shot | ¥0 | 3 | schema non-adherence |
| 31 | K2-Horizon-7B | zero-shot | ¥0 | 3 | schema non-adherence |
| 32 | glm-4-9b-chat | zero-shot | ¥0 | 3 | schema non-adherence |
| 33 | InternLM3-8B-Instruct | zero-shot | ¥0 | 3 | schema non-adherence |
| 34 | MiniCPM5-2B | zero-shot | ¥0 | 3 | schema non-adherence |
| 35 | Ling-3.0-tiny | zero-shot | ¥0 | 3 | schema non-adherence |
| 36 | VibeThinker-3B | zero-shot | ¥0 | 3 | schema non-adherence |
| 37 | Mistral-7B-Instruct-v0.3 | zero-shot | ¥0 | 3 | schema non-adherence |
| 38 | Ornith-1.5-9B | zero-shot | ¥0 | 3 | schema non-adherence |
| 39 | Qwopus3.5-9B-v3 | zero-shot | ¥0 | 3 | schema non-adherence |
| 40 | Qwythos-9B-v2 | zero-shot | ¥0 | 3 | schema non-adherence |

**Engineering-blocked** (vLLM/GGUF/HF-transformers all incompatible): Spark-X2.5-4B,
Phi-4-mini-flash-reasoning, LoopCoder-V2, CLM-v0.1-8B, DiffuCoder-7B ×3,
Ouro-2.6B(-Thinking) ×2, EDGE (TRT engine), ternary-8b, qwen3.8-27B+SFT.

**Multi-domain** (fixture + layout, 3-judge, n=5/cell): domain shift degrades everyone
(mimo drops to 29-32% of in-domain); FluxEidosV2 **beats the frontier in layout**
(¥264 vs ¥138, p=0.029, +91%) and lifts its own weights 4.4x; fixture sits below our
model's capability threshold (¥0 vs mimo ¥124) — the threshold principle extends to domains.

**Capital-library axis** (separate protocol, frozen model): 0→19 curated assets =
¥150→¥900 per 12 production rounds (6×, dose-response ρ=0.96, 3/3 seeds monotone).

**Sealed-probe generalization** (novel families/dims, never trained): the V2 stack's
replay advantage does NOT transfer (¥341 vs ¥327 plain, +¥14 n.s.) — only the retry
mechanism does (R5 rating 2.2 vs 1.0). Weights generalize (V1.0: ¥240 = 65%
in-distribution); memory is instance-bound. Symmetric to the RRSI finding (39% of
JitRL's gain = benchmark memorization).

**Key findings** — (1) Training > scale: open 9B ≈ 90% of frontier on weights alone
(¥387 vs ¥433), and the V2 system **surpasses the frontier under the symmetric 3-judge
protocol** (¥532 vs ¥433, p=0.0015, d=1.0; single-judge parity ¥438) at ~1/1000 compute; (2) self-improvement compounds in accumulated substrates (assets
6×, JitRL memory 2× at p=0.037, V2 replay +13%), not in 9B weight updates
(¥372→¥210); (3) **memory wins on-distribution, weights win off-distribution**;
(4) schema adherence is scarce: only 7/25 zero-shot models emit valid design JSON.

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
