#!/usr/bin/env python3
"""Phase 2 analysis: RSI arm vs matched-compute control on the sealed probe."""
import json, statistics, sys
from pathlib import Path
from math import erf

HERE = Path(__file__).resolve().parent.parent
OUT = HERE / 'runs' / 'rsi_night'


def mann_whitney(a, b):
    u = sum(1 for x in a for y in b if x > y) + 0.5 * sum(1 for x in a for y in b if x == y)
    n1, n2 = len(a), len(b)
    if n1 == 0 or n2 == 0:
        return float('nan'), float('nan')
    mu = n1 * n2 / 2
    sd = (n1 * n2 * (n1 + n2 + 1) / 12) ** 0.5
    z = (u - mu) / sd if sd else 0
    p = 2 * (1 - 0.5 * (1 + erf(abs(z) / 2 ** 0.5)))
    return z, p


def load(arm):
    """Aggregate across all seed dirs: <arm> (seed0), <arm>_s1, <arm>_s2 ..."""
    runs = []
    for d in sorted(OUT.glob(f'{arm}*')):
        if not d.is_dir():
            continue
        if d.name != arm and not d.name.startswith(arm + '_s'):
            continue
        try:
            probe = json.loads((d / 'probe_log.json').read_text())
            chain = json.loads((d / 'chain.json').read_text())
            recipes = json.loads((d / 'recipe_log.json').read_text()) if (d / 'recipe_log.json').exists() else []
            probe = [dict(x, seed=d.name) for x in probe]
            runs.append({'dir': d.name, 'probe': probe, 'chain': chain, 'recipes': recipes})
        except FileNotFoundError:
            continue
    return runs or None


def main():
    print('=' * 70)
    print('  OVERNIGHT RSI EXPERIMENT — SEALED PROBE TRAJECTORIES (all seeds)')
    print('=' * 70)
    pooled = {}
    for arm in ('rsi', 'control'):
        runs = load(arm)
        if not runs:
            print(f'\n[{arm}] no data'); continue
        pooled[arm] = runs
        for run in runs:
            probe = run['probe']
            accepted = [x for x in probe[1:] if x.get('accepted', True)]
            means = [x['mean'] for x in probe]
            print(f"\n[{arm} | {run['dir']}] " +
                  ' -> '.join(f"g{x['gen']}:¥{x['mean']:.0f}{'' if x.get('accepted', True) else '✗'}" for x in probe))
            if accepted:
                print(f'  baseline ¥{means[0]:.0f} -> last accepted ¥{accepted[-1]["mean"]:.0f} '
                      f'({(accepted[-1]["mean"]/max(means[0],1)-1)*100:+.0f}%)')
            if run['recipes'] and arm == 'rsi':
                for r in run['recipes'][1:]:
                    rec = r['recipe']
                    print(f"    g{r['gen']}: mix={ {k: round(rec[k],1) for k in ('draft','improve','debug')} } "
                          f"top_q={rec['top_q']:.2f} lr={rec['lr']:.1e}")

    a = [x['mean'] for run in pooled.get('rsi', []) for x in run['probe'][1:] if x.get('accepted', True)]
    b = [x['mean'] for run in pooled.get('control', []) for x in run['probe'][1:]]
    if a and b:
        z, p = mann_whitney(a, b)
        print(f'\nPOOLED RSI vs control (accepted gen probe means): '
              f'RSI n={len(a)} mean={statistics.mean(a):.0f} | control n={len(b)} mean={statistics.mean(b):.0f} '
              f'| Mann-Whitney z={z:.2f} p={p:.4f}')
    try:
        rej = json.loads((OUT / 'baseline_rejudge.json').read_text())
        print('\n3-judge symmetric baseline recompute:')
        for k, v in rej.items():
            print(f'  {k:20s} n={len(v):2d} mean=¥{statistics.mean(v):.0f} runs={[round(x) for x in v][:8]}...')
    except FileNotFoundError:
        pass


if __name__ == '__main__':
    main()
