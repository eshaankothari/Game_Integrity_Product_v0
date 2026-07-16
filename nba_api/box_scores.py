"""For each player-game in the test set, pull that player's box score.

Two steps per game (both cached to nba_cache/, so reruns cost 0 calls):
  1. resolve the NBA game_id from the game's US/Eastern date + team names
     (ScoreboardV2 for that date -> match home/away team ids)
  2. BoxScoreTraditionalV3(game_id) -> that player's row (points, min, reb, ast...)

Then join the actual points against the closing prop line to see the result
(under = actual points < close_line).

NOTE: stats.nba.com blocks datacenter/VPN IPs -- run this on a residential
connection. Caches survive so you only pay for games not yet fetched.

    python box_scores.py            # process all rows (uses cache first)
    python box_scores.py 5          # only the first 5 rows (smoke test)
"""
import sys
import json
import unicodedata
from pathlib import Path

import pandas as pd
from nba_api.stats.static import teams as static_teams
from nba_api.stats.endpoints import scoreboardv2, boxscoretraditionalv3

HERE = Path(__file__).parent
ROOT = HERE.parent                        # project root (holds OddsAPI/ and nba_api/)
KF = ROOT / "OddsAPI" / "Key Figures"     # data lives under OddsAPI, not next to this script
SRC = KF / "test_dataset_jan_mar.csv"
OUT = KF / "test_dataset_jan_mar_boxscores.csv"
CACHE = ROOT / "nba_cache"
CACHE.mkdir(exist_ok=True)
TIMEOUT = 30

# full team name -> NBA team id (e.g. "Toronto Raptors" -> 1610612761)
NAME_TO_ID = {t["full_name"]: t["id"] for t in static_teams.get_teams()}


def _ascii(s):
    """Strip accents/diacritics so 'Jokić' matches 'Jokic'."""
    s = unicodedata.normalize("NFKD", str(s))
    return "".join(c for c in s if not unicodedata.combining(c)).strip().lower()


def us_date(ts):
    """UTC timestamp -> US/Eastern calendar date (NBA's game date)."""
    return pd.to_datetime(ts, utc=True).tz_convert("America/New_York").strftime("%Y-%m-%d")


def teams_from_game(game):
    """'Away Team @ Home Team' -> (away_id, home_id) or (None, None)."""
    away, home = [s.strip() for s in game.split("@")]
    return NAME_TO_ID.get(away), NAME_TO_ID.get(home)


def scoreboard(date):
    """Cached ScoreboardV2 game_header for a date (list of game dicts)."""
    cache = CACHE / f"sb_{date}.csv"
    if cache.exists():
        return pd.read_csv(cache)
    sb = scoreboardv2.ScoreboardV2(game_date=date, league_id="00", timeout=TIMEOUT)
    gh = sb.game_header.get_data_frame()
    gh.to_csv(cache, index=False)
    return gh


def resolve_game_id(date, away_id, home_id):
    gh = scoreboard(date)
    hit = gh[(gh["HOME_TEAM_ID"] == home_id) & (gh["VISITOR_TEAM_ID"] == away_id)]
    if hit.empty:  # try swapped, in case the game string order is reversed
        hit = gh[(gh["HOME_TEAM_ID"] == away_id) & (gh["VISITOR_TEAM_ID"] == home_id)]
    return str(hit.iloc[0]["GAME_ID"]).zfill(10) if not hit.empty else None


def box_players(game_id):
    """Cached BoxScoreTraditionalV3 player_stats for a game."""
    cache = CACHE / f"box_{game_id}.csv"
    if cache.exists():
        return pd.read_csv(cache)
    b = boxscoretraditionalv3.BoxScoreTraditionalV3(game_id=game_id, timeout=TIMEOUT)
    df = b.player_stats.get_data_frame()
    df.to_csv(cache, index=False)
    return df


def player_row(game_id, player):
    df = box_players(game_id)
    full = (df["firstName"].fillna("") + " " + df["familyName"].fillna("")).map(_ascii)
    hit = df[full == _ascii(player)]
    return hit.iloc[0] if not hit.empty else None


def main(limit=None):
    src = pd.read_csv(SRC)
    if limit:
        src = src.head(limit)

    rows = []
    for _, r in src.iterrows():
        date = us_date(r["time"])
        away_id, home_id = teams_from_game(r["game"])
        if not away_id or not home_id:
            print(f"!! {r['player']} {date}: could not map teams '{r['game']}'")
            continue
        try:
            gid = resolve_game_id(date, away_id, home_id)
        except Exception as e:
            print(f"!! {r['player']} {date}: scoreboard failed ({e})")
            continue
        if not gid:
            print(f"!! {r['player']} {date}: game not found on scoreboard")
            continue
        try:
            pr = player_row(gid, r["player"])
        except Exception as e:
            print(f"!! {r['player']} {date} game {gid}: box score failed ({e})")
            continue
        if pr is None:
            print(f"!! {r['player']} {date} game {gid}: player not in box score (DNP?)")
            pts = None
        else:
            pts = pr.get("points")
        line = r["close_line"]
        rows.append({
            "player": r["player"], "group": r["group"], "game": r["game"],
            "date": date, "game_id": gid,
            "minutes": None if pr is None else pr.get("minutes"),
            "points": pts,
            "rebounds": None if pr is None else pr.get("reboundsTotal"),
            "assists": None if pr is None else pr.get("assists"),
            "close_line": line,
            "margin_vs_line": None if pts is None or pd.isna(line) else round(line - pts, 1),
            "result": None if pts is None or pd.isna(line) else ("UNDER" if pts < line else "OVER"),
        })
        print(f"ok {r['player']:22s} {date}  game {gid}  pts={pts}  line={line}")

    out = pd.DataFrame(rows)
    out.to_csv(OUT, index=False)
    print(f"\nwrote {OUT.name} ({len(out)} rows)")
    if not out.empty and "result" in out:
        res = out.dropna(subset=["result"])
        print("\nresult by group:")
        print(res.groupby(["group", "result"]).size().to_string())


if __name__ == "__main__":
    lim = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else None
    main(lim)
