import sys
from pathlib import Path

import numpy as np
import pandas as pd

# --- locate the CSVs using the repo's finder (works from any folder) ---
HERE = Path(__file__).resolve().parent
_root = HERE
while not (_root / "datapaths.py").exists() and _root.parent != _root:
    _root = _root.parent
sys.path.insert(0, str(_root))
from datapaths import find_data           # noqa: E402


# Beasley only, already per-48 standardized (z-scored)

def get_coefficients(df, C=1.0):
    print(df['player'][0] + ':')
    zcols = [c for c in df.columns if c.endswith("_z") and c not in ("core_z", "full_z")]
    X = df[zcols]

    y = df["flag"]

    from sklearn.linear_model import LogisticRegression
    # penalty="l1" zeros redundant features; smaller C = stronger regularization
    model = LogisticRegression(max_iter=1000)
    model.fit(X.fillna(0), y)

    for f, w in sorted(zip(zcols, model.coef_[0]), key=lambda t: t[1]):
        print(f"{f:20s} {w:+.3f}")
    print('----------')
    diff = X[y == 1].mean() - X[y == 0].mean()
    print(diff.sort_values().round(3))
    print('----------')
    print(X.corr().round(2))


def permutation_test(df, n=10000):
    zcols = [c for c in df.columns if c.endswith("_z") and c not in ("core_z", "full_z")]
    X = df[zcols].fillna(0)
    y = df["flag"].to_numpy()

    stat = lambda yy: (X[yy == 1].mean() - X[yy == 0].mean()).abs().mean()   # mean univariate |diff|
    observed = stat(y)

    rng = np.random.default_rng(0)
    null = np.array([stat(rng.permutation(y)) for _ in range(n)])            # separation under random labels
    beat = int((null >= observed).sum())
    print(f"observed mean|diff| = {observed:.3f}")
    print(f"p-value = {beat/n:.4f}  ({beat}/{n} random shuffles separate this well)")


def reg_path(df):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from sklearn.linear_model import LogisticRegression

    zcols = [c for c in df.columns if c.endswith("_z") and c not in ("core_z", "full_z")]
    X, y = df[zcols].fillna(0), df["flag"]
    
    Cs = np.logspace(1, -2, 30)          # sweep C from 10 (weak) down to 0.01 (strong)
    coefs = np.array([LogisticRegression(penalty="l1", solver="liblinear", C=C, max_iter=1000)
                      .fit(X, y).coef_[0] for C in Cs])

    # dropout point: smallest C at which each feature is still non-zero (dies-first = biggest)
    alive = np.abs(coefs) > 1e-6
    surv = {f: (Cs[alive[:, j]].min() if alive[:, j].any() else np.inf) for j, f in enumerate(zcols)}
    diff = (X[y == 1].mean() - X[y == 0].mean()).abs()
    print("feature            last-C-nonzero   |univariate diff|   (converge FIRST at top)")
    for f in sorted(surv, key=surv.get, reverse=True):
        print(f"{f:20s} {surv[f]:>10.3g}   {diff[f]:>12.3f}")

    for j, f in enumerate(zcols):
        plt.plot(Cs, coefs[:, j], label=f)
    plt.xscale("log")
    plt.gca().invert_xaxis()             # weak reg (high C) left -> strong reg (low C) right
    plt.axhline(0, color="grey", lw=0.5)
    plt.xlabel("C   (← weaker penalty     stronger penalty →)")
    plt.ylabel("coefficient")
    plt.legend(fontsize=6, ncol=2)
    plt.title("L1 regularization path")
    plt.savefig(HERE / "reg_path.png", dpi=120, bbox_inches="tight")
    print("wrote reg_path.png")


DROP = ["speed_z", "plusMinus_z", "contestedShots_z", "deflections_z"]

files = ["malik_beasley_weighted_z_raw.csv", "jontay_porter_weighted_z_raw.csv",
         "gary_trent_jr._weighted_z_raw.csv", "mike_muscala_weighted_z_raw.csv"]
df = pd.concat([pd.read_csv(find_data(f)) for f in files], ignore_index=True)
flagged = {("Malik Beasley", "2024-01-06"), ("Malik Beasley", "2024-01-26"),
           ("Malik Beasley", "2024-02-27"), ("Jontay Porter", "2024-01-26"),
           ("Jontay Porter", "2024-03-20")}
