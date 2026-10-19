# Theory note — the information sweet spot (propositions + fittable predictions)

Status: draft before the seed-replicated data arrive. The fits will be redone on
the 3-seed arms; the propositions are the paper's SI core.

## Setting

A designer must choose an action a (a design, an update, a candidate) to maximize
a decision-relevant target T (execution-verified quality; or the priced market
outcome). Two evaluation channels are available:

- a real channel E: cost c_r per evaluation, noise variance σ_r², bias β_r
  relative to T;
- a surrogate channel Z: cost c_s ≪ c_r, built from the observation X (the
  design text), with information I(Z;T) about the target and I(Z;N) about
  nuisance N (format, style, retest noise).

The surrogate share s ∈ [0,1] is the fraction of the decision that uses Z
(equivalently, in screening, the fraction of candidates not verified by E).

## Proposition 1 (minimal sufficient statistic, information bottleneck)

For a fixed budget of information about X, the decision payoff is maximized when
Z is a minimal sufficient statistic of T: it preserves I(Z;T) and discards as
much I(Z;N) as possible.

*Proof sketch.* By the data-processing inequality, any extra information about X
that is not about T cannot increase I(Z;T); it can only increase I(Z;N). Under
optimization pressure (the policy or the selection rule acts on Z), the error
directions of Z are searched, so nuisance information is not neutral: it is
converted into decision error at a rate proportional to the exploitable error
mass. Hence the optimal representation is the IB solution
argmin I(Z;X) − β I(Z;T) with β set by the decision stakes, not the
maximum-information representation.

Corollary: "knowing everything" is suboptimal not because information is
costly, but because the excess information is nuisance that the optimizer finds.

## Proposition 2 (bias floor and the interior sweet point)

Let the surrogate have correlation ρ with T and bias β_s (the part of its error
that no amount of simulation removes). With n real evaluations and N surrogate
evaluations, the effective error on T is

  σ_eff² = σ_r² (1 − ρ²) / N + β_s² .

The decision payoff decreases with σ_eff² and increases with the surrogate share
subject to cost. If β_s > 0 and the real channel is noisy, the payoff U(s) is
single-peaked, with

  ∂U/∂s = 0  at  s* = s*(I(Z;T), β_s, c_r/c_s),

where s* increases with I(Z;T) and c_r/c_s and decreases with β_s. In the
variance-limited regime (β_s = 0) the optimum is a corner (all surrogate); in the
bias-limited regime it is interior or all-real.

Corollary (sample equivalence): a surrogate with correlation ρ is worth
1/(1−ρ²) real samples per surrogate sample in the variance term. With
ρ = 0.4 this is 1.19×; the observed decision gain is larger because the real
channel also carries bias (the judge mispricing).

## Proposition 3 (reward vs screening)

When Z is used as a screening device and E selects among the shortlist, the
error of Z enters only through the ranking, and the bias of E is bounded by the
shortlist size. When Z is used as the reward, its error is optimized directly;
the exploitable error mass grows with the optimization pressure. Hence the
sweet point for the reward usage lies at a lower surrogate share than for
screening at the same ρ (the pre-registered P5).

## Fittable predictions

Reward usage (label mixing a = the share of judge information in the surrogate
label):

  U(a) = U0 + A (1 − e^{−a/τ}) − B a^γ ,

with U0 the pure-truth payoff, A/τ the saturation of useful judge information,
and B/γ the exploitable-nuisance term. Predictions: A, B > 0; the peak
a* = argmax U lies in (0,1); a* decreases when the judge's target-relevance
falls (robot domain with an uninformative judge: a* = 0); a* increases with the
judge's correlation with the target.

Screening usage (real budget B on the shortlist):

  P(B) = P_s + (P_r − P_s)(1 − e^{−B/λ}) − D (B/K)^κ ,

where P_s is the surrogate-only payoff, P_r the real-only payoff, and D the
pricing error of the real channel. Predictions: λ decreases with ρ; the interior
peak B* decreases with ρ (measured: 8 → 3 → 2 as ρ rises 0.1 → 0.4); when the
surrogate is near-perfect (ρ → 1), B* → 0 and the real channel adds only cost.

## What the experiments must show

1. Seed-replicated U(a) with 3 seeds per a: the peak a* must be inside (0,1) with
   a bootstrap CI excluding the endpoints (or the boundary result must be
   reported).
2. The robot domain with an informative judge: a* should move with the judge's
   target-relevance, testing the Proposition-2 dependence.
3. Screening B*(ρ): already measured in simulation; the paper reports the
   measured curve and the fitted λ(ρ).
4. JEPA representation: the invariance-weight sweep measures the
   invariance–fidelity frontier; the Proposition-1 prediction is that the
   decision payoff peaks at an interior invariance weight, not at maximum
   invariance.
