"""Stage B: map each player-game to its OddsAPI historical event_id.

Two sources, cheapest first:
  1. LOCAL: the cached season events file (events_2023-2024_full_season.json) -> 0 calls.
  2. API:   for games not in the local file, the historical events endpoint, batched
            ONE CALL PER UNIQUE DATE (each returns every game that day, cached).

Default is a DRY run: 0 calls, just reports how many games mapped locally and the
EXACT number of events-endpoint calls the remaining games would need.

    python map_events.py            # DRY: report planned calls, write nothing
    python map_events.py run        # REAL: fetch uncached dates, write games_events.csv
"""
import os
import sys
import json
from datetime import timedelta

import pandas as pd
import requests
from nba_api.stats.static import teams as static_teams

import config
from datapaths import find_data

API_KEY = os.environ.get("ODDSAPI_KEY")
EVENTS_URL = "https://api.the-odds-api.com/v4/historical/sports/basketball_nba/events"
ABBR2NICK = {t["abbreviation"]: t["nickname"].lower() for t in static_teams.get_teams()}

_calls = 0                                          # actual events-endpoint calls made


def _nicks(matchup):
    """'MIL vs. PHI' / 'MIL @ CHI' -> (nickname1, nickname2), lowercased."""
    a, b = [s.strip() for s in matchup.replace(" vs. ", " @ ").split(" @ ")]
    return ABBR2NICK.get(a, ""), ABBR2NICK.get(b, "")


def _match(events, date, n1, n2):
    """Find the event on `date` (or the day after, UTC spillover) with both teams."""
    days = {date, (pd.to_datetime(date) + timedelta(days=1)).strftime("%Y-%m-%d")}
    for e in events:
        if e["commence_time"][:10] in days:
            blob = (e["away_team"] + " " + e["home_team"]).lower()
            if n1 and n2 and n1 in blob and n2 in blob:
                return e["id"], e["commence_time"]
    return None, None


def _events_for_date(date):
    """Cached historical-events call for one date (returns list of events)."""
    global _calls
    cache = config.EVENTS_CACHE / f"events_{date}.json"
    if cache.exists():
        return json.loads(cache.read_text()).get("data", [])
    _calls += 1
    d0 = pd.to_datetime(date)
    r = requests.get(EVENTS_URL, params={
        "apiKey": API_KEY, "dateFormat": "iso",
        "commenceTimeFrom": d0.strftime("%Y-%m-%dT00:00:00Z"),
        "commenceTimeTo": (d0 + timedelta(days=2)).strftime("%Y-%m-%dT00:00:00Z"),
        "date": d0.strftime("%Y-%m-%dT18:00:00Z")})
    r.raise_for_status()
    payload = r.json()
    config.EVENTS_CACHE.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(payload))
    return payload.get("data", [])


def map_events(dry=True):
    games = pd.read_csv(config.GAMES_CSV, dtype={"game_id": str})
    local = json.loads(find_data("events_2023-2024_full_season.json").read_text())

    # pass 1: local map
    eid, ct = [], []
    for _, g in games.iterrows():
        n1, n2 = _nicks(g["MATCHUP"])
        i, c = _match(local, g["date"], n1, n2)
        eid.append(i); ct.append(c)
    games["event_id"], games["commence_time"] = eid, ct
    unmatched = games[games["event_id"].isna()]
    need_dates = sorted(unmatched["date"].unique())
    planned = [d for d in need_dates if not (config.EVENTS_CACHE / f"events_{d}.json").exists()]

    print(f"local file matched : {games['event_id'].notna().sum()}/{len(games)} games")
    print(f"unmatched locally  : {len(unmatched)} games across {len(need_dates)} unique dates")
    print(f"already cached      : {len(need_dates) - len(planned)} of those dates")
    print(f"==> PLANNED events-endpoint API calls: {len(planned)}  (1 credit each, 1 per uncached date)")

    if dry:
        print("\nDRY RUN: 0 calls made, nothing written. Re-run with 'run' to execute.")
        return games

    # pass 2: fill the rest from the events endpoint (batched by date)
    for idx, g in unmatched.iterrows():
        events = _events_for_date(g["date"])
        n1, n2 = _nicks(g["MATCHUP"])
        i, c = _match(events, g["date"], n1, n2)
        games.at[idx, "event_id"], games.at[idx, "commence_time"] = i, c

    still = games["event_id"].isna().sum()
    config.ensure_data_dir()
    games.to_csv(config.GAMES_EVENTS_CSV, index=False)
    print(f"\nACTUAL API calls made: {_calls}")
    print(f"wrote {config.GAMES_EVENTS_CSV.name}: {len(games) - still}/{len(games)} mapped"
          + (f"  ({still} STILL unmatched)" if still else ""))
    if still:
        print(games[games['event_id'].isna()][['player', 'date', 'MATCHUP']].to_string(index=False))
    return games


if __name__ == "__main__":
    map_events(dry=("run" not in sys.argv))
