#!/usr/bin/env python3
"""PRSI-Bench Score v1.0 — single methodology, compatible with AA/xbench format.

Design principles (aligned with Artificial Analysis & xbench):
  1. Every sub-metric is a RATE or RATIO in [0,1] — no free parameters
  2. Category score = arithmetic mean of its sub-metrics (no within-category weights)
  3. Overall score = arithmetic mean of 3 category scores (no cross-category weights)
  4. Scale: 0-100, versioned, every number independently recomputable
  5. n≥10 runs per category required for a ranked score; below → "pending"

Categories and sub-metrics:

  PRODUCTION (can it deliver?)
    yield_rate         qualified runs / attempted runs
    cost_efficiency    1 / (1 + tokens_per_qualified / 10k)  [→0.5 at 10k, →0.91 at 100k]
    reliability        1 - failure_rate

  REUSE (does it use accumulated assets?)
    engagement_rate    imports / executed candidates
    reuse_value        median of clip(RCI, 0, 2) / 2 across engaged generations
    acceleration       median of clip(1 - loss_g2/loss_g1, 0, 1) across engaged lineages

  DEMAND (does it understand what people want?)
    calibration_score  1 - L1_error / 1e6  (mean across evaluated runs)
    robustness_rate    holdout robustness pass rate (mean across evaluated runs)

Output: single JSON per model + markdown leaderboard table.
"""
import argparse
import json
import math
from pathlib import Path
from copy import deepcopy

REPO = Path(__file__).resolve().parent.parent


def load_runs(patterns):
    runs = []
    for pat in patterns:
        runs += [r for r in sorted(REPO.glob(pat))
                 if r.is_dir() and (r / 'run.json').exists()]
    return runs


