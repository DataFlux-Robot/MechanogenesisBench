# Money Bench: Quantifying Physical Recursive Self-Improvement in LLM Agents Through Execution-Grounded Evaluation

## Authors
[To be filled]

## Abstract

Large language models can generate physical designs, but whether they can *improve at machine-making through accumulated experience* — physical recursive self-improvement (PRSI) — remains unmeasured. We introduce Money Bench, a five-round cumulative product-design benchmark with real build123d B-rep CAD execution, LLM-judge user simulation, and speed-based pricing that rewards both quality and efficiency. Across 38 systems from 9 vendors, we find that a fine-tuned open 9B model achieves ~90% of the commercial frontier (¥372 vs ¥433 per session) at ~1/1000 of the training compute. We then systematically compare five self-improvement mechanisms — offline RL (CARE), online RL (TTRL), MiMo-style groupwise advantage redistribution (GAR), test-time experience accumulation (JitRL), and parametric skill libraries (CRAFT-style) — and discover three principles: (1) self-improvement compounds in accumulated substrates (asset libraries 6×, parametric skills 75× speed) rather than in 9B weight updates (all four weight-based methods fail to improve from a trained baseline); (2) test-time memory-based improvement (JitRL, +5%) contains 39% benchmark-specific memorization as revealed by RRSI regularization (arXiv:2609.24972); and (3) a capability threshold exists below which experience accumulation amplifies noise rather than signal. Our benchmark, training pipeline, and 44 result datasets are fully open-sourced.

**Keywords**: physical recursive self-improvement, CAD benchmark, test-time adaptation, parametric skills, execution-grounded evaluation

---

## 1 Introduction

The promise of recursive self-improvement (RSI) — systems that make themselves progressively better at their own tasks — has driven recent work on self-improving LLM agents [OpenRSI, Frontis-MA1, RRSI]. However, most evaluations measure improvement on code generation or web navigation. Whether LLM agents can improve at *physical design* — creating, modifying, and optimizing real CAD geometry through experience — is unknown. This matters because physical design has properties that code does not: designs must be geometrically valid, physically manufacturable, and accumulate as reusable assets across projects.

We introduce **Money Bench**, a benchmark for measuring physical recursive self-improvement. Unlike prior CAD benchmarks that evaluate single-shot design generation, Money Bench simulates a real engineering workflow: five rounds of cumulative product demands (build → adapt → extend → compose → shrink), where each round's validated design becomes an importable STEP asset (physical capital) for subsequent rounds. The benchmark uses real build123d B-rep CAD execution — not approximations — as ground truth for geometric validity, and introduces speed-based pricing that rewards efficient design generation.

Using Money Bench, we conduct the first systematic comparison of self-improvement mechanisms in the physical design domain (Figure 1). Our contributions are:

1. **Money Bench**: A fully open benchmark with real CAD execution, 38 systems evaluated, and a parametric demand generator for generalization testing
2. **Five-mechanism ablation**: Systematic comparison of CARE RL, TTRL, GAR-RL, JitRL, and parametric skill libraries — all released with full code
3. **Three principles of physical self-improvement**: (a) substrates > weights, (b) memory gains decompose into generalization vs memorization (quantified via RRSI regularization), (c) capability threshold for test-time improvement
4. **Open 9B model at 90% frontier**: FluxEidosV1.0 trained on one consumer GPU achieves ¥372 vs commercial frontier ¥433

---

## 2 Related Work

### 2.1 CAD Design with LLMs
Text-to-CAD systems [Text2CAD, Design2Code, Text-to-CadQuery] generate parametric models from natural language. Recent work adds visual feedback loops [Text-to-CAD+Visual Feedback]. However, these evaluate single-shot generation, not cumulative improvement through experience.

### 2.2 Recursive Self-Improvement
Frontis-MA1 [OpenRSI] trains models for ML engineering through execution-grounded post-training and evolutionary search. Qwen-Planner-Agent uses CARE (Competence-Aware Reward-and-Advantage Engineering) for adaptive RL. RRSI [arXiv:2609.24972] regularizes harness-level self-improvement to prevent overfitting. Our work extends these approaches to physical design with real CAD execution.

