#!/usr/bin/env python3
"""极简形式模型三面板图（中文标注版）— nmi_submission_cn 图 5。
模型同 formal_model_sim.py：
  P1 基底单调性：仅执行验证后入库 => V_S(n) = c * Binomial(n, p) 期望单调。
  P2 权重更新阈值：E[dF] = eta*||g||^2 - (eta^2 sigma^2 L)/2；低于噪声即不可检出。
  P3 记忆实例绑定：回放增益 ~ s_bar * p；权重保持率与 s 无关。
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import cjkfont
import natstyle
cjkfont.register()
natstyle.NATURE['font.sans-serif'] = ['Noto Sans CJK SC', 'Liberation Sans', 'DejaVu Sans']
natstyle.NATURE['axes.unicode_minus'] = False
natstyle.activate()
from natstyle import BLUE, ORANGE, GREEN, RED, PURPLE, GRAY, INK, panel, clean, mm
import matplotlib.pyplot as plt
import numpy as np

FIG = Path(__file__).resolve().parent.parent / 'paper' / 'figures' / 'cn'
FIG.mkdir(parents=True, exist_ok=True)
rng = np.random.default_rng(42)

fig, axes = plt.subplots(1, 3, figsize=(mm(183), mm(62)))

# ── P1：剂量—响应 ──
ax = axes[0]
n = np.arange(0, 20)
p_dose = 0.55
trials = 4000
curves = rng.binomial(n[:, None], p_dose, (len(n), trials)) * 50.0  # c=50 元/资产
mean, lo, hi = curves.mean(1), np.percentile(curves, 10, 1), np.percentile(curves, 90, 1)
ax.plot(n, mean, color=BLUE, lw=2, label='模型 $c\\cdot n\\hat p$')
ax.fill_between(n, lo, hi, color=BLUE, alpha=0.18, label='10–90 百分位（P1）')
dose = [0, 3, 6, 12, 19]
prof = [150, 600, 750, 750, 900]
ax.scatter(dose, prof, color=RED, zorder=5, s=45, label='实测（3 种子）')
ax.set_xlabel('基底（库）规模 $n$')
ax.set_ylabel('生产利润（¥ / 12 轮）')
ax.set_title('基底累积单调')
panel(ax, 'a'); clean(ax)
ax.legend(fontsize=6.2)
ax.spines[['top', 'right']].set_visible(False)

# ── P2：能力阈值 ──
ax = axes[1]
snr = np.linspace(0.02, 2.0, 200)          # ||g||^2 / (sigma^2 L)，相对值
eta = 0.5
improve = eta * snr - eta**2 / 2            # 期望相对增益（信号 − 收缩）
noise_floor = 0.16                          # 评测噪声（已训练模型探针 sd/mean）
trials = 2000
obs = improve[:, None] + rng.normal(0, noise_floor, (len(snr), trials))
ax.plot(snr, improve, color=BLUE, lw=2, label='期望增益')
ax.fill_between(snr, np.percentile(obs, 10, 1), np.percentile(obs, 90, 1),
                color='#D8DBDE', alpha=0.35, label='评测噪声（10–90 百分位）')
ax.axhline(0, color='k', lw=0.6)
# 实证锚点：V0-Self（阈值以下）、V1.0+JitRL（阈值以上）
ax.scatter([0.35], [-0.54], color=RED, zorder=5, s=55, marker='x')
ax.annotate('V0-Self +JitRL\n（实测 −54%）', (0.35, -0.54), textcoords='offset points',
            xytext=(8, -4), fontsize=6.2, color=RED)
ax.scatter([1.15], [0.05], color=GREEN, zorder=5, s=55, marker='o')
ax.annotate('V1.0 +JitRL\n（实测 +5%, p=0.037）', (1.15, 0.05), textcoords='offset points',
            xytext=(8, 6), fontsize=6.2, color=GREEN)
ax.set_xlabel('信噪比 $\\|g\\|^2/(\\sigma^2 L)$')
ax.set_ylabel('相对增益')
ax.set_title('权重更新需 SNR 越过阈值')
panel(ax, 'b'); clean(ax)
ax.legend(fontsize=6.2, loc='upper left')
ax.spines[['top', 'right']].set_visible(False)

# ── P3：记忆迁移 vs 重叠 ──
ax = axes[2]
s = np.linspace(0, 1, 100)
gain_mem = 0.13 * s                          # 回放增益（同分布 +13%）
ax.plot(s, gain_mem * 100, color=BLUE, lw=2, label='记忆增益 $\\propto \\bar s$（P3）')
ax.plot(s, np.full_like(s, 65.0), color=PURPLE, lw=2, ls='--',
        label='权重保持率（65%，与 s 无关）')
ax.scatter([1.0], [13.0], color=BLUE, zorder=5, s=45)
ax.annotate('标准基准\n（实测 +13%）', (1.0, 13), textcoords='offset points',
            xytext=(-78, 4), fontsize=6.2)
ax.scatter([0.08], [4.3], color=RED, zorder=5, s=45)
ax.annotate('封存探针\n（实测 +4%，不显著）', (0.08, 4.3), textcoords='offset points',
            xytext=(10, -2), fontsize=6.2, color=RED)
ax.set_xlabel('训练—测试实例重叠 $\\bar s$')
ax.set_ylabel('增益 / 保持率（%）')
ax.set_title('记忆实例绑定，权重可迁移')
panel(ax, 'c'); clean(ax)
ax.legend(fontsize=6.2, loc='center left')
ax.spines[['top', 'right']].set_visible(False)

plt.tight_layout(w_pad=1.5)
out = FIG / 'formal_model.png'
plt.savefig(out, dpi=200)
print(f'saved {out}')
