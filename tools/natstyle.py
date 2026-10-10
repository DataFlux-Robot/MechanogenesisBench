"""Nature-style matplotlib defaults + helpers, shared by paper figures."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import rcParams

# palette (muted, colorblind-safe)
BLUE, ORANGE, GREEN, RED, PURPLE, GRAY, INK = \
    '#3B6EA5', '#E08E45', '#5E8C61', '#B55454', '#7E6FAE', '#8C9196', '#1A1D21'

NATURE = {
    'font.family': 'sans-serif',
    'font.sans-serif': ['Liberation Sans', 'Arial', 'DejaVu Sans'],
    'font.size': 7.0,
    'axes.titlesize': 7.5, 'axes.titleweight': 'bold', 'axes.titlepad': 5,
    'axes.labelsize': 7.0, 'axes.labelcolor': INK,
    'axes.linewidth': 0.6, 'axes.edgecolor': '#4A4E54',
    'axes.spines.top': False, 'axes.spines.right': False,
    'axes.grid': False,
    'xtick.major.size': 2.2, 'ytick.major.size': 2.2,
    'xtick.major.width': 0.6, 'ytick.major.width': 0.6,
    'xtick.major.pad': 2.5, 'ytick.major.pad': 2.5,
    'xtick.labelsize': 6.5, 'ytick.labelsize': 6.5, 'xtick.color': '#4A4E54', 'ytick.color': '#4A4E54',
    'legend.fontsize': 6.2, 'legend.frameon': False, 'legend.handlelength': 1.2,
    'lines.linewidth': 1.1, 'lines.markersize': 3.2,
    'figure.dpi': 300, 'savefig.dpi': 300,
    'pdf.fonttype': 42, 'ps.fonttype': 42,
}


def activate():
    rcParams.update(NATURE)


def panel(ax, letter, dx=-0.16, dy=1.06):
    """Bold lowercase panel letter, Nature style."""
    ax.text(dx, dy, letter, transform=ax.transAxes, fontsize=9,
            fontweight='bold', color=INK, va='bottom', ha='left')


def mm(mm_width):
    return mm_width / 25.4


def clean(ax, grid_axis=None):
    for side in ('top', 'right'):
        ax.spines[side].set_visible(False)
    ax.tick_params(direction='out')
    if grid_axis:
        ax.grid(axis=grid_axis, color='#D8DBDE', lw=0.45, alpha=0.8)
        ax.set_axisbelow(True)
