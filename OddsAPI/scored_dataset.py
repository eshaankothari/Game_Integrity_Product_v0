"""Add a 'suspicious trading' score to the Jan-Mar test set (Option A baseline).

score = equal-weighted average of three z-scores, all oriented so HIGHER = more
suspicious, computed relative to the 28-game TEST SET (not the full league):

  z1 = -z(line_move_pct)                     line DROP scores high
  z2 = -z(under_move_pct | line pinned)      Under price DROP scores high
                                             (only for games with NO line move)
  z3 = -z(ou_ratio = close_over/close_under) ratio < 1 (Over-favored) scores high

For games where the line moved, z2 is N/A and the score averages z1 & z3.
Writes a DUPLICATE -> test_dataset_jan_mar_scored.csv (original untouched).

    python scored_dataset.py
"""
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).parent
SRC = HERE / "Key Figures" / "test_dataset_jan_mar.csv"
OUT = HERE / "Key Figures" / "test_dataset_jan_mar_scored.csv"


def z(series):
    """Standard z-score over the test set (sample std)."""
    return (series - series.mean()) / series.std()


df = pd.read_csv(SRC)

# --- metrics ---
df["line_move_pct"] = (df["close_line"] - df["start_line"]) / df["start_line"] * 100
df["under_move_pct"] = (df["close_under"] - df["start_under"]) / df["start_under"] * 100
df["ou_ratio"] = df["close_over"] / df["close_under"]
df["ratio_change"] = (df["close_over"] / df["close_under"]) - (df["start_over"] / df["start_under"])
no_line_move = df["line_move_pct"] == 0

# --- z-scores, all flipped so higher = more suspicious ---
df["z1"] = -z(df["line_move_pct"])                 # line drop -> high
df["z3"] = -z(df["ou_ratio"])                      # closing ratio < 1 -> high
df["z4"] = -z(df["ratio_change"])                  # ratio DROP open->close -> high

# z2 only for no-line-move games, baselined on that subset
sub = df.loc[no_line_move, "under_move_pct"]
df["z2"] = np.nan
df.loc[no_line_move, "z2"] = -((sub - sub.mean()) / sub.std())   # under price drop -> high

# --- equal-weighted average of the enabled components present on each row ---
INCLUDE_Z3 = False   # z3 = closing O/U ratio LEVEL
INCLUDE_Z4 = False   # z4 = O/U ratio CHANGE (open -> close) -- noisy on flagged set, reverted
components = ["z1", "z2"] + (["z3"] if INCLUDE_Z3 else []) + (["z4"] if INCLUDE_Z4 else [])
df["suspicious_score"] = df[components].mean(axis=1)            # nan-skips z2 when line moved
df["zscore_basis"] = (f"test_set (n={len(df)}), "
                      f"z3={'on' if INCLUDE_Z3 else 'OFF'}, z4={'on' if INCLUDE_Z4 else 'OFF'}")

df = df.sort_values("suspicious_score", ascending=False)
cols = ["player", "group", "time", "line_move_pct", "under_move_pct", "ou_ratio", "ratio_change",
        "z1", "z2", "z3", "z4", "suspicious_score", "zscore_basis"]
df.round(3).to_csv(OUT, index=False, columns=cols + [c for c in df.columns if c not in cols])

print(f"wrote {OUT.name} ({len(df)} rows), ranked by suspicious_score\n")
show = df[["player", "group", "time", "line_move_pct", "ou_ratio",
           "z1", "z2", "z3", "suspicious_score"]].copy()
show["time"] = pd.to_datetime(show["time"], format="mixed").dt.strftime("%Y-%m-%d")
print(show.round(2).to_string(index=False))
print(f"\nno-line-move games (z2 applies): {int(no_line_move.sum())} of {len(df)}")
print("\nmean suspicious_score by group:")
print(df.groupby("group")["suspicious_score"].mean().round(3).to_string())
