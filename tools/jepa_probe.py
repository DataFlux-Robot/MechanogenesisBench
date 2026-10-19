#!/usr/bin/env python3
"""JEPA-Anything probe: a latent predictive encoder for design evaluation.

Builds on Gen-Verse/JEPA-Anything (OPF factorization + EMA-target JEPA baseline).
Observation = frozen Qwen3.5-9B embedding of the design text; context view =
original design, target view = semantically identical format perturbation. The
predictor is trained in latent space (factor prediction) while readout heads
predict execution quality Q and the judge rating. Tests whether the JEPA-style
latent (i) tracks the noiseless channel better than the TF-IDF baseline and
(ii) is invariant to format nuisance.

Run: python tools/jepa_probe.py
"""
import glob, json, sys, time
import numpy as np
from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as F
from scipy.stats import spearmanr

sys.path.insert(0, '/home/exuber/CODE/CORE/pythonProject1/AUTORESEARCH/vendor/jepa-anything/jepa-anything-core/src')
from jepa_anything_core import (OrthogonalFactorProjection, MLPPredictor,
                                factor_prediction_loss, factor_activity_loss,
                                projector_orthogonality_loss, ema_update)

BENCH = Path('/home/exuber/CODE/CORE/pythonProject1/AUTORESEARCH/MechanogenesisBench-upstream')
BASE = '/home/exuber/models/qwen3.5-9b-bf16'
DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'
HOLDOUT = 'rl_v5b'


def load_designs():
    facts = [json.loads(l) for l in open(BENCH / 'runs/probes/facts_from_rollouts.jsonl')]
    facts = [r for r in facts if r.get('valid')]
    seen, u = set(), []
    for r in facts:
        if r['text'] in seen:
            continue
        seen.add(r['text']); u.append(r)
    ratings = {}
    for f in glob.glob(str(BENCH / 'runs/*/rollouts.jsonl')):
        for line in open(f):
            x = json.loads(line)
            t = x.get('text') or ''
            if len(t) >= 40:
                ratings.setdefault(t, x['rw'].get('rating', 0))
    for r in u:
        r['R'] = ratings.get(r['text'])
        r['Q'] = 1.0 if (r['excess'] <= 1.0 and r['overlap'] <= 50.0) else 0.0
    return [r for r in u if r['R'] is not None]


def perturb(text):
    """Semantically identical variant (part renaming + compact JSON + reordered parts)."""
    try:
        d = json.loads(text)
    except Exception:
        return text
    for i, p in enumerate(d.get('parts', [])):
        p['name'] = f'component_{chr(65 + i)}'
    d['parts'] = list(reversed(d.get('parts', [])))
    return json.dumps(d, ensure_ascii=False, separators=(',', ':'))


def perturb2(text):
    """Second nuisance view: node-id renaming + hypothesis change + re-indent."""
    try:
        d = json.loads(text)
    except Exception:
        return text
    mp = {}
    for i, n in enumerate(d.get('nodes', [])):
        old = n.get('id')
        if old:
            mp[old] = f'n{i:02d}'
    for n in d.get('nodes', []):
        if 'id' in n:
            n['id'] = mp.get(n['id'], n['id'])
        if 'inputs' in n:
            n['inputs'] = [mp.get(x, x) for x in n['inputs']]
        if 'input' in n:
            n['input'] = mp.get(n['input'], n['input'])
    for p in d.get('parts', []):
        if 'node' in p:
            p['node'] = mp.get(p['node'], p['node'])
    d['hypothesis'] = 'dock_variant_revision'
    return json.dumps(d, ensure_ascii=False, indent=2)


def embed(texts, batch=8, max_len=1024):
    from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
    cache = BENCH / 'runs/probes/jepa_emb.npz'
    import hashlib
    key = f'emb_{len(texts)}_{hashlib.md5(("|".join(texts[:3])).encode()).hexdigest()[:10]}'
    if cache.exists():
        z = np.load(cache)
        if key in z:
            print(f'[embed] cache hit {key}', flush=True)
            return torch.tensor(z[key])
    tok = AutoTokenizer.from_pretrained(BASE, trust_remote_code=True)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_type='nf4',
                             bnb_4bit_compute_dtype=torch.bfloat16,
                             bnb_4bit_use_double_quant=True)
    model = AutoModelForCausalLM.from_pretrained(BASE, quantization_config=bnb,
                                                 device_map='cuda', trust_remote_code=True)
    model.eval()
    out = []
    t0 = time.time()
    with torch.no_grad():
        for i in range(0, len(texts), batch):
            chunk = texts[i:i + batch]
            enc = tok(chunk, return_tensors='pt', padding=True, truncation=True,
                      max_length=max_len).to(model.device)
            hs = model(**enc, output_hidden_states=True).hidden_states[-1]
            mask = enc['attention_mask'].unsqueeze(-1).float()
            feats = (hs.float() * mask).sum(1) / mask.sum(1).clamp(min=1)
            out.append(feats.cpu())
            if i % 80 == 0:
                print(f'  embed {i}/{len(texts)} ({time.time()-t0:.0f}s)', flush=True)
    del model
    torch.cuda.empty_cache()
    feats = torch.cat(out)
    # persist embedding for reruns
    try:
        old = dict(np.load(cache)) if cache.exists() else {}
        old[key] = feats.numpy()
        np.savez_compressed(cache, **old)
    except Exception:
        pass
    return feats


