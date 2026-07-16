"""Heatmap of the robust percentile components + composite suspicion percentile.

Rows = player-games (most -> least suspicious), columns = p_line, p_price,
p_ratio and the composite. Color = percentile in [0,1], centered at 0.5 (median):
red = suspicious, blue = clean, grey = price component N/A (line moved).

    python visualize_scores_robust.py
"""
from pathlib import Path
import numpy as np
import pandas as pd
import plotly.graph_objects as go

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
CSV = find_data("test_dataset_jan_mar_robust.csv")

df = pd.read_csv(CSV).sort_values("suspicious_score", ascending=False).reset_index(drop=True)
df["date"] = pd.to_datetime(df["time"], format="ISO8601").dt.strftime("%b %d")
df["label"] = df["player"] + " — " + df["date"] + " (" + df["group"] + ")"

COLS = ["p_line", "p_price", "p_ratio", "suspicious_score"]
COL_LABELS = ["p_line<br>line", "p_price<br>price|pinned", "p_ratio<br>ratio",
              "SUSPICION<br>PERCENTILE"]
M = df[COLS].to_numpy(dtype=float)
GROUP_COLOR = {"flagged": "#d62728", "control": "#1f77b4"}

# --- interactive HTML (hover = full metadata) ---
custom = np.dstack([np.tile(df["player"].to_numpy()[:, None], (1, len(COLS))),
                    np.tile(df["game"].to_numpy()[:, None], (1, len(COLS))),
                    np.tile(df["date"].to_numpy()[:, None], (1, len(COLS))),
                    np.tile(df["group"].to_numpy()[:, None], (1, len(COLS)))])
fig = go.Figure(go.Heatmap(
    z=M, x=[c.replace("<br>", " ") for c in COL_LABELS], y=df["label"],
    colorscale="RdBu_r", zmid=0.5, zmin=0, zmax=1,
    text=np.where(np.isnan(M), "", np.round(M, 2).astype(str)),
    texttemplate="%{text}", textfont={"size": 10}, customdata=custom,
    hovertemplate=("<b>%{customdata[0]}</b> (%{customdata[3]})<br>"
                   "%{customdata[1]} — %{customdata[2]}<br>"
                   "%{x}: %{z:.2f}<extra></extra>"),
    colorbar=dict(title="percentile"),
))
fig.update_layout(title="Robust suspicion percentiles by player-game (Jan-Mar test set)",
                  yaxis=dict(autorange="reversed"), height=760, width=780)
fig.write_html(HERE / "scores_heatmap_robust.html")

# --- static PNG ---
masked = np.ma.masked_invalid(M)
cmap = plt.cm.RdBu_r.copy(); cmap.set_bad("lightgrey")
fig2, ax = plt.subplots(figsize=(7.5, 11))
im = ax.imshow(masked, cmap=cmap, vmin=0, vmax=1, aspect="auto")
ax.set_xticks(range(len(COLS)))
ax.set_xticklabels([c.replace("<br>", "\n") for c in COL_LABELS], fontsize=9)
ax.set_yticks(range(len(df)))
ax.set_yticklabels(df["label"], fontsize=8)
for tick, grp in zip(ax.get_yticklabels(), df["group"]):
    tick.set_color(GROUP_COLOR[grp])
for i in range(len(df)):
    for j in range(len(COLS)):
        if not np.isnan(M[i, j]):
            ax.text(j, i, f"{M[i, j]:.2f}", ha="center", va="center", fontsize=7.5,
                    color="black" if 0.25 < M[i, j] < 0.8 else "white")
ax.axvline(2.5, color="black", lw=1.5)
ax.set_title("Robust suspicion percentiles by player-game\n(red = suspicious; grey = price N/A)")
fig2.colorbar(im, ax=ax, fraction=0.035, pad=0.03, label="percentile")
fig2.savefig(HERE / "scores_heatmap_robust.png", dpi=120, bbox_inches="tight")

print("wrote scores_heatmap_robust.html / .png")
