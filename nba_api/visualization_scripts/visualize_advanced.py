"""Heatmap of residual + minutes + advanced box-score metrics per player-game.

Reads test_dataset_jan_mar_advanced.csv (from advanced_stats.py). Columns shown:
  residual (line - points)   -- how far under/over the prop line the player landed
  minutes                    -- playing time
  netRating, turnoverRatio, trueShootingPercentage, usagePercentage, pace, PIE

Every column is z-scored across the set so the colors are comparable (red = high
for that metric, blue = low); the printed number in each cell is the RAW value.
Rows sorted by residual (biggest under at top); labels tinted by group.

    python visualize_advanced.py
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
CSV = find_data("test_dataset_jan_mar_advanced.csv")
KF = CSV.parent                            # write outputs next to the data (move-proof)


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


def z(col):
    s = pd.to_numeric(col, errors="coerce")
    sd = s.std()
    return (s - s.mean()) / sd if sd else s * 0.0


df = pd.read_csv(CSV)
df["min_f"] = df["minutes"].map(_min_to_float)
df = df.dropna(subset=["margin_vs_line"]).sort_values("margin_vs_line", ascending=False).reset_index(drop=True)
df["d"] = pd.to_datetime(df["date"]).dt.strftime("%b %d")
df["label"] = df["player"] + " — " + df["d"] + " (" + df["group"] + ")"

# residual + minutes + whichever advanced cols are populated
ADV = ["netRating", "turnoverRatio", "trueShootingPercentage", "usagePercentage", "pace", "PIE"]
ADV = [c for c in ADV if c in df.columns and pd.to_numeric(df[c], errors="coerce").notna().any()]
RAWCOLS = ["margin_vs_line", "min_f"] + ADV
LABELS = ["residual<br>(line−pts)", "minutes", "net<br>rating", "TO<br>ratio",
          "TS%", "usage%", "pace", "PIE"]
LABELS = LABELS[:2] + [LABELS[2 + ["netRating", "turnoverRatio", "trueShootingPercentage",
                                   "usagePercentage", "pace", "PIE"].index(c)] for c in ADV]

Z = np.column_stack([z(df[c]).to_numpy() for c in RAWCOLS])     # color scale
# raw text per cell (minutes keeps mm:ss, others rounded)
def _raw_text(c, i):
    if c == "min_f":
        return "" if pd.isna(df["minutes"].iloc[i]) else str(df["minutes"].iloc[i])
    v = pd.to_numeric(df[c], errors="coerce").iloc[i]
    return "" if pd.isna(v) else f"{v:.1f}"
TXT = np.array([[_raw_text(c, i) for c in RAWCOLS] for i in range(len(df))])
vmax = np.nanmax(np.abs(Z))
GROUP_COLOR = {"flagged": "#d62728", "control": "#1f77b4"}

# --- interactive HTML ---
fig = go.Figure(go.Heatmap(
    z=Z, x=[l.replace("<br>", " ") for l in LABELS], y=df["label"],
    colorscale="RdBu_r", zmid=0, zmin=-vmax, zmax=vmax,
    text=TXT, texttemplate="%{text}", textfont={"size": 9},
    hovertemplate="%{y}<br>%{x}: raw %{text} (z=%{z:.2f})<extra></extra>",
    colorbar=dict(title="z"),
))
fig.update_layout(title="Residual + minutes + advanced metrics (z-scored color, raw labels)",
                  yaxis=dict(autorange="reversed"), height=1000, width=880)
fig.write_html(KF / "advanced_heatmap.html")

# --- static PNG ---
masked = np.ma.masked_invalid(Z)
cmap = plt.cm.RdBu_r.copy(); cmap.set_bad("lightgrey")
fig2, ax = plt.subplots(figsize=(9.5, 14))
im = ax.imshow(masked, cmap=cmap, vmin=-vmax, vmax=vmax, aspect="auto")
ax.set_xticks(range(len(RAWCOLS)))
ax.set_xticklabels([l.replace("<br>", "\n") for l in LABELS], fontsize=9)
ax.set_yticks(range(len(df))); ax.set_yticklabels(df["label"], fontsize=7)
for tick, grp in zip(ax.get_yticklabels(), df["group"]):
    tick.set_color(GROUP_COLOR[grp])
for i in range(len(df)):
    for j in range(len(RAWCOLS)):
        if TXT[i, j]:
            ax.text(j, i, TXT[i, j], ha="center", va="center", fontsize=6.5,
                    color="black" if abs(Z[i, j]) < vmax * 0.6 else "white")
ax.axvline(1.5, color="black", lw=1.5)     # separate residual|minutes from advanced
ax.set_title("Residual + minutes + advanced box-score metrics\n"
             "(color = z-score within column; number = raw value)")
fig2.colorbar(im, ax=ax, fraction=0.03, pad=0.02, label="z within column")
fig2.savefig(KF / "advanced_heatmap.png", dpi=120, bbox_inches="tight")

print(f"wrote advanced_heatmap.html / .png ({len(df)} games, cols: {RAWCOLS})")
