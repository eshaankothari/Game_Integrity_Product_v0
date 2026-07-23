"""Heatmap of margin_vs_line (closing prop line - actual points) per player-game.

margin_vs_line > 0  => player scored UNDER the line  (red)
margin_vs_line < 0  => player scored OVER the line   (blue)
Rows sorted most-under -> most-over; row labels carry player/date, tinted by
group (flagged red / control blue). Hover (HTML) shows points vs line + result.

    python visualize_margin.py
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

df = pd.read_csv(CSV).dropna(subset=["margin_vs_line"])
df = df.sort_values("margin_vs_line", ascending=False).reset_index(drop=True)
df["d"] = pd.to_datetime(df["date"]).dt.strftime("%b %d")
df["label"] = df["player"] + " — " + df["d"] + " (" + df["group"] + ")"


def _min_to_float(m):
    """'38:25' -> 38.42 decimal minutes; blanks/NaN -> nan."""
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


df["min_f"] = df["minutes"].map(_min_to_float)

M = df[["margin_vs_line"]].to_numpy(dtype=float)
MN = df[["min_f"]].to_numpy(dtype=float)
vmax = np.nanmax(np.abs(M))
GROUP_COLOR = {"flagged": "#d62728", "control": "#1f77b4"}

# --- interactive HTML (two panels: margin | minutes, each its own colorscale) ---
from plotly.subplots import make_subplots
custom = np.column_stack([df["player"], df["game"], df["d"],
                          df["points"], df["close_line"], df["result"], df["minutes"]])[:, None, :]
figi = make_subplots(rows=1, cols=2, shared_yaxes=True, horizontal_spacing=0.03,
                     column_widths=[0.55, 0.45])
figi.add_trace(go.Heatmap(
    z=M, x=["margin (line − pts)"], y=df["label"],
    colorscale="RdBu_r", zmid=0, zmin=-vmax, zmax=vmax,
    text=np.round(M, 1).astype(str), texttemplate="%{text}", textfont={"size": 10},
    customdata=custom,
    hovertemplate=("<b>%{customdata[0][0]}</b><br>%{customdata[0][1]} — %{customdata[0][2]}<br>"
                   "points %{customdata[0][3]} vs line %{customdata[0][4]} → "
                   "%{customdata[0][5]}<br>minutes %{customdata[0][6]}<extra></extra>"),
    colorbar=dict(title="margin", x=0.44)), row=1, col=1)
figi.add_trace(go.Heatmap(
    z=MN, x=["minutes"], y=df["label"],
    colorscale="Greys", zmin=0, zmax=np.nanmax(MN),
    text=df["minutes"].fillna("").astype(str).to_numpy()[:, None],
    texttemplate="%{text}", textfont={"size": 9},
    customdata=custom,
    hovertemplate=("<b>%{customdata[0][0]}</b><br>minutes %{customdata[0][6]}<extra></extra>"),
    colorbar=dict(title="min", x=1.0)), row=1, col=2)
figi.update_layout(title="Points vs closing line (margin) + minutes played",
                   yaxis=dict(autorange="reversed"), height=900, width=720)
figi.write_html(KF / "margin_heatmap.html")

# --- static PNG (two panels sharing rows: margin | minutes) ---
fig2, (ax, axm) = plt.subplots(1, 2, figsize=(6.4, 13), sharey=True,
                               gridspec_kw={"width_ratios": [1, 1], "wspace": 0.08})
im = ax.imshow(M, cmap=plt.cm.RdBu_r, vmin=-vmax, vmax=vmax, aspect="auto")
ax.set_xticks([0]); ax.set_xticklabels(["margin\n(line − pts)\nred = UNDER"], fontsize=9)
ax.set_yticks(range(len(df))); ax.set_yticklabels(df["label"], fontsize=7.5)
for tick, grp in zip(ax.get_yticklabels(), df["group"]):
    tick.set_color(GROUP_COLOR[grp])
for i in range(len(df)):
    ax.text(0, i, f"{M[i, 0]:.1f}", ha="center", va="center", fontsize=7,
            color="black" if abs(M[i, 0]) < vmax * 0.6 else "white")
ax.set_title("Points vs line\n(red = UNDER)")
fig2.colorbar(im, ax=ax, fraction=0.05, pad=0.04, label="line − points")

mmax = np.nanmax(MN)
imm = axm.imshow(MN, cmap=plt.cm.Greys, vmin=0, vmax=mmax, aspect="auto")
axm.set_xticks([0]); axm.set_xticklabels(["minutes\nplayed"], fontsize=9)
for i in range(len(df)):
    v = MN[i, 0]
    axm.text(0, i, "" if np.isnan(v) else df["minutes"].iloc[i], ha="center", va="center",
             fontsize=6.5, color="white" if v > mmax * 0.6 else "black")
axm.set_title("Minutes\n(darker = more)")
fig2.colorbar(imm, ax=axm, fraction=0.05, pad=0.04, label="minutes")
fig2.savefig(KF / "margin_heatmap.png", dpi=120, bbox_inches="tight")

print(f"wrote margin_heatmap.html / .png ({len(df)} games)")
print("\nmean margin by group (higher = more under):")
print(df.groupby("group")["margin_vs_line"].mean().round(2).to_string())
print("\nunder rate by group:")
print(df.assign(under=df["result"].eq("UNDER")).groupby("group")["under"].mean().round(3).to_string())

import slideshow           # noqa: E402  (repo root already on sys.path)
slideshow.add(KF / "margin_heatmap.html", "7 · Outcome: points vs line + minutes",
              "Did the player actually go under? Margin (line − points) with minutes played.")
