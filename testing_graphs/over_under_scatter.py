"""Scatter normalized Over-price move (x) vs normalized Under-price move (y).

One dot per player-game from the Jan-Mar test set, both axes as % of start:
  x = (close_over  - start_over)  / start_over
  y = (close_under - start_under) / start_under
Over & Under are opposite sides, so pure juice shifts land on the anti-diagonal
(one up, one down). Points where BOTH move the same way = the line itself moved.
Hover shows full player-game metadata. Colored by player, shaped by group.

    python over_under_scatter.py
"""
from pathlib import Path
import pandas as pd
import plotly.express as px

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
CSV = find_data("test_dataset_jan_mar.csv")

COLORS = {
    "Jontay Porter": "#d62728", "Malik Beasley": "#2ca02c", "Terry Rozier": "#9467bd",
    "Nikola Jokic": "#1f77b4", "Giannis Antetokounmpo": "#ff7f0e", "Jayson Tatum": "#8c564b",
}
GROUP_MARKER = {"flagged": "o", "control": "D"}

df = pd.read_csv(CSV)
df = df.dropna(subset=["start_over", "start_under", "close_over", "close_under"])
df["over_move_pct"] = (df["close_over"] - df["start_over"]) / df["start_over"] * 100
df["under_move_pct"] = (df["close_under"] - df["start_under"]) / df["start_under"] * 100
df["date"] = pd.to_datetime(df["time"], format="ISO8601").dt.strftime("%Y-%m-%d")

# --- interactive HTML ---
fig = px.scatter(
    df, x="over_move_pct", y="under_move_pct",
    color="player", symbol="group", color_discrete_map=COLORS,
    hover_name="player",
    hover_data={"game": True, "date": True, "group": True,
                "start_over": True, "close_over": True,
                "start_under": True, "close_under": True,
                "start_line": True, "close_line": True,
                "over_move_pct": ":.1f", "under_move_pct": ":.1f", "player": False},
    title="Over vs Under price move (normalized) — Jan-Mar test set",
)
fig.update_traces(marker=dict(size=12, line=dict(width=0.6, color="black")))
fig.add_hline(y=0, line_color="grey", line_width=1)
fig.add_vline(x=0, line_color="grey", line_width=1)
fig.update_layout(xaxis_title="Over price move (% of start)",
                  yaxis_title="Under price move (% of start)")
fig.write_html(HERE / "over_under_scatter.html")

# --- static PNG ---
fig2, ax = plt.subplots(figsize=(8.5, 7.5))
ax.axhline(0, color="grey", lw=1); ax.axvline(0, color="grey", lw=1)
lim = max(df["over_move_pct"].abs().max(), df["under_move_pct"].abs().max()) * 1.1
ax.plot([-lim, lim], [lim, -lim], ls=":", color="grey", alpha=0.6,
        label="pure juice shift (anti-diagonal)")
for player, color in COLORS.items():
    d = df[df["player"] == player]
    if d.empty:
        continue
    grp = d["group"].iloc[0]
    ax.scatter(d["over_move_pct"], d["under_move_pct"], s=90, color=color,
               marker=GROUP_MARKER[grp], edgecolor="black", linewidth=0.4,
               label=f"{player} ({grp})", zorder=3)
ax.set_xlabel("Over price move (% of start)")
ax.set_ylabel("Under price move (% of start)")
ax.set_title("Over vs Under price move (normalized) — Jan-Mar test set")
ax.grid(True, alpha=0.3)
ax.legend(fontsize=8, loc="best")
fig2.savefig(HERE / "over_under_scatter.png", dpi=110, bbox_inches="tight")

print(f"{len(df)} player-games plotted -> over_under_scatter.html / .png")
print("\nmean normalized move by group:")
print(df.groupby("group")[["over_move_pct", "under_move_pct"]].mean().round(2).to_string())
