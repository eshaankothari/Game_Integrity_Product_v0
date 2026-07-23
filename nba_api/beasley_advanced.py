"""Advanced box-score metrics for every Beasley 2023-24 game (BoxScoreAdvancedV3).

Reuses advanced_stats.adv_row (same retry/caching to nba_cache/adv_<id>.csv), so
games already pulled for the Jan-Mar set load instantly. For each of Beasley's
game_ids in beasley_2023_24_boxscores.csv, extracts:
  netRating, turnoverRatio, trueShootingPercentage, usagePercentage, pace, PIE
and merges them onto his per-game rows -> beasley_2023_24_advanced.csv.

NOTE: run on a residential connection (stats.nba.com blocks datacenter/VPN IPs).

    python beasley_advanced.py            # all games (cache first)
    python beasley_advanced.py 5          # first 5 (smoke test)
"""
import sys
from pathlib import Path

import pandas as pd

from advanced_stats import adv_row, ADV_COLS   # reuse the advanced fetch + retry/cache

_root = Path(__file__).resolve().parent
while not (_root / "datapaths.py").exists() and _root.parent != _root:
    _root = _root.parent
sys.path.insert(0, str(_root))
from datapaths import find_data           # noqa: E402  (repo-root helper)

PLAYER = "Malik Beasley"
SRC = find_data("beasley_2023_24_boxscores.csv")
OUT = SRC.with_name("beasley_2023_24_advanced.csv")


def main(limit=None):
    box = pd.read_csv(SRC, dtype={"game_id": str})
    box["game_id"] = box["game_id"].str.zfill(10)
    if limit:
        box = box.head(limit)

    rows = []
    for _, r in box.iterrows():
        gid = r["game_id"]
        try:
            pr, have = adv_row(gid, PLAYER)
        except Exception as e:
            print(f"!! {r['date']} game {gid}: advanced fetch failed ({e})")
            pr, have = None, list(ADV_COLS)
        rec = r.to_dict()
        for c in ADV_COLS:
            rec[c] = (None if pr is None or c not in have else pr.get(c))
        rows.append(rec)
        vals = "  ".join(f"{c}={rec[c]}" for c in ADV_COLS)
        print(f"ok {r['date']}  {r.get('matchup','')}  {vals}")

    out = pd.DataFrame(rows)
    out.to_csv(OUT, index=False)
    got = out[ADV_COLS].notna().all(axis=1).sum()
    print(f"\nwrote {OUT.name} ({len(out)} games, {got} with full advanced stats)")
    if got:
        print("\nseason advanced averages:")
        print(out[ADV_COLS].apply(pd.to_numeric, errors="coerce").mean().round(3).to_string())


if __name__ == "__main__":
    lim = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else None
    main(lim)
