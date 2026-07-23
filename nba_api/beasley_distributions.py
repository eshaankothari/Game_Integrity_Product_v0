"""Distributions of Beasley's 2023-24 box-score stats (points, rebounds, assists, minutes).

Histogram per stat across all games, with mean (solid) and median (dashed) marked
and mean/std/n annotated. Writes a 2x2 static PNG + an interactive HTML; adds the
HTML to the slideshow.

    python beasley_distributions.py
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).parent
_root = HERE
while not (_root / "datapaths.py").exists() and _root.parent != _root:
    _root = _root.parent
sys.path.insert(0, str(_root))
from datapaths import find_data           # noqa: E402  (repo-root helper)

CSV = find_data("beasley_2023_24_boxscores.csv")


def _min_to_float(m):
    if pd.isna(m):
        return np.nan
    s = str(m)
    if ":" in s:
        mm, ss = s.split(":")[:2]
        return int(mm) + int(ss) / 60
    try:
        return float(s)
    except ValueError:
        return np.nan


df = pd.read_csv(CSV)
df["minutes_f"] = df["minutes"].map(_min_to_float)
STATS = [("points", "Points"), ("rebounds", "Rebounds"),
         ("assists", "Assists"), ("minutes_f", "Minutes")]
COLOR = "#2ca02c"   # Beasley green (matches earlier player-graphs)

# --- interactive HTML (2x2) ---
fig = make_subplots(rows=2, cols=2, subplot_titles=[t for _, t in STATS])
for k, (col, title) in enumerate(STATS):
    r, c = k // 2 + 1, k % 2 + 1
    s = pd.to_numeric(df[col], errors="coerce").dropna()
    fig.add_trace(go.Histogram(x=s, marker_color=COLOR, opacity=0.8,
                               name=title, showlegend=False), row=r, col=c)
    fig.add_vline(x=s.mean(), line_color="black", row=r, col=c,
                  annotation_text=f"mean {s.mean():.1f}", annotation_position="top")
    fig.add_vline(x=s.median(), line_color="grey", line_dash="dash", row=r, col=c)
fig.update_layout(title=f"Malik Beasley 2023-24 — stat distributions (n={len(df)} games)",
                  height=720, width=900, bargap=0.05)
fig.write_html(HERE / "beasley_distributions.html")

# --- static PNG (2x2) ---
fig2, axes = plt.subplots(2, 2, figsize=(11, 7.5))
for ax, (col, title) in zip(axes.ravel(), STATS):
    s = pd.to_numeric(df[col], errors="coerce").dropna()
    ax.hist(s, bins=15, color=COLOR, edgecolor="white", alpha=0.85)
    ax.axvline(s.mean(), color="black", lw=1.5, label=f"mean {s.mean():.1f}")
    ax.axvline(s.median(), color="grey", lw=1.2, ls="--", label=f"median {s.median():.1f}")
    ax.set_title(f"{title}  (μ={s.mean():.1f}, σ={s.std():.1f}, n={len(s)})", fontsize=10)
    ax.set_xlabel(title); ax.set_ylabel("games"); ax.legend(fontsize=8)
    ax.grid(True, alpha=0.25)
fig2.suptitle("Malik Beasley 2023-24 — box-score stat distributions", fontsize=13)
fig2.tight_layout(rect=[0, 0, 1, 0.97])
fig2.savefig(HERE / "beasley_distributions.png", dpi=120, bbox_inches="tight")

print("wrote beasley_distributions.html / .png")
print(df[["points", "rebounds", "assists", "minutes_f"]].describe().round(2).to_string())

import slideshow           # noqa: E402  (repo root already on sys.path)
slideshow.add(HERE / "beasley_distributions.html", "12 · Beasley stat distributions",
              "Histograms of points, rebounds, assists, minutes across 2023-24.")
