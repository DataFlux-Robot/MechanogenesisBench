# Money Bench v5 — Leaderboard

**Benchmark**: 5-round cumulative product design (phone-dock workstation family) with
**real build123d B-rep CAD execution** (build → STEP export → re-import → precise
intersection/envelope measurement), LLM-judge user simulation, and speed-based pricing
(`<10s = 1.5× … >120s = 0.5×`). Profit = Σ sold rounds × ¥100 × speed multiplier.
Capital reuse is free and faster: each round's validated design becomes an importable
STEP asset (`capital(asset_id)`) for later rounds.

**Protocols**
- *single-judge*: mimo-v2.6-pro median rating decides the sale (all rows same judge).
- *3-judge symmetric*: median of mimo-v2.6-pro + glm-5.3 + glm-5.3-flash on identical designs.

## Unified main table — every evaluated system, one ranking

Ranking uses each system's best-protocol number (column "protocol"); cross-protocol
comparisons are approximate — the 3-judge protocol is the symmetric gold standard,
system entries (V2, JitRL) are single-judge and flagged.

| # | System | Profit / session | n | Protocol | Notes |
|---|---|---:|---:|---|---|
| 1 | **FluxEidosV2-9B system (ours)** | **¥438** (median 450) | 40 | single | V1.5 weights + test-time stack; **frontier parity** (p=0.39 vs mimo-flash), +13% over weights-only champion |
| 2 | mimo-v2.6-flash (Xiaomi) | **¥433** | 14 | 3-judge | commercial frontier |
| 3 | mimo-v2.6-pro (Xiaomi) | ¥418 | 11 | 3-judge | |
| 4 | **FluxEidosV1.5-9B (CARE-v3 iter6) (ours)** | **¥390** | 5 | single | weights-only champion |
| 4 | **FluxEidosV1.0-9B + JitRL mature (ours)** | **¥390** | 5 | single | frozen test-time memory; p=0.037 vs plain control |
| 6 | **FluxEidosV1.0-9B (CARE-v3) (ours)** | **¥387** | 10 | 3-judge | 9B open model, ~250 SFT examples + CARE RL, one RTX 4090D |
| 7 | glm-5.3 (Zhipu) | ¥380 | 11 | 3-judge | |
| 8 | FluxEidosV1.0-9B (CARE-v3) (ours) | ¥372 | 10 | single | best single session ¥750 (4/5 sold, 3/4 reuse) |
| 9 | mimo-v2.6-pro (Xiaomi) | ¥377 | 11 | single | |
| 9 | mimo-v2.6-flash (Xiaomi) | ¥377 | 14 | single | |
| 11 | glm-5.3 (Zhipu) | ¥338 | 11 | single | |
| 12 | **FluxEidosV1.1-9B (CARE-v4) (ours)** | **¥330** | 10 | single | ultra-stable variant (sd ¥60) |
| 13 | glm-5.3-flash (Zhipu) | ¥311 | 16 | 3-judge | |
| 14 | **FluxEidosV0.5-9B (SFT-v2a) (ours)** | **¥260** | 3 | single | gated-SFT only (150 examples) |
| 15 | **FluxEidosV1.2-9B (CARE-v5) (ours)** | **¥255** | 10 | single | over-trained |
| 16 | qwen3.5-27B (zero-shot) | ¥213 | 3 | single | scale ≠ capability |
| 17 | **FluxEidosV1.0-D-9B (ours, rejected)** | **¥216** | 5 | single | distill base WORSE than Qwen base after identical SFT (rigidity) |
| 18 | **FluxEidosV1.0-RSI-9B (ours, rejected)** | **¥210** | 5 | single | weight-level self-update: probe gains did NOT transfer |
| 19 | gemma-4-12B-it (zero-shot, AWQ) | ¥200 | 3 | single | **best zero-shot of all models**; strong instruction following |
| 20 | glm-5.3-flash (Zhipu) | ¥229 | 16 | single | |
| 21 | deepseek-flash (V4.1) | ¥174 | 5 | single | thinking time is billed |
| 22 | qwen9b-RL-v1-it3 (ours, early) | ¥144 | 10 | single | |
| 23 | OmniCoder-9B (zero-shot) | ¥130 | 3 | single | coder merge; partial schema adherence |
| 24 | Frontis-MA1-30B (zero-shot) | ¥120 | 1 | single | ML-domain RSI agent; reasoning burns the speed budget (89 s/gen) |
| 25 | NeoHorse-1-9B (zero-shot) | ¥90 | 3 | single | |
| 25 | Seed-Coder-8B-Instruct (zero-shot) | ¥90 | 3 | single | only non-zero of its batch besides gemma |
| 27 | ZDTaichu5.0-9B (zero-shot, Q4 GGUF) | ¥50 | 3 | single | served via llama.cpp (custom vision code incompatible with vLLM) |
| 28 | mimo-distill-9B (zero-shot) | ¥0 | 3 | single | mimo-v2.6 distillation does NOT transfer schema adherence |
| 28 | Seed-Coder-8B-Reasoning (zero-shot) | ¥0 | 3 | single | reasoning budget burned on format |
| 28 | Seed-Coder-8B-Base (zero-shot) | ¥0 | 3 | single | base model, expected |
| 28 | K2-Horizon-7B (zero-shot) | ¥0 | 3 | single | |
| 28 | glm-4-9b-chat (zero-shot) | ¥0 | 3 | single | older GLM generation |
| 28 | InternLM3-8B-Instruct (zero-shot) | ¥0 | 3 | single | |
| 28 | MiniCPM5-2B (zero-shot) | ¥0 | 3 | single | |
| 28 | Ling-3.0-tiny (zero-shot) | ¥0 | 3 | single | BTE looped-adjacent arch |
| 28 | VibeThinker-3B (zero-shot) | ¥0 | 3 | single | |
| 28 | Mistral-7B-Instruct-v0.3 (zero-shot) | ¥0 | 3 | single | |
| 28 | Ornith-1.5-9B (zero-shot) | ¥0 | 3 | single | |
| 28 | Qwopus3.5-9B-v3 (zero-shot) | ¥0 | 3 | single | community Qwen-merge; schema confusion |
| 28 | Qwythos-9B-v2 (zero-shot) | ¥0 | 3 | single | community Qwen-merge |
| 28 | qwen3.5-9B (zero-shot) | ¥0 | 1 | single | cannot emit valid design JSON |

