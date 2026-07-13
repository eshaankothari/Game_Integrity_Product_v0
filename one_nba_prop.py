"""Fetch ONE player prop for a single NBA 2024-25 game from OddsPapi.

The simplest possible end-to-end example: find a finished game, pull its
DraftKings historical odds, and print the first player prop line found.

Run:
    export ODDSPAPI_KEY=your_key      # or put it in .env
    python one_nba_prop.py

NOTE: OddsPapi only retains historical odds for a recent rolling window, so
the 2024-25 season (ended June 2025) will return "no odds". Point TOURNAMENT_ID
and the date window at a currently in-season league to see it print a real prop.
"""
import os
import requests

API_KEY = os.environ.get("ODDSPAPI_KEY")
BASE = "https://api.oddspapi.io/v4"

TOURNAMENT_ID = 132                       # NBA
BOOKMAKER = "draftkings"
SEASON_FROM = "2024-11-01T00:00:00Z"      # any window inside 2024-25
SEASON_TO = "2024-11-08T23:59:59Z"


def get(path, **params):
    """GET one endpoint, returning JSON or raising with the API's message."""
    params["apiKey"] = API_KEY
    r = requests.get(f"{BASE}{path}", params=params)
    if not r.ok:
        raise RuntimeError(f"{r.status_code} from {path}: {r.text}")
    return r.json()


def first_player_prop(fixture_id):
    """Return the first player-prop entry for a game, or None if it has none.

    /historical-odds nests: bookmakers -> markets -> outcomes -> players.
    Player props are entries tied to a real player (playerId != "0").
    """
    data = get("/historical-odds", fixtureId=fixture_id, bookmakers=BOOKMAKER)
    for book in data.get("bookmakers", {}).values():
        for market_id, market in book.get("markets", {}).items():
            for outcome_id, outcome in market.get("outcomes", {}).items():
                for player_id, entries in outcome.get("players", {}).items():
                    if player_id == "0" or not entries:
                        continue
                    return {
                        "marketId": market_id,
                        "outcomeId": outcome_id,
                        "playerId": player_id,
                        "price": entries[0].get("price"),
                        "line": entries[0].get("limit"),
                    }
    return None


def main():
    if not API_KEY:
        raise SystemExit("Set ODDSPAPI_KEY (export it or put it in .env).")

    fixtures = get(
        "/fixtures",
        tournamentId=TOURNAMENT_ID,
        statusId=2,  # finished
        **{"from": SEASON_FROM, "to": SEASON_TO},
    )
    print(f"Found {len(fixtures)} finished games in the window.")

    for fixture in fixtures:
        try:
            prop = first_player_prop(fixture["fixtureId"])
        except RuntimeError:
            continue  # no historical odds for this game; try the next
        if prop:
            print(f"One player prop from game {fixture['fixtureId']}:")
            print(prop)
            return

    print(
        f"No player props available for any game in this window on {BOOKMAKER}.\n"
        "OddsPapi's historical-odds retention has expired for this season."
    )


if __name__ == "__main__":
    main()
