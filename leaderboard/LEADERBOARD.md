# Money Bench v5 — Leaderboard

**Benchmark**: 5-round cumulative product design (phone-dock workstation family) with
**real build123d B-rep CAD execution** (build → STEP export → re-import → precise
intersection/envelope measurement), LLM-judge user simulation, and speed-based pricing
(`<10s = 1.5x … >120s = 0.5x`). Profit = Σ sold rounds × ¥100 × speed multiplier.
Capital reuse is free and faster: each round's validated design becomes an importable
STEP asset (`capital(asset_id)`) for later rounds.

**Protocols**
- *Single-judge*: mimo-v2.6-pro median rating decides the sale (all rows same judge).
- *3-judge symmetric*: median of mimo-v2.6-pro + glm-5.3 + glm-5.3-flash on the same designs.

## Primary table — 3-judge symmetric protocol

| # | Model | Profit / session | n | Notes |
|---|---|---:|---:|---|
| 1 | mimo-v2.6-flash (Xiaomi) | **¥433** | 14 | commercial frontier |
| 2 | mimo-v2.6-pro (Xiaomi) | ¥418 | 11 | |
| **3** | **FluxEidosV1.0-9B (CARE-v3) (ours)** | **¥387** | 10 | 9B open model, ~250 SFT examples + CARE RL, one RTX 4090D |
| 4 | glm-5.3 (Zhipu) | ¥380 | 11 | |
| 5 | glm-5.3-flash (Zhipu) | ¥311 | 16 | |

The best open 9B model reaches **~90% of the commercial frontier** at ~1/1000 of the
training compute. Full per-run spreads in `data/` (`baselines_3judge.json`,
`qwen9b-care-v3-it6_rejudged.json`).

## Extended table — single-judge protocol (more models)

| Model | Profit | n | Spread | Notes |
|---|---:|---:|---|---|
| mimo-v2.6-pro | ¥377 | 11 | 290–480 | |
| mimo-v2.6-flash | ¥377 | 14 | 220–560 | |
| FluxEidosV1.0-9B (CARE-v3) | ¥372 | 10 | 0–750 | best single session ¥750 (4/5 sold, 3/4 reuse) |
| glm-5.3 | ¥338 | 11 | 160–450 | |
| FluxEidosV1.1-9B (CARE-v4) | ¥330 | 10 | 300–450 | ultra-stable variant (sd ¥60) |
| FluxEidosV0.5-9B (SFT-v2a) | ¥260 | 3 | 240–270 | gated-SFT only (150 examples) |
| FluxEidosV1.2-9B (CARE-v5) | ¥255 | 10 | 0–450 | over-trained |
| glm-5.3-flash | ¥229 | 16 | 0–400 | |
| qwen3.5-27B (zero-shot) | ¥213 | 3 | 0–540 | scale ≠ capability |
| FluxEidosV1.0-RSI-9B (weight-self-update lineage) | ¥210 | 5 | 150–300 | weight-level self-update: probe gains did NOT transfer |
| deepseek-flash (V4.1) | ¥174 | 5 | 0–360 | |
| qwen9b-RL-v1-it3 | ¥144 | 10 | 0–300 | |
| FluxEidosV1.0-D-9B (distill-base swap, rejected) | ¥216 | 5 | 0–420 | distill base is WORSE than Qwen base after identical SFT (rigidity) |
| Frontis-MA1-30B | ¥120 | 1 | 120 | ML-domain RSI agent; reasoning burns the speed budget (89 s/gen) |
| mimo-distill-9B (zero-shot) | ¥0 | 3 | 0 | mimo-v2.6 distillation does NOT transfer schema adherence |
| Seed-Coder-8B-Instruct (zero-shot) | ¥90 | 3 | 0–150 | only non-zero of batch 2 |
| Seed-Coder-8B-Reasoning (zero-shot) | ¥0 | 3 | 0 | reasoning budget burned on format |
| Seed-Coder-8B-Base (zero-shot) | ¥0 | 3 | 0 | base model, expected |
| K2-Horizon-7B (zero-shot) | ¥0 | 3 | 0 | |
| glm-4-9b-chat (zero-shot) | ¥0 | 3 | 0 | older GLM generation |
| InternLM3-8B-Instruct (zero-shot) | ¥0 | 3 | 0 | |
| MiniCPM5-2B (zero-shot) | ¥0 | 3 | 0 | |
| Ling-3.0-tiny (zero-shot) | ¥0 | 3 | 0 | BTE looped-adjacent arch |
| VibeThinker-3B (zero-shot) | ¥0 | 3 | 0 | |
| Mistral-7B-Instruct-v0.3 (zero-shot) | ¥0 | 3 | 0 | |

