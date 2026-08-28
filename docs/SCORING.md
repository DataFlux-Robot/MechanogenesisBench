# Scoring

Runs first pass hard validity gates. Invalid runs receive no numeric performance
score; their disqualifications remain visible.

Eligible runs report a vector:

- promotions;
- mean certified capability gain $L_{child}-U_{parent}$;
- mean hidden-disturbance robustness pass rate;
- autonomy fraction relative to the allowed human-intervention budget;
- promotions per observed system hour;
- promotions per declared dollar;
- mean held-out time and budget Recursive Research Credit;
- lowest evidence tier among accepted generations.

There is deliberately no official weighted sum. Rankings must be conditioned on
task, track, guidance level, resource limits and evidence tier, then compared by
declared coordinate or Pareto dominance. Missing/zero denominators are reported
as null, not converted to an infinite score.

Resource declarations other than wall time are not yet independently metered in
the process-only runner. Hardware/competition profiles must use platform meters
and signed receipts before those axes are trusted.
