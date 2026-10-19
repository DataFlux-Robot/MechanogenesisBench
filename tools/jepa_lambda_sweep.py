#!/usr/bin/env python3
"""JEPA invariance-weight sweep: the representation-level sweet spot.

Reuses the cached Qwen3.5-9B embeddings and the JEPA-Anything model from
tools/jepa_probe.py; sweeps the readout-consistency weight lambda and reports
rho_Q, format shifts, and the screening peak.
"""
import json, sys
import numpy as np
import torch
import torch.nn.functional as F
from scipy.stats import spearmanr

sys.path.insert(0, '/home/exuber/CODE/CORE/pythonProject1/AUTORESEARCH/MechanogenesisBench-upstream/tools')
from jepa_probe import (load_designs, perturb, perturb2, embed, Encoder, Readout,
                        BENCH, DEVICE, HOLDOUT)
from jepa_anything_core import (OrthogonalFactorProjection, MLPPredictor,
                                factor_prediction_loss, factor_activity_loss,
                                projector_orthogonality_loss, ema_update)

LAMBDAS = [0.0, 0.05, 0.1, 0.2, 0.5, 1.0]
EPOCHS = 40


def train_eval(E_tr, E_te, P_tr, P2_tr, P_te, P2_te, y_tr, y_te, lam):
    torch.manual_seed(7)
    enc = Encoder(E_tr.shape[1]).to(DEVICE)
    tgt = Encoder(E_tr.shape[1]).to(DEVICE)
    tgt.load_state_dict(enc.state_dict())
    for p in tgt.parameters():
        p.requires_grad = False
    predictor = MLPPredictor(256, 256, 512, depth=2).to(DEVICE)
    opf = OrthogonalFactorProjection(state_dim=256, num_factors=4, factor_dim=64,
                                     learnable=True).to(DEVICE)
    readout = Readout().to(DEVICE)
    params = (list(enc.parameters()) + list(predictor.parameters())
              + list(opf.parameters()) + list(readout.parameters()))
    opt = torch.optim.AdamW(params, lr=1e-3, weight_decay=1e-4)
    n = len(E_tr)
    for epoch in range(EPOCHS):
        perm = torch.randperm(n)
        for i in range(0, n, 64):
            idx = perm[i:i + 64]
            x = E_tr[idx].to(DEVICE); xp = P_tr[idx].to(DEVICE); xp2 = P2_tr[idx].to(DEVICE)
            y = y_tr[idx].to(DEVICE)
            zc = enc(x); zc2 = enc(xp2)
            with torch.no_grad():
                zt = tgt(xp); zt2 = tgt(xp2)
            pred = predictor(zc)
            loss = (factor_prediction_loss(opf(pred), opf(zt))
                    + 0.5 * factor_prediction_loss(opf(predictor(zc2)), opf(zt2))
                    + 0.1 * projector_orthogonality_loss(opf.analysis_basis())
                    + 0.1 * factor_activity_loss(opf(zc), min_std=0.1)
                    + 0.5 * F.mse_loss(readout(zc), y))
            if lam > 0:
                loss = loss + lam * F.mse_loss(readout(zc2), readout(zc).detach())
            opt.zero_grad(); loss.backward(); opt.step()
            ema_update(tgt, enc, 0.996)
    with torch.no_grad():
        pred_te = readout(enc(E_te.to(DEVICE))).cpu()
        pred_p = readout(enc(P_te.to(DEVICE))).cpu()
        pred_p2 = readout(enc(P2_te.to(DEVICE))).cpu()
    q = pred_te[:, 0].numpy(); qp = pred_p[:, 0].numpy(); qp2 = pred_p2[:, 0].numpy()
    q_true = y_te[:, 0].numpy()
    rho = spearmanr(q, q_true)[0]
    return float(rho), float(np.mean(np.abs(qp - q))), float(np.mean(np.abs(qp2 - q)))


def main():
    global test
    designs = load_designs()
    train = [r for r in designs if r['run'] != HOLDOUT]
    test = [r for r in designs if r['run'] == HOLDOUT]
    E_tr = embed([r['text'] for r in train]); E_te = embed([r['text'] for r in test])
    P_tr = embed([perturb(r['text']) for r in train])
    P_te = embed([perturb(r['text']) for r in test])
    P2_tr = embed([perturb2(r['text']) for r in train]); P2_te = embed([perturb2(r['text']) for r in test])
    y_tr = torch.tensor([[r['Q'], r['R'] / 10.0] for r in train], dtype=torch.float32)
    y_te = torch.tensor([[r['Q'], r['R'] / 10.0] for r in test], dtype=torch.float32)
    out = {}
    print(f"{'lambda':>6} {'rho_Q':>6} {'shift1':>7} {'shift2':>7}")
    for lam in LAMBDAS:
        rho, s1, s2 = train_eval(E_tr, E_te, P_tr, P2_tr, P_te, P2_te, y_tr, y_te, lam)
        out[lam] = {'rho_q': round(rho, 3), 'shift1': round(s1, 3), 'shift2': round(s2, 3)}
        print(f'{lam:6.2f} {rho:6.3f} {s1:7.3f} {s2:7.3f}', flush=True)
    json.dump(out, open(BENCH / 'runs/probes/jepa_lambda_sweep.json', 'w'), indent=2)
    print('saved runs/probes/jepa_lambda_sweep.json')


if __name__ == '__main__':
    main()
