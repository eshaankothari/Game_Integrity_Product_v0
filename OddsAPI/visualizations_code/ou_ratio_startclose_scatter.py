"""Scatter starting vs closing Over/Under price ratio, per player-game.

  x = start_over / start_under      (ratio when the line opened)
  y = close_over / close_under      (ratio at tip)
The dashed y=x diagonal = no change. Below it => ratio DROPPED open->close
(Over became more favored, e.g. after a line drop). Grey lines mark ratio = 1
(even). Colored by group (flagged red / control blue); hover = player-game.

    python ou_ratio_startclose_scatter.py
"""
from pathlib import Path
import pandas as pd
import plotly.express as px

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).parent
KF = HERE.parent / "Key Figures"
CSV = KF / "test_dataset_jan_mar.csv"

GROUP_COLOR = {"flagged": "#d62728", "control": "#1f77b4"}
GROUP_MARKER = {"flagged": "o", "control": "D"}

df = pd.read_csv(CSV)
df["start_ratio"] = df["start_over"] / df["start_under"]
df["close_ratio"] = df["close_over"] / df["close_under"]
df["ratio_change"] = df["close_ratio"] - df["start_ratio"]
df["date"] = pd.to_datetime(df["time"], format="mixed").dt.strftime("%Y-%m-%d")
df = df.dropna(subset=["start_ratio", "close_ratio"])

lo = min(df["start_ratio"].min(), df["close_ratio"].min()) - 0.01
hi = max(df["start_ratio"].max(), df["close_ratio"].max()) + 0.01

# --- interactive HTML ---
fig = px.scatter(
    df, x="start_ratio", y="close_ratio",
    color="group", symbol="group", color_discrete_map=GROUP_COLOR,
    hover_name="player",
    hover_data={"game": True, "date": True, "group": False,
                "start_ratio": ":.3f", "close_ratio": ":.3f", "ratio_change": ":.3f"},
    title=f"Starting vs closing O/U ratio — {df['player'].nunique()} players",
)
fig.update_traces(marker=dict(size=11, line=dict(width=0.5, color="black")))
fig.add_shape(type="line", x0=lo, y0=lo, x1=hi, y1=hi, line=dict(color="grey", dash="dash"))
fig.add_hline(y=1.0, line_color="lightgrey", line_width=1)
fig.add_vline(x=1.0, line_color="lightgrey", line_width=1)
fig.update_layout(xaxis_title="starting O/U ratio (over/under)",
                  yaxis_title="closing O/U ratio (over/under)")
fig.write_html(KF / "ou_ratio_startclose_scatter.html")

# --- static PNG ---
fig2, ax = plt.subplots(figsize=(8, 8))
ax.plot([lo, hi], [lo, hi], ls="--", color="grey", label="no change (y=x)")
ax.axhline(1.0, color="lightgrey", lw=1); ax.axvline(1.0, color="lightgrey", lw=1)
for grp, color in GROUP_COLOR.items():
    d = df[df["group"] == grp]
    ax.scatter(d["start_ratio"], d["close_ratio"], s=80, color=color,
               marker=GROUP_MARKER[grp], edgecolor="black", linewidth=0.4,
               alpha=0.85, label=f"{grp} (n={len(d)})", zorder=3)
ax.set_xlabel("starting O/U ratio (over/under)")
ax.set_ylabel("closing O/U ratio (over/under)")
ax.set_title(f"Starting vs closing O/U ratio — {df['player'].nunique()} players")
ax.set_xlim(lo, hi); ax.set_ylim(lo, hi); ax.grid(True, alpha=0.3); ax.legend()
fig2.savefig(KF / "ou_ratio_startclose_scatter.png", dpi=110, bbox_inches="tight")

print(f"{len(df)} player-games -> ou_ratio_startclose_scatter.html / .png")
print(df.groupby("group")[["start_ratio", "close_ratio", "ratio_change"]].mean().round(3).to_string())
