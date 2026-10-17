#!/usr/bin/env python3
"""Exchange-rate probe: surrogate screening vs real judged sampling.

Task: from K candidate designs, select one to "build". Truth = execution-gated
quality Q (desk-fit and low overlap from the CAD kernel). The expensive channel
is the judge rating (one recorded draw per design); the cheap channel is a text
surrogate (TF-IDF+ridge trained on the rollout archive).

Policies swept over real-evaluation budget n_r:
  n_r=0      surrogate only (rank all K, take top)
  0<n_r<K    surrogate screens, then n_r candidates are judged for real
  n_r=K      judge everything (recorded ratings), no surrogate
Cost = K*c_s + n_r*c_r; payoff = Q of the chosen design (mean over random groups).
"""
import glob, json, random, re
import numpy as np
from scipy.sparse import hstack, csr_matrix
from scipy.stats import spearmanr
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import Ridge

BENCH = '/home/exuber/CODE/CORE/pythonProject1/AUTORESEARCH/MechanogenesisBench-upstream'
C_R, C_S = 1.0, 0.01     # one real judged evaluation vs one surrogate simulation
K, GROUPS = 8, 4000


def load_rollouts():
    rows = []
    for f in sorted(glob.glob(f'{BENCH}/runs/*/rollouts.jsonl')):
        for line in open(f):
            r = json.loads(line)
            t = r.get('text') or ''
            if len(t) >= 40:
                rows.append((t, r['rw'].get('rating', 0)))
    return rows


def struct_feats(text):
    try:
        d = json.loads(text)
        nodes, parts = d.get('nodes', []), d.get('parts', [])
        cap = sum(1 for n in nodes if n.get('op') == 'capital')
        return [len(nodes), len(parts), cap, len(text),
                sum(1 for n in nodes if n.get('op') == 'union'),
                sum(1 for n in nodes if n.get('op') == 'difference')]
    except Exception:
        return [0, 0, 0, len(text), 0, 0]


def main():
    train = load_rollouts()
    joined = json.load(open(f'{BENCH}/runs/probes/design_join.json'))
    print(f'train surrogate on {len(train)} rollout designs; evaluate selection on {len(joined)} joined designs')

    vec = TfidfVectorizer(analyzer='char_wb', ngram_range=(2, 4), min_df=3,
                          max_features=40000, sublinear_tf=True)
    Xtr = vec.fit_transform([t for t, _ in train])
    Xtr = hstack([Xtr, csr_matrix(np.array([struct_feats(t) for t, _ in train], float))]).tocsr()
    ytr = np.array([r for _, r in train], float)
    model = Ridge(alpha=2.0).fit(Xtr, ytr)

    Xj = vec.transform([r['text'] for r in joined])
    Xj = hstack([Xj, csr_matrix(np.array([struct_feats(r['text']) for r in joined], float))]).tocsr()
    s_pred = model.predict(Xj)
    y_judge = np.array([r['rating'] for r in joined], float)
    # truth: execution-gated quality (fit and no overlap)
    Q = np.array([1.0 if (r['excess'] <= 0.01 and r['overlap'] <= 50) else 0.0 for r in joined])
    rho, p = spearmanr(s_pred, y_judge)
    rho_q, p_q = spearmanr(s_pred, Q)
    print(f'surrogate vs judge on joined: rho={rho:.3f} (p={p:.2g})')
    print(f'surrogate vs execution-Q:     rho={rho_q:.3f} (p={p_q:.2g})')
    print(f'judge vs execution-Q:         rho={spearmanr(y_judge, Q)[0]:+.3f}')
    print(f'base rate Q: {Q.mean():.2f}')

    # random groups, policies
    rng = random.Random(11)
    res = []
    for n_r in [0, 1, 2, 3, 4, 8]:
        picks_q, oracle_q, hit = [], [], []
        for _ in range(GROUPS):
            idx = rng.sample(range(len(joined)), K)
            q = Q[idx]; j = y_judge[idx]; s = s_pred[idx]
            if n_r == 0:
                choose = int(np.argmax(s))
            elif n_r >= K:
                choose = int(np.argmax(j))
            else:
                short = list(np.argsort(-s)[:n_r])
                choose = short[int(np.argmax(j[short]))]
            picks_q.append(q[choose])
            oracle_q.append(q.max())
            hit.append(1.0 if q[choose] == q.max() else 0.0)
        res.append({'n_real': n_r, 'cost': K * C_S + n_r * C_R,
                    'mean_Q': float(np.mean(picks_q)), 'hit_best': float(np.mean(hit)),
                    'oracle_Q': float(np.mean(oracle_q))})
        print(f"n_real={n_r} cost={K*C_S+n_r*C_R:.2f} | Q={np.mean(picks_q):.3f} "
              f"| hit-best={np.mean(hit):.3f} (oracle Q={np.mean(oracle_q):.3f})")

    out = {'c_r': C_R, 'c_s': C_S, 'K': K, 'groups': GROUPS,
           'rho_surrogate_judge': float(rho), 'rho_surrogate_Q': float(rho_q),
           'base_rate_Q': float(Q.mean()), 'curve': res}
    json.dump(out, open(f'{BENCH}/runs/probes/exchange_rate.json', 'w'), indent=2)
    print('saved runs/probes/exchange_rate.json')


if __name__ == '__main__':
    main()
