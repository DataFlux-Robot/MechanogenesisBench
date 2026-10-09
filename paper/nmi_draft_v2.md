# Self-Improvement in Machine-Making Models Lives in Substrates, Not Weights

**Money Bench: an execution-grounded economic benchmark for cumulative design, and the case for freezing the model**

*Draft v2 — restructured narrative: failure → root cause → substrate solution → boundary conditions → evaluation methodology. (Supersedes nmi_draft_v1.md.)*

---

## Abstract (draft)

The dominant approach to making language models better at real-world machine-making is to keep updating their weights — supervised fine-tuning, reinforcement learning, test-time weight adaptation. We build a ruler that measures whether this works: **Money Bench**, a five-round cumulative product-design benchmark where designs must execute as real build123d B-rep CAD geometry, are priced by a speed-tiered market (¥100/sale × speed multiplier), and where each round's validated artifact becomes importable capital for later rounds. Evaluating 39 systems from 9 vendors, the ruler exposes three failures: (1) the strongest commercial models retain only 29–32% of their profit when the task domain shifts; (2) all four families of weight-level self-improvement we test at 9B scale (CARE RL extensions, groupwise advantage redistribution, test-time RL, self-distilled SFT) fail to improve a trained baseline — probe noise of identical weights spans ¥38–225, exceeding per-update drift; (3) test-time "self-improvement" via experience replay is 39% benchmark memorization under RRSI-style regularization. We then formalize a minimal model: verified-substrate accumulation is monotone by construction and has no capability threshold, while gradient-based weight updates inherit a signal-to-noise threshold and memory-based gains scale with train–test instance overlap. All three predictions are empirically validated. Operationally, the model prescribes freezing the weights and improving the substrates: a curated asset library compounds production profit 6× (dose–response ρ=0.96), cross-session experience doubles profit (p=0.037), and a five-mechanism inference-time stack takes a 9B open model past the strongest commercial frontier model under a symmetric three-vendor judging protocol (¥532 vs ¥433 per session, Mann–Whitney p=0.0015, d=1.0, n=40) at ~1/1000 of its training compute. Cross-vendor judges agree adequately (Krippendorff's α=0.676, sale-decision agreement 80%) and show no family bias. We open-source the benchmark, 59 result datasets, and all training/inference code.

---

## 1. Introduction — the story in one page

**The default.** When practitioners want a model to get better at a task through experience, the reflex is to change the weights: fine-tune, RL, distill. The self-improvement literature at large optimizes parameters.

**The ruler.** We ask a sharper, economic question: *through accumulated machine-making experience, does the system earn more money?* Money Bench makes this measurable: designs must survive real CAD execution (not string matching); the market pays per sale with speed-tiered pricing; validated designs become reusable capital so improvement can compound across rounds; and everything — 39 systems, 9 vendors, 59 datasets — is open.

**Three failures the ruler exposes.**
1. **Frontier models collapse off-distribution.** The strongest commercial model keeps 29–32% of its in-domain profit on two unseen task domains (fixture design, production-line layout).
2. **Weight-level self-improvement at 9B is noise-dominated.** From a trained baseline (¥372–390), every weight-update family we test regresses or stagnates: weight self-update lineage ¥210, GAR-RL ¥270, TTRL ¥270. Identical-weights probe runs span ¥38–225 — the evaluation noise floor swamps per-update drift at ~30 samples/generation.
3. **Test-time "gains" partially memorize.** RRSI-style regularization reveals 39% of experience-replay improvement is benchmark-specific memorization.

**The counterintuitive resolution.** Freeze the weights; improve the **substrates** — execution-verified assets, cross-session experience, and inference-time selection. These compound: assets 6×, experience 2×, and the full stack surpasses the frontier under symmetric judging (¥532 vs ¥433, p=0.0015) at 1/1000 compute. A 9B model on one consumer GPU beats the strongest API system it was benchmarked against.

**A minimal formal model** (§7) explains all of it with three propositions: substrates are monotone (no threshold), weight updates have an SNR threshold, memory gains scale with instance overlap. Each prediction is validated empirically — including the uncomfortable ones: below-threshold systems amplify noise (−54%), and memory does not transfer off-distribution (+4%, n.s.).

**Contribution summary.**
1. An execution-grounded economic benchmark of cumulative self-improvement (open).
2. A systematic negative result: four weight-update families fail at 9B, with a root-cause noise analysis.
3. A substrate-first alternative that surpasses the commercial frontier at 1/1000 compute, under a symmetric, family-bias-checked three-vendor protocol.
4. A minimal formal model with three validated predictions, unifying the threshold, dose–response, and instance-binding phenomena.
5. Honest-decomposition methodology (memorization accounting, judge-consistency auditing).

