"""Scatter normalized line move (y) vs prop-open duration (x).

One dot per player-game from the Jan-Mar test set:
  x = close_snapshot - start_snapshot   (hours between our two snapshots)
  y = (close_line - start_line) / start_line   (normalized line move, %)

CAVEAT: duration here is mostly the sampling window (start offset was -12h for
most, -3h for late openers, -10min for Porter), NOT the true market-open time.
Porter's short duration is genuine (his line existed only minutes before tip);
the others' durations reflect where we chose/could take the opening snapshot.

    python line_vs_duration_scatter.py
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
df = df.dropna(subset=["start_line", "close_line", "start_snapshot", "close_snapshot"])
df["line_move_pct"] = (df["close_line"] - df["start_line"]) / df["start_line"] * 100
df["duration_h"] = ((pd.to_datetime(df["close_snapshot"], format="ISO8601") - pd.to_datetime(df["start_snapshot"], format="ISO8601"))
                    .dt.total_seconds() / 3600)
df["date"] = pd.to_datetime(df["time"], format="ISO8601").dt.strftime("%Y-%m-%d")

# --- interactive HTML ---
fig = px.scatter(
    df, x="duration_h", y="line_move_pct",
    color="player", symbol="group", color_discrete_map=COLORS,
    hover_name="player",
    hover_data={"game": True, "date": True, "group": True,
                "start_snapshot": True, "close_snapshot": True,
                "start_line": True, "close_line": True,
                "duration_h": ":.2f", "line_move_pct": ":.1f", "player": False},
    title="Normalized line move vs prop-open duration — Jan-Mar test set",
)
fig.update_traces(marker=dict(size=12, line=dict(width=0.6, color="black")))
fig.add_hline(y=0, line_color="grey", line_width=1)
fig.update_layout(xaxis_title="prop-open duration (hours between start & close snapshot)",
                  yaxis_title="line move (% of start)")
fig.write_html(HERE / "line_vs_duration_scatter.html")

# --- static PNG ---
fig2, ax = plt.subplots(figsize=(9, 6.5))
ax.axhline(0, color="grey", lw=1)
for player, color in COLORS.items():
    d = df[df["player"] == player]
    if d.empty:
        continue
    grp = d["group"].iloc[0]
    ax.scatter(d["duration_h"], d["line_move_pct"], s=90, color=color,
               marker=GROUP_MARKER[grp], edgecolor="black", linewidth=0.4,
               label=f"{player} ({grp})", zorder=3)
ax.set_xlabel("prop-open duration (hours between start & close snapshot)")
ax.set_ylabel("line move (% of start)")
ax.set_title("Normalized line move vs prop-open duration — Jan-Mar test set")
ax.grid(True, alpha=0.3)
ax.legend(fontsize=8, loc="best")
fig2.savefig(HERE / "line_vs_duration_scatter.png", dpi=110, bbox_inches="tight")

print(f"{len(df)} player-games plotted -> line_vs_duration_scatter.html / .png")
print("\nduration (h) by player:")
print(df.groupby("player")["duration_h"].agg(["min", "max"]).round(2).to_string())
