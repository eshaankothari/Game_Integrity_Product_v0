"""Rolling prior-window z-scores for Malik Beasley's 2023-24 games.

For each stat and game t, the baseline is the 15 games IMMEDIATELY BEFORE it:
    z_t = (x_t - mean(x_{t-15..t-1})) / std(x_{t-15..t-1})
The .shift(1) makes it causal (game t never sees itself/future). Requires a full
15 prior games, so the first 15 games get NaN (skipped) by design.

Stats: points, rebounds, assists, minutes (minutes parsed from MM:SS).
Writes beasley_2023_24_zscores.csv and a per-game z heatmap; adds it to the deck.

    python beasley_zscores.py
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import plotly.graph_objects as go

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
OUT = CSV.with_name("beasley_2023_24_zscores.csv")
WINDOW = 15
STATS = ["points", "rebounds", "assists", "minutes_f"]


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


df = pd.read_csv(CSV).sort_values("date").reset_index(drop=True)
df["minutes_f"] = df["minutes"].map(_min_to_float)

# rolling z on the 15 games PRIOR to each game (shift(1) => excludes current game)
for s in STATS:
    prior_mean = df[s].rolling(WINDOW).mean().shift(1)
    prior_std = df[s].rolling(WINDOW).std().shift(1)      # sample std (ddof=1)
    df[f"{s}_z"] = (df[s] - prior_mean) / prior_std
df["prior_games"] = df.index                              # games available before this one
df["has_z"] = df.index >= WINDOW                          # True once 15 priors exist

ZCOLS = [f"{s}_z" for s in STATS]
df.round(3).to_csv(OUT, index=False)

# --- heatmap: rows = games (chronological), cols = stat z-scores ---
plot = df.copy()
plot["d"] = pd.to_datetime(plot["date"]).dt.strftime("%b %d")
plot["label"] = plot["d"] + "  " + plot["matchup"]
M = plot[ZCOLS].to_numpy(dtype=float)
vmax = np.nanmax(np.abs(M[np.isfinite(M)])) if np.isfinite(M).any() else 1.0
LABELS = ["points z", "rebounds z", "assists z", "minutes z"]

fig = go.Figure(go.Heatmap(
    z=M, x=LABELS, y=plot["label"],
    colorscale="RdBu_r", zmid=0, zmin=-vmax, zmax=vmax,
    text=np.where(np.isnan(M), "", np.round(M, 2).astype(str)),
    texttemplate="%{text}", textfont={"size": 9},
    hovertemplate="%{y}<br>%{x}: %{z:.2f}<extra></extra>",
    colorbar=dict(title="z"),
))
fig.update_layout(title=f"Beasley 2023-24 — rolling z-score vs prior {WINDOW} games "
                        f"(first {WINDOW} skipped)",
                  yaxis=dict(autorange="reversed"), height=1300, width=640)
fig.write_html(HERE / "beasley_zscores_heatmap.html")

# --- static PNG ---
masked = np.ma.masked_invalid(M)
cmap = plt.cm.RdBu_r.copy(); cmap.set_bad("lightgrey")
fig2, ax = plt.subplots(figsize=(5.5, 16))
im = ax.imshow(masked, cmap=cmap, vmin=-vmax, vmax=vmax, aspect="auto")
ax.set_xticks(range(len(ZCOLS))); ax.set_xticklabels(LABELS, fontsize=9)
ax.set_yticks(range(len(plot))); ax.set_yticklabels(plot["label"], fontsize=6)
for i in range(len(plot)):
    for j in range(len(ZCOLS)):
        if not np.isnan(M[i, j]):
            ax.text(j, i, f"{M[i, j]:.2f}", ha="center", va="center", fontsize=6,
                    color="black" if abs(M[i, j]) < vmax * 0.6 else "white")
ax.set_title(f"Beasley rolling z (prior {WINDOW} games)\ngrey = first {WINDOW} (no baseline)")
fig2.colorbar(im, ax=ax, fraction=0.04, pad=0.03, label="z")
fig2.savefig(HERE / "beasley_zscores_heatmap.png", dpi=120, bbox_inches="tight")

n_scored = int(df["has_z"].sum())
print(f"wrote {OUT.name} and beasley_zscores_heatmap.html/.png "
      f"({n_scored}/{len(df)} games scored; first {WINDOW} skipped)")
print("\nmost anomalous games (|z| across stats):")
tmp = df[df["has_z"]].copy()
tmp["maxabs"] = tmp[ZCOLS].abs().max(axis=1)
print(tmp.sort_values("maxabs", ascending=False).head(5)[
    ["date", "matchup", "points", "points_z", "rebounds_z", "assists_z", "minutes_f", "minutes_f_z"]
].round(2).to_string(index=False))

import slideshow           # noqa: E402  (repo root already on sys.path)
slideshow.add(HERE / "beasley_zscores_heatmap.html", "11 · Beasley rolling z (15-game prior)",
              "Per-game z-scores vs the prior 15 games; first 15 skipped (no baseline).")
