"""Record each player's CLOSING Under price for a list of games -> one CSV.

For every event id you pass, this makes ONE historical-odds call, snapshotted
at the game's commence_time (from the events JSON), which returns the last odds
posted before tip -- i.e. the closing line. It writes one row per player:

    game | time | player | bet type | line | closing_price

Cost: exactly 1 API call per game. The Odds API bills historical odds by
(regions x markets), so we use a single region + single market to hit the
floor. The `bookmakers` filter does NOT change cost -- it only narrows the
response -- so keep it to one book for clean, single-price rows.

Every raw response is cached under closing_cache/, so rebuilding the CSV (e.g.
to add a column) re-reads the cache and costs NO new API calls.

    export ODDSAPI_KEY=your_key
    python closing_prices.py
"""
import os
import csv
import json
import time
import requests
from pathlib import Path

API_KEY = os.environ.get("ODDSAPI_KEY")
ODDS_URL = ("https://api.the-odds-api.com/v4/historical/sports/"
            "basketball_nba/events/{event_id}/odds")

import sys
_root = Path(__file__).resolve().parent
while not (_root / "datapaths.py").exists() and _root.parent != _root:
    _root = _root.parent
sys.path.insert(0, str(_root))
from datapaths import find_data           # noqa: E402  (repo-root helper)
EVENTS_FILE = find_data("events_2023-2024_full_season.json")
OUT_CSV = Path(__file__).parent / "closing_under_prices.csv"
CACHE_DIR = Path(__file__).parent / "closing_cache"   # raw responses, per event

# Comma-separated markets. Each market is one "bet type" and adds one billed
# unit per call (cost = regions x markets), but it's still 1 API call per game.
# Extend later, e.g. "player_points,player_rebounds,player_assists".
MARKETS = "player_points"
BOOKMAKER = "fanduel"
REGIONS = "us"
COLUMNS = ["game", "time", "player", "bet type", "line", "closing_price"]


def load_events(events_file=EVENTS_FILE):
    """Return {event_id: event_dict} from the events JSON."""
    return {e["id"]: e for e in json.loads(Path(events_file).read_text())}


def fetch_event_odds(event, markets=MARKETS, bookmaker=BOOKMAKER, regions=REGIONS):
    """Return the raw closing-snapshot `data` dict for a game, or None if the
    API has no odds for it (404). Caches the raw response under CACHE_DIR, so a
    later re-run reads the cache and makes no new API call.
    """
    cache = CACHE_DIR / f"{event['id']}.json"
    if cache.exists():
        return json.loads(cache.read_text())

    params = {
        "apiKey": API_KEY, "regions": regions, "markets": markets,
        "dateFormat": "iso", "oddsFormat": "decimal",
        "bookmakers": bookmaker,
        "date": event["commence_time"],   # closing snapshot
    }
    url = ODDS_URL.format(event_id=event["id"])
    for attempt in range(4):
        resp = requests.get(url, params=params)
        if resp.status_code == 404:
            # No odds snapshot for this game (book didn't post this market, or
            # nothing recorded at commence). Skip it rather than crash the run.
            return None
        if resp.status_code == 429:
            time.sleep(1 + attempt)       # transient rate limit -> back off
            continue
        resp.raise_for_status()
        break
    else:
        return None                        # still rate limited after retries

    data = resp.json().get("data") or {}
    CACHE_DIR.mkdir(exist_ok=True)
    cache.write_text(json.dumps(data))     # keep the full response for later
    return data


def closing_under_rows(event, markets=MARKETS, bookmaker=BOOKMAKER, regions=REGIONS):
    """Closing Under rows for a game: one per player, with the line and price.

    Uses the cached raw response when present (no API call). The snapshot is the
    last one at/just before commence_time, so its point/price are the closing
    line for each player. Keeps every Under across every requested market.
    """
    data = fetch_event_odds(event, markets, bookmaker, regions)
    if data is None:
        return None

    game = f'{event["away_team"]} @ {event["home_team"]}'
    rows = []
    for book in data.get("bookmakers", []):
        if book["key"] != bookmaker:
            continue
        for mkt in book.get("markets", []):        # every requested market
            for outcome in mkt["outcomes"]:
                if outcome["name"] != "Under":
                    continue
                rows.append({
                    "game": game,
                    "time": event["commence_time"],
                    "player": outcome["description"],
                    "bet type": f"{mkt['key']} under",
                    "line": outcome.get("point"),        # the final Under line
                    "closing_price": outcome.get("price"),
                })
    return rows


def build_closing_csv(event_ids, events_file=EVENTS_FILE, out_csv=OUT_CSV,
                      markets=MARKETS, bookmaker=BOOKMAKER):
    """1 call per game; write every game's closing Under prices to one CSV.

    Rows are written to disk as we go, so an error mid-run never loses progress.
    Games with no odds snapshot (404) are skipped and counted, not fatal.
    """
    events = load_events(events_file)
    rows_written = 0
    skipped = []
    with open(out_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        for i, event_id in enumerate(event_ids, 1):
            event = events.get(event_id)
            if not event:
                skipped.append(event_id)
                continue
            rows = closing_under_rows(event, markets=markets, bookmaker=bookmaker)
            if not rows:                       # 404 / no data for this game
                skipped.append(event_id)
            else:
                writer.writerows(rows)
                f.flush()                      # persist progress each game
                rows_written += len(rows)
            if i % 25 == 0 or i == len(event_ids):
                print(f"  {i}/{len(event_ids)} games, {rows_written} rows, "
                      f"{len(skipped)} skipped")
        f.flush()
        os.fsync(f.fileno())               # force the whole CSV to physical disk

    print(f"{rows_written} rows from {len(event_ids) - len(skipped)} games "
          f"({len(skipped)} skipped) -> {Path(out_csv).name}")
    return rows_written, skipped


if __name__ == "__main__":
    events = load_events()
    # Pass any subset here. Default: every game in the JSON (1 call each).
    event_ids = list(events.keys())
    build_closing_csv(event_ids)
