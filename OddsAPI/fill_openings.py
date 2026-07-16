"""Fill blank start_line rows in test_dataset_jan_mar.csv with an earlier snapshot.

For every row missing start_line, take ONE snapshot before tip (-3h for normal
players, -10min for Porter whose lines open late) and write in its line/prices.
Self-contained; caches to the ROOT snapshot_cache/ (reuse + save, no recall).

    python fill_openings.py        # DRY: prints the exact call count, writes nothing
    python fill_openings.py run    # REAL: fetches only-uncached snapshots + updates CSV
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

HERE = Path(__file__).parent
KF = HERE / "Key Figures"
CACHE_DIR = HERE.parent / "snapshot_cache"
OUT = KF / "test_dataset_jan_mar.csv"
EVENTS = KF / "events_2023-2024_full_season.json"
MARKET, BOOK, REGIONS = "player_points", "fanduel", "us"


def _cache_path(event_id, date):
    tag = f"{date}_{MARKET}_{BOOK}_{REGIONS}".replace(":", "").replace("/", "")
    return CACHE_DIR / f"{event_id}_{tag}.json"


def get_event_odds(event_id, date):
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
                    out[o["name"].lower()] = o.get("price")
    return out


def event_lookup():
    events = json.loads(EVENTS.read_text())
    return {(f"{e['away_team']} @ {e['home_team']}", pd.to_datetime(e["commence_time"])): e["id"]
            for e in events}


def _offsets(player):
    """Hours-before-tip to probe, earliest first (take earliest with a line)."""
    if player == "Jontay Porter":
        return [0.167]                       # ~10 min; his lines open late
    return [3, 2, 1, 0.5, 0.2]               # escalate toward tip until the line exists


def run(dry=True):
    df = pd.read_csv(OUT)
    key2id = event_lookup()
    blanks = df[df["start_line"].isna()]
    print(f"{len(blanks)} blank openings to fill (escalating -3h -> -12m until a line appears)")
    if dry:
        print("DRY RUN: no API calls, nothing written. Run with 'run' to execute.")
        return

    new_calls, filled, still_blank = 0, 0, []
    for i, r in blanks.iterrows():
        eid = key2id.get((r["game"], pd.to_datetime(r["time"])))
        commence = pd.to_datetime(r["time"])
        for h in _offsets(r["player"]):
            date = (commence - timedelta(hours=h)).strftime(FMT)
            if not _cache_path(eid, date).exists():
                new_calls += 1
            resp = get_event_odds(eid, date)
            rec = _player_ou(resp, r["player"])
            if rec.get("point") is not None:
                df.at[i, "start_snapshot"] = resp.get("timestamp")
                df.at[i, "start_line"] = rec.get("point")
                df.at[i, "start_over"] = rec.get("over")
                df.at[i, "start_under"] = rec.get("under")
                filled += 1
                break
        else:
            still_blank.append(f"{r['player']} {str(r['time'])[:10]}")

    df.to_csv(OUT, index=False)
    print(f"filled {filled} of {len(blanks)} using {new_calls} new API calls -> {OUT.name}")
    if still_blank:
        print("still blank (no line even ~12m before tip):")
        for s in still_blank:
            print("  ", s)
    else:
        print("all openings now populated.")


if __name__ == "__main__":
    run(dry=("run" not in sys.argv))
