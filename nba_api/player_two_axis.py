"""Two-axis suspicion model: AVAILABILITY vs EFFICIENCY (separates the two mechanisms).

A single normalized composite can't catch both "he took himself out" (a minutes
story) and "he dogged it while playing" (a per-48 rate story) -- per-48 is blind to
the first, raw muddles them. So we DON'T blend; we score two independent axes and
flag a game if EITHER is low:

  availability_z = z of MINUTES vs his season norm.        low => self-removal / DNP-ish
  efficiency_z   = mean per-48 z of production stats,
                   baseline from games with >= MIN_MIN minutes only; games below that
                   get N/A (per-48 is meaningless / pure noise on tiny minutes).

Outputs a scatter (availability x, efficiency y; sub-threshold games pinned at the
bottom as "availability-only") and a 2-column heatmap. Adds the scatter to the deck.

    python player_two_axis.py "Jontay Porter"
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

MIN_MIN = 8.0          # minutes needed for per-48 efficiency to be trustworthy
FLAG = -1.0            # z below this on either axis = flagged

# efficiency stats: name, per48?, flip? (higher=better after orient; TOratio flipped)
EFF = [("points", True, False), ("rebounds", True, False), ("assists", True, False),
       ("plusMinus", True, False), ("fga", True, False),
       ("turnoverRatio", False, True), ("usagePercentage", False, False),
       ("contestedShots", True, False), ("deflections", True, False),
       ("speed", False, False), ("distance", True, False), ("touches", True, False)]


def main(player):
    slug = player.lower().replace(" ", "_")
    df = pd.read_csv(find_data(f"{slug}_all_games.csv")).sort_values("date").reset_index(drop=True)
    df["minutes"] = pd.to_numeric(df["minutes"], errors="coerce")
    df = df[df["minutes"] >= 1].reset_index(drop=True)          # drop sub-minute cameos
    reliable = df["minutes"] >= MIN_MIN

    # --- availability: minutes vs season norm (all games) ---
    m = df["minutes"]
    df["availability_z"] = (m - m.mean()) / m.std()

    # --- efficiency: per-48 production, baseline from >=MIN_MIN games only ---
    zcols = []
    for name, per48, flip in EFF:
        if name not in df.columns or pd.to_numeric(df[name], errors="coerce").notna().sum() == 0:
            continue
        val = pd.to_numeric(df[name], errors="coerce")
        if per48:
            val = val / df["minutes"] * 48.0
        base = val[reliable]                                   # baseline: trustworthy games
        z = (val - base.mean()) / base.std() if base.std() else val * 0.0
        df[f"eff_{name}_z"] = -z if flip else z
        zcols.append(f"eff_{name}_z")
    df["efficiency_z"] = df[zcols].mean(axis=1)
    df.loc[~reliable, "efficiency_z"] = np.nan                 # not scored on efficiency

    # --- flag mechanism ---
    def classify(r):
        a = r["availability_z"] < FLAG
        e = pd.notna(r["efficiency_z"]) and r["efficiency_z"] < FLAG
        if a and e: return "both"
        if a:       return "availability"
        if e:       return "efficiency"
        return "none"
    df["flag"] = df.apply(classify, axis=1)
    df["d"] = pd.to_datetime(df["date"]).dt.strftime("%b %d")
    df["label"] = df["d"] + "  " + df["matchup"].astype(str)
    OUT = find_data(f"{slug}_all_games.csv").with_name(f"{slug}_two_axis.csv")
    df.round(3).to_csv(OUT, index=False)

    COLOR = {"both": "#d62728", "availability": "#ff7f0e", "efficiency": "#9467bd", "none": "#7fa8d0"}
    ymin = np.nanmin(df["efficiency_z"]) if df["efficiency_z"].notna().any() else -1
    pin = ymin - 0.8                                           # y-pin for sub-threshold games

    # --- scatter ---
    fig = go.Figure()
    for flag, c in COLOR.items():
        sub = df[(df["flag"] == flag) & reliable]
        if len(sub):
            fig.add_trace(go.Scatter(
                x=sub["availability_z"], y=sub["efficiency_z"], mode="markers",
                marker=dict(size=11, color=c, line=dict(width=0.5, color="black")),
                name=flag, text=sub["label"] + "  (" + sub["minutes"].round(1).astype(str) + " min)",
                hovertemplate="%{text}<br>avail %{x:.2f}, eff %{y:.2f}<extra></extra>"))
    low = df[~reliable]                                        # sub-threshold: efficiency N/A
    if len(low):
        fig.add_trace(go.Scatter(
            x=low["availability_z"], y=[pin] * len(low), mode="markers",
            marker=dict(size=12, color="#ff7f0e", symbol="triangle-down", line=dict(width=0.5, color="black")),
            name=f"min<{MIN_MIN:.0f} (eff N/A)",
            text=low["label"] + "  (" + low["minutes"].round(1).astype(str) + " min)",
            hovertemplate="%{text}<br>avail %{x:.2f}, eff N/A<extra></extra>"))
    fig.add_hline(y=FLAG, line_dash="dash", line_color="grey")
    fig.add_vline(x=FLAG, line_dash="dash", line_color="grey")
    fig.add_hline(y=pin + 0.4, line_color="lightgrey", line_width=1)
    fig.update_layout(
        title=f"{player} — availability vs efficiency (flag if either < {FLAG})",
        xaxis_title="availability z  (minutes vs norm; ← self-removal)",
        yaxis_title="efficiency z  (per-48 production; ↓ dogged it)",
        height=680, width=860)
    fig.write_html(HERE / f"{slug}_two_axis.html")

    # --- static scatter PNG ---
    fig2, ax = plt.subplots(figsize=(9, 6.5))
    for flag, c in COLOR.items():
        sub = df[(df["flag"] == flag) & reliable]
        ax.scatter(sub["availability_z"], sub["efficiency_z"], s=80, c=c, edgecolor="black",
                   linewidth=0.4, label=flag, zorder=3)
    if len(low):
        ax.scatter(low["availability_z"], [pin] * len(low), s=90, c="#ff7f0e", marker="v",
                   edgecolor="black", linewidth=0.4, label=f"min<{MIN_MIN:.0f} (eff N/A)", zorder=3)
        ax.axhline(pin + 0.4, color="lightgrey", lw=1)
    for _, r in df[df["flag"] != "none"].iterrows():
        yv = r["efficiency_z"] if reliable[r.name] else pin
        ax.annotate(r["d"], (r["availability_z"], yv), fontsize=6, xytext=(3, 3),
                    textcoords="offset points")
    ax.axhline(FLAG, ls="--", color="grey"); ax.axvline(FLAG, ls="--", color="grey")
    ax.set_xlabel("availability z  (minutes vs norm; left = self-removal)")
    ax.set_ylabel("efficiency z  (per-48 production; down = dogged it)")
    ax.set_title(f"{player}: availability vs efficiency (flag if either < {FLAG})")
    ax.legend(fontsize=8); ax.grid(True, alpha=0.25)
    fig2.savefig(HERE / f"{slug}_two_axis.png", dpi=120, bbox_inches="tight")

    # --- 2-column heatmap (availability | efficiency), sorted by availability ---
    h = df.sort_values("availability_z").reset_index(drop=True)
    M = h[["availability_z", "efficiency_z"]].to_numpy(dtype=float)
    vmax = np.nanmax(np.abs(M[np.isfinite(M)]))
    masked = np.ma.masked_invalid(M)
    cmap = plt.cm.RdBu_r.copy(); cmap.set_bad("lightgrey")
    fig3, ax3 = plt.subplots(figsize=(4.2, max(4, 0.3 * len(h))))
    im = ax3.imshow(masked, cmap=cmap, vmin=-vmax, vmax=vmax, aspect="auto")
    ax3.set_xticks([0, 1]); ax3.set_xticklabels(["availability z\n(minutes)", "efficiency z\n(per-48, min≥8)"], fontsize=8)
    ax3.set_yticks(range(len(h))); ax3.set_yticklabels(h["label"], fontsize=6)
    for i in range(len(h)):
        for j in range(2):
            v = M[i, j]
            txt = "N/A" if np.isnan(v) else f"{v:.2f}"
            ax3.text(j, i, txt, ha="center", va="center", fontsize=6,
                     color="grey" if np.isnan(v) else ("black" if abs(v) < vmax * 0.6 else "white"))
    ax3.set_title("Two axes (blue = low/worse; grey = N/A)")
    fig3.savefig(HERE / f"{slug}_two_axis_heatmap.png", dpi=120, bbox_inches="tight")

    print(f"wrote {OUT.name}, {slug}_two_axis.html/.png, {slug}_two_axis_heatmap.png "
          f"({len(df)} games; {int(reliable.sum())} scored on efficiency)")
    print(f"\nflagged games (availability or efficiency < {FLAG}):")
    fl = df[df["flag"] != "none"].sort_values("availability_z")
    print(fl[["date", "matchup", "minutes", "availability_z", "efficiency_z", "flag"]]
          .round(2).to_string(index=False))

    import slideshow           # noqa: E402
    slideshow.add(HERE / f"{slug}_two_axis.html", f"{player} — availability vs efficiency (2-axis)",
                  "Minutes-vs-norm (self-removal) vs per-48 production (in-game); flag if either < -1.")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:]]
    if not args:
        raise SystemExit('usage: python player_two_axis.py "Player Name"')
    main(" ".join(args))