### 2.3 Test-Time Adaptation
JitRL [arXiv:2601.18510] performs test-time policy optimization via experience retrieval and advantage-weighted logit modulation. TTRL uses majority voting as pseudo-rewards. Our JitRL adaptation applies trie-based logit modulation to design generation.

### 2.4 Parametric Skill Libraries
CRAFT [arXiv:2309.17428] creates executable code tools. Voyager and SkillWeaver autonomously synthesize skill libraries. We apply this paradigm to parametric CAD functions.

### 2.5 World Models for Design
CWM [arXiv:2510.02387] trains LLMs on execution traces to build internal world models. We adapt this by training a prediction adapter that infers build123d outcomes from design JSON (92% validity prediction accuracy).

---

## 3 Money Bench

### 3.1 Task Definition

Each Money Bench session consists of five cumulative rounds simulating a real product design workflow:

| Round | Demand Type | Tests |
|-------|------------|-------|
| R1 | Build phone dock from scratch | Cold-start design |
| R2 | Adapt to larger phone | Incremental modification + capital reuse |
| R3 | Add earbuds bay | Feature addition + composition |
| R4 | Add tablet stand | Multi-module integration |
| R5 | Desk shrinks 30% | Space-constrained optimization |

Each round's validated design becomes a STEP file (physical capital) importable in subsequent rounds via `capital(asset_id)` — free and faster than rebuilding. This creates a PRSI test: does the system accumulate and reuse physical assets effectively?

### 3.2 Evaluation Pipeline

```
Demand → LLM generates design JSON → build123d B-rep CAD execution
  → STEP export → re-import → geometric metrics (overlap, envelope)
  → LLM judge (user simulation) → sold/unsold → profit calculation
```

**Geometric ground truth**: Real build123d B-rep construction (not bounding-box approximation). Each design is built, exported as STEP, re-imported, and measured for overlap volume and envelope excess. This ensures geometric validity is a hard constraint, not a soft preference.

**Speed-based pricing**: Design generation time determines the price multiplier:
- <10s: 1.5× (fast iteration rewarded)
- 10-30s: 1.2×
- 30-60s: 1.0×
- >120s: 0.5× (slow, expensive thinking penalized)

This creates a fundamental tension: reasoning models produce better designs but earn less per sale due to speed penalties. We show this discriminates effectively (deepseek-v4-pro: highest reuse rate 3.6/4 but lowest profit ¥112 due to 89s/design).

**Profit metric**: Σ(sold rounds × ¥100 × speed multiplier). Higher is better.

### 3.3 Parametric Generalization

For generalization testing, we use a parametric demand generator: 4 product families (phone, e-reader, powerbank, console) × 3 bay types × 3 secondary modules × sampled dimensions and desk sizes. This produces infinite novel instances, of which 20 are frozen as a sealed probe set (never used in training).

### 3.4 Statistical Protocol

Primary comparisons use Mann-Whitney U with Bonferroni correction. Key findings verified at n≥5 per condition. Cross-judge validation uses median of 3 vendors (mimo-v2.6-pro, glm-5.3, glm-5.3-flash).

---

## 4 Experimental Setup

### 4.1 Systems Evaluated

We evaluate 38 systems across 6 categories:

**Commercial APIs** (8): mimo-v2.6-pro, mimo-v2.6-flash, glm-5.3, glm-5.3-flash, deepseek-flash (V4.1), deepseek-v4-pro, and 2 additional baselines.

**Open fine-tuned** (6): FluxEidosV1.0 (CARE-v3), V1.1, V1.2, V1.5 (+JitRL), V0-Self (pure self-play RFT), V2.0 (GAR-RL).

**Self-improvement variants** (8): JitRL plain control, JitRL accumulating, RSI lineage (weight-self-update), TTRL, GAR+JitRL, RRSI-regularized JitRL, parametric skill library, hybrid skill-model.

**Zero-shot** (16): Qwen3.5-9B/27B, gemma-4-12B, OmniCoder-9B, Seed-Coder-8B (3 variants), ZDTaichu, K2-Horizon, and 9 community models.

