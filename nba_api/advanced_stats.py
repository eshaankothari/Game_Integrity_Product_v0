"""Add advanced box-score metrics to each player-game via BoxScoreAdvancedV3.

Reuses the game_ids already resolved in test_dataset_jan_mar_boxscores.csv, so
the ONLY new calls are BoxScoreAdvancedV3 per unique game (cached to nba_cache/
adv_<game_id>.csv). Pulls, per player:
  netRating, turnoverRatio, trueShootingPercentage, usagePercentage, pace, PIE
and merges them onto the box-score rows -> test_dataset_jan_mar_advanced.csv.

NOTE: stats.nba.com blocks datacenter/VPN IPs -- run on a residential connection.
Caches survive, so reruns only fetch games not yet pulled.

    python advanced_stats.py            # all games (cache first)
    python advanced_stats.py 5          # first 5 rows (smoke test)
"""
import sys
import time
from pathlib import Path

import pandas as pd
import requests
from nba_api.stats.endpoints import boxscoreadvancedv3

# reuse helpers/paths from the traditional box-score script
from box_scores import _ascii, CACHE, TIMEOUT

_root = Path(__file__).resolve().parent
while not (_root / "datapaths.py").exists() and _root.parent != _root:
    _root = _root.parent
sys.path.insert(0, str(_root))
from datapaths import find_data           # noqa: E402  (repo-root helper)

SRC = find_data("test_dataset_jan_mar_boxscores.csv")
OUT = SRC.with_name("test_dataset_jan_mar_advanced.csv")
ADV_COLS = ["netRating", "turnoverRatio", "trueShootingPercentage",
            "usagePercentage", "pace", "PIE"]


RETRIES = 4          # stats.nba.com stalls intermittently; retry with backoff


def adv_players(game_id):
    """Cached BoxScoreAdvancedV3 player_stats for a game (10-digit id).

    Retries on read timeout / connection error (nba.com throttles into stalls),
    waiting longer each attempt. Each success is cached, so reruns resume.
    """
    cache = CACHE / f"adv_{game_id}.csv"
    if cache.exists():
        return pd.read_csv(cache)
    last = None
    for attempt in range(1, RETRIES + 1):
        try:
            b = boxscoreadvancedv3.BoxScoreAdvancedV3(game_id=game_id, timeout=TIMEOUT)
            df = b.player_stats.get_data_frame()
            df.to_csv(cache, index=False)
            return df
        except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError) as e:
            last = e
            wait = 5 * attempt          # 5s, 10s, 15s ...
            print(f"   timeout on {game_id} (attempt {attempt}/{RETRIES}); "
                  f"waiting {wait}s and retrying")
            time.sleep(wait)
    raise last


def adv_row(game_id, player):
    df = adv_players(game_id)
    have = [c for c in ADV_COLS if c in df.columns]
    if not have:
        raise KeyError(f"none of {ADV_COLS} in BoxScoreAdvancedV3 columns: {list(df.columns)}")
    full = (df["firstName"].fillna("") + " " + df["familyName"].fillna("")).map(_ascii)
    hit = df[full == _ascii(player)]
    return (hit.iloc[0], have) if not hit.empty else (None, have)


def main(limit=None):
    box = pd.read_csv(SRC, dtype={"game_id": str})
    box["game_id"] = box["game_id"].str.zfill(10)     # restore leading zeros
    if limit:
        box = box.head(limit)

    rows = []
    for _, r in box.iterrows():
        gid, player = r["game_id"], r["player"]
        try:
            pr, have = adv_row(gid, player)
        except Exception as e:
            print(f"!! {player} game {gid}: advanced fetch failed ({e})")
            pr, have = None, [c for c in ADV_COLS]
        rec = r.to_dict()
        for c in ADV_COLS:
            rec[c] = (None if pr is None or c not in have else pr.get(c))
        rows.append(rec)
        vals = "  ".join(f"{c}={rec[c]}" for c in ADV_COLS)
        print(f"ok {player:22s} {r['date']}  {vals}")

    out = pd.DataFrame(rows)
    out.to_csv(OUT, index=False)
    got = out[ADV_COLS].notna().all(axis=1).sum()
    print(f"\nwrote {OUT.name} ({len(out)} rows, {got} with full advanced stats)")


if __name__ == "__main__":
    lim = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else None
    main(lim)
