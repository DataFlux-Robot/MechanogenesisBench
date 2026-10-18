#!/usr/bin/env python3
"""Pre-registered sweet-spot probe (screening stage).

Surrogate family: label y_a = (1-a)*Q + a*(R/10), a in [0,1]. Q = execution-gated
truth (desk fit AND zero self-intersections AND reuse), R = recorded judge rating.
a=0 is truth-anchored; a=1 is judge-trained. Training: care_v4+care_v4b (>=600
unique designs); test: rl_v5b (held out). Capacity/regularization variants as in
paper/protocols/sweetspot.md.

Screening: K=8, screen by y_a, judge top B with the recorded rating, select the
best judged. Payoff on two targets: T_physics = selected Q, T_market = selected R.
"""
import glob, json, random
import numpy as np
from scipy.sparse import hstack, csr_matrix
from scipy.stats import spearmanr
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import Ridge

BENCH = '/home/exuber/CODE/CORE/pythonProject1/AUTORESEARCH/MechanogenesisBench-upstream'
A_GRID = [round(i * 0.1, 1) for i in range(11)]
CAPS = [(5000, 2.0, 'cap5k_a2'), (40000, 2.0, 'cap40k_a2'), (40000, 10.0, 'cap40k_a10')]
K, GROUPS, REPEATS = 8, 4000, 3
BS = [0, 2, 3, 4, 8]


def load():
    facts = [json.loads(l) for l in open(f'{BENCH}/runs/probes/facts_from_rollouts.jsonl')]
    facts = [r for r in facts if r.get('valid')]
    seen, u = set(), []
    for r in facts:
        if r['text'] in seen:
            continue
        seen.add(r['text']); u.append(r)
    ratings = {}
    for f in glob.glob(f'{BENCH}/runs/*/rollouts.jsonl'):
        for line in open(f):
            x = json.loads(line)
            t = x.get('text') or ''
            if len(t) >= 40:
                ratings.setdefault(t, x['rw'].get('rating', 0))
    for r in u:
        r['R'] = ratings.get(r['text'])
        r['Q'] = 1.0 if (r['excess'] <= 1.0 and r['overlap'] <= 50.0) else 0.0
    u = [r for r in u if r['R'] is not None]
    return u


def feats(text):
    try:
        d = json.loads(text); n = d.get('nodes', []); p = d.get('parts', [])
        return [len(n), len(p), sum(1 for x in n if x.get('op') == 'capital'),
                sum(1 for x in n if x.get('op') == 'union'),
                sum(1 for x in n if x.get('op') == 'difference'), len(text)]
    except Exception:
        return [0, 0, 0, 0, 0, len(text)]


def train_surrogate(rows, a, max_features, alpha):
    vec = TfidfVectorizer(analyzer='char_wb', ngram_range=(2, 4), min_df=3,
                          max_features=max_features, sublinear_tf=True)
    X = vec.fit_transform([r['text'] for r in rows])
    X = hstack([X, csr_matrix(np.array([feats(r['text']) for r in rows], float))]).tocsr()
    y = np.array([(1 - a) * r['Q'] + a * (r['R'] / 10.0) for r in rows])
    return vec, Ridge(alpha=alpha).fit(X, y)


def predict(model, texts):
    vec, reg = model
    X = vec.transform(texts)
    X = hstack([X, csr_matrix(np.array([feats(t) for t in texts], float))]).tocsr()
    return reg.predict(X)


def screening(score, Q, R, b, seed):
    rng = random.Random(seed)
    phys, mkt = [], []
    order_nan = np.nan_to_num(R, nan=-1e9)
    for _ in range(GROUPS):
        idx = rng.sample(range(len(Q)), K)
        ss, qq, rr = score[idx], Q[idx], R[idx]
        order = list(np.argsort(-ss))
        if b <= 1:
            pick = order[0]
        else:
            cand = order[:b] if b < K else order
            pick = cand[int(np.argmax(order_nan[idx][cand]))]
        phys.append(qq[pick]); mkt.append(rr[pick])
    return float(np.mean(phys)), float(np.mean(mkt))


def main():
    rows = load()
    train = [r for r in rows if r['run'] != 'rl_v5b']
    test = [r for r in rows if r['run'] == 'rl_v5b']
    print(f'[data] train={len(train)} test={len(test)} | Q rate {np.mean([r["Q"] for r in test]):.2f} | '
          f'judge mean {np.mean([r["R"] for r in test]):.2f}')
    Q = np.array([r['Q'] for r in test]); R = np.array([r['R'] for r in test], float)
    out = {'protocol': 'paper/protocols/sweetspot.md', 'test_n': len(test),
           'a_grid': A_GRID, 'BS': BS, 'variants': {}}
    print('\n== screening payoff vs a ==')
    for cap, alpha, name in CAPS:
        var = {'rho_Q': {}, 'rho_R': {}, 'curves': {}}
        print(f'\n-- variant {name}')
        print(f"{'a':>4} {'rhoQ':>6} {'rhoR':>6} | " + ' '.join(f'B{b}:phys/mkt' for b in BS))
        for a in A_GRID:
            model = train_surrogate(train, a, cap, alpha)
            s = predict(model, [r['text'] for r in test])
            rq = spearmanr(s, Q)[0]; rr = spearmanr(s, R)[0]
            var['rho_Q'][a] = round(float(rq), 3); var['rho_R'][a] = round(float(rr), 3)
            row = {}
            for b in BS:
                pm = [screening(s, Q, R, b, 1000 * i + b) for i in range(REPEATS)]
                ph = float(np.mean([x[0] for x in pm])); mk = float(np.mean([x[1] for x in pm]))
                row[b] = {'phys': round(ph, 4), 'mkt': round(mk, 3)}
            var['curves'][a] = row
            print(f'{a:4.1f} {rq:+6.3f} {rr:+6.3f} | ' +
                  ' '.join(f'{row[b]["phys"]:.3f}/{row[b]["mkt"]:.2f}' for b in BS))
        out['variants'][name] = var
        # peak locations per B/target
        print('  peaks:', {f'B{b}': {
            'phys': max(A_GRID, key=lambda x: var['curves'][x][b]['phys']),
            'mkt': max(A_GRID, key=lambda x: var['curves'][x][b]['mkt'])}
            for b in BS})
    json.dump(out, open(f'{BENCH}/runs/probes/sweetspot_screening.json', 'w'), indent=2)
    print('\nsaved runs/probes/sweetspot_screening.json')


if __name__ == '__main__':
    main()