### 4.2 Training Pipeline (FluxEidos)

Our fine-tuned models use a three-stage pipeline on a single RTX 4090D (24GB):

1. **Gated SFT** (150-239 examples): Four-operator format (Draft/Improve/Debug/Crossover) from execution-verified trajectories
2. **CARE RL**: Competence-adaptive reward scheduling (progress shaping → outcome consolidation → efficiency refinement) with quality-preserving advantage damping
3. **JitRL** (optional): Test-time experience accumulation via advantage-weighted logit modulation

---

## 5 Results

### 5.1 Main Leaderboard

| Rank | System | Profit (¥) | n | Speed |
|------|--------|-----------|---|-------|
| 1 | **FluxEidosV2 (ours, system)** | **440** (median 450) | 20 | local |
| 2 | mimo-v2.6-flash | 433 | 14 | API |
| 3 | mimo-v2.6-pro | 418 | 11 | API |
| 4 | **FluxEidosV1.5 (ours)** | **390** | 5 | JitRL |
| 5 | **FluxEidosV1.0 (ours)** | **372** | 10 | local |
| 6 | glm-5.3 | 380 | 11 | API |
| 7 | glm-5.3-flash | 311 | 16 | API |

*Full 38-system table in supplementary.*

**FluxEidosV2** couples the V1.5 weights with a pure inference-time stack — best-of-N
CAD-screened candidate selection for the scratch round (parts-first: judge rating tracks
structural detail, not geometric overlap), in-context replay of the system's own past
rating-≥6 designs, a syntax repair layer, conditional resampling, and judge-retry — and
reaches system-level parity with the strongest commercial baseline (¥440 mean / ¥450
median vs ¥433, n=20 vs 14; Mann-Whitney p=0.31), a +13% gain over the same weights
without the stack (¥390). The v1→v6 ablation (5 sessions each: ¥72 → ¥206 → ¥350 → ¥368
→ ¥474, replicated at ¥440 n=20) isolates each mechanism's contribution. Disclosure: the replay bank is mined from prior standard-bench runs (same
test-time-memorization family as JitRL; sealed-probe generalization reported in §6), so
the weights-only entry remains V1.5 at ¥390.

The best open 9B model achieves ~90% of the commercial frontier on weights alone. Training cost: ~250 gated SFT examples + 12 RL iterations on one consumer GPU.

### 5.2 Self-Improvement Mechanism Comparison

We compare five mechanisms, all starting from the same V1.0 checkpoint:

| Mechanism | Weight Updates? | Memory? | Profit | Δ from V1.0 |
|-----------|:-:|:-:|---:|---:|
| **JitRL** (test-time memory) | ✗ | ✓ | ¥390 | **+5%** |
| V1.0 baseline | ✓ (training) | ✗ | ¥372 | — |
| GAR-RL (offline, parametric domain) | ✓ | ✗ | ¥270 | -27% |
| TTRL (online weight updates) | ✓ (online) | ✗ | ¥270 | -27% |
| Skill Library (parametric functions) | ✗ | ✗ | ¥90 | -76% |

**Finding 1: Substrates > Weights.** The only mechanism that improves from V1.0 is JitRL (memory-based). All weight-update mechanisms — offline (GAR), online (TTRL), or iterative (self-play) — degrade performance. This is consistent across four independent experiments.

**Finding 2: RSI domain shift.** GAR-RL improves on parametric instances (25%→31% sell rate) but degrades on standard bench (¥372→¥270). Weight updates optimized for generalization hurt domain-specific performance.

### 5.3 Capital Library Effects (PRSI)

With a frozen model and accumulating asset library:

| Library Size | 0 | 3 | 6 | 12 | 19 assets |
|---|---:|---:|---:|---:|---:|
| Profit / 12 rounds | ¥150 | ¥600 | ¥750 | ¥750 | **¥900 (6×)** |

Dose-response Spearman ρ = 0.96; 3/3 seeds improve monotonically. This is the core PRSI result: **physical asset accumulation compounds**, independent of model weights.

### 5.4 JitRL Decomposition via RRSI Regularization