---

## 2. The ruler: Money Bench v5

**Task.** Five-round cumulative product design: (R1) scratch design for a demand with sampled dimensions; (R2) adapt to upgraded dimensions *reusing round 1's base*; (R3) add a bay module; (R4) add a second module combining everything; (R5) desk shrinks — compress while keeping all functions.

**Execution, not strings.** Every design is a CSG JSON (`workstation-csg/1`: box, cylinder, union, difference, transform, capital) that must build as real build123d B-rep geometry: build → STEP export → re-import → exact intersection and envelope measurement. Designs that fail to execute score zero.

**Economy.** A sale pays ¥100 × speed multiplier (<10s: 1.5×; <30s: 1.2×; <60s: 1.0×; <120s: 0.8×; ≥120s: 0.5×). Quality gate is a 0–10 user-satisfaction rating from LLM judges (§9); sale requires rating ≥5.

**Capital.** Each round's executed design registers as an importable STEP asset (`capital(asset_id)`) — free and faster than rebuilding. This is where cross-round compounding lives.

**Protocols.** Single-judge (mimo-v2.6-pro median) and symmetric 3-judge (mimo-v2.6-pro + glm-5.3 + glm-5.3-flash, median decides). All rows same judge(s); full per-run spreads open-sourced.

**Scale of evaluation.** 39 systems: 6 commercial APIs, 21 zero-shot open models, 12 of our own lineage entries; 59 result datasets; sealed parametric probe set (seed 20261005, never used in training) for generalization.

---

## 3. What the ruler exposes — three failures

### 3.1 Frontier models collapse off-distribution

| arm | fixture | layout | workstation (in-domain) |
|---|---:|---:|---:|
| mimo-v2.6-flash | ¥124 | ¥138 | ¥433 |
| FluxEidosV1.5 (ours, 9B) | ¥0 | ¥60 | ¥390 |
| FluxEidosV2 stack (ours) | ¥0 | **¥264** | **¥532 (3-judge)** |

The strongest commercial model retains 29–32% of in-domain profit on two unseen domains (3-judge, n=5/cell). Note this is *not* only our model's weakness — the domain shift degrades everyone; the ruler just makes it a number.

### 3.2 Weight-level self-improvement at 9B fails from a trained baseline

| mechanism | profit | verdict |
|---|---:|---|
| FluxEidosV1.0 (CARE-v3, trained baseline) | ¥372–387 | — |
| + weight self-update lineage (RSI) | ¥210 | −44%; probe gains do not transfer |
| + GAR-RL (groupwise advantage redistribution) | ¥270 | regression; catastrophic forgetting at lr 2e-5 |
| + TTRL (online test-time RL) | ¥270 | regression |
| + self-distilled SFT (V0.2 lineage) | ¥0 | format contamination |

**Root cause (§5): evaluation noise exceeds per-update drift.** Repeated evaluation of *identical weights* spans ¥38–225 (n=10 probe sessions). Each RL generation carries ~30 samples; the gradient signal-to-noise ratio at this sample count cannot clear the noise floor. Weight updates at this scale are expensive coin flips.

### 3.3 Test-time "gains" are 39% memorization

RRSI-style regularization (critic screening + noise floor + cost rule) rejects 21/21 experience memories retrieved on benchmark demands (self-similarity = 1.0). Decomposition: JitRL's ¥390 = ¥240 honest generalization + ¥150 benchmark memorization. The honest share transfers to sealed probes; the memorized share does not (§8).

---

## 4. The resolution — substrates, not weights

### 4.1 Execution-verified assets compound (within and across sessions)

Frozen V1.0 weights; only the curated asset library grows:

| library size | 0 | 3 | 6 | 12 | 19 |
|---|---:|---:|---:|---:|---:|
| production profit / 12 rounds | ¥150 | ¥600 | ¥750 | ¥750 | **¥900** |

Monotone on 3/3 seeds; dose–response Spearman ρ=0.96. 6× at 19 assets.

### 4.2 Cross-session experience doubles profit

Same weights, same inference path; only an advantage-weighted experience bank (JitRL) accumulates across sessions, starting empty: control ¥195 → accumulating ¥345 → frozen mature ¥390 (2.0×, p=0.037; 3-judge recompute ¥340–420).

### 4.3 The full inference-time stack surpasses the frontier