class Encoder(nn.Module):
    def __init__(self, in_dim, d=256):
        super().__init__()
        self.net = nn.Sequential(nn.Linear(in_dim, 512), nn.GELU(),
                                 nn.LayerNorm(512), nn.Linear(512, d))

    def forward(self, x):
        return self.net(x)


class Readout(nn.Module):
    def __init__(self, d=256):
        super().__init__()
        self.head = nn.Sequential(nn.Linear(d, d // 2), nn.GELU(), nn.Linear(d // 2, 2))

    def forward(self, z):
        return self.head(z)


def main():
    designs = load_designs()
    train = [r for r in designs if r['run'] != HOLDOUT]
    test = [r for r in designs if r['run'] == HOLDOUT]
    print(f'[data] train={len(train)} test={len(test)}')
    t0 = time.time()
    E_tr = embed([r['text'] for r in train])
    E_te = embed([r['text'] for r in test])
    P_tr = embed([perturb(r['text']) for r in train])
    P2_tr = embed([perturb2(r['text']) for r in train])
    P2_te = embed([perturb2(r['text']) for r in test])
    print(f'[embed] done in {time.time()-t0:.0f}s', flush=True)
    y_tr = torch.tensor([[r['Q'], r['R'] / 10.0] for r in train], dtype=torch.float32)
    y_te = torch.tensor([[r['Q'], r['R'] / 10.0] for r in test], dtype=torch.float32)

    torch.manual_seed(7)
    enc = Encoder(E_tr.shape[1]).to(DEVICE)
    tgt_enc = Encoder(E_tr.shape[1]).to(DEVICE)
    tgt_enc.load_state_dict(enc.state_dict())
    for p in tgt_enc.parameters():
        p.requires_grad = False
    predictor = MLPPredictor(256, 256, 512, depth=2).to(DEVICE)
    opf = OrthogonalFactorProjection(state_dim=256, num_factors=4, factor_dim=64,
                                     learnable=True).to(DEVICE)
    readout = Readout().to(DEVICE)
    params = list(enc.parameters()) + list(predictor.parameters()) + \
        list(opf.parameters()) + list(readout.parameters())
    opt = torch.optim.AdamW(params, lr=1e-3, weight_decay=1e-4)

    n = len(train)
    for epoch in range(1, 61):
        perm = torch.randperm(n)
        tot = 0.0
        for i in range(0, n, 64):
            idx = perm[i:i + 64]
            x = E_tr[idx].to(DEVICE)
            xp = P_tr[idx].to(DEVICE)
            xp2 = P2_tr[idx].to(DEVICE)
            y = y_tr[idx].to(DEVICE)
            zc = enc(x)
            zc2 = enc(xp2)
            with torch.no_grad():
                zt = tgt_enc(xp)
                zt2 = tgt_enc(xp2)
            pred = predictor(zc)
            coords_c = opf(zc)
            coords_p = opf(pred)
            loss = (factor_prediction_loss(coords_p, opf(zt))
                    + 0.5 * factor_prediction_loss(opf(predictor(zc2)), opf(zt2))
                    + 0.1 * projector_orthogonality_loss(opf.analysis_basis())
                    + 0.1 * factor_activity_loss(coords_c, min_std=0.1)
                    + 0.5 * F.mse_loss(readout(zc), y)
                    + 0.2 * F.mse_loss(readout(zc2), readout(zc).detach()))
            opt.zero_grad(); loss.backward(); opt.step()
            ema_update(tgt_enc, enc, 0.996)
            tot += loss.item()
        if epoch % 10 == 0:
            print(f'  epoch {epoch}: loss {tot / max(1, (n + 63) // 64):.4f}', flush=True)

    with torch.no_grad():
        zc_te = enc(E_te.to(DEVICE))
        pred_te = readout(zc_te).cpu()
        zc_te_raw = zc_te.cpu()
        zp_dev = enc(embed([perturb(r['text']) for r in test]).to(DEVICE))
        pred_p = readout(zp_dev).cpu()
        zp_te = zp_dev.cpu()
        zp2_dev = enc(P2_te.to(DEVICE))
        pred_p2 = readout(zp2_dev).cpu()
    q_pred = pred_te[:, 0].numpy(); r_pred = pred_te[:, 1].numpy() * 10
    q_pred_p = pred_p[:, 0].numpy()
    q_pred_p2 = pred_p2[:, 0].numpy()
    jepa_shift = float(np.mean(np.abs(q_pred_p - q_pred)))
    jepa_shift2 = float(np.mean(np.abs(q_pred_p2 - q_pred)))
    q_true = y_te[:, 0].numpy(); r_true = y_te[:, 1].numpy() * 10
    rho_q = spearmanr(q_pred, q_true)[0]
    rho_r = spearmanr(r_pred, r_true)[0]
    inv = float((zc_te_raw - zp_te).norm(dim=1).mean())
    print(f'[result] JEPA surrogate vs Q: rho={rho_q:.3f}')
    print(f'[result] JEPA surrogate vs rating: rho={rho_r:.3f}')
    print(f'[result] format shift in latent space: {inv:.3f} | JEPA readout prediction shift: {jepa_shift:.3f} (view1) / {jepa_shift2:.3f} (view2)')
    np.savez_compressed(BENCH / 'runs/probes/jepa_preds.npz', q_pred=q_pred,
                        r_pred=r_pred, q_true=q_true, r_true=r_true,
                        test_texts=np.array([r['text'] for r in test]), test_run=np.array([r['run'] for r in test]))

    # ── TF-IDF baseline on the same split/labels ──
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import Ridge
    from scipy.sparse import hstack, csr_matrix

    def feats_tfidf(t):
        try:
            d = json.loads(t); n = d.get('nodes', []); p = d.get('parts', [])
            return [len(n), len(p), sum(1 for x in n if x.get('op') == 'capital'), len(t)]
        except Exception:
            return [0, 0, 0, len(t)]
    vec = TfidfVectorizer(analyzer='char_wb', ngram_range=(2, 4), min_df=3,
                          max_features=40000, sublinear_tf=True)
    Xtr = vec.fit_transform([r['text'] for r in train])
    Xtr = hstack([Xtr, csr_matrix(np.array([feats_tfidf(r['text']) for r in train], float))]).tocsr()
    Xte = vec.transform([r['text'] for r in test])
    Xte = hstack([Xte, csr_matrix(np.array([feats_tfidf(r['text']) for r in test], float))]).tocsr()
    base = Ridge(alpha=2.0).fit(Xtr, np.array([r['Q'] for r in train]))
    b_pred = base.predict(Xte)
    b_rho = spearmanr(b_pred, q_true)[0]
    Xp = vec.transform([perturb(r['text']) for r in test])
    Xp = hstack([Xp, csr_matrix(np.array([feats_tfidf(perturb(r['text'])) for r in test], float))]).tocsr()
    b_shift = float(np.mean(np.abs(base.predict(Xp) - b_pred)))
    print(f'[baseline] TF-IDF surrogate vs Q: rho={b_rho:.3f} | format prediction shift {b_shift:.3f}')

    # ── screening exchange rate for both surrogates ──
    import random
    DESK_ORDER = None
    K, GROUPS = 8, 2000
    Rvals = np.array([r['R'] for r in test], float)
    def screen(score, b, seed):
        rng = random.Random(seed); picks = []
        for _ in range(GROUPS):
            idx = rng.sample(range(len(q_true)), K)
            ss, yy, rr = score[idx], q_true[idx], Rvals[idx]
            order = list(np.argsort(-ss))
            if b <= 1:
                pick = order[0]
            else:
                cand = order[:b] if b < K else order
                pick = cand[int(np.argmax(rr[cand]))]
            picks.append(yy[pick])
        return float(np.mean(picks))
    curves = {}
    for name, sc in (('jepa', q_pred), ('tfidf', b_pred)):
        curves[name] = {b: round(np.mean([screen(sc, b, 300 + i) for i in range(3)]), 4)
                        for b in (0, 1, 2, 3, 4, 8)}
        print(f'[screen] {name}: ' + ' '.join(f'B{b} {v:.3f}' for b, v in curves[name].items()))
    json.dump({'n_train': len(train), 'n_test': len(test),
               'rho_q_jepa': float(rho_q), 'rho_r_jepa': float(rho_r),
               'rho_q_tfidf': float(b_rho),
               'format_shift_jepa_latent': inv, 'format_shift_jepa_pred': jepa_shift,
               'format_shift_jepa_pred2': jepa_shift2,
               'format_shift_tfidf_pred': b_shift,
               'screen': curves},
              open(BENCH / 'runs/probes/jepa_probe.json', 'w'), indent=2)
    print('saved runs/probes/jepa_probe.json')


if __name__ == '__main__':
    main()
