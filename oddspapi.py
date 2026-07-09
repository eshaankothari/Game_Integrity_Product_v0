"""Fetch all historical NBA prop odds, per game, for the 2024-25 season.

Uses the OddsPapi API (https://api.oddspapi.io). Player props come back nested
inside each game's historical odds. Past odds never change, so every game's
response is cached to disk and never re-fetched.

Setup:
    export ODDSPAPI_KEY=your_key
    python -c "import oddspapi; oddspapi.discover()"   # find NBA's tournamentId
    # paste that id into TOURNAMENT_ID below, then:
    python oddspapi.py
"""
import os
import time
import json
import csv
import requests
from pathlib import Path

API_KEY = os.environ.get("ODDSPAPI_KEY")
BASE = "https://api.oddspapi.io/v4"

TOURNAMENT_ID = 132                          # NBA league id — run discover()
BOOKMAKERS = "pinnacle,draftkings,fanduel"    # max 3 slugs — see discover()
SEASON_FROM = "2024-10-22T00:00:00Z"
SEASON_TO = "2025-06-23T23:59:59Z"

CACHE_DIR = Path(__file__).parent / "oddspapi_cache"
CSV_FILE = Path(__file__).parent / "nba_prop_odds.csv"


def _get(path, **params):
    """GET one endpoint and return its JSON, waiting out rate limits."""
    params["apiKey"] = API_KEY
    for _ in range(6):
        response = requests.get(f"{BASE}{path}", params=params)
        if response.status_code == 429:
            # The API tells us exactly how long to wait (retryMs).
            retry_ms = response.json().get("error", {}).get("retryMs", 2000)
            time.sleep(retry_ms / 1000 + 0.25)
            continue
        if not response.ok:
            # Surface the API's own message (raise_for_status hides it).
            raise RuntimeError(f"{response.status_code} from {path}: {response.text}")
        return response.json()
    raise RuntimeError(f"still rate limited after retries: {path}")


def discover(query, kind="sports", sport_id=None):
    """Search a reference list for `query` and print the matches only.

        discover("basketball")                              # -> basketball sportId
        discover("NBA", "tournaments", sport_id=<that id>)  # -> NBA tournamentId
        discover("draftkings", "bookmakers")                # -> a bookmaker slug
    """
    endpoint = {"sports": "/sports", "tournaments": "/tournaments",
                "bookmakers": "/bookmakers"}[kind]
    params = {"sportId": sport_id} if kind == "tournaments" else {}
    hits = [item for item in _get(endpoint, **params)
            if query.lower() in json.dumps(item).lower()]
    print(json.dumps(hits, indent=2))
    return hits


def get_season_fixtures():
    """Return every finished NBA game in the season window."""
    if TOURNAMENT_ID is None:
        raise SystemExit(
            "Set TOURNAMENT_ID first. Find NBA's id with:\n"
            "  python3 -c \"import oddspapi; oddspapi.discover('basketball')\"\n"
            "  python3 -c \"import oddspapi; oddspapi.discover('NBA', 'tournaments', sport_id=<ID>)\""
        )
    return _get(
        "/fixtures",
        tournamentId=TOURNAMENT_ID,
        statusId=2,  # finished
        **{"from": SEASON_FROM, "to": SEASON_TO},
    )


def get_historical_odds(fixture_id):
    """Return one game's historical odds (incl. player props), cached to disk.

    Returns {} for games the API has no historical odds for (a 404), so the
    season run skips them instead of crashing.
    """
    cache = CACHE_DIR / f"{fixture_id}.json"
    if cache.exists():
        return json.loads(cache.read_text())

    try:
        data = _get("/historical-odds", fixtureId=fixture_id, bookmakers=BOOKMAKERS)
    except RuntimeError as err:
        if "No historical odds" in str(err):
            return {}  # this game has no odds for these books; skip it
        raise
    CACHE_DIR.mkdir(exist_ok=True)
    cache.write_text(json.dumps(data))
    return data


def get_prop_odds(fixture_id):
    """Return only the player-prop odds for one game.

    /v4/historical-odds nests bookmakers -> markets -> outcomes -> players.
    Player props are the entries tied to a real player (playerId != "0");
    game markets (moneyline/spread/total) use playerId "0", so we skip those.
    """
    data = get_historical_odds(fixture_id)
    rows = []
    for slug, book in data.get("bookmakers", {}).items():
        for market_id, market in book.get("markets", {}).items():
            for outcome_id, outcome in market.get("outcomes", {}).items():
                for player_id, entries in outcome.get("players", {}).items():
                    if player_id == "0":
                        continue  # not a player prop
                    for entry in entries:
                        rows.append({
                            "fixtureId": fixture_id,
                            "bookmaker": slug,
                            "marketId": market_id,
                            "outcomeId": outcome_id,
                            "playerId": player_id,
                            "price": entry.get("price"),
                            "limit": entry.get("limit"),
                            "active": entry.get("active"),
                            "createdAt": entry.get("createdAt"),
                        })
    return rows


def fetch_all():
    """Write every NBA prop bet's odds for the season to CSV."""
    fixtures = get_season_fixtures()
    rows, games_with_odds = [], 0
    for fixture in fixtures:
        prop_rows = get_prop_odds(fixture["fixtureId"])
        if prop_rows:
            games_with_odds += 1
            rows.extend(prop_rows)
        time.sleep(1.5)  # stay under the ~1-req-per-few-seconds rate limit

    if not rows:
        # Every game came back empty -> almost certainly bad bookmaker slugs.
        raise SystemExit(
            f"No prop odds across {len(fixtures)} games. Check the BOOKMAKERS "
            "slugs, e.g.:\n"
            "  python3 -c \"import oddspapi; oddspapi.discover('draftkings', 'bookmakers')\""
        )

    with open(CSV_FILE, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"{games_with_odds}/{len(fixtures)} games had prop odds")
    return rows


if __name__ == "__main__":
    rows = fetch_all()
    print(f"Wrote {len(rows)} NBA prop odds to {CSV_FILE.name}")
