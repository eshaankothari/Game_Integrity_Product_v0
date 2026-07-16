"""Distributions of the 3 raw metrics BEFORE standardization, with mean & variance.

These are the quantities that get turned into z1/z2/z3. Mean & variance shown are
exactly what standardization uses (sample, ddof=1).
  - line_move_pct   (z1 basis)  -- all 28 games
  - under_move_pct  (z2 basis)  -- only the no-line-move subset it's baselined on
  - ou_ratio        (z3 basis)  -- all 28 games
Bars colored by group (flagged vs control) for context.

    python visualize_distributions.py
"""
from pathlib import Path
import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import sys
HERE = Path(__file__).parent
_root = HERE
while not (_root / "datapaths.py").exists() and _root.parent != _root:
    _root = _root.parent
sys.path.insert(0, str(_root))
from datapaths import find_data           # noqa: E402  (repo-root helper)
CSV = find_data("test_dataset_jan_mar_scored.csv")
GROUP_COLOR = {"flagged": "#d62728", "control": "#1f77b4"}

df = pd.read_csv(CSV)
pinned = df[df["line_move_pct"] == 0]

panels = [
    ("line_move_pct", df, "z1 basis: normalized line move (%)"),
    ("under_move_pct", pinned, "z2 basis: Under-price move (%) — no-line-move games only"),
    ("ou_ratio", df, "z3 basis: closing Over/Under ratio"),
]

fig, axes = plt.subplots(3, 1, figsize=(8.5, 11))
for ax, (col, data, title) in zip(axes, panels):
    vals = data[col]
    mean, var, std, n = vals.mean(), vals.var(), vals.std(), len(vals)
    ctrl = data[data["group"] == "control"][col]
    flag = data[data["group"] == "flagged"][col]
    bins = np.histogram_bin_edges(vals, bins=12)

    ax.hist([ctrl, flag], bins=bins, stacked=True,
            color=[GROUP_COLOR["control"], GROUP_COLOR["flagged"]],
            label=[f"control (n={len(ctrl)})", f"flagged (n={len(flag)})"],
            edgecolor="white", linewidth=0.5)
    ax.axvline(mean, color="black", ls="--", lw=1.5, label=f"mean = {mean:.3f}")
    ax.axvspan(mean - std, mean + std, color="grey", alpha=0.12, label=f"±1 std ({std:.3f})")

    ax.set_title(title, fontsize=11)
    ax.set_ylabel("count")
    ax.set_xlabel(col)
    txt = f"mean = {mean:.3f}\nvariance = {var:.3f}\nstd = {std:.3f}\nn = {n}"
    ax.text(0.98, 0.95, txt, transform=ax.transAxes, va="top", ha="right", fontsize=9,
            bbox=dict(boxstyle="round", fc="white", ec="grey", alpha=0.9))
    ax.legend(loc="upper left", fontsize=8)

fig.suptitle("Raw metric distributions before standardization (Jan-Mar test set)",
             fontsize=13, y=0.995)
fig.tight_layout()
fig.savefig(HERE / "score_distributions.png", dpi=120, bbox_inches="tight")

print("wrote score_distributions.png\n")
for col, data, title in panels:
    v = data[col]
    print(f"{col:16} n={len(v):2}  mean={v.mean():.4f}  variance={v.var():.4f}  std={v.std():.4f}")
