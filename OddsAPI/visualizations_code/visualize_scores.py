"""Heatmap of the z-score components + final suspicious_score per player-game.

Rows = player-games (sorted most -> least suspicious), columns = z1, z2, z3 and
the final score. Diverging color: red = high (suspicious), blue = low. Row labels
carry the metadata (player, date, group); group also tints the label color.

    python visualize_scores.py
"""
from pathlib import Path
import numpy as np
import pandas as pd
import plotly.graph_objects as go

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).parent
KF = HERE.parent / "Key Figures"          # OddsAPI/Key Figures (up from visualizations_code/)
CSV = KF / "test_dataset_jan_mar_scored.csv"

df = pd.read_csv(CSV).sort_values("suspicious_score", ascending=False).reset_index(drop=True)
df["date"] = pd.to_datetime(df["time"], format="mixed").dt.strftime("%b %d")
df["label"] = df["player"] + " — " + df["date"] + " (" + df["group"] + ")"

COLS = ["z1", "z2", "suspicious_score"]
COL_LABELS = ["z1<br>line", "z2<br>price|pinned", "SUSPICIOUS<br>SCORE"]
M = df[COLS].to_numpy(dtype=float)
vmax = np.nanmax(np.abs(M))

GROUP_COLOR = {"flagged": "#d62728", "control": "#1f77b4"}

# --- interactive HTML (hover = full metadata) ---
custom = np.dstack([np.tile(df["player"].to_numpy()[:, None], (1, len(COLS))),
                    np.tile(df["game"].to_numpy()[:, None], (1, len(COLS))),
                    np.tile(df["date"].to_numpy()[:, None], (1, len(COLS))),
                    np.tile(df["group"].to_numpy()[:, None], (1, len(COLS)))])
fig = go.Figure(go.Heatmap(
    z=M, x=[c.replace("<br>", " ") for c in COL_LABELS], y=df["label"],
    colorscale="RdBu_r", zmid=0, zmin=-vmax, zmax=vmax,
    text=np.where(np.isnan(M), "", np.round(M, 2).astype(str)),
    texttemplate="%{text}", textfont={"size": 10},
    customdata=custom,
    hovertemplate=("<b>%{customdata[0]}</b> (%{customdata[3]})<br>"
                   "%{customdata[1]} — %{customdata[2]}<br>"
                   "%{x}: %{z:.2f}<extra></extra>"),
    colorbar=dict(title="z"),
))
fig.update_layout(title="Suspicious-trading z-scores by player-game (Jan-Mar test set)",
                  yaxis=dict(autorange="reversed"), height=760, width=760)
fig.write_html(KF / "scores_heatmap.html")

# --- static PNG ---
masked = np.ma.masked_invalid(M)
cmap = plt.cm.RdBu_r.copy(); cmap.set_bad("lightgrey")
fig2, ax = plt.subplots(figsize=(7.5, 11))
im = ax.imshow(masked, cmap=cmap, vmin=-vmax, vmax=vmax, aspect="auto")
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
                    color="black" if abs(M[i, j]) < vmax * 0.6 else "white")
ax.axvline(1.5, color="black", lw=1.5)   # separate components from final score
ax.set_title("Suspicious-trading z-scores by player-game\n(red = suspicious; grey = z2 N/A)")
fig2.colorbar(im, ax=ax, fraction=0.035, pad=0.03, label="z")
fig2.savefig(KF / "scores_heatmap.png", dpi=120, bbox_inches="tight")

print("wrote scores_heatmap.html / .png")
