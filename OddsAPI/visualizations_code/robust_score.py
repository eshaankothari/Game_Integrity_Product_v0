"""Robust 'suspicious trading' score: percentile-based composite (+ modified-z).

Fixes two problems with the plain z-score version:
  1. Non-normal / lumpy metrics -> use rank-based percentiles, not mean/std.
  2. Equal-weighting requires a COMMON scale -> put all 3 components on [0,1]
     percentiles, then the equal-weighted average is just their mean.

Each metric is oriented so HIGHER = more suspicious, then percentile-ranked
within the dataset you pass (test set now, full league later -- same code):
  s_line  = -line_move_pct            line DROP -> high percentile
  s_price = -under_move_pct           Under price DROP -> high  (pinned games)
  s_ratio = -ou_ratio                 ratio < 1 (Over-favored) -> high

suspicious_score = mean of the available component percentiles (price only
enters on no-line-move games). A guarded modified-z is also reported per
component for comparison (MAD==0 -> fall back to std -> 0).

    python robust_score.py                 # scores the Jan-Mar test set
    python robust_score.py path/to.csv     # score any csv with the same columns
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).parent
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "Key Figures" / "test_dataset_jan_mar.csv"
OUT = SRC.with_name(SRC.stem + "_robust.csv")


def suspicion_percentile(s):
    """Percentile rank in [0,1]; higher input -> higher percentile (ties averaged)."""
    return s.rank(pct=True, method="average")


def modified_z(s):
    """Guarded MAD-based modified z. Falls back to std if MAD==0, else 0."""
    med = s.median()
    mad = (s - med).abs().median()
    if mad > 0:
        return 0.6745 * (s - med) / mad
    sd = s.std()
    if sd and sd > 0:
        return (s - med) / sd
    return pd.Series(0.0, index=s.index)


df = pd.read_csv(SRC)

# --- metrics, oriented so higher = more suspicious ---
df["line_move_pct"] = (df["close_line"] - df["start_line"]) / df["start_line"] * 100
df["under_move_pct"] = (df["close_under"] - df["start_under"]) / df["start_under"] * 100
df["ou_ratio"] = df["close_over"] / df["close_under"]
df["s_line"] = -df["line_move_pct"]
df["s_price"] = -df["under_move_pct"]
df["s_ratio"] = -df["ou_ratio"]
pinned = df["line_move_pct"] == 0

# --- component percentiles (common [0,1] scale) ---
df["p_line"] = suspicion_percentile(df["s_line"])
df["p_ratio"] = suspicion_percentile(df["s_ratio"])
df["p_price"] = np.nan
df.loc[pinned, "p_price"] = suspicion_percentile(df.loc[pinned, "s_price"])

# --- composite = equal-weight mean of available percentiles ---
df["suspicious_score"] = df[["p_line", "p_price", "p_ratio"]].mean(axis=1)

# --- diagnostic: guarded modified-z per component + its composite ---
df["mz_line"] = modified_z(df["s_line"])
df["mz_ratio"] = modified_z(df["s_ratio"])
df["mz_price"] = np.nan
df.loc[pinned, "mz_price"] = modified_z(df.loc[pinned, "s_price"])
df["suspicious_mz"] = df[["mz_line", "mz_price", "mz_ratio"]].mean(axis=1)

df["basis"] = f"percentile within this dataset (n={len(df)})"
df = df.sort_values("suspicious_score", ascending=False)
df.round(4).to_csv(OUT, index=False)

print(f"wrote {OUT.name} ({len(df)} rows), ranked by suspicious_score (percentile composite)\n")
show = df[["player", "group", "time", "line_move_pct", "ou_ratio",
           "p_line", "p_price", "p_ratio", "suspicious_score", "suspicious_mz"]].copy()
show["time"] = pd.to_datetime(show["time"]).dt.strftime("%Y-%m-%d")
print(show.round(3).to_string(index=False))
print("\nmean suspicious_score (percentile) by group:")
print(df.groupby("group")["suspicious_score"].mean().round(3).to_string())
