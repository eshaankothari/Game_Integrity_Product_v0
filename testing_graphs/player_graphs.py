"""One graph per investigated player: their player_points Under closing odds.

For each player, writes a static PNG and an interactive HTML (hover = game +
date + price) into player_graphs/. A dashed line marks the league-wide median
Under price, so you can see whether a player's Unders sit unusually low
(= market leaning toward them going Under).

    python player_graphs.py
"""
from pathlib import Path

import pandas as pd
import plotly.express as px

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

PLAYERS = {
    "Jontay Porter": "#d62728",   # red
    "Malik Beasley": "#2ca02c",   # green
    "Terry Rozier": "#9467bd",    # purple
}

import sys
_HERE = Path(__file__).parent
_root = _HERE
while not (_root / "datapaths.py").exists() and _root.parent != _root:
    _root = _root.parent
sys.path.insert(0, str(_root))
from datapaths import find_data           # noqa: E402  (repo-root helper)
CSV = find_data("closing_under_prices.csv")

OUT = _HERE / "player_graphs"
OUT.mkdir(exist_ok=True)


def _safe(name):
    return name.replace(" ", "_")


df = pd.read_csv(CSV)
df["time"] = pd.to_datetime(df["time"])
df["closing_price"] = pd.to_numeric(df["closing_price"], errors="coerce")
df = df.dropna(subset=["closing_price"])
league_median = df["closing_price"].median()

for player, color in PLAYERS.items():
    d = df[df["player"] == player].sort_values("time")
    if d.empty:
        print(f"  {player}: no rows, skipped")
        continue

    # --- static PNG ---
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.axhline(league_median, ls="--", color="grey", alpha=0.7,
               label=f"league median ({league_median:.2f})")
    ax.scatter(d["time"], d["closing_price"], s=55, color=color,
               edgecolor="black", linewidth=0.4, zorder=3)
    ax.set_title(f"{player} — player_points Under closing odds ({len(d)} games)")
    ax.set_xlabel("game tip-off")
    ax.set_ylabel("Under closing decimal odds")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best")
    fig.autofmt_xdate()
    fig.savefig(OUT / f"{_safe(player)}_unders.png", dpi=110, bbox_inches="tight")
    plt.close(fig)

    # --- interactive HTML (hover = game + date + price) ---
    ifig = px.scatter(
        d, x="time", y="closing_price",
        hover_name="player",
        hover_data={"game": True, "time": True, "closing_price": True, "player": False},
        title=f"{player} — player_points Under closing odds ({len(d)} games)",
    )
    ifig.update_traces(marker=dict(size=10, color=color,
                                   line=dict(width=0.6, color="black")))
    ifig.add_hline(y=league_median, line_dash="dash", line_color="grey",
                   annotation_text=f"league median {league_median:.2f}")
    ifig.update_layout(xaxis_title="game tip-off",
                       yaxis_title="Under closing decimal odds")
    ifig.write_html(OUT / f"{_safe(player)}_unders.html")

    print(f"  {player}: {len(d)} games | median under {d['closing_price'].median():.2f} "
          f"| min {d['closing_price'].min():.2f}")

print(f"league median under price: {league_median:.2f}")
print(f"graphs written to {OUT.name}/  (one PNG + one HTML per player)")