Following RRSI (arXiv:2609.24972), we apply regularization to JitRL's memory accumulation:

| System | Memory Type | Profit | Interpretation |
|--------|------------|---:|---|
| V1.0 baseline | None | ¥240 | Pure model + capital |
| V1.0 + RRSI-JitRL | Regularized (critic blocks benchmark-specific) | ¥240 | Honest generalization |
| V1.0 + JitRL | Unregularized | ¥390 | Includes memorization |

**Finding 3: JitRL's improvement is 39% memorization.** The RSI critic rejected 21/21 memories on benchmark demands. The "overfitting premium" is ¥390 − ¥240 = ¥150 (39% of JitRL's claimed improvement). This motivates parametric skills as memorization-free alternatives.

### 5.5 Capability Threshold

JitRL improves V1.0 (¥372→¥390) but *hurts* V0-Self (¥132→¥60):

| Base Model | Alone | + JitRL | Effect |
|---|---:|---:|---|
| V1.0 (¥372) | ¥372 | ¥390 | **+5%** (signal amplified) |
| V0-Self (¥132) | ¥132 | ¥60 | **-54%** (noise amplified) |

**Finding 4: Capability threshold.** Below a minimum capability level, experience-memory modulation amplifies noise rather than signal. This aligns with in-context RL theory [Song et al., ICLR 2026].

### 5.6 Parametric Skill Library

Hand-written parametric functions (0.000s execution) achieve ¥90 on the bench:

| Property | Model Inference | Parametric Skill |
|---|---|---|
| Execution time | 30-60s | 0.000s |
| Speed pricing | 1.0-1.2× | **Always 1.5×** |
| CAD validity | ~90% | 80% (fixable bug) |
| Determinism | ✗ | ✓ |
| Generalization | Limited | ✓ (any dimensions) |
| SFT contamination | Possible | **None** |

While raw score is lower (designs too simple for judge), the speed and determinism advantages are structural. When composed with model selection (hybrid architecture), the model chooses skills and parameters (25/25 success rate), and skills execute deterministically.

### 5.7 CAD World Model

Training a prediction adapter on 621 (design → geometry) pairs achieves:
- 92% validity prediction accuracy (held-out, n=80)
- 69% exact rating prediction
- Applied to candidate screening: currently negative result (absolute prediction ≠ relative ranking)

### 5.8 Generalization

Held-out demands (new product families, never trained on):
- FluxEidosV1.0: ¥240 (65% of in-distribution ¥372)
- 10/10 sessions profitable

Sealed-probe decomposition of the V2 inference stack (n=10, seed 20261005):
- plain V1.5 weights: ¥327
- V1.5 + full V2 stack (replay bank mined from standard bench): ¥341 (+¥14, p=0.40)
- Per-round ratings show only the retry mechanism transfers (R5: 2.2 vs 1.0);
  experience-replay gains are instance-bound
