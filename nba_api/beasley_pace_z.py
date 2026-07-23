"""Minutes-normalized PACE for Beasley, with a rolling 15-game prior z-score.

pace is a per-48 rate, so we minutes-normalize it into possessions on court:
    possessions = pace * minutes / 48        (tempo weighted by playing time)
Then a causal rolling z vs the prior 15 games (shift(1) excludes the game itself;
first 15 games have no full baseline -> skipped):
    z_t = (poss_t - mean(poss_{t-15..t-1})) / std(poss_{t-15..t-1})

Heatmap columns: pace (raw) | possessions (min-normalized) | possessions z (prior-15),
each colored by its within-column z, raw value printed. Adds slide to the deck.

    python beasley_pace_z.py
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import plotly.graph_objects as go

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).parent
_root = HERE
while not (_root / "datapaths.py").exists() and _root.parent != _root:
    _root = _root.parent
sys.path.insert(0, str(_root))
from datapaths import find_data           # noqa: E402  (repo-root helper)

CSV = find_data("beasley_2023_24_advanced.csv")
OUT = CSV.with_name("beasley_2023_24_pace_z.csv")
WINDOW = 15


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


def zcol(s):
    s = pd.to_numeric(s, errors="coerce")
    sd = s.std()
    return (s - s.mean()) / sd if sd else s * 0.0


df = pd.read_csv(CSV).sort_values("date").reset_index(drop=True)
df["minutes_f"] = df["minutes"].map(_min_to_float)
df["pace"] = pd.to_numeric(df["pace"], errors="coerce")

# --- minutes-normalize pace -> possessions on court ---
df["possessions"] = df["pace"] * df["minutes_f"] / 48.0

# --- rolling z vs prior 15 games (causal) ---
prior_mean = df["possessions"].rolling(WINDOW).mean().shift(1)
prior_std = df["possessions"].rolling(WINDOW).std().shift(1)
df["possessions_z"] = (df["possessions"] - prior_mean) / prior_std
df["has_z"] = df.index >= WINDOW
df.round(3).to_csv(OUT, index=False)

# --- heatmap ---
df["d"] = pd.to_datetime(df["date"]).dt.strftime("%b %d")
df["label"] = df["d"] + "  " + df["matchup"].astype(str)
COLS = ["pace", "possessions", "possessions_z"]
LABELS = ["pace<br>(per-48)", "possessions<br>(pace·min/48)", "possessions z<br>(prior 15)"]
# color: pace & possessions by within-season z; possessions_z is already a z
COLOR = np.column_stack([zcol(df["pace"]).to_numpy(),
                         zcol(df["possessions"]).to_numpy(),
                         df["possessions_z"].to_numpy()])
RAW = np.column_stack([df["pace"].to_numpy(),
                       df["possessions"].to_numpy(),
                       df["possessions_z"].to_numpy()])
vmax = np.nanmax(np.abs(COLOR[np.isfinite(COLOR)])) if np.isfinite(COLOR).any() else 1.0
TXT = np.where(np.isnan(RAW), "", np.round(RAW, 1).astype(str))

fig = go.Figure(go.Heatmap(
    z=COLOR, x=[l.replace("<br>", " ") for l in LABELS], y=df["label"],
    colorscale="RdBu_r", zmid=0, zmin=-vmax, zmax=vmax,
    text=TXT, texttemplate="%{text}", textfont={"size": 9},
    hovertemplate="%{y}<br>%{x}: raw %{text}<extra></extra>",
    colorbar=dict(title="z"),
))
fig.update_layout(title=f"Beasley 2023-24 — minutes-normalized pace + rolling z (prior {WINDOW})",
                  yaxis=dict(autorange="reversed"), height=1300, width=680)
fig.write_html(HERE / "beasley_pace_z_heatmap.html")

# --- static PNG ---
masked = np.ma.masked_invalid(COLOR)
cmap = plt.cm.RdBu_r.copy(); cmap.set_bad("lightgrey")
fig2, ax = plt.subplots(figsize=(6, 16))
im = ax.imshow(masked, cmap=cmap, vmin=-vmax, vmax=vmax, aspect="auto")
ax.set_xticks(range(len(COLS))); ax.set_xticklabels([l.replace("<br>", "\n") for l in LABELS], fontsize=8)
ax.set_yticks(range(len(df))); ax.set_yticklabels(df["label"], fontsize=6)
ax.axvline(1.5, color="black", lw=1.5)      # raw pace/possessions | the z
for i in range(len(df)):
    for j in range(len(COLS)):
        if TXT[i, j]:
            ax.text(j, i, TXT[i, j], ha="center", va="center", fontsize=6,
                    color="black" if abs(COLOR[i, j]) < vmax * 0.6 else "white")
ax.set_title(f"Beasley minutes-normalized pace\n+ rolling z (prior {WINDOW}; first {WINDOW} grey)")
fig2.colorbar(im, ax=ax, fraction=0.04, pad=0.03, label="z")
fig2.savefig(HERE / "beasley_pace_z_heatmap.png", dpi=120, bbox_inches="tight")

print(f"wrote {OUT.name} and beasley_pace_z_heatmap.html/.png "
      f"({int(df['has_z'].sum())}/{len(df)} games scored)")
print("\nmost anomalous possession-load games (|z|):")
t = df[df["has_z"]].dropna(subset=["possessions_z"]).copy()
t["absz"] = t["possessions_z"].abs()
print(t.sort_values("absz", ascending=False).head(5)[
    ["date", "matchup", "minutes_f", "pace", "possessions", "possessions_z"]].round(2).to_string(index=False))

import slideshow           # noqa: E402  (repo root already on sys.path)
slideshow.add(HERE / "beasley_pace_z_heatmap.html", "13 · Beasley pace (min-normalized) rolling z",
              "Possessions = pace·min/48, z-scored vs prior 15 games.")
