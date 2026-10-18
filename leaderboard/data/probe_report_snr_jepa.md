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

## Intervention — filtered-channel training (2026-10-18)

Two arms trained with the truth-anchored surrogate as the dense reward (no judge
calls), real CAD as the hard gate. Recipe otherwise identical to the judge arm
(RISE+Reflect, lr 2e-5, k=6, 12-prompt env).

### Training-time execution quality Q (base prompts)

| arm | start | it1 | it2 | it3 | it4 | it5 | it6 | detectable steps |
|---|---|---|---|---|---|---|---|---|
| judge channel (care_v4/v4b) | SFT | 0.139 | 0.113 | 0.304 | 0.255 | 0.173 | 0.142 | 1/5 (it3) |
| surrogate channel (rl_v7_qs) | SFT | 0.139 | 0.278 | 0.667 | 0.694 | 0.889 | 0.917 | 1/5 (it3, z=3.16) |
| surrogate channel (rl_v6_q) | champion | 0.903 | 0.931 | 1.000 | 0.972 | 0.972 | 0.875 | 1/5 (it6 negative) |

The surrogate channel reaches Q=0.92 in 6 iterations from SFT where the judge
channel is still at 0.14 (it reaches 0.81 only after 8).

### Judged market and execution ruler (eval harness, single judge, v7 gate)

| arm | n | judge mean | median | exec fit |
|---|---|---|---|---|
| judge channel @6 iters (v4b/iter2) | 10 | **390** | 300 | 50/50 |
| surrogate channel from SFT @6 (v7qs/iter6) | 10 | **285** | 300 | 50/50 |
| surrogate channel from champion @+3 (v6q/iter3) | 10 | **420** | 450 | 50/50 |
| champion @12 (v4b/iter8, published) | 10 | 375 | 450 | 50/50 |
| CARE-v3 @6 (published) | 10 | 330 | 300 | 21/49 |

### What it means

1. **The eval execution ruler is saturated**: every trained arm scores 50/50 desk
   fit (¥750 execution-gated), so physics improvements beyond the ceiling are
   invisible on the priced market. The training-env Q advantage (0.14 vs 0.92)
   does not transfer to the five fixed demands.
2. **Channel alignment dominates channel noise.** A noiseless but incomplete
   channel (geometry only, no demand satisfaction) loses ~¥105 of market income
   when trained from scratch. From a judge-trained champion the same channel is
   non-inferior and +¥45 (n.s.) on the market with perfect physics.
3. The exchange-rate law needs the bias term: sigma_eff^2 = sigma_r^2(1-rho^2) +
   beta^2. Here beta (misalignment with the priced decision) is the dominant
   term, not sigma.

### Next design (not yet run)

Composite channel: reward = w * Q_phys + (1-w) * R_demand, where R_demand is the
judge-trained surrogate (rho=0.59 with the judge). Tests whether denoising the
market target (without dropping demand satisfaction) lifts judged profit at the
same sample budget. Also: harden the execution ruler (tighter desks/overlap) so
physics competence is not saturated and the market cannot ignore it.

### Hardened execution ruler (post-hoc, from existing eval artifacts)

The soft ruler (desk-fit only) saturates for every trained arm. The demands
themselves require more: a real dock must have no self-intersecting parts and
rounds 2-5 MUST reuse capital. Hard ruler: fit AND zero self-intersections AND
(reuse or round 1). Computed on the same archived eval sessions:

| arm | fit | clean | reuse | all three | hard-ruler ¥ |
|---|---|---|---|---|---|
| judge channel @6 (v4b/iter2) | 50/50 | 17/50 | 50/50 | 17/50 | 255 |
| surrogate channel from SFT @6 (v7qs/iter6) | 50/50 | **50/50** | 50/50 | **50/50** | **750** |
| surrogate channel from champion (v6q/iter3) | 50/50 | **50/50** | 50/50 | **50/50** | **750** |
| champion @12 (v4b/iter8) | 50/50 | 30/50 | 50/50 | 30/50 | 450 |
| CARE-v3 @6 | 21/50 | 5/50 | 49/50 | 4/50 | 60 |

Correction to the earlier reading: the execution channel is NOT saturated — the
soft ruler was. Under a demand-faithful ruler the surrogate channel dominates
(¥750 vs ¥255 for the same-budget judge arm, ¥450 for the champion, ¥60 for
CARE-v3). The judged market prices demand satisfaction and ignores geometric
cleanliness (champion 30/50 clean still earns ¥375-450), so the two rulers
diverge — which is exactly the channel-alignment term beta.

### Composite channel (wq=0.5) — negative result

Reward = 0.5 * predicted Q + 0.5 * predicted demand (judge surrogate), trained
6 iterations from SFT, no judge calls. Training looked healthy (Q 0.139 -> 0.806,
predicted demand 2.13 -> 6.56, one detectable step z=5.08 at it3), but:

| checkpoint | eval (n) | judge mean | hard ruler |
|---|---|---|---|
| iter4 | 2 | 225 | 3/5 per session |
| iter6 | 10 | **0** (all sessions) | 0/5 |

