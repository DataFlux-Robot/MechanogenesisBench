#!/usr/bin/env python3
"""Truth-anchored surrogate probe.

Once execution facts exist for archived rollouts (build_facts_dataset.py), train
a text surrogate on the NOISELESS channel (desk-fit + overlap) instead of the
judge, then ask the exchange-rate question again:

  rho(surrogate, Q) vs rho(judge, Q) on a held-out RUN
  selection: K candidates -> policies (random / surrogate / judge / hybrid)

Q = execution-gated quality (valid, within desk footprint, bounded overlap).
Ratings are joined from the rollout archive by design text.
"""
import glob, json, random
import numpy as np
from scipy.sparse import hstack, csr_matrix
from scipy.stats import spearmanr
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import Ridge

BENCH = '/home/exuber/CODE/CORE/pythonProject1/AUTORESEARCH/MechanogenesisBench-upstream'
FACTS = f'{BENCH}/runs/probes/facts_from_rollouts.jsonl'
HOLDOUT = 'rl_v5b'          # leave-one-run-out test
K, GROUPS = 8, 4000
C_R, C_S = 1.0, 0.01
OVERLAP_MAX = 50.0


def load_facts():
    rows = [json.loads(l) for l in open(FACTS)]
    rows = [r for r in rows if r.get('valid')]
    # dedupe by text, keep first
    seen, out = set(), []
    for r in rows:
        if r['text'] in seen:
            continue
        seen.add(r['text']); out.append(r)
    return out


def load_ratings():
    m = {}
    for f in sorted(glob.glob(f'{BENCH}/runs/*/rollouts.jsonl')):
        for line in open(f):
            r = json.loads(line)
            t = r.get('text') or ''
            if len(t) >= 40:
                m.setdefault(t, r['rw'].get('rating', 0))
    return m


def struct_feats(text):
    try:
        d = json.loads(text)
        nodes, parts = d.get('nodes', []), d.get('parts', [])
        return [len(nodes), len(parts),
                sum(1 for n in nodes if n.get('op') == 'capital'),
                sum(1 for n in nodes if n.get('op') == 'union'),
                sum(1 for n in nodes if n.get('op') == 'difference'),
                len(text)]
    except Exception:
        return [0, 0, 0, 0, 0, len(text)]


def main():
    facts = load_facts()
    ratings = load_ratings()
    for r in facts:
        r['Q'] = 1.0 if (r['excess'] <= 1.0 and r['overlap'] <= OVERLAP_MAX) else 0.0
        r['rating'] = ratings.get(r['text'], None)
    n_q = len(facts)
    print(f'[facts] {n_q} unique valid designs; Q rate={np.mean([r["Q"] for r in facts]):.2f}; '
          f'with rating={sum(1 for r in facts if r["rating"] is not None)}')

    train = [r for r in facts if r['run'] != HOLDOUT]
    test = [r for r in facts if r['run'] == HOLDOUT]
    print(f'[split] train={len(train)} ({sorted({r["run"] for r in train})}) '
          f'test={len(test)} ({HOLDOUT})')

    vec = TfidfVectorizer(analyzer='char_wb', ngram_range=(2, 4), min_df=3,
                          max_features=40000, sublinear_tf=True)
    Xtr = vec.fit_transform([r['text'] for r in train])
    Xtr = hstack([Xtr, csr_matrix(np.array([struct_feats(r['text']) for r in train], float))]).tocsr()
    Xte = vec.transform([r['text'] for r in test])
    Xte = hstack([Xte, csr_matrix(np.array([struct_feats(r['text']) for r in test], float))]).tocsr()
    model = Ridge(alpha=2.0).fit(Xtr, np.array([r['Q'] for r in train], float))
    pred = model.predict(Xte)

    q = np.array([r['Q'] for r in test], float)
    j = np.array([r['rating'] for r in test], float)
    has_j = ~np.isnan(j)
    rho_s = spearmanr(pred, q)
    rho_j = spearmanr(j[has_j], q[has_j])
    print(f'[heldout] surrogate vs Q: rho={rho_s[0]:.3f} (p={rho_s[1]:.2g})')
    print(f'[heldout] judge vs Q:     rho={rho_j[0]:.3f} (p={rho_j[1]:.2g})  (n={has_j.sum()})')

    # exchange-rate sim on the held-out run
    rng = random.Random(5)
    res = []
    for n_r in [0, 1, 2, 3, 4, 8]:
        picks = []
        for _ in range(GROUPS):
            idx = rng.sample(range(len(test)), K)
            qq, jj, ss = q[idx], j[idx], pred[idx]
            if n_r == 0:
                ch = int(np.argmax(ss))
            elif n_r >= K:
                ch = int(np.argmax(np.nan_to_num(jj, nan=-1e9)))
            else:
                short = list(np.argsort(-ss)[:n_r])
                ch = short[int(np.argmax(np.nan_to_num(jj[short], nan=-1e9)))]
            picks.append(qq[ch])
        res.append({'n_real': n_r, 'cost': K*C_S + n_r*C_R, 'mean_Q': float(np.mean(picks))})
        print(f"n_real={n_r} cost={K*C_S+n_r*C_R:.2f} | Q={np.mean(picks):.3f}")

    json.dump({'rho_surrogate_Q': float(rho_s[0]), 'rho_judge_Q': float(rho_j[0]),
               'n_train': len(train), 'n_test': len(test), 'holdout': HOLDOUT,
               'curve': res}, open(f'{BENCH}/runs/probes/exchange_rate_truth.json', 'w'), indent=2)
    print('saved runs/probes/exchange_rate_truth.json')


if __name__ == '__main__':
    main()
