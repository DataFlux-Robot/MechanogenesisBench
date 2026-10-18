# Pre-registered protocol — the information sweet spot of surrogate-assisted self-improvement

Status: written before running the sweep (2026-10-18). Any deviation to be reported in the paper.

## Question

Decision payoff as a function of the surrogate's information content: is there an
interior optimum (inverted U) — a minimal sufficient statistic that knows the
decision target and not the channel's nuisance — rather than monotone improvement
with more information?

## Surrogate family (one controlled axis)

For a ∈ {0, 0.1, …, 1.0}, train a text surrogate on the convex label

    y_a = (1 − a) · Q + a · (R / 10)

where Q is the execution-gated truth (desk fit AND zero self-intersections AND
reuse, from the CAD kernel) and R is the recorded judge rating (0–10). a = 0 is the
truth-anchored surrogate; a = 1 reproduces the judge-trained surrogate. Increasing
a adds information about the judged channel, which contains both demand signal
(useful) and judge nuisance (format/style/retest noise).

Model: TF-IDF char 2–4 grams (max_features ∈ {5k, 40k}) + structural features,
Ridge (alpha ∈ {2, 10}). Training set: care_v4 + care_v4b execution-facts dataset
(≥600 unique designs). Test set: rl_v5b (291 designs, held-out generation).
No design in the test set is used for training or model selection.

## Usages and metrics

1. Screening (decision aid): K = 8 candidates; screen all with the surrogate,
   evaluate the top B with the real judge (recorded rating), select the best
   judged. B ∈ {0, 1, 2, 3, 4, 8}. 4,000 random groups, 12 noise draws. Two
   decision targets:
   - **T_market**: the selected design's recorded judge rating;
   - **T_physics**: the selected design's execution quality Q.
2. Direct reward (separate stage): CARE training with the surrogate score as the
   reward (no judge calls), 6 iterations from SFT, n = 10 evaluation. Only run if
   the screening sweep shows an interior optimum.

## Predictions (falsifiable)

P1. ρ(y_a, Q) decreases and ρ(y_a, R) increases with a.
P2. Screening payoff on T_physics has an interior peak at a* < 1 (surrogates with
    a > a* inherit judge nuisance that is anti-aligned with physics).
P3. Screening payoff on T_market is monotone or peaks at higher a (the market
    target is the judge).
P4. Higher capacity shifts a* toward lower a (more capacity fits more nuisance).
P5. In the reward usage, payoff has an interior peak in a and the peak is lower
    than in screening (optimization pressure amplifies nuisance).

## Decision rule

The sweet-spot hypothesis is supported if P2 holds with a* inside (0, 1) and a
bootstrap 95% CI on the peak location excluding both endpoints, and if the
capacity sweep moves a* in the predicted direction. If no interior peak is found,
report a boundary result (monotone information value) and adjust the paper's
claim accordingly.

## Sample size and stopping

Sweep: 11 a-values × 2 capacities × 2 alphas × 6 B-values × 2 targets, 4,000
groups each (simulation; no early stopping). Reward stage: 4 a-values × 6
iterations × n=10 evaluation, fixed in advance; no optional stopping.
