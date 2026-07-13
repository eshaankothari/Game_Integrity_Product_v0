"""Scatter every player_points Under closing price; hover shows the player-game.

x = game tip-off time, y = Under closing decimal odds, one dot per player-game.
Three investigated players are highlighted in distinct colors; everyone else is
muted grey. Writes an interactive HTML (hover = player + game) and a static PNG.

    python scatter_unders.py
"""
import pandas as pd
import plotly.express as px

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# The CSV lives in the Key Figures/ folder; fall back to the project root.
from pathlib import Path
_HERE = Path(__file__).parent
CSV = next((p for p in [_HERE / "Key Figures" / "closing_under_prices.csv",
                        _HERE / "closing_under_prices.csv"] if p.exists()), None)
if CSV is None:
    raise SystemExit("closing_under_prices.csv not found in Key Figures/ or project root")

# Players to highlight, each with its own color. Everyone else -> "Other".
HIGHLIGHT = {
    "Jontay Porter": "#d62728",   # red
    "Malik Beasley": "#2ca02c",   # green
    "Terry Rozier": "#9467bd",    # purple
}
OTHER_COLOR = "lightgrey"

df = pd.read_csv(CSV)
df["time"] = pd.to_datetime(df["time"])
df["closing_price"] = pd.to_numeric(df["closing_price"], errors="coerce")
df = df.dropna(subset=["closing_price"])

df["highlight"] = df["player"].where(df["player"].isin(HIGHLIGHT), "Other")

hover_cols = {"player": True, "game": True, "time": True,
              "bet type": True, "closing_price": True, "highlight": False}
color_map = {"Other": OTHER_COLOR, **HIGHLIGHT}
order = ["Other", *HIGHLIGHT]          # "Other" first so it's drawn underneath

# --- interactive HTML ---
fig = px.scatter(
    df, x="time", y="closing_price",
    color="highlight", color_discrete_map=color_map, category_orders={"highlight": order},
    hover_name="player", hover_data=hover_cols,
    title=f"NBA player_points Under closing odds (2023-24) — highlighted players",
)
fig.update_traces(marker=dict(size=5, opacity=0.30), selector=dict(name="Other"))
for name in HIGHLIGHT:
    fig.update_traces(marker=dict(size=11, opacity=0.95,
                                  line=dict(width=0.6, color="black")),
                      selector=dict(name=name))
fig.update_layout(xaxis_title="game tip-off", yaxis_title="Under closing decimal odds",
                  legend_title_text="player")
fig.write_html("unders_scatter.html")

# --- static PNG ---
fig2, ax = plt.subplots(figsize=(12, 5))
other = df[df["highlight"] == "Other"]
ax.scatter(other["time"], other["closing_price"], s=6, alpha=0.18,
           color=OTHER_COLOR, label=f"Other ({len(other):,})")
for name, color in HIGHLIGHT.items():
    d = df[df["player"] == name]
    ax.scatter(d["time"], d["closing_price"], s=45, alpha=0.95, color=color,
               edgecolor="black", linewidth=0.4, label=f"{name} ({len(d)})", zorder=3)
ax.set_xlabel("game tip-off")
ax.set_ylabel("Under closing decimal odds")
ax.set_title("NBA player_points Under closing odds (2023-24) — highlighted players")
ax.grid(True, alpha=0.3)
ax.legend(loc="upper right", framealpha=0.9)
fig2.savefig("unders_scatter.png", dpi=110, bbox_inches="tight")

print(f"{len(df):,} unders plotted; highlighted:")
for name in HIGHLIGHT:
    print(f"  {name}: {(df['player'] == name).sum()} games")
print("  interactive: unders_scatter.html   static: unders_scatter.png")