At eval temperature the iter6 policy's modal output is schema-invalid (duplicate
node ids, invalid part references): 10/10 sessions earn nothing. The hard CAD
gate during training did not prevent the modal collapse — the demand head's
preference for elaborate templates (more nodes, "compact_workstation") can be
exploited by structurally redundant output that the post-hoc validator rejects.
The earlier iter4 checkpoint is valid but underperforms the judge arm on both
rulers (225 vs 390 market; 6/10 hard rounds vs 17/50).

Lesson: a surrogate reward needs validity-preserving constraints (syntax repair
inside the rollout loop, or a validity-aware surrogate head), not just a hard gate
at reward time. The composite arm as configured is rejected.

### Fixed composite (repair + annealed wq) — still loses the market

Changes: syntax repair inside the rollout loop (duplicate ids renamed, cross-wired
input/inputs fixed, invalid parts dropped); wq annealed 0.25 -> 0.75; 6 iterations
from SFT. Training healthy (Q 0.125 -> 0.597, predicted demand 1.92 -> 4.49,
repair rate ~1%), no collapse. Evaluated with the same repair layer:

| checkpoint | n | judge mean | fit | clean | reuse | hard | hard ¥ |
|---|---|---|---|---|---|---|---|
| iter6 (repair) | 10 | **105** (median 150) | 47/50 | 34/50 | 48/50 | 31/50 | 465 |

The repair fixed the schema collapse and kept execution healthy, but the judged
market collapsed (105 vs 375-420 for judge-trained arms). The policy optimizes
the surrogate pair into a region where the real judge rates 1-4: the demand
surrogate (rho=0.59 on held-out) is exploitable under direct optimization.

### Final matrix (eval n=10, single judge, v7 gate; hard ruler = fit & clean & reuse)

| arm | reward channel | judge ¥ | hard ruler |
|---|---|---|---|
| judge channel @6 | judge API | **390** | 17/50 (255) |
| champion @12 | judge API | 375 | 30/50 (450) |
| CARE-v3 @6 | judge API | 330 | 4/50 (60) |
| geometry surrogate @6 | Q surrogate | 285 | **50/50 (750)** |
| composite v1 it4 | 0.5 Q + 0.5 R | 225 | 6/10 |
| composite v1 it6 | 0.5 Q + 0.5 R | 0 (collapse) | 0/50 |
| composite v2 iter6 | annealed + repair | 105 | 31/50 (465) |

**No surrogate arm wins both rulers.** The judged market preserves demand
satisfaction and ignores geometric cleanliness; the geometry channel does the
opposite. Direct optimization of either surrogate moves the policy along one
ruler at the cost of the other. The two channels are misaligned (rho ~ 0.07 on
the lineage), and a surrogate composite inherits exploitable bias rather than
resolving the misalignment.

Prescription for the paper: keep the judged market as the objective (it is what
is priced), keep the hard execution ruler as the audit, use surrogates only for
screening where their exchange rate is validated (rho > ~0.2, verified on held-out
generations), and never optimize a surrogate as the sole reward.

## E1 (pre-registered) — information sweet spot, screening stage

Protocol: `paper/protocols/sweetspot.md`. Surrogate family y_a = (1-a)Q + a(R/10),
a in [0,1]; train care_v4+v4b (669), test rl_v5b (291, held out); K=8, 4,000
groups x 3 repeats; two decision targets.

Key numbers (cap40k, alpha=2):

| a | rho_Q | rho_R | B=0 phys | B=2 phys | B=2 mkt |
|---|---|---|---|---|---|
| 0.0 | +0.402 | -0.362 | 0.975 | 0.978 | 3.98 |
| 0.2 | +0.420 | -0.272 | **0.978** | 0.979 | 4.31 |
| 0.4 | **+0.436** | -0.020 | 0.975 | 0.979 | 5.28 |
| 0.5 | +0.425 | +0.199 | 0.972 | **0.981** | 6.25 |
| 0.6 | +0.355 | +0.419 | 0.963 | 0.963 | 6.94 |
| 0.8 | +0.052 | +0.684 | 0.911 | 0.896 | 7.42 |
| 1.0 | -0.140 | +0.682 | 0.796 | 0.846 | 7.44 |

- **Interior peak confirmed for the physics target**: rho_Q peaks at a=0.4
  (0.436), screening payoff peaks at a*=0.2 (B=0) and a*=0.5 (B=2/3), both beating
  the pure-truth (a=0) and pure-judge (a=1) surrogates. The judge signal helps
  the surrogate until it starts to carry style nuisance.
- Market target peaks at a=0.8-0.9 (B=0-4), but judging all eight is still best
  (7.84): on its own target the judge is the truth; the surrogate only buys cost.
- Regularization alpha=10 keeps the physics peak at a*=0.5 (B=2-4) and lowers the
  overall fidelity; the capacity axis (5k vs 40k features) did not bind because
  the char n-gram vocabulary after min_df=3 is below 5k.
