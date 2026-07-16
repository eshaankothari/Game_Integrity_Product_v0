"""Heatmap of z1 ONLY (normalized line move) per player-game.

Separate output from the main z1+z2 heatmap. Rows = player-games sorted by z1
(most -> least suspicious); single column = z1. Row labels carry the metadata;
group tints the label color (flagged red / control blue).

    python visualize_scores_z1only.py
"""
from pathlib import Path
import numpy as np
import pandas as pd
import plotly.graph_objects as go

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).parent
KF = HERE.parent / "Key Figures"
CSV = KF / "test_dataset_jan_mar_scored.csv"

df = pd.read_csv(CSV).sort_values("z1", ascending=False).reset_index(drop=True)
df["date"] = pd.to_datetime(df["time"], format="mixed").dt.strftime("%b %d")
df["label"] = df["player"] + " — " + df["date"] + " (" + df["group"] + ")"

COLS = ["z1"]
COL_LABELS = ["z1<br>line (= score)"]
M = df[COLS].to_numpy(dtype=float)
vmax = np.nanmax(np.abs(M))

GROUP_COLOR = {"flagged": "#d62728", "control": "#1f77b4"}

# --- interactive HTML ---
custom = np.dstack([np.tile(df["player"].to_numpy()[:, None], (1, len(COLS))),
                    np.tile(df["game"].to_numpy()[:, None], (1, len(COLS))),
                    np.tile(df["date"].to_numpy()[:, None], (1, len(COLS))),
                    np.tile(df["group"].to_numpy()[:, None], (1, len(COLS)))])
fig = go.Figure(go.Heatmap(
    z=M, x=[c.replace("<br>", " ") for c in COL_LABELS], y=df["label"],
    colorscale="RdBu_r", zmid=0, zmin=-vmax, zmax=vmax,
    text=np.round(M, 2).astype(str), texttemplate="%{text}", textfont={"size": 10},
    customdata=custom,
    hovertemplate=("<b>%{customdata[0]}</b> (%{customdata[3]})<br>"
                   "%{customdata[1]} — %{customdata[2]}<br>"
                   "z1: %{z:.2f}<extra></extra>"),
    colorbar=dict(title="z1"),
))
fig.update_layout(title="Normalized line-move z-score (z1 only) by player-game",
                  yaxis=dict(autorange="reversed"), height=760, width=520)
fig.write_html(KF / "scores_heatmap_z1only.html")

# --- static PNG ---
fig2, ax = plt.subplots(figsize=(3.6, 11))
im = ax.imshow(M, cmap=plt.cm.RdBu_r, vmin=-vmax, vmax=vmax, aspect="auto")
ax.set_xticks(range(len(COLS)))
ax.set_xticklabels([c.replace("<br>", "\n") for c in COL_LABELS], fontsize=9)
ax.set_yticks(range(len(df)))
ax.set_yticklabels(df["label"], fontsize=8)
for tick, grp in zip(ax.get_yticklabels(), df["group"]):
    tick.set_color(GROUP_COLOR[grp])
for i in range(len(df)):
    ax.text(0, i, f"{M[i, 0]:.2f}", ha="center", va="center", fontsize=7.5,
            color="black" if abs(M[i, 0]) < vmax * 0.6 else "white")
ax.set_title("z1 only\n(normalized line move; red = suspicious)")
fig2.colorbar(im, ax=ax, fraction=0.06, pad=0.04, label="z1")
fig2.savefig(KF / "scores_heatmap_z1only.png", dpi=120, bbox_inches="tight")

print("wrote scores_heatmap_z1only.html / .png")
