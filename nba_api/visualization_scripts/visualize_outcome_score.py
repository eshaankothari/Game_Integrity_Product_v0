"""Outcome-based suspicion z-score from the box scores, shown as a heatmap.

Two components, both oriented so HIGHER = more suspicious, z-scored over the set:
  z_margin  =  z(margin_vs_line)      big UNDER (line - points) scores high
  z_lowmin  = -z(minutes played)      FEW minutes scores high
  outcome_score = mean(z_margin, z_lowmin)   equal-weighted

Heatmap columns: z_margin | z_lowmin | OUTCOME SCORE, rows sorted most -> least
suspicious, labels tinted by group (flagged red / control blue).

    python visualize_outcome_score.py
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
KF = HERE.parent / "Key Figures"
_root = HERE
while not (_root / "datapaths.py").exists() and _root.parent != _root:
    _root = _root.parent
sys.path.insert(0, str(_root))
from datapaths import find_data           # noqa: E402  (repo-root helper)
CSV = find_data("test_dataset_jan_mar_boxscores.csv")
OUT = KF / "test_dataset_jan_mar_outcome_scored.csv"


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


def z(s):
    return (s - s.mean()) / s.std()


df = pd.read_csv(CSV).dropna(subset=["margin_vs_line"]).reset_index(drop=True)
df["min_f"] = df["minutes"].map(_min_to_float)

df["z_margin"] = z(df["margin_vs_line"])        # big under -> high
df["z_lowmin"] = -z(df["min_f"])                # few minutes -> high
df["outcome_score"] = df[["z_margin", "z_lowmin"]].mean(axis=1)

df = df.sort_values("outcome_score", ascending=False).reset_index(drop=True)
df["d"] = pd.to_datetime(df["date"]).dt.strftime("%b %d")
df["label"] = df["player"] + " — " + df["d"] + " (" + df["group"] + ")"
df.round(3).to_csv(OUT, index=False)

COLS = ["z_margin", "z_lowmin", "outcome_score"]
COL_LABELS = ["z margin<br>(under)", "z low-min<br>(few min)", "OUTCOME<br>SCORE"]
M = df[COLS].to_numpy(dtype=float)
vmax = np.nanmax(np.abs(M))
GROUP_COLOR = {"flagged": "#d62728", "control": "#1f77b4"}

# --- interactive HTML ---
custom = np.dstack([np.tile(df["player"].to_numpy()[:, None], (1, len(COLS))),
                    np.tile(df["game"].to_numpy()[:, None], (1, len(COLS))),
                    np.tile(df["d"].to_numpy()[:, None], (1, len(COLS))),
                    np.tile(df["points"].to_numpy()[:, None], (1, len(COLS))),
                    np.tile(df["close_line"].to_numpy()[:, None], (1, len(COLS))),
                    np.tile(df["minutes"].to_numpy()[:, None], (1, len(COLS)))])
fig = go.Figure(go.Heatmap(
    z=M, x=[c.replace("<br>", " ") for c in COL_LABELS], y=df["label"],
    colorscale="RdBu_r", zmid=0, zmin=-vmax, zmax=vmax,
    text=np.round(M, 2).astype(str), texttemplate="%{text}", textfont={"size": 10},
    customdata=custom,
    hovertemplate=("<b>%{customdata[0]}</b><br>%{customdata[1]} — %{customdata[2]}<br>"
                   "points %{customdata[3]} vs line %{customdata[4]}, %{customdata[5]} min<br>"
                   "%{x}: %{z:.2f}<extra></extra>"),
    colorbar=dict(title="z"),
))
fig.update_layout(title="Outcome-based suspicion (big under + few minutes)",
                  yaxis=dict(autorange="reversed"), height=900, width=680)
fig.write_html(KF / "outcome_score_heatmap.html")

# --- static PNG ---
fig2, ax = plt.subplots(figsize=(6.5, 13))
im = ax.imshow(M, cmap=plt.cm.RdBu_r, vmin=-vmax, vmax=vmax, aspect="auto")
ax.set_xticks(range(len(COLS)))
ax.set_xticklabels([c.replace("<br>", "\n") for c in COL_LABELS], fontsize=9)
ax.set_yticks(range(len(df))); ax.set_yticklabels(df["label"], fontsize=7.5)
for tick, grp in zip(ax.get_yticklabels(), df["group"]):
    tick.set_color(GROUP_COLOR[grp])
for i in range(len(df)):
    for j in range(len(COLS)):
        ax.text(j, i, f"{M[i, j]:.2f}", ha="center", va="center", fontsize=7,
                color="black" if abs(M[i, j]) < vmax * 0.6 else "white")
ax.axvline(1.5, color="black", lw=1.5)
ax.set_title("Outcome-based suspicion score\n(red = big under & few minutes)")
fig2.colorbar(im, ax=ax, fraction=0.035, pad=0.03, label="z")
fig2.savefig(KF / "outcome_score_heatmap.png", dpi=120, bbox_inches="tight")

print(f"wrote outcome_score_heatmap.html / .png and {OUT.name} ({len(df)} games)")
print("\nmean outcome_score by group:")
print(df.groupby("group")["outcome_score"].mean().round(3).to_string())
print("\ncorr(z_margin, z_lowmin):", round(df["z_margin"].corr(df["z_lowmin"]), 3))
print("\ntop 6:")
print(df.head(6)[["player", "group", "d", "points", "close_line", "minutes",
                  "z_margin", "z_lowmin", "outcome_score"]].to_string(index=False))
