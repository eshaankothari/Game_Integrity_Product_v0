"""Expand test_dataset_jan_mar.csv with 6 more players (stars + mid-tier).

Self-contained (does NOT import the moved price_movement.py). Caches to the
ROOT snapshot_cache/ so the 54 existing snapshots are reused and the ~46 new
ones are saved there -- no re-fetching, work is durable.

Same recipe as test_dataset.py: for each new player-game, opening snapshot at
-OPEN_OFFSET_HOURS and closing snapshot at tip. New rows are APPENDED (existing
players/rows untouched; re-running skips anything already in the CSV).

    python expand_dataset.py        # DRY: prints call count, writes nothing
    python expand_dataset.py run    # REAL: fetches only-uncached snapshots + appends
"""
import os
import sys
import json
import requests
from pathlib import Path
from datetime import timedelta

import pandas as pd

API_KEY = os.environ.get("ODDSAPI_KEY")
ODDS_URL = ("https://api.the-odds-api.com/v4/historical/sports/"
            "basketball_nba/events/{event_id}/odds")
FMT = "%Y-%m-%dT%H:%M:%SZ"

HERE = Path(__file__).parent                 # OddsAPI/
KF = HERE / "Key Figures"
CACHE_DIR = HERE.parent / "snapshot_cache"   # ROOT cache (shared, already has 54)
CSV_IN = KF / "closing_under_prices.csv"
EVENTS = KF / "events_2023-2024_full_season.json"
OUT = KF / "test_dataset_jan_mar.csv"

# 6 new players, all in the legitimate 'control' group (variety: stars + mid-tier)
NEW_PLAYERS = {
    "Kevin Durant": "control", "Anthony Edwards": "control", "LeBron James": "control",
    "Bogdan Bogdanovic": "control", "Coby White": "control", "Naz Reid": "control",
}
CAP = 5
START, END = "2024-01-01", "2024-04-01"
OPEN_OFFSET_HOURS = 12
MARKET, BOOK, REGIONS = "player_points", "fanduel", "us"
COLUMNS = ["player", "group", "game", "time",
           "start_snapshot", "start_line", "start_over", "start_under",
           "close_snapshot", "close_line", "close_over", "close_under"]


def _cache_path(event_id, date):
    tag = f"{date}_{MARKET}_{BOOK}_{REGIONS}".replace(":", "").replace("/", "")
    return CACHE_DIR / f"{event_id}_{tag}.json"


def get_event_odds(event_id, date):
    """Cached snapshot fetch (root cache). Returns payload or None on 404."""
    cache = _cache_path(event_id, date)
    if cache.exists():
        return json.loads(cache.read_text())
    resp = requests.get(ODDS_URL.format(event_id=event_id), params={
        "apiKey": API_KEY, "regions": REGIONS, "markets": MARKET,
        "dateFormat": "iso", "oddsFormat": "decimal", "bookmakers": BOOK,
        "date": date, "includeRotationNumbers": "true", "includeMultipliers": "true"})
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    payload = resp.json()
    CACHE_DIR.mkdir(exist_ok=True)
    cache.write_text(json.dumps(payload))
    return payload


def _player_ou(resp, player):
    """Return {point, over, under} for a player at a snapshot."""
    out = {}
    data = (resp or {}).get("data") or {}
    for book in data.get("bookmakers", []):
        if book["key"] != BOOK:
            continue
        for mkt in book.get("markets", []):
            if mkt["key"] != MARKET:
                continue
            for o in mkt["outcomes"]:
                if o["description"] == player:
                    out["point"] = o.get("point")
                    out[o["name"].lower()] = o.get("price")   # over / under
    return out


def build_selection():
    df = pd.read_csv(CSV_IN); df["time"] = pd.to_datetime(df["time"])
    win = df[(df["time"] >= START) & (df["time"] < END)]
    sel = []
    for player, grp in NEW_PLAYERS.items():
        for _, r in win[win["player"] == player].sort_values("time").head(CAP).iterrows():
            sel.append({"player": player, "group": grp, "game": r["game"], "time": r["time"]})
    return sel


def event_lookup():
    events = json.loads(EVENTS.read_text())
    return {(f"{e['away_team']} @ {e['home_team']}", pd.to_datetime(e["commence_time"])): e["id"]
            for e in events}


def run(dry=True):
    sel = build_selection()
    key2id = event_lookup()

    # already-present (player,time) pairs, so a re-run doesn't duplicate
    have = set()
    if OUT.exists():
        old = pd.read_csv(OUT)
        have = {(p, str(pd.to_datetime(t))) for p, t in zip(old["player"], old["time"])}
    sel = [s for s in sel if (s["player"], str(s["time"])) not in have]

    # count new (uncached) calls over UNIQUE (event, snapshot) pairs, so shared
    # games (teammates) aren't double-counted before caching dedupes them
    snapshots = set()
    for s in sel:
        eid = key2id.get((s["game"], s["time"]))
        if not eid:
            continue
        for dt in [s["time"] - timedelta(hours=OPEN_OFFSET_HOURS), s["time"]]:
            snapshots.add((eid, dt.strftime(FMT)))
    calls = sum(1 for eid, d in snapshots if not _cache_path(eid, d).exists())
    print(f"{len(sel)} new player-games, {len(snapshots)//2} unique games; "
          f"NEW API calls (unique uncached snapshots): {calls}")
    if dry:
        print("DRY RUN: no API calls, nothing appended. Run with 'run' to execute.")
        return

    rows = []
    for s in sel:
        eid = key2id.get((s["game"], s["time"]))
        commence = s["time"]
        oresp = get_event_odds(eid, (commence - timedelta(hours=OPEN_OFFSET_HOURS)).strftime(FMT))
        cresp = get_event_odds(eid, commence.strftime(FMT))
        o, c = _player_ou(oresp, s["player"]), _player_ou(cresp, s["player"])
        rows.append({
            "player": s["player"], "group": s["group"], "game": s["game"],
            "time": commence.strftime(FMT),
            "start_snapshot": (oresp or {}).get("timestamp"),
            "start_line": o.get("point"), "start_over": o.get("over"), "start_under": o.get("under"),
            "close_snapshot": (cresp or {}).get("timestamp"),
            "close_line": c.get("point"), "close_over": c.get("over"), "close_under": c.get("under"),
        })

    new_df = pd.DataFrame(rows, columns=COLUMNS)
    combined = pd.concat([pd.read_csv(OUT), new_df], ignore_index=True) if OUT.exists() else new_df
    combined.to_csv(OUT, index=False)
    blanks = sum(1 for r in rows if r["start_line"] is None)
    print(f"appended {len(rows)} rows -> {OUT.name} (now {len(combined)} total); "
          f"{blanks} had no -12h opening (fill separately if wanted)")


if __name__ == "__main__":
    run(dry=("run" not in sys.argv))
