#!/usr/bin/env python3
"""Publication figures (Nature style) for nmi_draft_v2.
fig1 = HTML/CSS schematic rendered via headless chromium (see fig1.html).
This script produces figs 2-6; fig5 = formal_model.png (formal_model_sim.py).
"""
import json, sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import natstyle
natstyle.activate()
from natstyle import (BLUE, ORANGE, GREEN, RED, PURPLE, GRAY, INK, panel, clean, mm)
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
FIG = ROOT / 'paper' / 'figures'


def save(fig, name):
    fig.savefig(FIG / name, bbox_inches='tight', pad_inches=0.02)
    plt.close(fig)
    print('saved', name)


# ═══════ Fig 2: leaderboard (half-width portrait, 89 mm) ═══════
def fig2():
    rows = [
        ('FluxEidosV2 system', 532, 'sys'), ('mimo-v2.6-flash', 433, 'com'),
        ('mimo-v2.6-pro', 418, 'com'), ('FluxEidosV1.5 weights', 390, 'own'),
        ('V1.0 + JitRL mature', 390, 'sys'), ('FluxEidosV1.0', 387, 'own'),
        ('glm-5.3', 380, 'com'), ('mimo pro/flash (1-j)', 377, 'com'),
        ('FluxEidosV1.0 (1-j)', 372, 'own'), ('glm-5.3 (1-j)', 338, 'com'),
        ('V1.5a JitRL accum.', 345, 'sys'), ('FluxEidosV1.1', 330, 'own'),
        ('glm-5.3-flash', 311, 'com'), ('V0.5 (SFT only)', 260, 'own'),
        ('V1.2 (over-trained)', 255, 'own'), ('V1.0-D (rejected)', 216, 'own'),
        ('qwen3.5-27B zs', 213, 'zs'), ('V1.0-RSI (rejected)', 210, 'own'),
        ('gemma-4-12B zs', 200, 'zs'), ('JitRL control', 195, 'sys'),
        ('qwen3.8-27B zs', 190, 'zs'), ('deepseek-flash', 174, 'com'),
    ]
    colors = {'sys': PURPLE, 'own': BLUE, 'com': ORANGE, 'zs': GRAY}
    fig, ax = plt.subplots(figsize=(mm(89), mm(118)))
    y = np.arange(len(rows))[::-1]
    vals = [r[1] for r in rows]
    ax.hlines(y, 0, vals, color=[colors[r[2]] for r in rows], lw=1.1, alpha=0.45)
    ax.scatter(vals, y, s=16, c=[colors[r[2]] for r in rows], zorder=3, linewidths=0)
    for yi, r in zip(y, rows):
        ax.text(r[1] + 7, yi, str(r[1]), va='center', fontsize=5.8, color='#4A4E54')
    ax.axvline(433, color=INK, lw=0.7, ls=(0, (2, 2)))
    ax.text(437, len(rows) - 0.6, 'commercial\nfrontier', fontsize=5.8, color=INK, va='top')
    ax.set_yticks(y)
    ax.set_yticklabels([r[0] for r in rows], fontsize=6.0)
    ax.set_xlabel('profit per 5-round session (¥)')
    ax.set_xlim(0, 600)
    clean(ax, grid_axis='x')
    h = [plt.Line2D([], [], marker='o', ls='', color=colors[k], markersize=3.5, label=l)
         for k, l in [('sys', 'our system'), ('own', 'our weights'), ('com', 'commercial API'), ('zs', 'zero-shot')]]
    ax.legend(handles=h, loc='lower right', handletextpad=0.4, borderaxespad=0.2)
    panel(ax, 'a')
    save(fig, 'fig2_leaderboard.png')


