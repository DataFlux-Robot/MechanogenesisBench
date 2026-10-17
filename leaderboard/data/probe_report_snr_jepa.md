# Probe report — SNR threshold × surrogate (JEPA) experiments

Date: 2026-10-18. All probes use archived runs; no new LLM training was started.
Data: `runs/probes/*.json`, `facts_from_rollouts.jsonl`, `format_noise.json`.

## P2/P3 — threshold structure (6 CARE lineages, 32 single updates)

Per-iteration mean reward vs its own standard error (prompt-level, k=6 samples):

| quantity | value |
|---|---|
| single updates detectable at \|z\|>1.96 | **0/32** |
| mean \|z\| at k=6 | 0.65 (max 1.76) |
| mean \|z\| at k=1 / 2 / 3 / 6 | 0.27 / 0.37 / 0.46 / 0.65 |

Reading: at practitioner budgets no individual weight update clears its own noise;
detectability comes from cumulative multi-step drift. The sample budget raises the
z linearly in sqrt(k), but k=6 is far from the threshold.

## C — judge variance decomposition (283 designs × 3 vendors)

| component | value |
|---|---|
| between-design sd (signal) | 2.06 |
| within-design across-judge sd (disagreement) | 1.08 |
| within/between variance ratio | 0.28 |
| vendor offsets | mimo +0.00, glm-5.3 +0.10, glm-5.3-flash −0.10 |
| corr(judge, mean of other two) | 0.73–0.77 |

Reading: judge disagreement is mostly design×judge interaction (taste), not a
systematic vendor offset. A three-judge median damps it but cannot remove it.

## P1 — format-noise decomposition (12 designs × 4 variants × 3 reps; 89/144 calls valid)

Semantically identical variants (part renaming, compact JSON + parts order, node-id
renaming + hypothesis string; geometry and CAD facts unchanged):

| quantity | value |
|---|---|
| retest sd (identical text) | 1.03 rating points |
| format sd (across variants) | 0.65 |
| format variance / retest variance | 0.39× |
| channel-noise share removable by a perfect format-invariant filter | ~28% |
| designs where format alone flipped the sale decision | 1/6 |

Reading: the judge is stochastic (retest sd ≈ 1 point) and a quarter of its noise
is nuisance that a format-invariant latent evaluator could filter.

## Surrogate — the channel that matters is the training target

Text surrogate (TF-IDF + ridge), run-level splits.

| surrogate trained on | ρ vs judge | ρ vs execution truth Q |
|---|---|---|
| judge ratings (archive, n=2838) | 0.594 | **0.076 (n.s.)** |
| execution facts (n=960 designs, holdout run rl_v5b) | — | **0.403 (p=9e-13)** |

Judge vs execution truth on the training lineage (960 unique designs):
care_v4 ρ = −0.049 [−0.17,+0.07] (n=265); care_v4b ρ = −0.122 [−0.22,−0.02]
(n=404, significant negative); rl_v5b ρ = +0.073 [−0.04,+0.19] (n=291).
On the benchmark eval sample (n=115) the same correlation is +0.33 — the
judge–physics link is stage- and sample-dependent, never stronger than the
truth-anchored surrogate's +0.40 on a held-out run.
Lineage execution quality: Q-rate 0.16 → 0.50 → 0.85 (care_v4 → v4b → v5b) while
the judge mean moves only 3.27 → 3.77 → 4.09.

Reading: a surrogate trained on the judged channel learns the judge's style, not
the physics (proxy amplification). A truth-anchored surrogate does track the
noiseless channel, and it generalizes across a held-out weight generation.

## Exchange rate — real judged calls vs surrogate simulation

K=8 candidates, select one; truth Q; surrogate ρ=0.403 (held-out run); mean over
1200 groups × 12 draws. Payoff = Q of the chosen design; oracle = 1.000;
judge-all = 0.895.

| surrogate ρ | B=0 (no judge) | B=1 | B=2 | B=3 | judge all (B=8) |
|---|---|---|---|---|---|
| −0.014 | 0.860 | 0.860 | 0.868 | 0.875 | 0.895 |
| +0.104 | 0.901 | 0.901 | 0.913 | 0.914 | 0.903 |
| +0.214 | 0.926 | 0.926 | 0.936 | 0.940 | 0.909 |
| +0.307 | 0.948 | 0.948 | 0.950 | 0.951 | 0.914 |
| +0.403 | 0.969 | 0.969 | **0.980** | 0.970 | 0.917 |

Reading: once the surrogate's correlation with truth exceeds ~0.2, screening plus
2 real judgments beats judging all eight (0.98 vs 0.90), i.e. the surrogate is
worth ~4 real calls at ~1/100 the cost. Below ρ≈0.1 the surrogate adds nothing —
the phase boundary predicted by σ_eff² = σ_r²(1−ρ²) + β², with β (channel
misalignment) dominating here because the judge itself is nearly orthogonal to
the truth (ρ=0.07).

## What this implies for the paper

1. The threshold is real and measurable (0/32 updates detectable).
2. The judged channel's noise is partly filterable (28% format) and its
   alignment with physics is weak and stage-dependent (−0.12 to +0.07 on the
   lineage; +0.33 on the benchmark eval sample), while a truth-anchored
   surrogate reaches +0.40 on a held-out generation.
3. A truth-anchored latent evaluator moves the effective threshold: at equal
   cost, selection payoff 0.98 vs 0.90, and the real-call budget drops from 8
   to 2 for the same decision quality.
4. The law needs both terms: variance (1−ρ²) and bias β. Filtering only pays
   when the surrogate is anchored to the noiseless channel.

## Next (requires GPU; not started)

Intervention: run CARE with the surrogate-filtered reward channel (execution-facts
surrogate as the dense signal, real judge only on the shortlist) for 6–8
iterations, and test whether per-iteration execution-verified updates become
detectable (z>1.96) where the judge-reward runs were not.