**Unserviceable despite retries** (trust-remote-code, GGUF/llama.cpp, HF-transformers
paths): Spark-X2.5-4B (arch absent from vLLM), Phi-4-mini-flash-reasoning,
LoopCoder-V2 (config schema), CLM-v0.1-8B (unknown arch `clm`), DiffuCoder
Base/Instruct/cpGRPO (diffusion-LLM custom code), Ouro-2.6B(-Thinking) (looped
transformer; vLLM, llama.cpp and transformers all incompatible without forking custom
code — the host models of LoopSpec, arXiv:2609.17184), EDGE (TRT engine),
"ternary 8b" (no repo found on HuggingFace).

Headline: the best open 9B weights reach **~90% of the commercial frontier**
(¥387 vs ¥433); with the V2 test-time stack the system reaches **statistical parity**
(¥438 vs ¥433, pooled n=40, Mann-Whitney p=0.39) at ~1/1000 of commercial training
compute. Full per-run spreads in `data/` (`baselines_3judge.json`,
`qwen9b-care-v3-it6_rejudged.json`, `surpass_v6_n20.json`, `surpass_v7_n20.json`).

## FluxEidosV2-9B: the inference-time stack behind rank 1

Same champion weights (FluxEidosV1.5-9B, CARE-v3 iter6), zero weight updates, zero
external data. Mechanisms (each isolated by ablation, 5 sessions per version):