# ═══════ Fig 3: three failures (full width 183 mm) ═══════
def fig3():
    fig, axes = plt.subplots(1, 3, figsize=(mm(183), mm(58)))
    # a — domain collapse
    ax = axes[0]
    doms = ['in-domain', 'fixture', 'layout']
    arms = [('mimo-v2.6-flash', [433, 124, 138], ORANGE), ('FluxEidosV1.5', [390, 0, 60], BLUE),
            ('FluxEidosV2', [532, 0, 264], PURPLE)]
    x, w = np.arange(3), 0.27
    for i, (k, v, c) in enumerate(arms):
        ax.bar(x + (i - 1) * w, v, w * 0.9, color=c, linewidth=0)
        for xi, vi in zip(x + (i - 1) * w, v):
            if vi > 0:
                ax.text(xi, vi + 12, f'{int(round(100 * vi / v[0]))}%', ha='center', fontsize=5.6, color='#4A4E54')
    ax.set_xticks(x); ax.set_xticklabels(doms, fontsize=6.2)
    ax.set_ylabel('profit (¥)'); ax.set_ylim(0, 600)
    ax.legend([plt.Rectangle((0, 0), 1, 1, fc=c, ec='none') for _, _, c in arms],
              [a[0] for a in arms], loc='upper right', handlelength=1.0, handleheight=0.8)
    panel(ax, 'a')
    clean(ax)
    # b — weight mechanisms
    ax = axes[1]
    mechs = ['V1.0\nbaseline', 'weight\nRSI', 'GAR-RL', 'TTRL', 'self-SFT\n(V0.2)']
    vals = [387, 210, 270, 270, 0]
    ax.bar(range(5), vals, 0.62, color=[BLUE] + [RED] * 4, linewidth=0)
    ax.axhspan(372 - 85, 372 + 85, color=GRAY, alpha=0.16, lw=0)
    ax.plot([-0.5, 4.5], [387, 387], color=BLUE, lw=0.8, ls=(0, (2, 2)))
    ax.text(4.4, 397, 'noise floor of\nidentical weights (±1 s.d.)', fontsize=5.6, ha='right', color='#4A4E54')
    for i, v in enumerate(vals):
        ax.text(i, v + 12, str(v), ha='center', fontsize=6.0, color=INK)
    ax.set_xticks(range(5)); ax.set_xticklabels(mechs, fontsize=6.0)
    ax.set_ylim(0, 510); ax.set_ylabel('profit (¥)')
    panel(ax, 'b')
    clean(ax)
    # c — memorization
    ax = axes[2]
    ax.barh([1], [195], 0.5, color=GRAY, linewidth=0)
    ax.barh([0], [240], 0.5, color=GREEN, linewidth=0, label='honest generalization')
    ax.barh([0], [150], 0.5, left=240, color=RED, linewidth=0, label='benchmark memorization')
    ax.text(200, 1, '195', va='center', fontsize=6.2, color=INK)
    ax.text(395, 0, '390', va='center', fontsize=6.2, color=INK)
    ax.annotate('39% memorized (RRSI critic)', xy=(318, 0.06), xytext=(330, 0.42),
                fontsize=5.8, color=RED, arrowprops=dict(arrowstyle='-', color=RED, lw=0.6))
    ax.set_yticks([0, 1]); ax.set_yticklabels(['JitRL\nmature', 'plain\ncontrol'], fontsize=6.2)
    ax.set_xlabel('profit (¥)'); ax.set_xlim(0, 470)
    ax.legend(loc='lower right', handlelength=1.0, handleheight=0.8)
    panel(ax, 'c')
    clean(ax, grid_axis='x')
    save(fig, 'fig3_failures.png')


# ═══════ Fig 4: substrates (full width) ═══════
def fig4():
    fig, axes = plt.subplots(1, 3, figsize=(mm(183), mm(58)))
    # a — dose-response
    ax = axes[0]
    n, prof = [0, 3, 6, 12, 19], [150, 600, 750, 750, 900]
    ax.plot(n, prof, 'o-', color=GREEN, lw=1.2, ms=3.8)
    for xi, yi in zip(n, prof):
        ax.annotate(str(yi), (xi, yi), textcoords='offset points', xytext=(0, 5), ha='center', fontsize=5.8)
    ax.set_xlabel('verified-asset library size'); ax.set_ylabel('profit / 12 rounds (¥)')
    ax.set_ylim(0, 1000)
    ax.text(9.5, 300, 'ρ = 0.96 · 3/3 seeds\nmonotone · 6× at 19 assets', fontsize=6.0, color='#4A4E54')
    panel(ax, 'a'); clean(ax)
    # b — JitRL slope
    ax = axes[1]
    acc = [300, 600, 450, 600, 150, 0, 300, 300, 300, 450]
    pln = [0, 300, 150, 150, 300, 300, 450, 150, 0, 150]
    ax.plot(range(1, 11), np.cumsum(acc) / np.arange(1, 11), 'o-', color=PURPLE, ms=3.4, label='JitRL (memory grows)')
    ax.plot(range(1, 11), np.cumsum(pln) / np.arange(1, 11), 's-', color=GRAY, ms=3.0, label='plain control')
    ax.set_xlabel('session'); ax.set_ylabel('cumulative mean profit (¥)')
    ax.text(5.4, 480, '2.0× · p = 0.037', fontsize=6.4, color=PURPLE, fontweight='bold')
    ax.legend(loc='lower right'); ax.set_xticks(range(1, 11, 2))
    panel(ax, 'b'); clean(ax)
    # c — V2 vs frontier beeswarm
    ax = axes[2]
    rng = np.random.default_rng(3)
    v2 = [450,600,550,600,500,600,370,570,570,700,490,700,640,270,570,650,500,600,540,670,
          520,650,600,500,700,670,570,600,600,450,570,450,550,420,540,680,500,420,570,700]
    mimo = [370,480,440,560,560,480,340,420,370,500,220,380,400,540]
    for i, (d, c) in enumerate([(v2, PURPLE), (mimo, ORANGE)]):
        xs = rng.normal(i, 0.06, len(d))
        ax.scatter(xs, d, s=9, color=c, alpha=0.5, linewidths=0, zorder=3)
        m = float(np.mean(d))
        ax.plot([i - 0.22, i + 0.22], [m, m], color=c, lw=1.6, zorder=4)
        ax.scatter([i], [m], marker='D', s=16, color='white', edgecolor=c, linewidths=1.0, zorder=5)
        ax.text(i + 0.3, m, f'¥{m:.0f}', fontsize=6.4, color=c, va='center', fontweight='bold')
    ax.boxplot([v2, mimo], positions=[0, 1], widths=0.5, showfliers=False,
               medianprops=dict(lw=0), boxprops=dict(lw=0.6, color='#B8BDC2'),
               whiskerprops=dict(lw=0.6, color='#B8BDC2'), capprops=dict(lw=0))
    ax.set_xticks([0, 1]); ax.set_xticklabels(['FluxEidosV2\nn = 40', 'mimo-v2.6-flash\nn = 14'], fontsize=6.4)
    ax.set_ylabel('profit per session (¥)'); ax.set_xlim(-0.6, 1.75)
    ax.text(0.5, 745, 'Mann–Whitney p = 0.0015 · d = 1.0', fontsize=6.2, ha='center', color=INK)
    panel(ax, 'c'); clean(ax)
    save(fig, 'fig4_substrates.png')


