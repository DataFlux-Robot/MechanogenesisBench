#!/usr/bin/env python3
"""Parametric demand generator for the workstation PRSI domain.

Each instance = a 5-round cumulative demand sequence following the canonical
structure (scratch dock -> dimension change -> add bay -> add second module ->
desk shrink) with sampled product family, dimensions, and desk sizes.

Two roles:
  - probe instances: SEALED, generated once with fixed seed, never used in training
  - train instances: fresh sample each generation (reduces instance overfitting)
"""
import json, random
from pathlib import Path

HERE = Path(__file__).resolve().parent

FAMILIES = [
    # (name, w_range, d_range, h_range) mm
    ('phone', (70, 95), (8, 16), (145, 185)),
    ('ereader', (120, 160), (7, 12), (180, 220)),
    ('powerbank', (95, 130), (20, 32), (60, 90)),
    ('portable console', (170, 220), (12, 22), (80, 110)),
]
BAYS = [
    ('earbuds bay', (55, 75), (40, 58), (22, 32)),
    ('cable tray', (80, 110), (45, 65), (18, 28)),
    ('spare battery slot', (90, 120), (50, 70), (25, 38)),
]
SECOND_MODULES = [
    ('tablet stand', (220, 270), (8, 14), (160, 185)),
    ('monitor riser block', (180, 240), (120, 180), (60, 90)),
    ('speaker shelf', (120, 160), (100, 140), (70, 100)),
]


def fmt(*vals):
    return 'x'.join(str(int(round(v))) for v in vals)


def gen_instance(rng):
    fam, (w0, w1), (d0, d1), (h0, h1) = rng.choice(FAMILIES)
    w, d, h = rng.uniform(w0, w1), rng.uniform(d0, d1), rng.uniform(h0, h1)
    dw, dd, dh = w * rng.uniform(1.08, 1.22), d * rng.uniform(1.05, 1.2), h * rng.uniform(1.04, 1.14)
    bay_name, (bw0, bw1), (bd0, bd1), (bh0, bh1) = rng.choice(BAYS)
    bw, bd, bh = rng.uniform(bw0, bw1), rng.uniform(bd0, bd1), rng.uniform(bh0, bh1)
    mod_name, (mw0, mw1), (md0, md1), (mh0, mh1) = rng.choice(SECOND_MODULES)
    mw, md, mh = rng.uniform(mw0, mw1), rng.uniform(md0, md1), rng.uniform(mh0, mh1)
    desk_w = rng.uniform(380, 460)
    desk_d = rng.uniform(260, 320)
    small_w, small_d = desk_w * rng.uniform(0.68, 0.78), desk_d * rng.uniform(0.68, 0.78)
    return {
        'family': fam,
        'desk': (int(round(desk_w)), int(round(desk_d))),
        'demands': [
            f"Build a {fam} dock for a {fmt(w,d,h)}mm {fam}. Desk {int(round(desk_w))}x{int(round(desk_d))}mm. From scratch.",
            f"Customer upgraded to a {fmt(dw,dd,dh)}mm {fam}. Adapt the dock. MUST reuse the base from round 1.",
            f"Add an {bay_name} ({fmt(bw,bd,bh)}mm). MUST keep the adapted dock and add to it.",
            f"Add a {mod_name} ({fmt(mw,md,mh)}mm) behind. Combine all modules. MUST reuse dock+{bay_name.split()[0]}.",
            f"Desk shrank to {int(round(small_w))}x{int(round(small_d))}mm! Shrink but keep ALL functions. MUST optimize accumulated design.",
        ],
    }


def make_probe(n=20, seed=20261005):
    rng = random.Random(seed)
    return [gen_instance(rng) for _ in range(n)]


def sample_train(rng):
    return gen_instance(rng)


if __name__ == '__main__':
    out = HERE.parent / 'runs' / 'rsi_night'
    out.mkdir(parents=True, exist_ok=True)
    probe = make_probe()
    (out / 'probe_instances.json').write_text(json.dumps(probe, indent=2))
    print(f"sealed probe: {len(probe)} instances -> {out / 'probe_instances.json'}")
    rng = random.Random()
    demo = [sample_train(rng) for _ in range(3)]
    for i, inst in enumerate(demo):
        print(f"\ntrain sample {i+1} [{inst['family']}, desk {inst['desk'][0]}x{inst['desk'][1]}]:")
        for d in inst['demands']:
            print(f"  - {d[:100]}")
