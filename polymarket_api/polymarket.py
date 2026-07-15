import requests
import time
import re
import json
import csv
from pathlib import Path
from collections import defaultdict

# Use the offset-based /events endpoint. It is capped at offset 2000 (past
# that it returns a {"error": ...} dict instead of a list), so we page from
# newest to oldest and stop when we either hit that cap or get a short page.
# This reliably returns the ~2100 most recent NBA events; the keyset endpoint
# was avoided because its cursor loops forever and drops the tag filter.
EVENTS_URL = "https://gamma-api.polymarket.com/events"
TRADES_URL = "https://data-api.polymarket.com/trades"
LIMIT = 100
MAX_OFFSET = 2000         # /events hard cap on offset pagination
MAX_TRADES_OFFSET = 3000  # /trades hard cap on offset pagination

# Cache results next to this file so the API is only ever called once.
CACHE_FILE = Path(__file__).parent / "nba_props.json"       # {slug: markets}
VOLUME_CACHE_FILE = Path(__file__).parent / "market_volume.json"  # {conditionId: {Yes, No}}
CSV_FILE = Path(__file__).parent / "prop_volumes.csv"

# Polymarket has no dedicated "player prop" tag, so we classify by the event
# title. A player prop is about a player's in-game statistical line; we drop
# team futures (champion, series winner, seeds) and player futures (next team,
# awards, contracts).
FUTURES = re.compile(
    r'next team|to leave|to sign|be traded|retire|champion|conference|division|'
    r'series winner|play-?in|playoffs|make the playoffs|number of|no\. of|seed|'
    r'regular season wins|mvp|rookie of the year|defensive player|most improved|'
    r'sixth man|all-?star|cover athlete|coach|contract|draft',
    re.I,
)
PROP = re.compile(
    r'\b(points?|rebounds?|assists?|blocks?|steals?|three|3-point|triple-double|'
    r'double-double|record \d+\+|points leader|assists leader|rebounds leader|'
    r'to score)\b',
    re.I,
)


def is_player_prop(title):
    """True if an event title looks like a player prop (not a future)."""
    return bool(PROP.search(title)) and not FUTURES.search(title)


def _fetch_all_nba_events():
    """Page the Gamma /events endpoint and return every recent NBA event."""
    events = []
    offset = 0
    while offset <= MAX_OFFSET:
        response = requests.get(
            EVENTS_URL,
            params={
                "tag_slug": "nba",
                "order": "id",
                "ascending": "false",  # newest events first
                "limit": LIMIT,
                "offset": offset,
            },
        )
        data = response.json()

        # Past the cap the API returns an error dict instead of a list.
        if not isinstance(data, list):
            break

        events.extend(data)

        # A short page means we've reached the end of the results.
        if len(data) < LIMIT:
            break
        offset += LIMIT
        time.sleep(0.5)  # be polite between pages
    return events


def get_all_NBA_props(refresh=False):
    """Return {event_slug: markets} for every NBA player prop.

    The first call hits the API and writes the result to CACHE_FILE; every
    call after that reads the file instead, so the API is never re-hit unless
    you pass refresh=True.
    """
    if CACHE_FILE.exists() and not refresh:
        return json.loads(CACHE_FILE.read_text())

    props = {
        event["slug"]: event["markets"]
        for event in _fetch_all_nba_events()
        if is_player_prop(event.get("title", ""))
    }
    CACHE_FILE.write_text(json.dumps(props))
    return props


def get_over_under_volume(condition_id):
    """Return {"Yes": over_dollars, "No": under_dollars} for one market.

    Polymarket only reports one combined volume per market, so we rebuild the
    split from trade history: each trade is tagged with its outcome ("Yes" =
    Over, "No" = Under), and its dollar size is price * shares.
    """
    volume = defaultdict(float)
    offset = 0
    while True:
        trades = _get_trades_page(condition_id, offset)
        if not trades:
            break
        for trade in trades:
            volume[trade["outcome"]] += float(trade["size"]) * float(trade["price"])
        if len(trades) < 500:
            break
        offset += 500
        if offset >= MAX_TRADES_OFFSET:
            # The API won't page past 3000 trades, so on the busiest markets the
            # split is based on that 3000-trade sample. Flag it rather than
            # pretend the total is complete.
            print(f"  ! {condition_id[:12]}… >3000 trades; volume is a sample")
            break
        time.sleep(0.5)  # be polite between pages
    return dict(volume)


def _get_trades_page(condition_id, offset):
    """Fetch one page of trades as a list.

    The endpoint returns an error dict instead of a list in two cases: a
    transient rate-limit (retry with backoff) or the permanent 3000-offset cap
    (stop, signalled by returning []).
    """
    for attempt in range(5):
        trades = requests.get(
            TRADES_URL,
            params={"market": condition_id, "limit": 500, "offset": offset},
        ).json()
        if isinstance(trades, list):
            return trades
        if "offset" in str(trades.get("error", "")):
            return []  # hit the historical-activity cap; stop paging
        time.sleep(1 + attempt)  # transient error -> back off and retry
    raise RuntimeError(f"trades endpoint kept failing for {condition_id}: {trades}")


def save_prop_volumes_csv(path=CSV_FILE):
    """Write one CSV row per market: event, question, over volume, under volume.

    Per-market volumes are cached in VOLUME_CACHE_FILE and saved as we go, so a
    re-run (or a resumed interrupted run) skips any market already fetched.
    """
    cache = json.loads(VOLUME_CACHE_FILE.read_text()) if VOLUME_CACHE_FILE.exists() else {}

    rows = []
    for event_slug, markets in get_all_NBA_props().items():
        for market in markets:
            market_slug = market["slug"]
            if market_slug not in cache:
                cache[market_slug] = get_over_under_volume(market["conditionId"])
                VOLUME_CACHE_FILE.write_text(json.dumps(cache))  # save progress
            volume = cache[market_slug]
            rows.append({
                "event_slug": event_slug,
                "market_slug": market_slug,
                "question": market["question"],
                "over_volume": round(volume.get("Yes", 0.0), 2),
                "under_volume": round(volume.get("No", 0.0), 2),
            })

    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    return rows


if __name__ == "__main__":
    rows = save_prop_volumes_csv()
    print(f"Wrote {len(rows)} market rows to {CSV_FILE.name}")
