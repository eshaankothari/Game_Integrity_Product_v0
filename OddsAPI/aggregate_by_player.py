"""Aggregate the per-game suspicious_score up to the player level.

Reads test_dataset_jan_mar_scored.csv and, per player, reports:
  n_games, n_suspicious (games with score >= THRESHOLD), cumulative (sum),
  mean, max. Ranked by n_suspicious then cumulative. Writes a ranking CSV.

    python aggregate_by_player.py
"""
from pathlib import Path
import pandas as pd

HERE = Path(__file__).parent
KF = HERE / "Key Figures"
SRC = KF / "test_dataset_jan_mar_scored.csv"
OUT = KF / "player_suspicion_ranking.csv"

THRESHOLD = 1.0   # a game counts as "suspicious" if its score is >= this (~1 SD)

df = pd.read_csv(SRC)
df["is_suspicious"] = df["suspicious_score"] >= THRESHOLD

agg = (df.groupby(["player", "group"])
         .agg(n_games=("suspicious_score", "size"),
              n_suspicious=("is_suspicious", "sum"),
              cumulative=("suspicious_score", "sum"),
              mean=("suspicious_score", "mean"),
              max=("suspicious_score", "max"))
         .reset_index()
         .sort_values(["n_suspicious", "cumulative"], ascending=False))

agg[["cumulative", "mean", "max"]] = agg[["cumulative", "mean", "max"]].round(3)
agg.to_csv(OUT, index=False)

print(f"per-player aggregation (suspicious = game score >= {THRESHOLD}) -> {OUT.name}\n")
print(agg.to_string(index=False))
print("\nmean cumulative by group:")
print(agg.groupby("group")["cumulative"].mean().round(3).to_string())