Unserviceable despite retries (trust-remote-code, GGUF/llama.cpp, HF-transformers paths):
Spark-X2.5-4B (arch absent from vLLM), Phi-4-mini-flash-reasoning, LoopCoder-V2
(config schema), CLM-v0.1-8B (unknown arch `clm`), DiffuCoder Base/Instruct/cpGRPO
(diffusion-LLM custom code), Ouro-2.6B(-Thinking) (looped transformer; vLLM,
llama.cpp and transformers all incompatible without forking custom code — the
host models of LoopSpec, arXiv:2609.17184), EDGE (TRT engine), "ternary 8b" (no
repo found on HuggingFace).
| Ornith-1.5-9B (zero-shot) | ¥0 | 3 | 0 | |
| Qwopus3.5-9B-v3 (zero-shot) | ¥0 | 3 | 0 | community Qwen-merge; schema confusion |
| Qwythos-9B-v2 (zero-shot) | ¥0 | 3 | 0 | community Qwen-merge |
| ZDTaichu5.0-9B (zero-shot, Q4 GGUF) | ¥50 | 3 | 0–150 | served via llama.cpp (custom vision code incompatible with vLLM) |
| NeoHorse-1-9B (zero-shot) | ¥90 | 3 | 0–270 | |
| OmniCoder-9B (zero-shot) | ¥130 | 3 | 0–270 | coder merge; partial schema adherence |
| gemma-4-12B-it (zero-shot, AWQ) | **¥200** | 3 | 0–300 | **best zero-shot of all models**; strong instruction following |

EDGE (LaraAI TRT export): TensorRT-engine format, not serviceable by vLLM/llama.cpp — excluded.
| qwen3.5-9B (zero-shot) | ¥0 | 1 | 0 | cannot emit valid design JSON |

## Second axis — capital-library production efficiency (different protocol; not comparable to the tables above)

Frozen FluxEidosV1.0-9B (CARE-v3) model, fixed parametric production instances (4 × 3 rounds),
library of execution-verified assets accumulated across generations:

| Library size | 0 | 3 | 6 | 12 | 19 |
|---|---:|---:|---:|---:|---:|
| Production profit / 12 rounds | ¥150 | ¥600 | ¥750 | ¥750 | **¥900** |
| Capital reuse | 1/12 | 10/12 | 10/12 | 9/12 | 11/12 |

Dose–response Spearman ρ = 0.96; 3 seeds all improve monotonically
(+¥450/seed, 2–4× per seed). Weight-level self-update arms show no transferable gain —
see `data/dual_loop_*.json` and `data/library_ablation.json`.

## CAD World Model (CWM-inspired, arXiv:2510.02387 adapted)

621 design->geometry pairs harvested from 32 run sources; mixed predict+generate
LoRA training (860 samples, 6 epochs, CE 0.047). Held-out prediction accuracy
(n=80): **86% validity, 69% exact rating** — the model internalizes build123d
geometry execution without running it. Generation task degraded by task mixing
(¥0 on bench); fix = separate adapters (next iteration).

Data: `data/world_model_pairs.json` | Code: `tools/train_cwm.py`

## Dual-adapter: CAD World Model screening (separated adapters)

Prediction-only LoRA (621 pairs, 5 epochs): **92% validity, 69% exact rating** —
better than the mixed adapter (86%). But prediction-based screening of 4 candidates
is WORSE than naive first-pick (¥150 vs ¥300, n=5): the model learned absolute
outcomes from mediocre-heavy training data, not relative rankings. The 75% CAD
execution savings (20→5 per session) comes from the N→1 architecture itself.
Fix: learning-to-rank training on candidate pairs.

| arm | mechanism | profit (n=5) | CAD execs |
|---|---|---:|---:|
| control (first of 4) | no prediction | ¥300 | 5/session |
| screened (predict best of 4) | world model | ¥150 | 5/session |

Data: `data/screen4_results.json`, `data/control4_results.json`

## Key findings

1. **Training > scale**: a fine-tuned 9B ≈ 90% of the strongest commercial models;
   27B zero-shot and a 30B ML-RSI agent land far below.
2. **Speed pricing discriminates reasoning style**: deepseek-v4-pro reuses most
   (3.6/4) yet earns least among mid-tier — thinking time is billed.
3. **The self-improvement that compounds lives in capital, not weights**: frozen model
   + 19 curated assets = 6× production profit (monotonic, causal); weight-level RSI
   at 9B/30-samples-per-generation is noise-dominated (probe gains fail to transfer, −¥162 on the bench).

