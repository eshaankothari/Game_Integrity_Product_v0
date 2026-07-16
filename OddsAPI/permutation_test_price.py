"""Bootstrap p-value for the flagged group's normalized UNDER-price drop.

Same idea as permutation_test.py, but for the z2 feature and restricted to the
subsample where the LINE DID NOT MOVE (pinned games) -- so price movement isn't
confounded by a line move.

Statistic per game:  susp = -(close_under - start_under)/start_under * 100
  (Under price DROP -> positive -> "suspicious"; same direction as z2)

Observed = mean(susp) over flagged PINNED games.
Null     = resample k games at random from ALL pinned games, N_BOOT times.
p-value  = fraction of resampled means >= observed (one-sided).

    python permutation_test_price.py
"""
from pathlib import Path
import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).parent
CSV = HERE / "Key Figures" / "test_dataset_jan_mar.csv"
KF = HERE / "Key Figures"

N_BOOT = 100_000
rng = np.random.default_rng(0)

df = pd.read_csv(CSV)
df["line_move_pct"] = (df["close_line"] - df["start_line"]) / df["start_line"] * 100
df["susp"] = -(df["close_under"] - df["start_under"]) / df["start_under"] * 100

# --- restrict to pinned games (line did NOT move) ---
pinned = df[df["line_move_pct"] == 0].dropna(subset=["susp"])

flagged = pinned[pinned["group"] == "flagged"]
obs = flagged["susp"].mean()
k = len(flagged)

allvals = pinned["susp"].to_numpy()
means = rng.choice(allvals, size=(N_BOOT, k), replace=True).mean(axis=1)
p = (means >= obs).mean()

print(f"pinned games (no line move): {len(pinned)}   of which flagged: {k}")
print(f"observed flagged mean under-price drop (susp): {obs:.4f}")
print(f"bootstrap null mean: {means.mean():+.4f}   std: {means.std():.4f}")
print(f"resampled means >= observed: {int((means >= obs).sum())}/{N_BOOT}")
print(f"one-sided p-value: {p:.4f}")
print(f"observed sits {(obs - means.mean())/means.std():+.2f} sd above the bootstrap mean")

# --- histogram ---
fig, ax = plt.subplots(figsize=(8, 5))
ax.hist(means, bins=80, color="#c7e9c0", edgecolor="white")
ax.axvline(obs, color="#d62728", lw=2, label=f"observed flagged mean = {obs:.2f}  (p={p:.4f})")
ax.axvline(means.mean(), color="grey", lw=1, ls="--", label=f"bootstrap mean = {means.mean():.2f}")
ax.set_xlabel(f"mean normalized under-price drop of {k} random pinned games")
ax.set_ylabel("frequency")
ax.set_title(f"Bootstrap: {N_BOOT:,} resamples of {k} pinned games")
ax.legend()
fig.savefig(KF / "bootstrap_price_drop.png", dpi=110, bbox_inches="tight")
print(f"\nwrote {(KF / 'bootstrap_price_drop.png').name}")