df["flag"] = [int((pl, d) in flagged) for pl, d in zip(df["player"], df["date"])]
df = df.drop(columns=DROP)
get_coefficients(df)
permutation_test(df)


def apply_to(train_df, target):
    """Train on train_df; predict on `target` (a DataFrame, or a csv name to read)."""
    zcols = [c for c in train_df.columns if c.endswith("_z") and c not in ("core_z", "full_z")]
    from sklearn.linear_model import LogisticRegression
    model = LogisticRegression(max_iter=1000).fit(train_df[zcols].fillna(0), train_df["flag"])
    new = target.copy() if isinstance(target, pd.DataFrame) else pd.read_csv(find_data(target)).drop(columns=DROP)
    new["pred"] = model.predict_proba(new[zcols].fillna(0))[:, 1]
    cols = ["player", "date", "matchup"] + (["flag"] if "flag" in new else []) + ["pred"]
    print(new.sort_values("pred", ascending=False).head(15)[cols].round(3).to_string(index=False))


# apply_to(df, df)


# L1 survivors — feature SELECTION (which stats matter), NOT weighting
SELECTED = ["minutes_z", "points_z", "fga_z", "usagePercentage_z",
            "turnoverRatio_z", "distance_z", "touches_z", "rebounds_z", "assists_z"]


def isolation_forest(df, features=SELECTED):
    from sklearn.ensemble import IsolationForest
    # one-sided (LOW only): all _z are "higher=better", so clip the high side to 0.
    # a career/great game (high z) -> 0 = looks normal; only low-side deviations are anomalies.
    X = df[features].fillna(0).clip(upper=0)
    iso = IsolationForest(n_estimators=300, contamination=0.05, random_state=42).fit(X)
    scores = -iso.score_samples(X)                               # flip so HIGHER = more anomalous
    ranked = df.assign(anomaly=scores).sort_values("anomaly", ascending=False).reset_index(drop=True)

    print("most anomalous games (top 15):")
    print(ranked.head(15)[["player", "date", "matchup", "flag", "anomaly"]].round(3).to_string(index=False))
    print(f"\nrank of your 5 known flagged games (of {len(ranked)}):")
    for i, r in ranked[ranked["flag"] == 1].iterrows():
        print(f"  #{i+1:<4}{r['player']:15s} {r['date']} {r['matchup']:13s} anomaly={r['anomaly']:.3f}")


def rank_by_sum(df, features=SELECTED):
    s = df[features].fillna(0).sum(axis=1)                        # equal-weighted sum of z-scores
    ranked = df.assign(score=s).sort_values("score").reset_index(drop=True)   # lowest = most suspicious
    print("lowest total-z games (top 15):")
    print(ranked.head(15)[["player", "date", "matchup", "flag", "score"]].round(2).to_string(index=False))
    print(f"\nrank of your 5 known flagged games (of {len(ranked)}):")
    for i, r in ranked[ranked["flag"] == 1].iterrows():
        print(f"  #{i+1:<4}{r['player']:15s} {r['date']} {r['matchup']:13s} score={r['score']:.2f}")


# isolation_forest(df)
rank_by_sum(df)

# ==========================================================================
# STEP 3 — split into train / test        (we'll write this together)
# ==========================================================================
# from sklearn.model_selection import train_test_split
# stratify=y keeps the Porter/Beasley ratio the same in train and test (classes are imbalanced)
# X_train, X_test, y_train, y_test = train_test_split(
#     X, y, test_size=0.25, random_state=42, stratify=y)


# ==========================================================================
# STEP 4 — scale the features             (we'll write this together)
# ==========================================================================
# logistic regression is scale-sensitive; standardize using TRAIN stats only, then apply to TEST
# from sklearn.preprocessing import StandardScaler


# ==========================================================================
# STEP 5 — fit LogisticRegression         (we'll write this together)
# ==========================================================================
# from sklearn.linear_model import LogisticRegression


# ==========================================================================
# STEP 6 — evaluate (accuracy, confusion matrix, coefficients)  (together)
# ==========================================================================
# what each stat's coefficient says about "looks like a Porter game"
