# -*- coding: utf-8 -*-
"""
真实字段(NCBI 语料全部出现过的字段)覆盖率直方图 (Pareto)
------------------------------------------------
不同于 build_coverage_plot.py(那个画的是 1044 个字典条目),
本图画的是语料里**所有真实字段**(按 char_fp 归一化去重后 = 84,894 个),
展示前 90% 出现量只需极少数头部字段。

输入: Y:\ncbi_corpus\attribute_name_freq.csv  (raw attribute_name, freq)
输出(同目录):
  - realfield_frequencies.csv   rank / char_fp代表名 / occurrence_count / cumulative_pct
  - realfield_coverage.png
"""
import csv, os, re
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter, ScalarFormatter, NullFormatter

HERE = os.path.dirname(os.path.abspath(__file__))
FREQ = r"Y:\ncbi_corpus\attribute_name_freq.csv"

# ---- 原始字段名(不归一化): 每个 attribute_name 各算一个字段 ----
rows = []
with open(FREQ, encoding="utf-8-sig", newline="") as f:
    for row in csv.reader(f):
        if len(row) < 2 or not row[1].isdigit():
            continue
        nm, fr = row[0], int(row[1])
        rows.append([nm, fr])

rows.sort(key=lambda r: r[1], reverse=True)
freqs = np.array([r[1] for r in rows], dtype=float)
n = len(rows)
total = freqs.sum()
cum_pct = np.cumsum(freqs) / total * 100.0

def k_for(p): return min(int(np.searchsorted(cum_pct, p) + 1), n)
k50, k90, k95 = k_for(50), k_for(90), k_for(95)

# ---- 写 CSV ----
csv_out = os.path.join(HERE, "realfield_frequencies.csv")
with open(csv_out, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(["rank", "field_repr", "occurrence_count", "cumulative_pct"])
    for i, (nm, fr) in enumerate(rows, 1):
        w.writerow([i, nm, int(fr), round(cum_pct[i-1], 4)])

# ---- 画图 (与字典图同风格; 无表头; 只标注前90%) ----
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams.update({"font.size": 12, "axes.grid": False})
fig, ax = plt.subplots(figsize=(12, 6))
x = np.arange(1, n + 1)

def _fmt(v, _):
    if v >= 1e6: return f"{v/1e6:.0f}M"
    if v >= 1e3: return f"{v/1e3:.0f}K"
    return f"{v:.0f}"

# 等比(对数)横轴: 头部被拉宽、长尾按比例压缩 -> 全部字段都看得见(纵轴仍线性, 高度不失真)
ax.axvspan(1, k90, color="#ffe08a", alpha=0.6, zorder=0)
ax.fill_between(x, freqs, color="#2c7fb8", linewidth=0, zorder=2)
ax.set_xscale("log")
ax.set_ylim(0, freqs.max() * 1.05)
ax.set_xlim(1, n)
ax.set_xticks([1, 10, 100, 1000, 10000, 100000])
ax.xaxis.set_major_formatter(ScalarFormatter())   # 显示 1/10/100... 而非 10^n
ax.xaxis.set_minor_formatter(NullFormatter())
ax.set_xlabel("Metadata field")
ax.set_ylabel("Occurrence count", color="#2c7fb8")
ax.tick_params(axis="y", labelcolor="#2c7fb8")
ax.yaxis.set_major_formatter(FuncFormatter(_fmt))

ax2 = ax.twinx()
ax2.plot(x, cum_pct, color="#d95f0e", lw=2.4, zorder=3)
ax2.set_ylim(0, 101)
ax2.set_ylabel("Cumulative %", color="#d95f0e")
ax2.tick_params(axis="y", labelcolor="#d95f0e")
ax2.axhline(90, color="#d95f0e", ls=":", lw=1.2, alpha=0.7)
ax2.axvline(k90, color="#b30000", ls="--", lw=1.5)
ax2.annotate("90%",
             xy=(k90, 90), xytext=(k90 * 2.4, 55),
             fontsize=15, fontweight="bold", color="#b30000",
             arrowprops=dict(arrowstyle="->", color="#b30000", lw=1.5))

fig.tight_layout()
png_out = os.path.join(HERE, "realfield_coverage.png")
fig.savefig(png_out, dpi=160)
print("wrote:", csv_out)
print("wrote:", png_out)
print(f"n={n} total={total:.0f} k50={k50} k90={k90} k95={k95}")
