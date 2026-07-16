"""Bootstrap p-value for the flagged group's normalized line movement.

Statistic per game:  susp = -(close_line - start_line)/start_line * 100
  (a line DROP -> positive -> "suspicious"; same direction as z1)

Observed = mean(susp) over the 17 flagged games.
Null     = resample 17 games at random from the ENTIRE dataset, N_BOOT times,
           and build the distribution of those means.
p-value  = fraction of resampled means >= observed (one-sided).

    python permutation_test.py
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
df["susp"] = -(df["close_line"] - df["start_line"]) / df["start_line"] * 100
df = df.dropna(subset=["susp"])

flagged = df[df["group"] == "flagged"]
obs = flagged["susp"].mean()
k = len(flagged)

allvals = df["susp"].to_numpy()
means = rng.choice(allvals, size=(N_BOOT, k), replace=True).mean(axis=1)
p = (means >= obs).mean()

print(f"whole dataset: {len(df)} games   flagged: {k}")
print(f"observed flagged mean susp: {obs:.4f}")
print(f"bootstrap null mean: {means.mean():+.4f}   std: {means.std():.4f}")
print(f"resampled means >= observed: {int((means >= obs).sum())}/{N_BOOT}")
print(f"one-sided p-value: {p:.4f}")
print(f"observed sits {(obs - means.mean())/means.std():+.2f} sd above the bootstrap mean")

# --- histogram of the resampled means with the observed line ---
fig, ax = plt.subplots(figsize=(8, 5))
ax.hist(means, bins=80, color="#9ecae1", edgecolor="white")
ax.axvline(obs, color="#d62728", lw=2, label=f"observed flagged mean = {obs:.2f}  (p={p:.4f})")
ax.axvline(means.mean(), color="grey", lw=1, ls="--", label=f"bootstrap mean = {means.mean():.2f}")
ax.set_xlabel("mean normalized line move of 17 random games")
ax.set_ylabel("frequency")
ax.set_title(f"Bootstrap: {N_BOOT:,} resamples of {k} games from the full dataset")
ax.legend()
fig.savefig(KF / "bootstrap_line_move.png", dpi=110, bbox_inches="tight")
print(f"\nwrote {(KF / 'bootstrap_line_move.png').name}")
