"""Scatter normalized line move (y) vs closing Over/Under price ratio (x).

One dot per player-game from the (now 12-player) test set:
  x = close_over / close_under   (>1 => Under is the shorter/favored side)
  y = (close_line - start_line) / start_line  (normalized line move, %)
Colored by group (flagged red / control blue); hover shows the player-game.

    python line_vs_ratio_scatter.py
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
df["line_move_pct"] = (df["close_line"] - df["start_line"]) / df["start_line"] * 100
df["ou_ratio"] = df["close_over"] / df["close_under"]     # >1 => Under favored
df["date"] = pd.to_datetime(df["time"], format="mixed").dt.strftime("%Y-%m-%d")
df = df.dropna(subset=["line_move_pct", "ou_ratio"])

# --- interactive HTML ---
fig = px.scatter(
    df, x="ou_ratio", y="line_move_pct",
    color="group", symbol="group", color_discrete_map=GROUP_COLOR,
    hover_name="player",
    hover_data={"game": True, "date": True, "group": False,
                "close_over": True, "close_under": True,
                "ou_ratio": ":.3f", "line_move_pct": ":.1f"},
    title=f"Normalized line move vs closing O/U ratio — {df['player'].nunique()} players",
)
fig.update_traces(marker=dict(size=11, line=dict(width=0.5, color="black")))
fig.add_hline(y=0, line_color="grey", line_width=1)
fig.add_vline(x=1.0, line_color="grey", line_width=1, line_dash="dash",
              annotation_text="even (over=under)")
fig.update_layout(xaxis_title="closing Over/Under price ratio  (>1 = Under favored)",
                  yaxis_title="line move (% of start)")
fig.write_html(KF / "line_vs_ratio_scatter.html")

# --- static PNG ---
fig2, ax = plt.subplots(figsize=(9, 6.5))
ax.axhline(0, color="grey", lw=1)
ax.axvline(1.0, color="grey", lw=1, ls="--", label="even (over=under)")
for grp, color in GROUP_COLOR.items():
    d = df[df["group"] == grp]
    ax.scatter(d["ou_ratio"], d["line_move_pct"], s=80, color=color,
               marker=GROUP_MARKER[grp], edgecolor="black", linewidth=0.4,
               alpha=0.85, label=f"{grp} (n={len(d)})", zorder=3)
ax.set_xlabel("closing Over/Under price ratio  (>1 = Under favored)")
ax.set_ylabel("line move (% of start)")
ax.set_title(f"Normalized line move vs closing O/U ratio — {df['player'].nunique()} players")
ax.grid(True, alpha=0.3); ax.legend()
fig2.savefig(KF / "line_vs_ratio_scatter.png", dpi=110, bbox_inches="tight")

print(f"{len(df)} player-games -> line_vs_ratio_scatter.html / .png")
print(df.groupby("group")[["ou_ratio", "line_move_pct"]].mean().round(3).to_string())