- Reward-usage sweep (a in {0.25,0.5,0.75,1.0}, 6 iters from SFT, n=10 evals) is
  running; pre-registered prediction P5: the reward-side peak sits lower than the
  screening peak because optimization pressure amplifies nuisance.

## E1 reward-usage sweep — the mixed surrogate dominates the judge channel

Arms trained from SFT, 6 iterations, mix-and-match label y_a = (1-a)Q + a(R/10)
as the sole reward (no judge calls), n=10 evaluation each.

| a | market ¥ (sd) | hard ruler rounds | hard ¥ (sd) |
|---|---|---|---|
| 0.00 (geometry) | 285 (111) | 50/50 | 750 (0) |
| 0.25 | 210 (105) | 36/50 | 540 (77) |
| 0.50 | 135 (111) | 40/50 | 600 (0) |
| **0.75** | **390 (105)** | **32/50** | **480 (95)** |
| 1.00 (judge surrogate) | 180 (63) | 7/50 | 105 (123) |
| judge-trained @6 (reference) | 390 (126) | 17/50 | 255 (72) |

Statistics (Mann-Whitney, n=10/arm):
- a=0.75 vs judge-trained: market p=0.90 (parity), hard revenue p<1e-4 (a=0.75
  better) — same market income with almost double the execution-ruler income.
- a=0.75 vs a=0: market p=0.059 (a=0.75 better), hard revenue favors a=0 (p=1.0).
- a=0.75 vs a=1.00: both p<1e-3 (a=0.75 better on market and hard ruler).

Reading: the reward-side sweet spot is at a≈0.75. Knowing a lot about the judge
(preserving demand information) without imitating its noise keeps market parity
and doubles physical quality; full imitation (a=1) collapses both. The
pre-registered P5 (reward-side peak lower than screening) is NOT supported — the
reward-side market peak sits higher (0.75 vs 0.5). Caveat: one training run per
a-value; the a-curve is not monotonically single-peaked (the 0.25/0.5 dip may be
training stochasticity).

## E2 robot-domain pilot — judge misalignment replicates; exchange-rate boundary

Second execution substrate: simulated MicroDuck, 32 random designs in an 8-parameter
numeric space (mass/inertia scaling, trunk COM, joint-range scales), forward-0.1 m/s
acceptance (3 seeds x 2 worlds), frozen precision policy. Execution score S is the
continuous acceptance quality (pass fraction x tracking quality).

| quantity | value |
|---|---|
| S (execution) | 0.764 +/- 0.088 (range 0.628-0.920) |
| judge rating | 8.09 +/- 0.28 (3 reps; highly compressed) |
| judge vs S | **rho = -0.121** |
| surrogate vs S (LOO) | **rho = 0.958, MAE 0.059** |
| exchange rate (screen 8, verify B) | payoff 0.888 (B=0) -> 0.891 (B=8), flat |
| sweet spot (label mixing) | monotone 0.891 (a=0) -> 0.841 (a=1); a*=0 |

Reading:
1. The judge-misalignment replicates in a second substrate: the LLM judge's ratings
   are uncorrelated (slightly negative) with the physics and carry almost no
   variance, so demand-style information is absent.
2. When the surrogate is near-perfect (rho=0.96), extra real verification adds
   nothing: the surrogate's value is the cost reduction (32 designs x ~50 s of
   physics vs milliseconds), not selection quality.
3. With an uninformative judge, the sweet point sits at a=0 (truth only) — an
   interior peak requires the judge to carry partial target-relevant signal.
   This is a boundary condition of the sweet-spot law, not a refutation.
Caveats: one demand (0.1 m/s), n=32, judge prompt may suppress variance (ratings
compressed); the 8-param space is smooth, so the surrogate's task is easy.

## E4 — headline cells extended to n=30

| arm | n | market ¥ (median) | hard ruler rounds | hard ¥ |
|---|---|---|---|---|
| a=0.75 (mixed surrogate) | 30 | 335 (300) | 94/150 | 470 |
| judge-trained @6 | 30 | 350 (300) | 50/150 | 250 |
| V2.1 system, single judge | 30 | 545 (555) | — | — |

Statistics: a=0.75 vs judge-trained market p=0.70 (parity), hard ruler p<1e-4
(94/150 vs 50/150 rounds). V2.1 single-judge n=30 mean 545 vs V2 (v7, n=20) 436,
p=0.0032. The n=10 point estimates moved (a=0.75 390->335, judge 390->350) but the
conclusion is unchanged: market parity, ~1.9x hard-ruler income for the mixed
surrogate. Three-judge recompute of the extended V2.1 sessions is running.

## E4 final — V2.1 n=30 across the three rulers

| ruler | n | V2.1 | reference |
|---|---|---|---|
| single judge | 30 | 545 (median 555) | V2 436, p=0.0032 |
| symmetric 3-judge | 30 | 531 (median 540; bounds 513-550) | frontier 433, p=0.0010, d=1.05 |
| execution-gated | 30 | 488 (median 500) | V2 443 (n=20) |

The n=20 figures (534 / 540 / 492) were reproduced within noise; the headline and
its significance are unchanged by the extension.
