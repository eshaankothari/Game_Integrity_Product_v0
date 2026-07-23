"""Hustle stats for every Beasley 2023-24 game (BoxScoreHustleV2).

Pulls, per game (cached to nba_cache/hustle_<id>.csv, retried on nba.com stalls):
  contestedShots, deflections, looseBallsRecoveredTotal, boxOuts
for Malik Beasley, and writes beasley_2023_24_hustle.csv.

NOTE: new endpoint -> ~79 fresh calls; run on a residential connection.
Caches survive, so reruns only fetch games not already pulled.

    python beasley_hustle.py            # all games
    python beasley_hustle.py 5          # first 5 (smoke test)
"""
import sys
import time
from pathlib import Path

import pandas as pd
import requests
from nba_api.stats.endpoints import boxscorehustlev2

from box_scores import _ascii, CACHE, TIMEOUT

_root = Path(__file__).resolve().parent
while not (_root / "datapaths.py").exists() and _root.parent != _root:
    _root = _root.parent
sys.path.insert(0, str(_root))
from datapaths import find_data           # noqa: E402  (repo-root helper)

PLAYER = "Malik Beasley"
SRC = find_data("beasley_2023_24_boxscores.csv")
OUT = SRC.with_name("beasley_2023_24_hustle.csv")
HUSTLE_COLS = ["contestedShots", "deflections", "looseBallsRecoveredTotal", "boxOuts"]
RETRIES = 4


def hustle_players(game_id):
    """Cached BoxScoreHustleV2 player_stats for a game (retried)."""
    cache = CACHE / f"hustle_{game_id}.csv"
    if cache.exists():
        return pd.read_csv(cache)
    last = None
    for attempt in range(1, RETRIES + 1):
        try:
            b = boxscorehustlev2.BoxScoreHustleV2(game_id=game_id, timeout=TIMEOUT)
            df = b.player_stats.get_data_frame()
            df.to_csv(cache, index=False)
            return df
        except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError) as e:
            last = e
            print(f"   timeout on {game_id} (attempt {attempt}/{RETRIES}); waiting {5*attempt}s")
            time.sleep(5 * attempt)
    raise last


def main(limit=None):
    box = pd.read_csv(SRC, dtype={"game_id": str})
    box["game_id"] = box["game_id"].str.zfill(10)
    if limit:
        box = box.head(limit)

    rows = []
    for _, g in box.iterrows():
        gid = g["game_id"]
        try:
            df = hustle_players(gid)
        except Exception as e:
            print(f"!! {g['date']} game {gid}: hustle fetch failed ({e})")
            continue
        have = [c for c in HUSTLE_COLS if c in df.columns]
        if not have:
            print(f"!! {gid}: none of {HUSTLE_COLS} in columns: {list(df.columns)}")
        full = (df["firstName"].fillna("") + " " + df["familyName"].fillna("")).map(_ascii)
        hit = df[full == _ascii(PLAYER)]
        rec = {"date": g["date"], "matchup": g["matchup"], "game_id": gid}
        for c in HUSTLE_COLS:
            rec[c] = (df.loc[hit.index[0], c] if (not hit.empty and c in df.columns) else None)
        rows.append(rec)
        print(f"ok {g['date']}  {g['matchup']:20s}  " +
              "  ".join(f"{c}={rec[c]}" for c in HUSTLE_COLS))

    out = pd.DataFrame(rows)
    out.to_csv(OUT, index=False)
    got = out[HUSTLE_COLS].notna().all(axis=1).sum()
    print(f"\nwrote {OUT.name} ({len(out)} games, {got} with full hustle stats)")


if __name__ == "__main__":
    lim = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else None
    main(lim)
