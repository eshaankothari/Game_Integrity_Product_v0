"""Fetch all 12 tracked stats for a player's games (optionally one season), into one CSV.

  python fetch_player_all.py "Jontay Porter" 2023-24        # just that season
  python fetch_player_all.py "Jontay Porter" 2023-24 5      # first 5 (smoke test)
  python fetch_player_all.py "Jontay Porter"                # entire career

Step 1 (1 call): LeagueGameFinder -> every game_id the player played (then season-filtered).
Step 2 (per game): traditional + advanced + hustle box scores, reusing the cached/
        retried fetchers (box_players / adv_players / hustle_players). Extracts:
  box     : minutes, points, rebounds, assists, plusMinus, fga
  advanced: turnoverRatio, usagePercentage
  hustle  : contestedShots, deflections, looseBallsRecoveredTotal, boxOuts

Writes <player_slug>_all_games.csv (one row per game, chronological).
Run on a residential connection (stats.nba.com blocks datacenter/VPN IPs).
Every box score caches, so reruns resume where a stall left off.
"""
import sys
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import requests
from nba_api.stats.static import players
from nba_api.stats.endpoints import leaguegamefinder

from box_scores import box_players, _ascii
from advanced_stats import adv_players
from beasley_hustle import hustle_players
from player_track import track_players

RETRIES = 4
WORKERS = 6          # games fetched concurrently (lower to ~3 if nba.com starts timing out)
BOX = {"minutes": "minutes", "points": "points", "rebounds": "reboundsTotal",
       "assists": "assists", "plusMinus": "plusMinusPoints", "fga": "fieldGoalsAttempted"}
ADV = {"turnoverRatio": "turnoverRatio", "usagePercentage": "usagePercentage"}
HUS = {"contestedShots": "contestedShots", "deflections": "deflections",
       "looseBallsRecoveredTotal": "looseBallsRecoveredTotal", "boxOuts": "boxOuts"}
TRK = {"speed": "speed", "distance": "distance", "touches": "touches"}


def _min_to_float(m):
    if pd.isna(m):
        return None
    s = str(m)
    if ":" in s:
        mm, ss = s.split(":")[:2]
        return round(int(mm) + int(ss) / 60, 3)
    try:
        return float(s)
    except ValueError:
        return None


def _match(df, player):
    """Row for `player` in a box-score data frame (accent-insensitive), or None."""
    full = (df["firstName"].fillna("") + " " + df["familyName"].fillna("")).map(_ascii)
    hit = df[full == _ascii(player)]
    return hit.iloc[0] if not hit.empty else None


def all_games(player_id):
    """Every game (id, date, matchup, season) for a player (1 call, retried)."""
    last = None
    for attempt in range(1, RETRIES + 1):
        try:
            gf = leaguegamefinder.LeagueGameFinder(player_id_nullable=player_id, timeout=30)
            g = gf.get_data_frames()[0]
            # regular season only: SEASON_ID "2...." (preseason="1", allstar="3", playoffs="4");
            # equivalently game_id prefix "002". Excludes preseason games with no tracking data.
            g = g[g["SEASON_ID"].astype(str).str.startswith("2")].copy()
            g["game_id"] = g["GAME_ID"].astype(str).str.zfill(10)
            g["date"] = pd.to_datetime(g["GAME_DATE"]).dt.strftime("%Y-%m-%d")
            g["season"] = g["SEASON_ID"].astype(str).str[-4:].astype(int)
            g["season"] = g["season"].map(lambda y: f"{y}-{str(y+1)[-2:]}")
            return g[["game_id", "date", "MATCHUP", "season"]].sort_values("date").reset_index(drop=True)
        except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError) as e:
            last = e
            print(f"   gamefinder timeout (attempt {attempt}/{RETRIES}); waiting {5*attempt}s")
            time.sleep(5 * attempt)
    raise last


def _process_game(g, player):
    """Fetch one game's box+advanced+hustle+track for `player`; row dict or None."""
    gid = g["game_id"]

    def _try(fn):                           # each endpoint independent; box is essential
        try:
            return _match(fn(gid), player)
        except Exception as e:
            print(f"   {g['date']} {gid}: {fn.__name__} failed ({e})")
            return None

    b = _try(box_players)
    if b is None:
        print(f"!! {g['date']} game {gid}: {player} not in box / box failed (DNP?)")
        return None
    a, h, t = _try(adv_players), _try(hustle_players), _try(track_players)
    rec = {"player": player, "season": g["season"], "date": g["date"],
           "matchup": g["MATCHUP"], "game_id": gid, "minutes": _min_to_float(b.get("minutes"))}
    for name, col in list(BOX.items())[1:]:
        rec[name] = pd.to_numeric(b.get(col), errors="coerce")
    for name, col in ADV.items():
        rec[name] = pd.to_numeric(a.get(col), errors="coerce") if a is not None else None
    for name, col in HUS.items():
        rec[name] = pd.to_numeric(h.get(col), errors="coerce") if h is not None else None
    for name, col in TRK.items():
        rec[name] = pd.to_numeric(t.get(col), errors="coerce") if t is not None else None
    print(f"ok {g['season']} {g['date']}  {g['MATCHUP']:16s} pts={rec['points']} min={rec['minutes']}")
    return rec


def main(player, season=None, limit=None):
    pid = players.find_players_by_full_name(player)[0]["id"]
    games = all_games(pid)
    if season:
        games = games[games["season"] == season].reset_index(drop=True)
        print(f"filtered to {season}: {len(games)} games")
    if limit:
        games = games.head(limit)
    slug = player.lower().replace(" ", "_")
    out_path = Path(__file__).parent / f"{slug}_all_games.csv"
    print(f"{player} (id {pid}): {len(games)} career games\n")

    # fetch games concurrently (each game still does its 4 endpoints in order,
    # so at most WORKERS connections are open at once)
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        results = list(ex.map(lambda gr: _process_game(gr[1], player), games.iterrows()))
    rows = [r for r in results if r is not None]

    df = pd.DataFrame(rows)
    df.to_csv(out_path, index=False)
    stat_cols = ["minutes"] + list(BOX)[1:] + list(ADV) + list(HUS) + list(TRK)
    full = df[stat_cols].notna().all(axis=1).sum()
    print(f"\nwrote {out_path.name} ({len(df)} games, {full} with all 12 stats)")


if __name__ == "__main__":
    import re
    season = next((a for a in sys.argv[1:] if re.fullmatch(r"\d{4}-\d{2}", a)), None)
    lim = next((int(a) for a in sys.argv[1:] if a.isdigit()), None)
    name = [a for a in sys.argv[1:] if not a.isdigit() and a != season]
    if not name:
        raise SystemExit('usage: python fetch_player_all.py "Player Name" [2023-24] [limit]')
    main(" ".join(name), season, lim)