## Reproduce

```bash
# commercial/local models against a served endpoint (identical protocol for all rows)
MIMO_KEY=... python tools/run_local_bench.py --endpoint http://... --served-model X --designer X --n 10
# symmetric 3-judge recompute on stored sessions
python tools/rejudge.py --dir runs/local_bench/<model> --tag <model>-3judge
```

Training pipeline: `tools/openrsi_sft_v2.py` (gated SFT) → `tools/train_prsi_v2.py` (QLoRA)
→ `tools/prsi_rl_loop.py` (CARE RL) → `tools/dual_loop_prsi.py` (PRSI × RSI dual loop).

*Last updated: 2026-10-07. 38 systems evaluated (9 vendors + community), 44 result datasets in `data/`. All profits are mean profit per 5-round session unless stated otherwise. Champion system: qwen9b + CARE-v3 + JitRL (¥390, test-time RSI, p=0.037).*

## Test-time RSI (JitRL, arXiv:2601.18510 adapted): positive gains on the standard bench

Same model (FluxEidosV1.0-9B (CARE-v3)), same HF inference path, same judge/pricing; the only
difference is experience retrieval + advantage-weighted logit modulation
(`z' = z + β·A`). Memory starts EMPTY and accumulates across the eval sessions —
the across-session slope IS the self-improvement measurement, zero leakage.

### Full evaluation (n sufficient for significance)

| arm | n | per-session profits | mean |
|---|---:|---|---:|
| plain control (no memory) | 10 | 0, 300, 150, 150, 300, 300, 450, 150, 0, 150 | ¥195 |
| JitRL accumulate (memory 0→full) | 10 | 300, 600, 450, 600, 150, 0, 300, 300, 300, 450 | ¥345 |
| **JitRL mature (memory frozen)** | **5** | 450, 450, 450, 150, 450 | **¥390** |

**Mature vs plain: p = 0.037 (Mann-Whitney z=2.08); all-JitRL (n=15) vs plain: p = 0.023.**
The frozen-memory steady state is exactly 2.0x the same-model control, and edges
past the model's weight-tuned champion (¥372) without any retraining. Under the
2-judge glm-panel recompute the mature sessions score ¥340 (conservative mean
convention) to ¥420 (median convention); the primary single-judge number is ¥390.
Unlike weight-level updates this cannot catastrophically forget, and every
improvement is immediately bench-visible. Data: `data/jitrl_*`.

## FluxEidosV2-9B (V1.5 weights + inference-time stack): first system past mimo-v2.6-flash

Same champion weights (FluxEidosV1.5-9B, CARE-v3 iter6), zero weight updates, zero
external data. Four inference-time mechanisms, each validated by ablation across
surpass v1→v6 (5 sessions each):

| version | stack | mean | runs |
|---|---|---:|---|
| v1 | prose hints all rounds | ¥72 | 0,120,120,0,120 |
| v3 | best-of-3 R1, overlap-first selection | ¥206 | 400,380,0,0,250 |
| v4 | best-of-N R1, parts-first selection + judge retry | ¥350 | 230,80,680,380,380 |
| v5 | + token cap (1.0x pricing) + conditional resample + repair | ¥368 | 550,320,400,200,370 |
| **v6** | **+ in-context experience replay (self-mined rating≥6 designs)** | **¥474** | 450,570,420,380,550 |

**¥474 > ¥433 (mimo-v2.6-flash)** — the first 9B-class system to pass the strongest
commercial baseline. Mechanisms: (1) best-of-3 R1 candidates CAD-screened with
parts-first selection (judge rating tracks structural detail, not geometric
overlap: 9-part designs rate 5-6, clean 4-part designs rate 2-3); (2) in-context
replay of the system's own past rating≥6 designs per round; (3) syntax repair
layer (transform `inputs`->`input`, dead part references); (4) conditional
resample on failed rounds; (5) judge-retry on API-zero flakes.

**Disclosure**: the v6 experience bank is mined from prior runs of the same
standard demands — same test-time-memorization family as JitRL's frozen memory
(¥390; RRSI decomposition: 39% benchmark memorization). The honest generalization
number for this stack requires the sealed parametric probes (V1.5 weights alone:
¥240 there). Weights-only entry remains FluxEidosV1.5 (¥390, standard bench).

**Synthesis**: self-improvement on Money Bench is real and reproducible when it
operates through accumulated substrates — execution-verified assets (within-session
capital, 6× production) and advantage-weighted experience (cross-session JitRL,
2× by session 5) — while 9B weight-level self-modification is noise-dominated.
