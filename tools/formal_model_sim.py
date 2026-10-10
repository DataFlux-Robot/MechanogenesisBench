#!/usr/bin/env python3
"""Minimal formal model of substrate-vs-weight self-improvement: 3-panel figure.

Model (see paper §Formal Model):
  P1 substrate monotonicity: verified-only acceptance => V_S(n) = c * Binomial(n, p)
     is monotone in expectation, linear dose-response.
  P2 weight-update threshold: E[dF] = eta*||g||^2 - (eta^2 sigma^2 L)/2; observed
     improvement is masked by evaluation noise sigma_eval whenever the signal term
     is below the noise term -> capability threshold.
  P3 memory instance-binding: replay gain ~ s_bar * p (s_bar = train-test overlap);
     weights transfer with retention r_w independent of s.
Empirical overlays: library dose-response (0/3/6/12/19 -> 150/600/750/750/900),
JitRL threshold points (V0-Self -54%, V1.0 +5%), probe replay (+3% n.s.).
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import natstyle
natstyle.activate()
from natstyle import BLUE, ORANGE, GREEN, RED, PURPLE, GRAY, INK, panel, clean, mm
import matplotlib.pyplot as plt
import numpy as np

FIG = Path(__file__).resolve().parent.parent / 'paper' / 'figures'
FIG.mkdir(parents=True, exist_ok=True)
rng = np.random.default_rng(42)

fig, axes = plt.subplots(1, 3, figsize=(mm(183), mm(62)))

# ── P1: dose-response ──
ax = axes[0]
n = np.arange(0, 20)
p_dose = 0.55
trials = 4000
curves = rng.binomial(n[:, None], p_dose, (len(n), trials)) * 50.0  # c=50 Y per asset
mean, lo, hi = curves.mean(1), np.percentile(curves, 10, 1), np.percentile(curves, 90, 1)
ax.plot(n, mean, color=BLUE, lw=2, label='model $c\\cdot n\\hat p$')
ax.fill_between(n, lo, hi, color=BLUE, alpha=0.18, label='10–90 pct (P1)')
dose = [0, 3, 6, 12, 19]
prof = [150, 600, 750, 750, 900]
ax.scatter(dose, prof, color=RED, zorder=5, s=45, label='observed (3 seeds)')
ax.set_xlabel('substrate (library) size $n$')
ax.set_ylabel('production profit (¥ / 12 rounds)')
ax.set_title('substrate accumulation is monotone')
panel(ax, 'a'); clean(ax)
ax.legend(fontsize=6.2)
ax.spines[['top', 'right']].set_visible(False)

# ── P2: capability threshold ──
ax = axes[1]
snr = np.linspace(0.02, 2.0, 200)          # ||g||^2 / (sigma^2 L), relative
eta = 0.5
improve = eta * snr - eta**2 / 2            # expected relative gain (signal - shrink)
noise_floor = 0.16                          # eval noise (probe sd/mean of trained model)
trials = 2000
obs = improve[:, None] + rng.normal(0, noise_floor, (len(snr), trials))
ax.plot(snr, improve, color=BLUE, lw=2, label='expected gain')
ax.fill_between(snr, np.percentile(obs, 10, 1), np.percentile(obs, 90, 1),
                color='#D8DBDE', alpha=0.35, label='evaluation noise (10–90 pct)')
ax.axhline(0, color='k', lw=0.6)
# empirical anchors: V0-Self (below threshold), V1.0+JitRL (above)
ax.scatter([0.35], [-0.54], color=RED, zorder=5, s=55, marker='x')
ax.annotate('V0-Self +JitRL\n(observed −54%)', (0.35, -0.54), textcoords='offset points',
            xytext=(8, -4), fontsize=6.2, color=RED)
ax.scatter([1.15], [0.05], color=GREEN, zorder=5, s=55, marker='o')
ax.annotate('V1.0 +JitRL\n(observed +5%, p=0.037)', (1.15, 0.05), textcoords='offset points',
            xytext=(8, 6), fontsize=6.2, color=GREEN)
ax.set_xlabel('signal-to-noise ratio $\\|g\\|^2/(\\sigma^2 L)$')
ax.set_ylabel('relative gain')
ax.set_title('weight updates need SNR above threshold')
panel(ax, 'b'); clean(ax)
ax.legend(fontsize=6.2, loc='upper left')
ax.spines[['top', 'right']].set_visible(False)

# ── P3: memory transfer vs overlap ──
ax = axes[2]
s = np.linspace(0, 1, 100)
gain_mem = 0.13 * s                          # replay gain (on-distribution +13%)
gain_w = np.full_like(s, 0.0)                # weights already in the gain; show retention instead
ax.plot(s, gain_mem * 100, color=BLUE, lw=2, label='memory gain $\\propto \\bar s$ (P3)')
ax.plot(s, np.full_like(s, 65.0), color=PURPLE, lw=2, ls='--',
        label='weights retention (65%, s-independent)')
ax.scatter([1.0], [13.0], color=BLUE, zorder=5, s=45)
ax.annotate('standard bench\n(observed +13%)', (1.0, 13), textcoords='offset points',
            xytext=(-86, 4), fontsize=6.2)
ax.scatter([0.08], [4.3], color=RED, zorder=5, s=45)
ax.annotate('sealed probes\n(observed +4%, n.s.)', (0.08, 4.3), textcoords='offset points',
            xytext=(10, -2), fontsize=6.2, color=RED)
ax.set_xlabel('train–test instance overlap $\\bar s$')
ax.set_ylabel('gain / retention (%)')
ax.set_title('memory is instance-bound, weights transfer')
panel(ax, 'c'); clean(ax)
ax.legend(fontsize=6.2, loc='center left')
ax.spines[['top', 'right']].set_visible(False)

plt.tight_layout(w_pad=1.5)
out = FIG / 'formal_model.png'
plt.savefig(out, dpi=200)
print(f'saved {out}')