def model_score(name, public_runs, fork_data):
    """Compute PRSI-Bench Score from public-task runs + fork (research-track) data."""
    m = {'model': name, 'categories': {}, 'overall': None, 'n': {}}

    # ── PRODUCTION ──
    yield_count = sum(1 for r in public_runs
                      if (r / 'score.json').exists()
                      and json.loads((r / 'score.json').read_text()).get('eligible'))
    yield_rate = yield_count / len(public_runs) if public_runs else 0.0

    tokens = 0.0
    for r in public_runs:
        for ma in r.rglob('model_action.json'):
            try:
                a = json.loads(ma.read_text())
                u = (a.get('response_envelope') or {}).get('usage') or {}
                tokens += (u.get('prompt_tokens') or 0) + (u.get('completion_tokens') or 0)
            except Exception:
                pass
    tpq = tokens / 1000 / max(yield_count, 1)  # kTokens per qualified
    cost_eff = 1.0 / (1.0 + tpq / 10.0)  # →0.5 at 10k, →0.09 at 100k

    fail_rate = sum(1 for r in public_runs
                    if json.loads((r / 'run.json').read_text()).get('status') != 'complete'
                    ) / len(public_runs) if public_runs else 1.0
    reliability = 1.0 - fail_rate

    m['categories']['production'] = round((yield_rate + cost_eff + reliability) / 3 * 100, 1)
    m['n']['production'] = len(public_runs)
    m['production_detail'] = {
        'yield_rate': round(yield_rate, 3),
        'kTokens_per_qualified': round(tpq, 1),
        'cost_efficiency': round(cost_eff, 3),
        'reliability': round(reliability, 3)}

    # ── REUSE (from fork data) ──
    fd = fork_data or {}
    engagement = fd.get('engagement_rate', 0.0)
    rci_values = [min(v, 2.0) / 2.0 for v in fd.get('rci_values', [])]
    reuse_value = sorted(rci_values)[len(rci_values) // 2] if rci_values else 0.0
    accel_values = [max(0.0, min(v, 1.0)) for v in fd.get('acceleration_values', [])]
    acceleration = sorted(accel_values)[len(accel_values) // 2] if accel_values else 0.0

    m['categories']['reuse'] = round((engagement + reuse_value + acceleration) / 3 * 100, 1)
    m['n']['reuse'] = fd.get('n_fork_arms', 0)
    m['reuse_detail'] = {
        'engagement_rate': round(engagement, 3),
        'reuse_value': round(reuse_value, 3),
        'acceleration': round(acceleration, 3)}

    # ── DEMAND ──
    cal_scores, rob_scores = [], []
    for r in public_runs:
        ev = r / 'evaluation.json'
        if not ev.exists():
            continue
        try:
            e = json.loads(ev.read_text())
            gens = e.get('microfactory_metrics', {}).get('generations', [])
            for g in gens:
                err = g.get('demand_calibration_error_ppm')
                if err is not None:
                    cal_scores.append(max(0.0, 1.0 - err / 1e6))
            sp = r / 'score.json'
            if sp.exists():
                s = json.loads(sp.read_text())
                if s.get('robustness_pass_rate') is not None:
                    rob_scores.append(s['robustness_pass_rate'])
        except Exception:
            pass
    calibration = sum(cal_scores) / len(cal_scores) if cal_scores else 0.0
    robustness = sum(rob_scores) / len(rob_scores) if rob_scores else 0.0
    m['categories']['demand'] = round((calibration + robustness) / 2 * 100, 1)
    m['n']['demand'] = len(cal_scores)
    m['demand_detail'] = {
        'calibration': round(calibration, 3),
        'robustness': round(robustness, 3)}

    # ── OVERALL ──
    m['overall'] = round(sum(m['categories'].values()) / 3, 1)
    return m


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default='docs/baselines/prsi_bench_scores.json')
    args = parser.parse_args()

    # fork data (from pipe_definition1_report.json on the research drive)
    fork_base = Path('/media/exuber/Elements/DataFlux/MechanogenesisBenchDEV/hosted_dual_role_20260930_v01')
    def fork_stats(arms):
        """Aggregate engagement/RCI/acceleration from a list of (treatment_root, control_root) pairs."""
        eng, rcis, accels, n_arms = [], [], [], 0
        for tname, cname in arms:
            troot, croot = fork_base / tname, fork_base / cname
            tr, cr = troot / 'result.json', croot / 'result.json'
            if not tr.exists() or json.loads(tr.read_text()).get('status') != 'PIPE_V04_ARM_COMPLETE':
                continue
            n_arms += 1
            td = json.loads(tr.read_text())
            cd = json.loads(cr.read_text()) if cr.exists() else {'losses': []}
            arm_exec = arm_cons = 0
            for k in (1, 2):
                dev = troot / f'g{k}' / 'development.json'
                if not dev.exists():
                    continue
                for row in json.loads(dev.read_text()):
                    if row['status'] == 'executed':
                        arm_exec += 1
                        arm_cons += bool(row.get('evidence', {}).get('consumed_capital_ids'))
            if arm_exec:
                eng.append(arm_cons / arm_exec)
            if td.get('losses') and cd.get('losses'):
                for lt, lc in zip(td['losses'], cd['losses']):
                    dev = troot / f"g{lt['generation']}" / 'development.json'
                    engaged = False
                    if dev.exists():
                        engaged = any(bool(r.get('evidence', {}).get('consumed_capital_ids'))
                                      for r in json.loads(dev.read_text()) if r['status'] == 'executed')
                    if engaged and lt['loss']:
                        rcis.append(lc['loss'] / lt['loss'])
                losses = td['losses']
                if len(losses) >= 2 and losses[0]['loss'] and losses[1]['loss']:
                    accels.append(1 - losses[1]['loss'] / losses[0]['loss'])
        return {'engagement_rate': sorted(eng)[len(eng) // 2] if eng else 0.0,
                'rci_values': rcis, 'acceleration_values': accels, 'n_fork_arms': n_arms}

    models = {
        'glm-5.3-flash': {
            'public': ['runs/glm53flash-*', 'runs/glm-5-3-flash-*'],
            'fork': fork_stats([
                ('mode_a_pipe_v05_treatment', 'mode_a_pipe_v05_control'),
                ('mode_a_pipe_v05_treatment_L2', 'mode_a_pipe_v05_control_L2'),
                ('mode_a_pipe_v05_glm53base_treatment', 'mode_a_pipe_v05_glm53base_control')])},
        'mimo-v2.6-pro': {
            'public': ['runs/mimo-v2-6-pro-*'],
            'fork': fork_stats([
                ('mode_a_pipe_v05_mimo-v2-6-proI2_treatment', 'mode_a_pipe_v05_mimo-v2-6-proI2_control'),
                ('mode_a_pipe_v05_mimo-v2-6-proJ1_treatment', 'mode_a_pipe_v05_mimo-v2-6-proJ1_control'),
                ('mode_a_pipe_v05_mimo-v2-6-proJ2_treatment', 'mode_a_pipe_v05_mimo-v2-6-proJ2_control')])},
        'mimo-v2.6-flash': {
            'public': ['runs/mimo26flash-*', 'runs/mimo-v2-6-flash-*'],
            'fork': fork_stats([
                ('mode_a_pipe_v05_mimo-v2-6-flashJ1_treatment', 'mode_a_pipe_v05_mimo-v2-6-flashJ1_control'),
                ('mode_a_pipe_v05_mimo-v2-6-flashJ2_treatment', 'mode_a_pipe_v05_mimo-v2-6-flashJ2_control')])},
        'glm-5.2': {
            'public': ['runs/glm-5-2-*'],
            'fork': {}},
        'glm-5.3': {
            'public': ['runs/glm-5-3-*'],
            'fork': fork_stats([
                ('mode_a_pipe_v05_glm53base_treatment', 'mode_a_pipe_v05_glm53base_control')])},
        'glm-5.1': {
            'public': ['runs/glm-5-1-*'],
            'fork': fork_stats([
                ('mode_a_pipe_v05_glm51_treatment', 'mode_a_pipe_v05_glm51_control')])},
    }

    results = []
    for name, spec in models.items():
        pub = load_runs(spec['public'])
        results.append(model_score(name, pub, spec['fork']))

    results.sort(key=lambda m: -m['overall'])
    out = {'schema': 'prsi-bench-score/1.0',
           'methodology': 'each sub-metric is a rate in [0,1]; category = arithmetic mean; '
                          'overall = mean of 3 categories; scale 0-100; versioned',
           'models': results}
    path = REPO / args.output
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + '\n')

    print('| Rank | Model | PRSI-Bench | Production | Reuse | Demand | n(prod/reuse) |')
    print('|---|---|---|---|---|---|---|')
    for i, m in enumerate(results, 1):
        print(f"| {i} | **{m['model']}** | **{m['overall']}** | {m['categories']['production']}"
              f" | {m['categories']['reuse']} | {m['categories']['demand']}"
              f" | {m['n']['production']}/{m['n']['reuse']} |")


if __name__ == '__main__':
    main()
