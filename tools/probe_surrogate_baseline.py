#!/usr/bin/env python3
"""Surrogate baseline for the exchange-rate law probe.

Goal: estimate, from archived data only, how much of the expensive channel a cheap
text surrogate can reproduce.
  (a) surrogate-of-judge: predict the judge rating from the design text; rho =
      Spearman vs held-out judge ratings, beta = mean signed bias.
  (b) surrogate-of-truth: predict execution facts (envelope excess, overlap) from
      text; rho vs the noiseless CAD measurement.
Splits are by RUN (not by design) so style leakage cannot inflate rho.

Baseline model: TF-IDF char n-grams + structural features -> ridge.
"""
import glob, json, re
import numpy as np
from scipy.sparse import hstack, csr_matrix
from scipy.stats import spearmanr
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import Ridge

BENCH = '/home/exuber/CODE/CORE/pythonProject1/AUTORESEARCH/MechanogenesisBench-upstream'
HOLDOUT_RUNS = {'care_v4b', 'rl_v5b'}


def struct_feats(text):
    try:
        d = json.loads(text)
        nodes = d.get('nodes', [])
        parts = d.get('parts', [])
        cap = sum(1 for n in nodes if n.get('op') == 'capital')
        ops = {}
        for n in nodes:
            ops[n.get('op')] = ops.get(n.get('op'), 0) + 1
        return [len(nodes), len(parts), cap, len(ops), len(text),
                ops.get('union', 0), ops.get('difference', 0), ops.get('transform', 0)]
    except Exception:
        return [0, 0, 0, 0, len(text), 0, 0, 0]


def load_rollouts():
    rows = []
    for f in sorted(glob.glob(f'{BENCH}/runs/*/rollouts.jsonl')):
        tag = f.split('/')[-2]
        for line in open(f):
            r = json.loads(line)
            txt = r.get('text') or ''
            if len(txt) < 40:
                continue
            rows.append({'tag': tag, 'text': txt, 'rating': r['rw'].get('rating', 0),
                         'valid': bool(r['rw'].get('valid'))})
    return rows


def load_facts():
    rows = []
    for f in sorted(glob.glob(f'{BENCH}/runs/local_model_eval/*/r*_a*/cad/_job_in.json')):
        jo = f.replace('_job_in.json', '_job_out.json')
        try:
            m = json.loads(open(jo).read()).get('metrics') or {}
            txt = json.loads(open(f).read())['text']
            if m:
                rows.append({'text': txt,
                             'excess': float(m.get('occupied_envelope_excess_mm', 0) or 0),
                             'overlap': float(m.get('overlap_mm3', 0) or 0),
                             'session': f.split('/')[-4]})
        except Exception:
            continue
    # dedupe by text
    seen, out = set(), []
    for r in rows:
        if r['text'] in seen:
            continue
        seen.add(r['text']); out.append(r)
    return out


def fit_eval(rows, ykey, label):
    train = [r for r in rows if r['tag'] not in HOLDOUT_RUNS]
    test = [r for r in rows if r['tag'] in HOLDOUT_RUNS]
    vec = TfidfVectorizer(analyzer='char_wb', ngram_range=(2, 4), min_df=3,
                          max_features=40000, sublinear_tf=True)
    Xtr_txt = vec.fit_transform([r['text'] for r in train])
    Xte_txt = vec.transform([r['text'] for r in test])
    Xtr = hstack([Xtr_txt, csr_matrix(np.array([struct_feats(r['text']) for r in train], dtype=float))]).tocsr()
    Xte = hstack([Xte_txt, csr_matrix(np.array([struct_feats(r['text']) for r in test], dtype=float))]).tocsr()
    y = np.array([r[ykey] for r in train], dtype=float)
    model = Ridge(alpha=2.0).fit(Xtr, y)
    pred = model.predict(Xte)
    yt = np.array([r[ykey] for r in test], dtype=float)
    rho, p = spearmanr(pred, yt)
    beta = float(np.mean(pred - yt))
    resid = float(np.std(pred - yt))
    print(f'[{label}] train={len(train)} test={len(test)} | Spearman rho={rho:.3f} '
          f'(p={p:.2g}) | bias beta={beta:+.3f} | resid sd={resid:.3f}')
    return {'rho': float(rho), 'beta': beta, 'resid_sd': resid,
            'n_train': len(train), 'n_test': len(test)}


def main():
    rows = load_rollouts()
    print(f'[data] rollout designs with ratings: {len(rows)}')
    res = {'judge_surrogate': fit_eval(rows, 'rating', 'surrogate-of-judge')}

    facts = load_facts()
    print(f'[data] archived execution-fact pairs: {len(facts)}')
    # split facts by session name parity to keep sessions intact
    tr = [r | {'tag': 'train'} for r in facts if int(re.search(r'(\d+)$', r['session']).group(1)) % 2 == 0]
    te = [r | {'tag': 'test'} for r in facts if int(re.search(r'(\d+)$', r['session']).group(1)) % 2 == 1]
    # reuse fit_eval by mapping the tag trick: holdout = 'test'
    global HOLDOUT_RUNS
    HOLDOUT_RUNS = {'test'}
    res['facts_excess'] = fit_eval(tr + te, 'excess', 'surrogate-of-envelope')
    res['facts_overlap'] = fit_eval(tr + te, 'overlap', 'surrogate-of-overlap')
    out = f'{BENCH}/runs/probes/surrogate_baseline.json'
    import os
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(res, open(out, 'w'), indent=2)
    print('[saved]', out)


if __name__ == '__main__':
    main()
