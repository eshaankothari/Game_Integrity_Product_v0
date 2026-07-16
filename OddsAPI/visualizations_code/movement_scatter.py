"""Scatter normalized line move (y) vs normalized Under-price move (x).

One dot per player-game from the (now 12-player) test set. Both axes are % of
the starting value. Colored by group (flagged red / control blue); hover shows
the player-game.

    python movement_scatter.py
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
df["price_move_pct"] = (df["close_under"] - df["start_under"]) / df["start_under"] * 100
df["date"] = pd.to_datetime(df["time"], format="mixed").dt.strftime("%Y-%m-%d")
df = df.dropna(subset=["line_move_pct", "price_move_pct"])

# --- interactive HTML ---
fig = px.scatter(
    df, x="price_move_pct", y="line_move_pct",
    color="group", symbol="group", color_discrete_map=GROUP_COLOR,
    hover_name="player",
    hover_data={"game": True, "date": True, "group": False,
                "price_move_pct": ":.1f", "line_move_pct": ":.1f"},
    title=f"Line move vs Under-price move (normalized) — {df['player'].nunique()} players",
)
fig.update_traces(marker=dict(size=11, line=dict(width=0.5, color="black")))
fig.add_hline(y=0, line_color="grey", line_width=1)
fig.add_vline(x=0, line_color="grey", line_width=1)
fig.update_layout(xaxis_title="Under price move (% of start)",
                  yaxis_title="line move (% of start)")
fig.write_html(KF / "movement_scatter.html")

# --- static PNG ---
fig2, ax = plt.subplots(figsize=(9, 7))
ax.axhline(0, color="grey", lw=1); ax.axvline(0, color="grey", lw=1)
for grp, color in GROUP_COLOR.items():
    d = df[df["group"] == grp]
    ax.scatter(d["price_move_pct"], d["line_move_pct"], s=80, color=color,
               marker=GROUP_MARKER[grp], edgecolor="black", linewidth=0.4,
               alpha=0.85, label=f"{grp} (n={len(d)})", zorder=3)
ax.set_xlabel("Under price move (% of start)")
ax.set_ylabel("line move (% of start)")
ax.set_title(f"Line move vs Under-price move (normalized) — {df['player'].nunique()} players")
ax.grid(True, alpha=0.3); ax.legend()
fig2.savefig(KF / "movement_scatter.png", dpi=110, bbox_inches="tight")

print(f"{len(df)} player-games -> movement_scatter.html / .png")
print(df.groupby("group")[["line_move_pct", "price_move_pct"]].mean().round(2).to_string())
