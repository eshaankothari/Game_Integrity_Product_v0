"""Scatter normalized line move (y) vs normalized Under-price move (x).

One dot per player-game from the Jan-Mar test set. Both axes are % of the
starting value, so scoring level doesn't distort the comparison:
  x = (close_under - start_under) / start_under
  y = (close_line  - start_line)  / start_line
Hover shows the full player-game metadata. Colored by player, shaped by group.

    python movement_scatter.py
"""
from pathlib import Path
import pandas as pd
import plotly.express as px

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).parent
CSV = HERE / "Key Figures" / "test_dataset_jan_mar.csv"

COLORS = {
    "Jontay Porter": "#d62728", "Malik Beasley": "#2ca02c", "Terry Rozier": "#9467bd",
    "Nikola Jokic": "#1f77b4", "Giannis Antetokounmpo": "#ff7f0e", "Jayson Tatum": "#8c564b",
}
GROUP_MARKER = {"flagged": "o", "control": "D"}   # matplotlib markers

df = pd.read_csv(CSV)
df = df.dropna(subset=["start_line", "start_under", "close_line", "close_under"])
df["line_move_pct"] = (df["close_line"] - df["start_line"]) / df["start_line"] * 100
df["price_move_pct"] = (df["close_under"] - df["start_under"]) / df["start_under"] * 100
df["date"] = pd.to_datetime(df["time"]).dt.strftime("%Y-%m-%d")

# --- interactive HTML ---
fig = px.scatter(
    df, x="price_move_pct", y="line_move_pct",
    color="player", symbol="group",
    color_discrete_map=COLORS,
    hover_name="player",
    hover_data={"game": True, "date": True, "group": True,
                "start_line": True, "close_line": True,
                "start_under": True, "close_under": True,
                "price_move_pct": ":.1f", "line_move_pct": ":.1f",
                "player": False},
    title="Line move vs Under-price move (normalized) — Jan-Mar test set",
)
fig.update_traces(marker=dict(size=12, line=dict(width=0.6, color="black")))
fig.add_hline(y=0, line_color="grey", line_width=1)
fig.add_vline(x=0, line_color="grey", line_width=1)
fig.update_layout(xaxis_title="Under price move (% of start)",
                  yaxis_title="Line move (% of start)")
fig.write_html(HERE / "movement_scatter.html")

# --- static PNG ---
fig2, ax = plt.subplots(figsize=(9, 7))
ax.axhline(0, color="grey", lw=1); ax.axvline(0, color="grey", lw=1)
for player, color in COLORS.items():
    d = df[df["player"] == player]
    if d.empty:
        continue
    grp = d["group"].iloc[0]
    ax.scatter(d["price_move_pct"], d["line_move_pct"], s=90, color=color,
               marker=GROUP_MARKER[grp], edgecolor="black", linewidth=0.4,
               label=f"{player} ({grp})", zorder=3)
ax.set_xlabel("Under price move (% of start)")
ax.set_ylabel("Line move (% of start)")
ax.set_title("Line move vs Under-price move (normalized) — Jan-Mar test set")
ax.grid(True, alpha=0.3)
ax.legend(fontsize=8, loc="best")
fig2.savefig(HERE / "movement_scatter.png", dpi=110, bbox_inches="tight")

print(f"{len(df)} player-games plotted -> movement_scatter.html / .png")
print("\nmean normalized move by group:")
print(df.groupby("group")[["line_move_pct", "price_move_pct"]].mean().round(2).to_string())
