"""Rolling 15-game prior z-score for ANY Beasley stat, on a heatmap.

    python beasley_stat_z.py netRating          # default
    python beasley_stat_z.py usagePercentage
    python beasley_stat_z.py trueShootingPercentage

For game t, baseline = the prior 15 games (shift(1) excludes the game itself);
first 15 games have no full baseline -> skipped:
    z_t = (x_t - mean(x_{t-15..t-1})) / std(x_{t-15..t-1})

Rate stats (netRating, usage%, TS%, pace, PIE) are already per-100-poss/percent,
so they are z-scored as-is (no minutes normalization). Reads the advanced CSV.
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

STAT = sys.argv[1] if len(sys.argv) > 1 else "netRating"
WINDOW = 15
CSV = find_data("beasley_2023_24_advanced.csv")
OUT = CSV.with_name(f"beasley_2023_24_{STAT}_z.csv")


def zcol(s):
    s = pd.to_numeric(s, errors="coerce")
    sd = s.std()
    return (s - s.mean()) / sd if sd else s * 0.0


df = pd.read_csv(CSV).sort_values("date").reset_index(drop=True)
if STAT not in df.columns:
    raise SystemExit(f"'{STAT}' not in {CSV.name}. columns: {list(df.columns)}")
df[STAT] = pd.to_numeric(df[STAT], errors="coerce")

# rolling z vs prior 15 games (causal)
prior_mean = df[STAT].rolling(WINDOW).mean().shift(1)
prior_std = df[STAT].rolling(WINDOW).std().shift(1)
df[f"{STAT}_z"] = (df[STAT] - prior_mean) / prior_std
df["has_z"] = df.index >= WINDOW
df.round(3).to_csv(OUT, index=False)

# --- heatmap: raw stat (within-season z color) | rolling prior-15 z ---
df["d"] = pd.to_datetime(df["date"]).dt.strftime("%b %d")
df["label"] = df["d"] + "  " + df["matchup"].astype(str)
COLS = [STAT, f"{STAT}_z"]
LABELS = [f"{STAT}<br>(raw)", f"{STAT} z<br>(prior {WINDOW})"]
COLOR = np.column_stack([zcol(df[STAT]).to_numpy(), df[f"{STAT}_z"].to_numpy()])
RAW = np.column_stack([df[STAT].to_numpy(), df[f"{STAT}_z"].to_numpy()])
vmax = np.nanmax(np.abs(COLOR[np.isfinite(COLOR)])) if np.isfinite(COLOR).any() else 1.0
TXT = np.where(np.isnan(RAW), "", np.round(RAW, 2).astype(str))

fig = go.Figure(go.Heatmap(
    z=COLOR, x=[l.replace("<br>", " ") for l in LABELS], y=df["label"],
    colorscale="RdBu_r", zmid=0, zmin=-vmax, zmax=vmax,
    text=TXT, texttemplate="%{text}", textfont={"size": 9},
    hovertemplate="%{y}<br>%{x}: raw %{text}<extra></extra>", colorbar=dict(title="z"),
))
fig.update_layout(title=f"Beasley 2023-24 — {STAT} rolling z (prior {WINDOW}; first {WINDOW} skipped)",
                  yaxis=dict(autorange="reversed"), height=1300, width=620)
fig.write_html(HERE / f"beasley_{STAT}_z_heatmap.html")

masked = np.ma.masked_invalid(COLOR)
cmap = plt.cm.RdBu_r.copy(); cmap.set_bad("lightgrey")
fig2, ax = plt.subplots(figsize=(5.5, 16))
im = ax.imshow(masked, cmap=cmap, vmin=-vmax, vmax=vmax, aspect="auto")
ax.set_xticks(range(len(COLS))); ax.set_xticklabels([l.replace("<br>", "\n") for l in LABELS], fontsize=8)
ax.set_yticks(range(len(df))); ax.set_yticklabels(df["label"], fontsize=6)
ax.axvline(0.5, color="black", lw=1.5)
for i in range(len(df)):
    for j in range(len(COLS)):
        if TXT[i, j]:
            ax.text(j, i, TXT[i, j], ha="center", va="center", fontsize=6,
                    color="black" if abs(COLOR[i, j]) < vmax * 0.6 else "white")
ax.set_title(f"Beasley {STAT} rolling z (prior {WINDOW})\ngrey = first {WINDOW} (no baseline)")
fig2.colorbar(im, ax=ax, fraction=0.04, pad=0.03, label="z")
fig2.savefig(HERE / f"beasley_{STAT}_z_heatmap.png", dpi=120, bbox_inches="tight")

print(f"wrote {OUT.name} and beasley_{STAT}_z_heatmap.html/.png "
      f"({int(df['has_z'].sum())}/{len(df)} games scored)")
print(f"\nmost anomalous {STAT} games (|z|):")
t = df[df["has_z"]].dropna(subset=[f"{STAT}_z"]).copy()
t["absz"] = t[f"{STAT}_z"].abs()
print(t.sort_values("absz", ascending=False).head(5)[
    ["date", "matchup", "minutes", STAT, f"{STAT}_z"]].round(2).to_string(index=False))

import slideshow           # noqa: E402  (repo root already on sys.path)
slideshow.add(HERE / f"beasley_{STAT}_z_heatmap.html", f"Beasley {STAT} rolling z (15-game prior)",
              f"Per-game {STAT} z-scored vs the prior 15 games.")
