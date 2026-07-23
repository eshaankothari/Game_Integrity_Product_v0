"""Pull every 2023-24 game for Malik Beasley via the traditional box score.

Step 1 (1 call): PlayerGameLog -> all his regular-season game_ids + dates.
Step 2 (per game): BoxScoreTraditionalV3 (reusing box_scores.box_players, which
        caches to nba_cache/box_<id>.csv and retries on nba.com timeouts).
Extract points, rebounds, assists, minutes for Beasley (accent-insensitive match).

Writes beasley_2023_24_boxscores.csv next to this script.

NOTE: stats.nba.com blocks datacenter/VPN IPs -- run on a residential connection.
Caches survive, so reruns only fetch games not already pulled.

    python beasley_season.py            # all games (cache first)
    python beasley_season.py 5          # first 5 games (smoke test)
"""
import sys
import time
from pathlib import Path

import pandas as pd
import requests
from nba_api.stats.static import players
from nba_api.stats.endpoints import playergamelog

from box_scores import box_players, _ascii   # reuse existing traditional-box-score code

HERE = Path(__file__).parent
PLAYER = "Malik Beasley"
SEASON = "2023-24"
OUT = HERE / "beasley_2023_24_boxscores.csv"
RETRIES = 4


def game_log(player_id):
    """All regular-season games for the player (1 call, retried)."""
    last = None
    for attempt in range(1, RETRIES + 1):
        try:
            gl = playergamelog.PlayerGameLog(player_id=player_id, season=SEASON,
                                             season_type_all_star="Regular Season", timeout=30)
            return gl.get_data_frames()[0]
        except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError) as e:
            last = e
            print(f"   game-log timeout (attempt {attempt}/{RETRIES}); waiting {5*attempt}s")
            time.sleep(5 * attempt)
    raise last


def main(limit=None):
    pid = players.find_players_by_full_name(PLAYER)[0]["id"]
    log = game_log(pid)
    log["gid"] = log["Game_ID"].astype(str).str.zfill(10)
    log["date"] = pd.to_datetime(log["GAME_DATE"]).dt.strftime("%Y-%m-%d")   # e.g. "NOV 05, 2023"
    games = log[["gid", "date", "MATCHUP"]].sort_values("date").reset_index(drop=True)
    if limit:
        games = games.head(limit)
    print(f"{PLAYER} {SEASON}: {len(games)} regular-season games\n")

    rows = []
    for _, g in games.iterrows():
        gid = g["gid"]
        try:
            df = box_players(gid)
        except Exception as e:
            print(f"!! {g['date']} game {gid}: box score failed ({e})")
            continue
        full = (df["firstName"].fillna("") + " " + df["familyName"].fillna("")).map(_ascii)
        hit = df[full == _ascii(PLAYER)]
        if hit.empty:
            print(f"!! {g['date']} game {gid}: {PLAYER} not in box score (DNP?)")
            continue
        r = hit.iloc[0]
        rows.append({
            "player": PLAYER, "date": g["date"], "matchup": g["MATCHUP"], "game_id": gid,
            "minutes": r.get("minutes"), "points": r.get("points"),
            "rebounds": r.get("reboundsTotal"), "assists": r.get("assists"),
        })
        print(f"ok {g['date']}  {g['MATCHUP']:20s}  pts={r.get('points')} reb={r.get('reboundsTotal')} "
              f"ast={r.get('assists')} min={r.get('minutes')}")

    out = pd.DataFrame(rows)
    out.to_csv(OUT, index=False)
    print(f"\nwrote {OUT.name} ({len(out)} games)")
    if not out.empty:
        print("season averages:",
              out[["points", "rebounds", "assists"]].apply(pd.to_numeric, errors="coerce").mean().round(1).to_dict())


if __name__ == "__main__":
    lim = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else None
    main(lim)
