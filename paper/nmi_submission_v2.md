# The information sweet spot of surrogate-assisted self-improvement

Working draft v0 (law-centric rewrite; supersedes the substrate-first manuscript `nmi_submission.md`, kept for reference). Numbers marked [E1]/[E2]/[E4] refer to `runs/probes/REPORT.md`; [pending] marks results still running.

## Abstract (draft)

Self-improvement in machine-making models is often framed as an algorithm question. We show that it is an evaluation question: what an update can achieve is set by the signal-to-noise ratio of the channel that scores it, and how much of that channel a learned surrogate may replace is set by an information trade-off with an interior optimum. Three laws, measured on an execution-grounded economic benchmark and replicated on a second physical substrate: (i) at practitioner sample budgets no single weight update clears its own evaluation noise (0/32 updates detectable; detectability arrives as phase transitions), (ii) a surrogate with correlation rho to the truth is worth 1/(1-rho^2) effective samples and replaces real evaluation until its bias dominates, and (iii) decision payoff is an inverted U in the surrogate's information: a minimal sufficient statistic — knowing the target, not the channel's nuisance — is optimal, while full imitation of a noisy judge collapses both physical quality and market income. The mixed surrogate at a=0.75 matches the judge-trained system's market income (335 vs 350, p=0.70) while nearly doubling demand-faithful execution income (470 vs 250, p<1e-4). We connect the law to information bottleneck, rational inattention and the Kalman gain, and give a decision rule: market as objective, execution as audit, surrogates only for screening with a validated exchange rate.

## 1. Introduction

- RSI question; the CEO metaphor (can't know nothing, can't know everything).
- Contribution: three laws + two substrates + theory + prescription.
- [TODO] positioning vs self-training literature, reward hacking, information bottleneck.

## 2. Instruments

- Money Bench: 5-round cumulative CAD, build123d execution, three-vendor judge, speed pricing, capital registry; hard execution ruler (fit AND zero self-intersections AND reuse).
- Robot Bench: simulated MicroDuck, 8-parameter body design, MuJoCo acceptance (stand + forward), frozen precision policy; continuous execution score.
- [E2] both substrates; robot judge ratings compressed (8.09 +/- 0.28) and uncorrelated with physics (rho=-0.12).

## 3. Law 1 — the threshold

- [E1] 6 CARE lineages, 32 single updates: 0/32 detectable at |z|>1.96 (mean |z| 0.65); budget k=1->6 raises |z| 0.27->0.65.
- Phase transitions: 1/5 steps detectable (z 3.2-5.1); cumulative drift is detectable, per-step drift is not.
- [E2] robot domain: same structure at the evaluation layer.
- Formal anchor: P2, E[dF] = eta||g||^2 - eta^2 sigma^2 L/2, masked by sigma_eval.

## 4. Law 2 — noise structure and channel alignment

- [E1] judge retest sd 1.03; format-perturbation sd 0.65 (~28% of channel noise filterable); 1/6 designs flip their sale on format alone.
- [E1] three-vendor decomposition: within-design sd 1.08 = 28% of between-design signal; vendor offsets <=0.10; judge-judge rho 0.73-0.77.
- Judge-truth alignment: -0.12 to +0.07 on the lineage, +0.33 on the benchmark eval sample; -0.12 in the robot domain. Alignment, not variance, dominates.
- [E1] CARE-v4 head-to-head: judged ordering reverses under an independent panel (¥390 vs ¥495, p=0.043) while the execution ruler favours the same policy 750 vs 315 (p=2e-5).

## 5. Law 3 — the exchange rate

- Model: sigma_eff^2 = sigma_r^2 (1-rho^2) + beta^2.
- [E1] screening K=8: surrogate rho=0.40 + 2 real calls -> 0.980 vs judging all eight 0.895; below rho~0.1 the surrogate adds nothing (measured phase boundary).
- Corollary: a judge-trained surrogate (rho=0.59 with the judge, 0.08 with the truth) adds nothing; a truth-anchored surrogate reaches 0.40 on a held-out generation.
- [E2] when the surrogate is near-perfect (LOO rho=0.958), real verification adds nothing; the value is cost (32 designs x ~50 s of physics vs ms).

## 6. Law 4 — the information sweet spot

- Surrogate family y_a = (1-a) Q + a (R/10); a controls judge information.
- [E1] screening: rho_Q peaks at a=0.4 (0.436 vs 0.402 at a=0 and -0.14 at a=1); physics payoff peaks at a*=0.2 (B=0) and a*=0.5 (B=2): 0.981 vs 0.978/0.846.
- [E1/E4] reward usage (n=30 for the headline cells): a=0.75 market 335 (median 300) vs judge-trained 350 (300), p=0.70; hard ruler 94/150 vs 50/150 (470 vs 250), p<1e-4. a=1 collapses (180, 7/50); a=0 is physics-best but market-weaker (285, 50/50).
- [E2] robot domain: with an uninformative judge, the sweet point sits at a=0 — the boundary of the law.
- Theory: information bottleneck (minimal sufficient statistic), rational inattention, Kalman gain; [TODO] proposition and proof in SI.

## 7. Boundary conditions

- Soft ruler saturation (every trained arm 50/50 fit) vs the hard ruler (17/50-50/50); the ruler determines what is visible.
- Direct optimization of a surrogate can collapse (composite arms: 0 and 105 market; schema collapse without repair).
- Geometry-only training loses market income from SFT (285 vs 390) — alignment matters.
- Judge prompt construction controls the judge's variance (robot domain, compressed ratings).

## 8. Prescription and system

- Two-factor division of labour: weights cross the threshold once; substrates compound.
- Screening deployment: surrogate screens, real evaluations verify the shortlist (cost reduction).
- [E4] V2.1 system single-judge n=30: 545 (median 555) vs V2 436, p=0.0032; three-judge [pending] at n=20 was 534 vs the frontier 433 (p=0.0010).
- Decision rule: market = objective, hard ruler = audit, surrogate = screening only when the exchange rate is validated.

## 9. Relationship to prior theory (real-world anchors)

- Management: information overload, delegation.
- Economics: rational inattention (Sims).
- Control: Kalman gain as the explicit sweet point.
- Neuroscience: efficient coding.
- ML: Goodhart/reward hacking, information bottleneck, JEPA/world models.

## Methods (draft skeleton)

- Benchmark protocol; hard ruler definition; judge panels; probe protocols (P1-P5); surrogate construction (TF-IDF+ridge, LOO); exchange-rate simulation; reward-usage arms; robot-domain worker; statistics (Mann-Whitney, bootstrap, n per cell); pre-registration (`paper/protocols/sweetspot.md`).

## Figures (planned)

1. Two instruments (CAD + robot).
2. Threshold surface (0/32, budget, phase transitions).
3. Noise decomposition and judge audit.
4. Exchange rate + sweet spot (inverted U, a*).
5. System and screening deployment + hard ruler.
6. Boundary conditions / exploitability.

## Open items

- [pending] three-judge V2.1 n=30 recompute.
- [TODO] SI propositions and proofs (IB sweet point theorem).
- [TODO] figure generation for the new law figures.
- [TODO] extended discussion and limitations (no human eval, 9B only, two domains).
