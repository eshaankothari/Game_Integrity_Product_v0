"""Season(career)-long weighted z-score for any player from <slug>_all_games.csv.

  python player_weighted_z.py "Jontay Porter"

Same method as the Beasley heatmap:
  - per-48 standardize counting stats (points, rebounds, assists, +/- , FGA, and the
    4 hustle stats). minutes (time base), turnoverRatio, usagePercentage used as-is.
  - full-sample z over ALL the player's games (one baseline -> games comparable).
  - orient so higher = better (turnoverRatio negated: more TOs = worse).
  - CORE(8) = box+advanced, FULL(12) = +hustle; shown side by side, lowest first.
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

# name, per48?, flip?, source-group, label
STATS = [
    ("minutes",                  False, False, "core", "min"),
    ("points",                   True,  False, "core", "pts"),
    ("rebounds",                 True,  False, "core", "reb"),
    ("assists",                  True,  False, "core", "ast"),
    ("plusMinus",                True,  False, "core", "+/-"),
    ("fga",                      True,  False, "core", "FGA"),
    ("turnoverRatio",            False, True,  "core", "TOratio"),
    ("usagePercentage",          False, False, "core", "usage%"),
    ("contestedShots",           True,  False, "hustle", "cont.sh"),
    ("deflections",              True,  False, "hustle", "defl"),
    # boxOuts / looseBalls dropped: too sparse/noisy (mostly 0s)
    ("speed",                    False, False, "track", "speed"),   # avg mph = a RATE
    ("distance",                 True,  False, "track", "dist"),    # cumulative -> per-48
    ("touches",                  True,  False, "track", "touch"),   # cumulative -> per-48
]


def zc(s):
    s = pd.to_numeric(s, errors="coerce")
    sd = s.std()
    return (s - s.mean()) / sd if sd else s * 0.0


def main(player, mode="per48"):
    """mode='per48' scores production RATE (catches underperform-while-playing);
    mode='raw' scores per-game VOLUME (catches self-removal / minutes suppression,
    which per-48 cancels out)."""
    slug = player.lower().replace(" ", "_")
    CSV = find_data(f"{slug}_all_games.csv")
    df = pd.read_csv(CSV).sort_values("date").reset_index(drop=True)
    df["minutes"] = pd.to_numeric(df["minutes"], errors="coerce")

    # drop effective DNPs (0-minute / sub-minute cameos) before z-scoring
    dropped = df[df["minutes"] < 1]
    if len(dropped):
        print(f"dropped {len(dropped)} game(s) with <1 min played: "
              + ", ".join(f"{r['date']} {r['matchup']}" for _, r in dropped.iterrows()))
    df = df[df["minutes"] >= 1].reset_index(drop=True)

    active = [s for s in STATS if s[0] in df.columns
              and pd.to_numeric(df[s[0]], errors="coerce").notna().any()]
    zcols = []
    for name, per48, flip, grp, lbl in active:
        # per-48 only in 'per48' mode; 'raw' scores volume so self-removal isn't divided out
        val = df[name] / df["minutes"] * 48.0 if (per48 and mode == "per48") else df[name]
        z = zc(val)
        df[f"{name}_z"] = -z if flip else z          # oriented: higher = better
        zcols.append(f"{name}_z")

    core = [f"{n}_z" for n, *_ , grp, _l in active if grp == "core"]
    df["core_z"] = df[core].mean(axis=1, skipna=True)
    df["full_z"] = df[zcols].mean(axis=1, skipna=True)
    df["gap"] = df["full_z"] - df["core_z"]

    df = df.sort_values("core_z").reset_index(drop=True)
    df["d"] = pd.to_datetime(df["date"]).dt.strftime("%y-%m-%d")
    df["label"] = df["d"] + "  " + df["matchup"].astype(str)
    OUT = CSV.with_name(f"{slug}_weighted_z_{mode}.csv")
    df.round(3).to_csv(OUT, index=False)

    # --- heatmap: raw stats (color=oriented z) + CORE + FULL ---
    names = [s[0] for s in active]
    labels = [s[4] for s in active] + [f"CORE({len(core)})", f"FULL({len(active)})"]
    COLOR = np.column_stack([df[f"{n}_z"].to_numpy() for n in names]
                            + [df["core_z"].to_numpy(), df["full_z"].to_numpy()])
    RAW = np.column_stack([df[n].to_numpy() for n in names]
                          + [df["core_z"].to_numpy(), df["full_z"].to_numpy()])
    vmax = np.nanmax(np.abs(COLOR[np.isfinite(COLOR)]))
    TXT = np.where(np.isnan(RAW), "", np.round(RAW, 1).astype(str))

    fig = go.Figure(go.Heatmap(
        z=COLOR, x=labels, y=df["label"], colorscale="RdBu_r", zmid=0, zmin=-vmax, zmax=vmax,
        text=TXT, texttemplate="%{text}", textfont={"size": 8},
        hovertemplate="%{y}<br>%{x}: %{text}<extra></extra>", colorbar=dict(title="oriented z")))
    norm_lbl = "per-48 RATE" if mode == "per48" else "RAW per-game VOLUME"
    fig.update_layout(title=f"{player} — 2023-24 season z [{norm_lbl}], 12 stats + CORE/FULL "
                            f"(lowest first, n={len(df)})",
                      yaxis=dict(autorange="reversed"), height=max(500, 22 * len(df)), width=1120)
    fig.write_html(HERE / f"{slug}_weighted_z_{mode}_heatmap.html")

    masked = np.ma.masked_invalid(COLOR)
    cmap = plt.cm.RdBu_r.copy(); cmap.set_bad("lightgrey")
    fig2, ax = plt.subplots(figsize=(12, max(4, 0.28 * len(df))))
    im = ax.imshow(masked, cmap=cmap, vmin=-vmax, vmax=vmax, aspect="auto")
    ax.set_xticks(range(len(labels))); ax.set_xticklabels(labels, fontsize=7, rotation=45, ha="right")
    ax.set_yticks(range(len(df))); ax.set_yticklabels(df["label"], fontsize=6)
    ax.axvline(len(names) - 0.5, color="black", lw=1.5)
    for i in range(len(df)):
        for j in range(len(labels)):
            if TXT[i, j]:
                ax.text(j, i, TXT[i, j], ha="center", va="center", fontsize=5,
                        color="black" if abs(COLOR[i, j]) < vmax * 0.6 else "white")
    ax.set_title(f"{player} 2023-24 z [{norm_lbl}] — 12 stats + CORE/FULL composite (lowest first)")
    fig2.colorbar(im, ax=ax, fraction=0.02, pad=0.02, label="oriented z")
    fig2.savefig(HERE / f"{slug}_weighted_z_{mode}_heatmap.png", dpi=120, bbox_inches="tight")

    print(f"wrote {OUT.name} and {slug}_weighted_z_{mode}_heatmap.html/.png "
          f"({len(df)} games, {len(active)} stats, mode={mode})")
    print(f"\nLOWEST games (by CORE) [{norm_lbl}]:")
    print(df.head(8)[["season", "date", "matchup", "minutes", "points", "plusMinus",
                      "core_z", "full_z"]].round(2).to_string(index=False))

    import slideshow           # noqa: E402
    slideshow.add(HERE / f"{slug}_weighted_z_{mode}_heatmap.html",
                  f"{player} — 2023-24 weighted z ({mode})",
                  f"12 stats, {norm_lbl}, season z-scored; CORE(8) vs FULL(12), lowest first.")


if __name__ == "__main__":
    mode = next((a for a in sys.argv[1:] if a in ("raw", "per48")), "per48")
    name = [a for a in sys.argv[1:] if a not in ("raw", "per48")]
    if not name:
        raise SystemExit('usage: python player_weighted_z.py "Player Name" [raw|per48]')
    main(" ".join(name), mode)
