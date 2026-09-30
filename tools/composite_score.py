#!/usr/bin/env python3
"""Composite score for MechanogenesisBench runs (executable methodology).

Practice followed (cf. Artificial Analysis Intelligence Index): aggregate graded
0-100 component scores across runs and tasks. Every component is a NATIVE rate
or threshold-attainment already defined by the task evaluator — there are no
free weights and no model-dependent anchors; inside a run and across tasks the
aggregation is a plain arithmetic mean. Runs that never reached evaluation
(system_failed on the model side) score 0; transport-side failures are excluded
only with a failure-log justification passed via --exclude.

Components:
  successor_operator_chain (3):
    promotion_rate            = promotions / generations
    robustness_rate           = holdout robustness pass rate
    inheritance_attainment    = min(inheritance_advantage / gate, 1), gate = 500 um
  demand_driven_microfactory (5):
    promotion_rate            = promotions / generations
    robustness_rate
    calibration_accuracy      = 1 - L1 calibration error / 1e6
    update_gain_attainment    = min(update_gain / gate, 1), gate = 400000 ppm
    lineage_exactness         = 1 if exact operator inheritance verified

Task score = mean(run scores) * 100. Composite = mean(task scores).
"""
import argparse
import json
from pathlib import Path

SUCCESSOR_GATE_UM = 500.0
DEMAND_UPDATE_GATE_PPM = 400000.0


def _load(run):
    run = Path(run)
    score = json.loads((run / 'score.json').read_text())
    evaluation = json.loads((run / 'evaluation.json').read_text())
    run_meta = json.loads((run / 'run.json').read_text())
    return run_meta, score, evaluation


def successor_components(score):
    promotions = score.get('promotions', 0)
    generations = 2
    gain = score.get('capability_gain') or 0.0
    return {
        'promotion_rate': promotions / generations,
        'robustness_rate': score.get('robustness_pass_rate') or 0.0,
        'inheritance_attainment': min(gain / SUCCESSOR_GATE_UM, 1.0),
    }


def demand_components(score, evaluation):
    promotions = score.get('promotions', 0)
    metrics = evaluation.get('microfactory_metrics', {})
    gens = metrics.get('generations', [{}])
    err = min((g.get('demand_calibration_error_ppm') or 1e6) for g in gens) if gens else 1e6
    gain = metrics.get('demand_update_gain_ppm') or 0
    exact = bool(metrics.get('exact_operator_inheritance'))
    return {
        'promotion_rate': promotions / 2,
        'robustness_rate': score.get('robustness_pass_rate') or 0.0,
        'calibration_accuracy': max(0.0, 1.0 - err / 1e6),
        'update_gain_attainment': min(gain / DEMAND_UPDATE_GATE_PPM, 1.0),
        'lineage_exactness': 1.0 if exact else 0.0,
    }


def run_score(run, task_id):
    try:
        run_meta, score, evaluation = _load(run)
    except FileNotFoundError:
        return 0.0, {'reason': 'no evaluation outputs (system_failed) -> 0'}
    if run_meta.get('status') != 'complete' or not score.get('eligible'):
        comps = {'promotion_rate': 0.0, 'robustness_rate': 0.0}
        return 0.0, comps
    comps = (successor_components(score) if 'successor' in task_id
             else demand_components(score, evaluation))
    return sum(comps.values()) / len(comps), comps


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runs', nargs='+', required=True, help='run directories')
    parser.add_argument('--exclude', nargs='*', default=[],
                        help='runs excluded for transport-side failures (must appear in the failure log)')
    args = parser.parse_args()
    excluded = set(args.exclude)
    tasks = {}
    for run in args.runs:
        run = Path(run)
        if run.name in excluded:
            continue
        task_id = json.loads((run / 'run.json').read_text())['task_id']
        value, comps = run_score(run, task_id)
        tasks.setdefault(task_id, []).append((run.name, value, comps))
    composite, rows = [], []
    for task_id, entries in sorted(tasks.items()):
        task_score = sum(v for _, v, _ in entries) / len(entries) * 100
        composite.append(task_score)
        rows.append((task_id, task_score, entries))
    print('| Task | Runs | Task score | Components (per run) |')
    print('|---|---|---|---|')
    for task_id, task_score, entries in rows:
        detail = '; '.join(f'{name}={v*100:.1f}' for name, v, _ in entries)
        print(f'| {task_id} | {len(entries)} | **{task_score:.1f}** | {detail} |')
    overall = sum(composite) / len(composite) if composite else 0.0
    print(f'\nComposite score: **{overall:.1f}** over {len(composite)} task(s), '
          f'{sum(len(e) for _, _, e in rows)} scored runs, {len(excluded)} excluded (transport).')


if __name__ == '__main__':
    main()
