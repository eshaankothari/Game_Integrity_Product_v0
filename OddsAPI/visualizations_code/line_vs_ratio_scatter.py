"""Scatter normalized line move (y) vs closing Over/Under price ratio (x).

One dot per player-game from the Jan-Mar test set:
  x = close_over / close_under   (>1 => Under is the shorter/favored side)
  y = (close_line - start_line) / start_line  (normalized line move, %)
Hover shows full player-game metadata. Colored by player, shaped by group.

    python line_vs_ratio_scatter.py
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
GROUP_MARKER = {"flagged": "o", "control": "D"}

df = pd.read_csv(CSV)
df = df.dropna(subset=["start_line", "close_line", "close_over", "close_under"])
df["line_move_pct"] = (df["close_line"] - df["start_line"]) / df["start_line"] * 100
df["ou_ratio"] = df["close_over"] / df["close_under"]     # >1 => Under favored
df["date"] = pd.to_datetime(df["time"]).dt.strftime("%Y-%m-%d")

# --- interactive HTML ---
fig = px.scatter(
    df, x="ou_ratio", y="line_move_pct",
    color="player", symbol="group", color_discrete_map=COLORS,
    hover_name="player",
    hover_data={"game": True, "date": True, "group": True,
                "start_line": True, "close_line": True,
                "close_over": True, "close_under": True,
                "ou_ratio": ":.3f", "line_move_pct": ":.1f", "player": False},
    title="Normalized line move vs closing Over/Under price ratio — Jan-Mar test set",
)
fig.update_traces(marker=dict(size=12, line=dict(width=0.6, color="black")))
fig.add_hline(y=0, line_color="grey", line_width=1)
fig.add_vline(x=1.0, line_color="grey", line_width=1, line_dash="dash",
              annotation_text="even (over=under)")
fig.update_layout(xaxis_title="closing Over/Under price ratio  (>1 = Under favored)",
                  yaxis_title="line move (% of start)")
fig.write_html(HERE / "line_vs_ratio_scatter.html")

# --- static PNG ---
fig2, ax = plt.subplots(figsize=(9, 6.5))
ax.axhline(0, color="grey", lw=1)
ax.axvline(1.0, color="grey", lw=1, ls="--", label="even (over=under)")
for player, color in COLORS.items():
    d = df[df["player"] == player]
    if d.empty:
        continue
    grp = d["group"].iloc[0]
    ax.scatter(d["ou_ratio"], d["line_move_pct"], s=90, color=color,
               marker=GROUP_MARKER[grp], edgecolor="black", linewidth=0.4,
               label=f"{player} ({grp})", zorder=3)
ax.set_xlabel("closing Over/Under price ratio  (>1 = Under favored)")
ax.set_ylabel("line move (% of start)")
ax.set_title("Normalized line move vs closing Over/Under price ratio — Jan-Mar test set")
ax.grid(True, alpha=0.3)
ax.legend(fontsize=8, loc="best")
fig2.savefig(HERE / "line_vs_ratio_scatter.png", dpi=110, bbox_inches="tight")

print(f"{len(df)} player-games plotted -> line_vs_ratio_scatter.html / .png")
print("\nmean by group:")
print(df.groupby("group")[["ou_ratio", "line_move_pct"]].mean().round(3).to_string())