| version | stack | mean | runs |
|---|---|---:|---|
| v1 | prose hints all rounds | ¥72 | 0,120,120,0,120 |
| v3 | best-of-3 R1, overlap-first selection | ¥206 | 400,380,0,0,250 |
| v4 | parts-first selection + judge retry | ¥350 | 230,80,680,380,380 |
| v5 | + token cap (1.0× pricing) + conditional resample + syntax repair | ¥368 | 550,320,400,200,370 |
| v6 | + in-context experience replay (self-mined rating≥6 designs) | ¥474 | 450,570,420,380,550 (n=5) |
| v6 | full n=20 replication | ¥440 | median 450; one ¥0 cascade session |
| v7 | + executed-design capital registration + R4/R5 second retry | ¥436 | zero catastrophic sessions |

Pooled v6+v7 (n=40): **¥438**. Mechanism details: (1) best-of-3 R1 candidates
CAD-screened with parts-first selection — judge rating tracks structural detail, not
geometric overlap (9-part designs rate 5–6; geometrically-clean 4-part designs rate
2–3); (2) in-context replay of the system's own past rating≥6 designs per round;
(3) syntax repair layer (transform `inputs`→`input`, dead part references); (4)
conditional resampling on failed rounds; (5) judge-retry on API-zero flakes. Round
structure at n=20: R2 85% sold, R3 95% (replay's effect), R1 60% / R4 50% / R5 35%
(judge-threshold noise is the binding constraint).

## Test-time RSI (JitRL, arXiv:2601.18510 adapted)

Same model (FluxEidosV1.0-9B (CARE-v3)), same inference path, same judge/pricing; the
only difference is experience retrieval + advantage-weighted logit modulation
(`z' = z + β·A`). Memory starts EMPTY and accumulates across eval sessions — the
across-session slope IS the self-improvement measurement, zero leakage.

| arm | n | per-session profits | mean |
|---|---:|---|---:|
| plain control (no memory) | 10 | 0, 300, 150, 150, 300, 300, 450, 150, 0, 150 | ¥195 |
| JitRL accumulate (memory 0→full) | 10 | 300, 600, 450, 600, 150, 0, 300, 300, 300, 450 | ¥345 |
| **JitRL mature (memory frozen)** | **5** | 450, 450, 450, 150, 450 | **¥390** |

**Mature vs plain: p = 0.037 (Mann-Whitney z=2.08); all-JitRL (n=15) vs plain: p=0.023.**
The frozen-memory steady state is exactly 2.0× the same-model control and edges past
the weight-tuned champion (¥372) without retraining. Under the 2-judge glm-panel
recompute the mature sessions score ¥340 (conservative mean) to ¥420 (median); the
primary single-judge number is ¥390. Data: `data/jitrl_*`.

## Sealed-probe generalization (honest decomposition, seed 20261005)

Novel product families/dimensions/desks, never seen in any training or bank-mining:

| arm | profit (n=10) | mean rating by round R1→R5 |
|---|---:|---|
| plain V1.5 weights | ¥327 | 2.8, 5.9, 7.8, 4.4, 1.0 |
| V1.5 + full V2 stack | ¥341 (+¥14, p=0.40) | 2.8, 6.2, 6.6, 4.5, 2.2 |

**The replay advantage does not transfer** (+¥14, n.s.); only the retry mechanism
transfers (R5 +1.2). Combined with the RRSI finding (39% of JitRL's gain was benchmark
memorization): **memory wins on-distribution, weights win off-distribution.**
FluxEidosV1.0 weights-only on probes: ¥240 (65% of in-distribution ¥372). Cross-domain
(fixture design, different system prompt): ¥144 = commercial baseline (¥100–150).
Data: `data/probe_v6stack.json`, `data/probe_plain_weights.json`.

## Second axis — capital-library production efficiency (different protocol; not comparable to the tables above)

Frozen FluxEidosV1.0-9B (CARE-v3) model, fixed parametric production instances (4 × 3
rounds), library of execution-verified assets accumulated across generations:

| Library size | 0 | 3 | 6 | 12 | 19 |
|---|---:|---:|---:|---:|---:|
| Production profit / 12 rounds | ¥150 | ¥600 | ¥750 | ¥750 | **¥900** |
| Capital reuse | 1/12 | 10/12 | 10/12 | 9/12 | 11/12 |

Dose–response Spearman ρ = 0.96; 3 seeds all improve monotonically (+¥450/seed, 2–4×
per seed). Weight-level self-update arms show no transferable gain — see
`data/dual_loop_*.json` and `data/library_ablation.json`.

## CAD World Model (CWM-inspired, arXiv:2510.02387 adapted)

621 design→geometry pairs harvested from 32 run sources; mixed predict+generate LoRA
(860 samples, 6 epochs, CE 0.047). Held-out prediction accuracy (n=80): **86%
validity, 69% exact rating** — the model internalizes build123d execution without
running it. Generation degraded by task mixing (¥0 on bench) → separate adapters.

Prediction-only LoRA (621 pairs, 5 epochs): **92% validity, 69% exact rating** —
better than the mixed adapter. But prediction-based screening of 4 candidates is
WORSE than naive first-pick (¥150 vs ¥300, n=5): the model learned absolute outcomes,
not relative rankings. The 75% CAD-execution savings (20→5 per session) comes from
the N→1 architecture itself. Fix: learning-to-rank training on candidate pairs.

| arm | mechanism | profit (n=5) | CAD execs |
|---|---|---:|---:|
| control (first of 4) | no prediction | ¥300 | 5/session |
| screened (predict best of 4) | world model | ¥150 | 5/session |

Data: `data/world_model_pairs.json`, `data/screen4_results.json`, `data/control4_results.json`

## Key findings

1. **Training > scale**: a fine-tuned 9B ≈ 90% of the strongest commercial models
   (and reaches parity as a system); 27B zero-shot and a 30B ML-RSI agent land far below.
2. **Speed pricing discriminates reasoning style**: deepseek-v4-pro reuses most
   (3.6/4) yet earns least among mid-tier — thinking time is billed.
3. **The self-improvement that compounds lives in substrates, not weights**: frozen
   model + 19 curated assets = 6× production profit (monotonic, causal, ρ=0.96);
   cross-session experience (JitRL 2×, V2 stack +13%); weight-level RSI at
   9B/30-samples-per-generation is noise-dominated (probe gains fail to transfer,
   −¥162 on the bench).
4. **Memory is instance-bound, weights generalize**: the V2 stack's replay gains
   vanish on sealed probes (+¥14 n.s.) while weight-level gains retain 65%; RRSI
   decomposition puts JitRL's memorization share at 39%.

## Reproduce

```bash
# commercial/local models against a served endpoint (identical protocol for all rows)
MIMO_KEY=... python tools/run_local_bench.py --endpoint http://... --served-model X --designer X --n 10
# symmetric 3-judge recompute on stored sessions
python tools/rejudge.py --dir runs/local_bench/<model> --tag <model>-3judge
# FluxEidosV2 system stack (ablation versions via git history)
python tools/surpass_bench.py --sessions 20
# sealed-probe generalization (both arms)
python tools/probe_v6_bench.py --stack v6 --instances 10
python tools/probe_v6_bench.py --stack plain --instances 10
```

Training pipeline: `tools/openrsi_sft_v2.py` (gated SFT) → `tools/train_prsi_v2.py`
(QLoRA) → `tools/prsi_rl_loop.py` (CARE RL) → `tools/dual_loop_prsi.py` (PRSI × RSI
dual loop).

*Last updated: 2026-10-08. 39 systems evaluated (9 vendors + community), 52 result
datasets in `data/`. All profits are mean profit per 5-round session unless stated
otherwise. Champion system: FluxEidosV2 (¥438, frontier parity, n=40); champion
weights: FluxEidosV1.5 (¥390).*
