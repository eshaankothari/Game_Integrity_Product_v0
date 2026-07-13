"""Rank players by their average player_points Under closing price (desc).

Writes player_avg_under_ranking.csv: player | games | avg_under_price, sorted
highest average first. A high average = the Under was priced as a longshot
(market expected the player to go Over); a low average = the Under was juiced.

    python rank_unders.py
"""
from pathlib import Path
import pandas as pd

_HERE = Path(__file__).parent
CSV = next((p for p in [_HERE / "Key Figures" / "closing_under_prices.csv",
                        _HERE / "closing_under_prices.csv"] if p.exists()), None)
if CSV is None:
    raise SystemExit("closing_under_prices.csv not found in Key Figures/ or project root")

df = pd.read_csv(CSV)
df["closing_price"] = pd.to_numeric(df["closing_price"], errors="coerce")
df = df.dropna(subset=["closing_price"])

rank = (df.groupby("player")["closing_price"]
          .agg(games="count", avg_under_price="mean")
          .reset_index()
          .sort_values("avg_under_price", ascending=False))
rank["avg_under_price"] = rank["avg_under_price"].round(3)

out = _HERE / "player_avg_under_ranking.csv"
rank.to_csv(out, index=False)

pd.set_option("display.max_rows", 30)
print(f"{len(rank)} players ranked -> {out.name}\n")
print("=== TOP 15 highest average Under price ===")
print(rank.head(15).to_string(index=False))
print("\n=== BOTTOM 15 lowest average Under price (most juiced unders) ===")
print(rank.tail(15).to_string(index=False))
