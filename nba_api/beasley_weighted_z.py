"""Season-long weighted z-score for Beasley across 12 stats -> lowest games on a heatmap.

Sources (game_id-keyed):
  box (cached traditional): minutes, points, rebounds, assists, +/- , FGA
  advanced CSV            : turnoverRatio, usagePercentage
  hustle CSV              : contestedShots, deflections, looseBallsRecoveredTotal, boxOuts

Steps:
  1. per-48 standardize COUNTING stats (stat/minutes*48). Rate stats (minutes as the
     time base, usagePercentage, turnoverRatio) are used as-is.
  2. full-SEASON z of each: z = (x - season_mean)/season_std (one baseline; games comparable).
  3. ORIENT so higher = better: turnoverRatio is negated (more TOs = worse). All others
     already read "more is better", so a LOW composite = low-output/low-effort game.
  4. composite = equal-weighted mean of the available oriented z's (skips missing stats).
  5. heatmap: each raw stat (value printed, colored by its oriented z) + COMPOSITE z,
     sorted lowest-first.

If beasley_2023_24_hustle.csv is missing, those 4 stats are skipped with a warning
(run beasley_hustle.py first to include them).

    python beasley_weighted_z.py
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import plotly.graph_objects as go

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from box_scores import _ascii, CACHE

HERE = Path(__file__).parent
_root = HERE
while not (_root / "datapaths.py").exists() and _root.parent != _root:
    _root = _root.parent
sys.path.insert(0, str(_root))
from datapaths import find_data           # noqa: E402  (repo-root helper)

PLAYER = "Malik Beasley"
SRC = find_data("beasley_2023_24_boxscores.csv")
OUT = SRC.with_name("beasley_2023_24_weighted_z.csv")

# name, source, source-column, per48?, flip? (flip => higher value is WORSE), heatmap label
STATS = [
    ("minutes",       "box",    "minutes",                 False, False, "min"),
    ("points",        "box",    "points",                  True,  False, "pts"),
    ("rebounds",      "box",    "reboundsTotal",           True,  False, "reb"),
    ("assists",       "box",    "assists",                 True,  False, "ast"),
    ("plusMinus",     "box",    "plusMinusPoints",         True,  False, "+/-"),
    ("fga",           "box",    "fieldGoalsAttempted",     True,  False, "FGA"),
    ("turnoverRatio", "adv",    "turnoverRatio",           False, True,  "TOratio"),
    ("usagePct",      "adv",    "usagePercentage",         False, False, "usage%"),
    ("contestedShots", "hustle", "contestedShots",         True,  False, "cont.sh"),
    ("deflections",   "hustle", "deflections",             True,  False, "defl"),
    # boxOuts / looseBalls dropped: too sparse/noisy for a wing (mostly 0s)
]
WEIGHTS = {n: 1 for n, *_ in STATS}       # equal weights (edit to taste)


def _min_to_float(m):
    if pd.isna(m):
        return np.nan
    s = str(m)
    if ":" in s:
        mm, ss = s.split(":")[:2]
        return int(mm) + int(ss) / 60
    try:
        return float(s)
    except ValueError:
        return np.nan


def zc(s):
    s = pd.to_numeric(s, errors="coerce")
    sd = s.std()
    return (s - s.mean()) / sd if sd else s * 0.0


# --- load sources keyed by game_id ---
box = pd.read_csv(SRC, dtype={"game_id": str})
box["game_id"] = box["game_id"].str.zfill(10)

adv_path = find_data("beasley_2023_24_advanced.csv", must=False)
adv = pd.read_csv(adv_path, dtype={"game_id": str}) if adv_path else None
if adv is not None:
    adv["game_id"] = adv["game_id"].str.zfill(10)
    adv = adv.set_index("game_id")

hus_path = find_data("beasley_2023_24_hustle.csv", must=False)
hus = pd.read_csv(hus_path, dtype={"game_id": str}) if hus_path else None
if hus is not None:
    hus["game_id"] = hus["game_id"].str.zfill(10)
    hus = hus.set_index("game_id")
else:
    print("!! beasley_2023_24_hustle.csv not found -> skipping hustle stats "
          "(run beasley_hustle.py to include them)")

# drop stats whose source is unavailable
ACTIVE = [s for s in STATS if not (s[1] == "hustle" and hus is None)
          and not (s[1] == "adv" and adv is None)]

# --- assemble raw per-game values for every active stat ---
rows = []
for _, g in box.sort_values("date").iterrows():
    gid = g["game_id"]
    bs = pd.read_csv(CACHE / f"box_{gid}.csv") if (CACHE / f"box_{gid}.csv").exists() else None
    minutes_f = np.nan
    if bs is not None:
        full = (bs["firstName"].fillna("") + " " + bs["familyName"].fillna("")).map(_ascii)
        hitrow = bs[full == _ascii(PLAYER)]
        bs_row = hitrow.iloc[0] if not hitrow.empty else None
        minutes_f = _min_to_float(bs_row["minutes"]) if bs_row is not None else np.nan
    rec = {"game_id": gid, "date": g["date"], "matchup": g["matchup"], "minutes_f": minutes_f}
    for name, src, col, *_ in ACTIVE:
        if src == "box":
            val = minutes_f if name == "minutes" else (
                pd.to_numeric(bs_row.get(col), errors="coerce") if bs_row is not None else np.nan)
        elif src == "adv":
            val = pd.to_numeric(adv.loc[gid, col], errors="coerce") if gid in adv.index else np.nan
        else:  # hustle
            val = pd.to_numeric(hus.loc[gid, col], errors="coerce") if gid in hus.index else np.nan
        rec[name] = val
    rows.append(rec)
df = pd.DataFrame(rows).reset_index(drop=True)

# --- per-48 normalize, season z, orient ---
zcols = []
for name, src, col, per48, flip, lbl in ACTIVE:
    val = df[name] / df["minutes_f"] * 48.0 if per48 else df[name]
    zc_ = zc(val)
    df[f"{name}_z"] = -zc_ if flip else zc_        # oriented: higher = better
    zcols.append(f"{name}_z")

# two equal-weighted composites: CORE (box+advanced, 8) and FULL (+hustle, 12)
def _wmean(cols):
    w = pd.Series({c: WEIGHTS[c[:-2]] for c in cols})   # strip trailing "_z"
    Z = df[cols]
    return (Z * w).sum(axis=1, skipna=True) / (Z.notna() * w).sum(axis=1)

core_names = [n for n, src, *_ in ACTIVE if src in ("box", "adv")]
df["core_z"] = _wmean([f"{n}_z" for n in core_names])      # 8-stat: box + advanced
df["full_z"] = _wmean(zcols)                               # all available (12 with hustle)

df = df.sort_values("core_z").reset_index(drop=True)      # order by the sharper core signal
df["d"] = pd.to_datetime(df["date"]).dt.strftime("%b %d")
df["label"] = df["d"] + "  " + df["matchup"].astype(str)
df.round(3).to_csv(OUT, index=False)

# --- heatmap: raw stats (colored by oriented z) + CORE and FULL composites ---
names = [n for n, *_ in ACTIVE]
labels = [lbl for *_, lbl in ACTIVE] + [f"CORE({len(core_names)})", f"FULL({len(ACTIVE)})"]
COLOR = np.column_stack([df[f"{n}_z"].to_numpy() for n in names]
                        + [df["core_z"].to_numpy(), df["full_z"].to_numpy()])
RAW = np.column_stack([df[n].to_numpy() for n in names]
                      + [df["core_z"].to_numpy(), df["full_z"].to_numpy()])
vmax = np.nanmax(np.abs(COLOR[np.isfinite(COLOR)]))
TXT = np.where(np.isnan(RAW), "", np.round(RAW, 1).astype(str))

fig = go.Figure(go.Heatmap(
    z=COLOR, x=labels, y=df["label"], colorscale="RdBu_r", zmid=0, zmin=-vmax, zmax=vmax,
    text=TXT, texttemplate="%{text}", textfont={"size": 8},
    hovertemplate="%{y}<br>%{x}: %{text}<extra></extra>", colorbar=dict(title="oriented z"),
))
fig.update_layout(title="Beasley 2023-24 — season z (per-48) across 12 stats + weighted composite "
                        "(oriented so higher=better; sorted lowest-first)",
                  yaxis=dict(autorange="reversed"), height=1300, width=1120)
fig.write_html(HERE / "beasley_weighted_z_heatmap.html")

masked = np.ma.masked_invalid(COLOR)
cmap = plt.cm.RdBu_r.copy(); cmap.set_bad("lightgrey")
fig2, ax = plt.subplots(figsize=(12, 16))
im = ax.imshow(masked, cmap=cmap, vmin=-vmax, vmax=vmax, aspect="auto")
ax.set_xticks(range(len(labels))); ax.set_xticklabels(labels, fontsize=7, rotation=45, ha="right")
ax.set_yticks(range(len(df))); ax.set_yticklabels(df["label"], fontsize=6)
ax.axvline(len(names) - 0.5, color="black", lw=1.5)
for i in range(len(df)):
    for j in range(len(labels)):
        if TXT[i, j]:
            ax.text(j, i, TXT[i, j], ha="center", va="center", fontsize=5,
                    color="black" if abs(COLOR[i, j]) < vmax * 0.6 else "white")
ax.set_title("Beasley season z (per-48) — 12 stats + equal-weighted COMPOSITE\n"
             "value printed; color = oriented z (blue = low/worse); sorted lowest first")
fig2.colorbar(im, ax=ax, fraction=0.02, pad=0.02, label="oriented z")
fig2.savefig(HERE / "beasley_weighted_z_heatmap.png", dpi=120, bbox_inches="tight")

print(f"wrote {OUT.name} and beasley_weighted_z_heatmap.html/.png "
      f"({len(df)} games; CORE={len(core_names)} stats, FULL={len(ACTIVE)} stats)")
print("\nLOWEST games (by CORE) — core vs full side by side:")
show = ["date", "matchup", "minutes", "points", "plusMinus", "fga", "core_z", "full_z"]
print(df.head(6)[show].round(2).to_string(index=False))
df["gap"] = df["full_z"] - df["core_z"]
print("\nbiggest core->full SHIFTS (hustle changed the read most):")
print(df.reindex(df["gap"].abs().sort_values(ascending=False).index)
      .head(5)[["date", "matchup", "core_z", "full_z", "gap"]].round(2).to_string(index=False))

import slideshow           # noqa: E402
slideshow.add(HERE / "beasley_weighted_z_heatmap.html", "15 · Beasley season weighted z (core 8 vs full 12)",
              "Per-48/season z-scored; CORE (box+advanced) vs FULL (+hustle) composites side by side.")
