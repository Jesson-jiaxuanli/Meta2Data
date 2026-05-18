import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyArrowPatch
import numpy as np

# Color palette
C_READ    = "#B8C8DC"   # light steel blue — read body
C_ERROR   = "#8A2A44"   # dark crimson     — sequencing errors
C_ARROW   = "#324068"   # deep navy        — arrow + DADA2 label
C_VSEARCH = "#966729"   # gold             — vsearch label + counts
C_ASV     = "#356920"   # dark green       — output ASV bars
C_LABEL   = "#444444"   # dark gray        — section labels

fig, ax = plt.subplots(figsize=(5, 8))
ax.set_xlim(0, 10)
ax.set_ylim(0, 18)
ax.axis("off")

# ── helper ────────────────────────────────────────────────────────────────
def draw_read(ax, y, x_start, length, errors, color=C_READ, height=0.38):
    bar = mpatches.FancyBboxPatch(
        (x_start, y - height / 2), length, height,
        boxstyle="round,pad=0.05",
        facecolor=color, edgecolor="none", zorder=2
    )
    ax.add_patch(bar)
    for ex in errors:
        sq = mpatches.FancyBboxPatch(
            (x_start + ex - 0.13, y - 0.13), 0.26, 0.26,
            boxstyle="round,pad=0.02",
            facecolor=C_ERROR, edgecolor="none", zorder=3
        )
        ax.add_patch(sq)

# ══════════════════════════════════════════════════════════════════════════
# SECTION 1 — Input reads
# ══════════════════════════════════════════════════════════════════════════
ax.text(0.3, 17.4, "Input reads", fontsize=9, color=C_LABEL,
        va="center", fontstyle="italic")

# 8 reads: (y, x_start, length, [error_positions])
reads = [
    (16.6, 1.0, 7.2, [1.2, 3.8, 6.5]),
    (15.9, 1.2, 6.8, [2.1, 5.3]),
    (15.2, 0.9, 7.5, [0.8, 4.1, 6.9]),
    (14.5, 1.1, 7.0, [1.9, 3.3]),
    (13.8, 1.0, 7.3, [2.6, 5.0, 6.8]),
    (13.1, 1.3, 6.6, [1.5, 4.7]),
    (12.4, 0.8, 7.6, [0.9, 3.0, 5.8]),
    (11.7, 1.1, 7.1, [2.2, 4.4, 6.3]),
]
for y, xs, ln, errs in reads:
    draw_read(ax, y, xs, ln, errs)

# ── separator line ─────────────────────────────────────────────────────────
ax.axhline(11.1, xmin=0.02, xmax=0.98, color="#CCCCCC", linewidth=0.8, linestyle="--")

# ══════════════════════════════════════════════════════════════════════════
# SECTION 2 — Process arrow + labels
# ══════════════════════════════════════════════════════════════════════════
arrow = FancyArrowPatch(
    posA=(5.0, 10.7), posB=(5.0, 8.5),
    arrowstyle="-|>",
    mutation_scale=18,
    color=C_ARROW, linewidth=2.0, zorder=4
)
ax.add_patch(arrow)

ax.text(5.0, 10.15, "DADA2", fontsize=11, fontweight="bold",
        color=C_ARROW, ha="center", va="center", zorder=5)
ax.text(5.0, 9.45, "vsearch UNOISE3", fontsize=9, fontstyle="italic",
        color=C_VSEARCH, ha="center", va="center", zorder=5)

# ── separator line ─────────────────────────────────────────────────────────
ax.axhline(8.1, xmin=0.02, xmax=0.98, color="#CCCCCC", linewidth=0.8, linestyle="--")

# ══════════════════════════════════════════════════════════════════════════
# SECTION 3 — Output ASVs
# ══════════════════════════════════════════════════════════════════════════
ax.text(0.3, 7.7, "Representative sequences (ASVs)", fontsize=9,
        color=C_LABEL, va="center", fontstyle="italic")

asv_data = [
    (6.9, 1.0, 7.2, "× 312"),
    (5.9, 1.0, 7.2, "× 87"),
    (4.9, 1.0, 7.2, "× 41"),
]
for y, xs, ln, count in asv_data:
    draw_read(ax, y, xs, ln, [], color=C_ASV)
    ax.text(xs + ln + 0.25, y, count, fontsize=9, color=C_VSEARCH,
            va="center", fontweight="bold")

# ══════════════════════════════════════════════════════════════════════════
# Legend
# ══════════════════════════════════════════════════════════════════════════
legend_y = 3.8
legend_items = [
    (C_READ,  "Read"),
    (C_ERROR, "Sequencing error"),
    (C_ASV,   "ASV"),
]
for i, (color, label) in enumerate(legend_items):
    lx = 1.2 + i * 3.0
    rect = mpatches.FancyBboxPatch(
        (lx, legend_y - 0.18), 0.55, 0.36,
        boxstyle="round,pad=0.03",
        facecolor=color, edgecolor="none"
    )
    ax.add_patch(rect)
    ax.text(lx + 0.7, legend_y, label, fontsize=8.5, color=C_LABEL, va="center")

plt.tight_layout(pad=0.3)
out = "/home/user/Meta2Data/docs/denoising_schematic.pdf"
plt.savefig(out, dpi=300, bbox_inches="tight", facecolor="white")
out_png = "/home/user/Meta2Data/docs/denoising_schematic.png"
plt.savefig(out_png, dpi=300, bbox_inches="tight", facecolor="white")
print(f"Saved: {out}")
print(f"Saved: {out_png}")
