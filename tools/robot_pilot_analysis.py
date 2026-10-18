#!/usr/bin/env python3
"""Analyze the robot-domain pilot: surrogate exchange rate + information sweet spot.

Reads runs/robot_bench/pilot_{i}.json (physical acceptance) and pilot_judge.json
(judge ratings). Execution score S is the continuous acceptance quality; the
surrogate predicts S (or the mixed label) from the 8 design parameters.
"""
import glob, json, random
import numpy as np
from scipy.stats import spearmanr
from sklearn.linear_model import Ridge

BENCH = '/home/exuber/CODE/CORE/pythonProject1/AUTORESEARCH/MechanogenesisBench-upstream'
KEYS = ['trunk_mass_scale', 'trunk_com_x_m', 'upper_leg_mass_scale', 'lower_leg_mass_scale',
        'head_mass_scale', 'hip_range_scale', 'knee_ankle_range_scale',
        'leg_range_center_shift_rad']
K, GROUPS = 8, 2000
BS = [0, 1, 2, 3, 4, 8]
A_GRID = [round(i * 0.1, 1) for i in range(11)]


def feats(d):
    x = np.array([d[k] for k in KEYS], float)
    return np.concatenate([x, x ** 2])


def exec_score(path):
    d = json.load(open(path))
    if d.get('status') != 'ok':
        return 0.0, None
    c = d['cases'][0]
    passed = c['passed'] / max(1, c['trials'])
    vx = c['meanVx']; xy = c['meanXyRmse']
    q = max(0.0, 1 - abs(vx - 0.1) / 0.1 - 0.5 * max(0.0, (xy - 0.088) / 0.008))
    return float(passed * min(1.0, q)), c


def screening(score, S, b, seed):
    rng = random.Random(seed)
    picks = []
    for _ in range(GROUPS):
        idx = rng.sample(range(len(S)), K)
        ss, yy = score[idx], S[idx]
        order = list(np.argsort(-ss))
        if b <= 1:
            pick = order[0]
        else:
            cand = order[:b] if b < K else order
            pick = cand[int(np.argmax(yy[cand]))]
        picks.append(yy[pick])
    return float(np.mean(picks))


def main():
    designs = json.load(open(f'{BENCH}/runs/robot_bench/pilot_designs.json'))
    S = []
    for i in range(len(designs)):
        s, _ = exec_score(f'{BENCH}/runs/robot_bench/pilot_{i}.json')
        S.append(s)
    S = np.array(S)
    print(f'designs: {len(designs)} | S mean {S.mean():.3f} sd {S.std():.3f} '
          f'range {S.min():.3f}-{S.max():.3f}')
    jd = json.load(open(f'{BENCH}/runs/robot_bench/pilot_judge.json'))
    ratings = {}
    for r in jd['rows']:
        if r['rating'] is not None:
            ratings.setdefault(r['i'], []).append(r['rating'])
    R = np.array([np.mean(ratings.get(i, [0])) for i in range(len(designs))])
    print(f'judge: mean {R.mean():.2f} sd {R.std():.2f} | with ratings {sum(1 for i in ratings)}/{len(designs)}')
    X = np.array([feats(d) for d in designs])
    rho_j = spearmanr(R, S)[0]
    print(f'judge vs execution S: rho={rho_j:+.3f}')

    # surrogate of S (LOO-ish: fit all, evaluate in-sample rho; small n, disclose)
    reg = Ridge(alpha=1.0).fit(X, S)
    pred = reg.predict(X)
    print(f'surrogate vs S (in-sample): rho={spearmanr(pred, S)[0]:+.3f}')
    out = {'n': len(designs), 'S_mean': float(S.mean()), 'judge_mean': float(R.mean()),
           'rho_judge_S': float(rho_j), 'rho_surrogate_S': float(spearmanr(pred, S)[0]),
           'curves': {}}
    print('\n== exchange rate (screen by surrogate, verify top-B with real rollouts) ==')
    for b in BS:
        vals = [screening(pred, S, b, 100 + i) for i in range(3)]
        print(f'  B={b}: payoff {np.mean(vals):.3f}')
        out['curves'][b] = float(np.mean(vals))

    print('\n== sweet spot (label mixing, in-sample fit; pilot only) ==')
    sweet = {}
    for a in A_GRID:
        y = (1 - a) * S + a * (R / 10.0)
        rg = Ridge(alpha=1.0).fit(X, y)
        p = rg.predict(X)
        vals = [screening(p, S, 2, 200 + i) for i in range(3)]
        sweet[a] = float(np.mean(vals))
        print(f'  a={a:.1f}: rho(y,S)={spearmanr(y,S)[0]:+.2f} | screening payoff {np.mean(vals):.3f}')
    out['sweet'] = sweet
    json.dump(out, open(f'{BENCH}/runs/robot_bench/pilot_analysis.json', 'w'), indent=2)
    print('saved runs/robot_bench/pilot_analysis.json')


if __name__ == '__main__':
    main()