Five mechanisms on frozen V1.5 weights (ablated v1→v7, 5–20 sessions per version):
(1) best-of-3 R1 generation CAD-screened with parts-first selection;
(2) in-context replay of the system's own rating-≥6 designs;
(3) syntax repair layer;
(4) conditional resampling (second retry on weak rounds);
(5) judge-retry on API-zero flakes; plus executed-designs-register-as-capital semantics.

| protocol | FluxEidosV2 | mimo-v2.6-flash | verdict |
|---|---:|---:|---|
| single-judge | ¥438 (n=40) | ¥433 (n=14) | parity (p=0.39) |
| **3-judge symmetric** | **¥532 (median 540, n=40)** | ¥433 (n=14) | **+23%, p=0.0015, d=1.0** |

Resample-ambiguity bounds: pessimistic ¥489 / neutral ¥532 / optimistic ¥564 — all above the frontier. Cost: one consumer GPU, ~1/1000 of the frontier's training compute.

Notably, the V2 stack also **wins the layout domain** (¥264 vs mimo's ¥138, p=0.029, +91%) — substrate mechanisms transfer where the model is above threshold (§8).

---

## 5. Root cause analysis: why weights fail here

1. **Sample budget.** Each RL generation yields ~30 designs. Policy-gradient variance at this sample count is large relative to mean advantage.
2. **Noise floor.** Identical-weights probe re-evaluation spans ¥38–225 — any claimed improvement below ~¥80/ Session cannot be distinguished from re-rolling the dice.
3. **Interference.** GAR-RL at lr 2e-5 destroyed format competence (33/36 → 1/36 valid in three generations): single-task updates at 9B overwrite fragile instruction-format circuits.
4. **Compounding vs. lurching.** Substrate acceptance requires *execution verification* — a discrete, noiseless gate. Weight steps accept continuous, noisy deltas. This is the formal distinction §7 exploits.

---

## 6. …and why the substrates work (mechanistically)

- Assets are STEP files: once verified, they cannot "forget." Reuse is free and fast — the economics reward it directly (faster rounds → higher speed multiplier).
- Experience replay re-injects the system's own validated high-rated designs — it shifts the generation distribution toward proven modes without touching weights (and its memorization share is measured, §3.3).
- Selection (best-of-N with parts-first criterion) exploits a discovered judge regularity: ratings track *structural detail*, not geometric cleanliness (9-part designs rate 5–6; geometrically clean 4-part designs rate 2–3). CAD screening by overlap would actively pick worse designs.

---

## 7. A minimal formal model

**Setup.** Attempts are Bernoulli(p) — valid-and-sold with probability p (the model's capability). c = per-verified-asset value.

**Proposition 1 (substrate monotonicity).** Accept an asset into the library only after execution verification. Then accumulated value V_S(n) = c·Binomial(n,p) is monotone in expectation, E[V_S(n)] = cnp, with no threshold in p.
*Proof sketch:* verification is a 0/1 gate independent of noise magnitude; E is linear in n. ∎
*Empirics:* dose–response ρ=0.96, monotone on all seeds (Fig. 1, left).

**Proposition 2 (weight-update threshold).** A weight step Δθ = η(g + ε), ε zero-mean with variance σ², changes true performance by E[ΔF] = η‖g‖² − (η²σ²L)/2 (signal minus noise shrinkage, L = effective dimension). Observed improvement is additionally masked by evaluation noise σ_eval. Improvement is detectable only when η‖g‖² exceeds the sum of both noise terms — a capability threshold in p; substrates have none.
*Empirics:* below-threshold experience accumulation amplifies noise: V0-Self +JitRL = −54%; above threshold: V1.0 +JitRL = +5% (p=0.037); threshold also separates domains (fixture below, layout above) (Fig. 1, middle).

**Proposition 3 (memory instance-binding).** Replay retrieves a bank item with train–test overlap s; expected gain ∝ s̄·p. Weight-level capability instead transfers with retention r_w independent of s.
*Empirics:* on-distribution replay +13%; sealed-probe replay +4% (n.s., p=0.40) while weights retain 65% — memory wins on-distribution, weights win off-distribution (Fig. 1, right).

**Prescription.** Freeze weights when (a) sample budget is small, (b) evaluation noise is large, or (c) capability is near threshold. Improve substrates. All three conditions hold for 9B-class open models on executable design tasks today.

*(Figure: `paper/figures/formal_model.png` — three panels with model curves and empirical overlays.)*

---

## 8. Boundary conditions (the honest part)

1. **Capability threshold extends to domains.** In fixture design our model sits below threshold (round ratings 2.4–3.6; no design reaches 6, so the within-domain experience bank never accumulates; ¥0 vs mimo's ¥124). In layout it sits above (R1 rating 6.0; V2 beats the frontier +91%). Same stack, opposite outcomes — mechanism, not marketing.
2. **Memory is instance-bound.** Sealed probes: V2 stack ¥341 vs plain weights ¥327 (+¥14, p=0.40); only the retry mechanism transfers (R5 rating 2.2 vs 1.0). Weights-only retains 65% of in-distribution profit.
3. **Memorization accounting.** 39% of cross-session experience gain (§3.3) — reported, regularized, and excluded from generalization claims.
4. **Judge regularities are exploitable.** The parts-vs-overlap finding (§6) is exactly why symmetric protocols and disclosed inference stacks matter; our replay bank is disclosed as same-benchmark experience.

---

## 9. Evaluation methodology: can we trust LLM judges without humans?

No human study was run; we substitute three machine-auditable safeguards and disclose the limitation.

1. **Symmetric cross-vendor protocol.** Median of three judges from three vendors (Xiaomi, Zhipu×2 families). On 283 fully-judged round-triples across designers and domains: **Krippendorff's α (ordinal) = 0.676**; pairwise Spearman 0.66–0.74; **sale-decision agreement 75–81%** — the operational decision the economy prices.
2. **Family-bias audit.** The Xiaomi judge does *not* favor Xiaomi designs: its mean gap (mimo-designs minus ours) is −0.61 (n.s.); glm-5.3's is −0.25 (n.s.). The single-judge/3-judge gap for our system is judge-leniency structure, not vendor capture — and the symmetric protocol is applied identically to all systems.
3. **Execution-grounded backbone.** CAD validity, intersection volume, envelope excess, reuse rates, and speed are objective (geometry kernel) numbers; ratings only gate the final sale. The headline negative results (§3) hold on objective metrics alone.

*Limitation:* human preference validation remains future work; the cross-vendor consistency above is the strongest machine-only substitute we can offer.

---

## 10. Related work (to position)

- Test-time/weight RSI: JitRL, TTRL, self-play RFT — we compare four families head-to-head on one economic ruler.
- Benchmarks with execution: code benchmarks verify tests; we verify *physical geometry* and price *economics*.
- Skill/experience libraries (CRAFT/Voyager-style): our assets are execution-verified STEP artifacts with dose–response evidence.
- RRSI regularization (arXiv:2609.24972): we adopt its decomposition to audit our own gains.
- CAD world models (CWM, arXiv:2510.02387): our prediction adapter reaches 92% validity but fails as a ranker — negative result reported.
- Judge-validity literature: cross-vendor consensus + bias audit as human-substitute.

---

## 11. Limitations

1. No human evaluation (see §9 mitigation).
2. No manufactured artifacts; "physical" = executable B-rep geometry in an industry-standard STEP pipeline, not printed parts.
3. Mechanism-level analyses (GAR/TTRL/threshold) at n=5–10; headline claims at n=40 vs 14.
4. The replay bank is same-benchmark (disclosed; sealed probes quantify its non-transfer).
5. One model family (Qwen-9B base) for the fine-tuned lineage.

---

## 12. Conclusion

On an execution-grounded economic benchmark, the self-improvement that compounds lives in verified substrates — assets, experience, selection — while 9B weight updates are noise-dominated below a capability threshold that also separates domains. Freezing the weights and improving the substrates takes a 9B open model past the commercial frontier under symmetric cross-vendor judging, at 1/1000 the compute. The ruler, the failures, the model, and the data are all open.

---

### Appendix: key numbers index
- Frontiers: V2 3-judge ¥532 (n=40) vs mimo-flash ¥433 (n=14), p=0.0015, d=1.0; bounds ¥489–564.
- Weights-only: V1.5 ¥390; V1.0 ¥372/¥387; baseline zero-shot qwen3.5-9B ¥0.
- Failures: domain retention 29–32%; weight-RSI −44%; JitRL memorization 39%.
- Substrates: assets 6× (ρ=0.96); experience 2× (p=0.037); stack +13% over weights-only single-judge.
- Judges: α=0.676 (n=283); sale agreement 75–81%; family bias absent (gaps −0.61/−0.25/−1.11, all n.s. against pro-mimo direction).
- Probes: replay +¥14 n.s.; weights retention 65%; only retry transfers (R5 2.2 vs 1.0).