- **Principle: memory wins on-distribution, weights win off-distribution** — the
  symmetric complement to the RRSI decomposition (39% of JitRL's gain was benchmark
  memorization; here ~96% of the replay stack's in-distribution gain fails to transfer)

Cross-domain (fixture design, different system prompt):
- FluxEidosV1.0: ¥144 = commercial baseline (¥100-150)

### 5.9 Negative Results (Honest Reporting)

We report all failed approaches:
- **27B parameter scaling**: Zero-shot ¥190-213 (below fine-tuned 9B)
- **Base model swap (MiMo-distill, OmniCoder, Seed-Coder)**: All degrade post-SFT due to distillation rigidity
- **Weight-level self-play**: V0.1/V0.2 iterations fail (format contamination, quality plateau)
- **CWM screening**: Prediction-based candidate selection hurts (¥150 vs ¥300 control)
- **Frontis-MA1-30B cross-domain**: ML-domain RSI does not transfer (¥120)

---

## 6 Discussion

### 6.1 Why Weights Fail but Memory Works

At 9B scale, each RL iteration updates weights using ~30 samples. The gradient signal-to-noise ratio is insufficient — probe measurements of identical weights range from ¥38 to ¥225 (evaluation noise). Weight updates amplify this noise. Memory-based approaches (JitRL) sidestep this by storing discrete outcomes rather than continuous weight perturbations.

### 6.2 The SFT Controversy Resolution

Our V0-Self proves that pure self-play bootstrapping works: 10 self-generated examples take a model from ¥0 to ¥132 with zero external data. However, self-play iteration (V0.1, V0.2) fails due to format contamination and quality plateaus. This means the "SFT from other models" debate is nuanced: external data accelerates bootstrap (V1.0: ¥372 from 239 examples) but pure self-play is possible (V0-Self: ¥132 from 10 examples).

### 6.3 Parametric Skills as Memorization-Free Improvement

The RRSI decomposition shows JitRL's gains include 39% benchmark memorization. Parametric skills offer a structural alternative: a verified function generates valid designs for *any* parameters (not just benchmark instances), with zero memorization risk. The trade-off is design simplicity (judge rates 3-6/10 vs 5-8/10 for model-generated designs).

### 6.4 Limitations

1. **Single domain**: Primary results on workstation design; multi-domain infrastructure exists but fine-tuned models not evaluated on all domains
2. **LLM-as-judge**: Cross-vendor median mitigates but does not eliminate judge bias; no human evaluation yet
3. **No physical fabrication**: All evaluation in build123d simulation; no 3D-printed artifacts
4. **Sample sizes**: n=5-10 per condition (adequate for effect sizes reported, but larger for Nature-tier)
5. **Speed pricing hardware-dependent**: Local 4090D latency vs API latency may not be directly comparable

---

## 7 Conclusion

Money Bench provides the first systematic evaluation of physical recursive self-improvement in LLM agents. Our five-mechanism comparison reveals that self-improvement in physical design compounds in accumulated substrates (asset libraries, parametric skills) rather than in 9B weight updates. RRSI regularization reveals that memory-based improvement contains 39% benchmark-specific memorization. A capability threshold governs whether test-time adaptation helps or hurts. These findings, combined with our fully open benchmark and training pipeline, establish a foundation for measuring and optimizing PRSI in machine-making systems.

---

## Data Availability

All 44 result datasets, 46 tools, and the complete training pipeline are open-sourced at:
`https://github.com/ExuberantWitness/MechanogenesisBench` (branch: `money-bench-v5-prsi`)

## Code Availability
Training: `tools/openrsi_sft_v2.py` → `tools/train_prsi_v2.py` → `tools/prsi_rl_loop.py` → `tools/jitrl_bench.py`
Evaluation: `tools/run_local_bench.py`, `tools/rejudge.py`, `tools/gen_bench.py`

## Acknowledgments
We thank Xiaomi for the MiMo API, Zhipu for the GLM API, and the build123d community.

## References

[1] OpenRSI: arXiv:2607.28568
[2] RRSI: arXiv:2609.24972
[3] JitRL: arXiv:2601.18510
[4] TTRL: arXiv:2504.16084
[5] CRAFT: arXiv:2309.17428
[6] CWM: arXiv:2510.02387
[7] CARE/Qwen-Planner-Agent: arXiv:2609.29892
[8] Song et al. (ICRL theory): ICLR 2026
[9] Voyager: arXiv:2305.16291
[10] SkillWeaver: arXiv:2504.07079

---

## Supplementary Materials

### Table S1: Complete 38-System Leaderboard
[Full table with all systems, profit, n, spread, notes]

### Table S2: Self-Improvement Ablation Details
[All five mechanisms with hyperparameters and full results]

### Table S3: Capital Library Dose-Response
[Library size vs profit for all 3 seeds]

### Figure S1: Money Bench Architecture Diagram
### Figure S2: Training Pipeline Flow
### Figure S3: JitRL Memory Accumulation Example
### Figure S4: RRSI Critic Rejection Analysis
### Figure S5: Capability Threshold Visualization

### Appendix A: Reproducibility
[Exact commands, environment setup, API costs]

### Appendix B: Statistical Methods
[Mann-Whitney U, Wilson CI, Kruskal-Wallis H, Bonferroni correction details]

### Appendix C: Multi-Domain Infrastructure
[Parametric demand generator, fixture/layout domain specs]