# ═══════ Fig 6: judges (full width) ═══════
def fig6():
    rows = json.loads((ROOT / 'leaderboard' / 'data' / 'judge_triples.json').read_text())
    m = np.array([r['mimo-v2.6-pro'] for r in rows])
    g = np.array([r['glm-5.3'] for r in rows])
    fig, axes = plt.subplots(1, 2, figsize=(mm(183), mm(70)), gridspec_kw={'width_ratios': [1, 1.15]})
    # a — hexbin density
    ax = axes[0]
    from scipy.stats import spearmanr
    rho, _ = spearmanr(m, g)
    hb = ax.hexbin(m, g, gridsize=22, cmap='Blues', mincnt=1, linewidths=0.2, edgecolors='white')
    ax.plot([-0.5, 10.5], [-0.5, 10.5], color=INK, lw=0.7, ls=(0, (2, 2)))
    ax.set_xlabel('mimo-v2.6-pro rating'); ax.set_ylabel('glm-5.3 rating')
    ax.set_xlim(-0.5, 10.5); ax.set_ylim(-0.5, 10.5)
    cb = plt.colorbar(hb, ax=ax, shrink=0.85, pad=0.02)
    cb.ax.tick_params(labelsize=5.5)
    cb.set_label('triples', fontsize=6.0)
    ax.text(0.1, 9.6, f'ρ = {rho:.2f} · n = 283\nα = 0.676 (ordinal)\nsale agreement 80%', fontsize=6.2, color=INK)
    panel(ax, 'a'); clean(ax)
    # b — family-bias gaps with bootstrap CI (forest style)
    ax = axes[1]
    judges = ['mimo-v2.6-pro', 'glm-5.3', 'glm-5.3-flash']
    rng = np.random.default_rng(7)
    gaps, cis = [], []
    for j in judges:
        md = np.array([r[j] for r in rows if r['designer'] == 'mimo-v2.6-flash'])
        ou = np.array([r[j] for r in rows if r['designer'] in ('FluxEidosV1.5', 'FluxEidosV2')])
        boots = [np.mean(rng.choice(md, len(md))) - np.mean(rng.choice(ou, len(ou))) for _ in range(2000)]
        gaps.append(md.mean() - ou.mean())
        cis.append(np.percentile(boots, [2.5, 97.5]))
    ypos = np.arange(3)[::-1]
    for yi, gp, ci, c in zip(ypos, gaps, cis, [ORANGE, BLUE, BLUE]):
        ax.plot(ci, [yi, yi], color=c, lw=1.4, solid_capstyle='round')
        ax.scatter([gp], [yi], s=22, color=c, zorder=3)
        ax.text(max(ci[1], gp) + 0.08, yi, f'{gp:+.2f}', fontsize=6.4, va='center', color=c)
    ax.axvline(0, color=INK, lw=0.7)
    ax.set_yticks(ypos); ax.set_yticklabels(judges, fontsize=6.6)
    ax.set_xlabel('rating gap: mimo-family designs − our designs (95% bootstrap CI)')
    ax.set_xlim(-2.6, 1.0)
    ax.text(-2.45, -0.62, 'negative = judge scores own-family designs LOWER · all CIs cross 0', fontsize=5.9, color='#4A4E54')
    panel(ax, 'b'); clean(ax, grid_axis='x')
    save(fig, 'fig6_judges.png')


if __name__ == '__main__':
    fig2(); fig3(); fig4(); fig6()
    print('figures 2-6 done (fig1 via chromium, fig5 via formal_model_sim)')
