"""Add specific named games for flagged players to test_dataset_jan_mar.csv.

Self-contained; caches to the ROOT snapshot_cache/ (reuse + save). For each game:
  1. resolve its event id (local events file first; else 1 events-endpoint call, cached)
  2. fetch opening + closing snapshots (opening = -10min for Porter's late lines,
     -12h otherwise), extract the player's line/over/under
  3. append a row (same columns). Re-running skips anything already present.

    python add_specific_games.py        # DRY: prints planned calls, writes nothing
    python add_specific_games.py run     # REAL
"""
import os
import sys
import json
import requests
from pathlib import Path
from datetime import timedelta

import pandas as pd

API_KEY = os.environ.get("ODDSAPI_KEY")
EVENTS_URL = "https://api.the-odds-api.com/v4/historical/sports/basketball_nba/events"
ODDS_URL = EVENTS_URL + "/{event_id}/odds"
FMT = "%Y-%m-%dT%H:%M:%SZ"

HERE = Path(__file__).parent
KF = HERE / "Key Figures"
CACHE_DIR = HERE.parent / "snapshot_cache"
OUT = KF / "test_dataset_jan_mar.csv"
EVENTS_FILE = KF / "events_2023-2024_full_season.json"
MARKET, BOOK, REGIONS = "player_points", "fanduel", "us"

# player, group, game day (YYYY-MM-DD, US date), opponent substring
GAMES = [
    ("Jontay Porter", "flagged", "2024-01-26", "Clippers"),
    ("Malik Beasley", "flagged", "2024-01-31", "Portland"),
    ("Malik Beasley", "flagged", "2024-03-10", "Charlotte"),
    ("Malik Beasley", "flagged", "2024-03-21", "Brooklyn"),
]


def _get(url, params, cache_name):
    """GET with disk cache (root snapshot_cache/), returns json or None on 404."""
    cache = CACHE_DIR / cache_name
    if cache.exists():
        return json.loads(cache.read_text())
    r = requests.get(url, params={**params, "apiKey": API_KEY})
    if r.status_code == 404:
        return None
    r.raise_for_status()
    payload = r.json()
    CACHE_DIR.mkdir(exist_ok=True)
    cache.write_text(json.dumps(payload))
    return payload


def resolve_event(day, opp):
    """Return (event_id, commence_time). Local events file first, else 1 API call."""
    d0 = pd.to_datetime(day)
    days = {d0.strftime("%Y-%m-%d"), (d0 + timedelta(days=1)).strftime("%Y-%m-%d")}
    for e in json.loads(EVENTS_FILE.read_text()):
        if e["commence_time"][:10] in days and opp.lower() in (e["away_team"] + e["home_team"]).lower():
            return e["id"], e["commence_time"], True   # from local file (no call)
    # events-endpoint lookup (1 call, cached)
    cfrom = d0.strftime("%Y-%m-%dT00:00:00Z")
    cto = (d0 + timedelta(days=2)).strftime("%Y-%m-%dT00:00:00Z")
    snap = d0.strftime("%Y-%m-%dT18:00:00Z")
    data = _get(EVENTS_URL, {"dateFormat": "iso", "commenceTimeFrom": cfrom,
                             "commenceTimeTo": cto, "date": snap,
                             "includeRotationNumbers": "false"},
                f"lookup_{day}_{opp}.json")
    for e in (data or {}).get("data", []):
        if opp.lower() in (e["away_team"] + e["home_team"]).lower():
            return e["id"], e["commence_time"], False
    return None, None, False


def _cache_path(event_id, date):
    tag = f"{date}_{MARKET}_{BOOK}_{REGIONS}".replace(":", "").replace("/", "")
    return CACHE_DIR / f"{event_id}_{tag}.json"


def get_odds(event_id, date):
    cache = _cache_path(event_id, date)
    if cache.exists():
        return json.loads(cache.read_text())
    r = requests.get(ODDS_URL.format(event_id=event_id), params={
        "apiKey": API_KEY, "regions": REGIONS, "markets": MARKET, "dateFormat": "iso",
        "oddsFormat": "decimal", "bookmakers": BOOK, "date": date,
        "includeRotationNumbers": "true", "includeMultipliers": "true"})
    if r.status_code == 404:
        return None
    r.raise_for_status()
    payload = r.json()
    CACHE_DIR.mkdir(exist_ok=True)
    cache.write_text(json.dumps(payload))
    return payload


def _player_ou(resp, player):
    out = {}
    for b in ((resp or {}).get("data") or {}).get("bookmakers", []):
        if b["key"] != BOOK:
            continue
        for m in b.get("markets", []):
            if m["key"] != MARKET:
                continue
            for o in m["outcomes"]:
                if o["description"] == player:
                    out["point"] = o.get("point")
                    out[o["name"].lower()] = o.get("price")
    return out


def _open_offset(player):
    return timedelta(minutes=10) if player == "Jontay Porter" else timedelta(hours=12)


def run(dry=True):
    have = set()
    if OUT.exists():
        old = pd.read_csv(OUT)
        have = {(p, pd.to_datetime(t).strftime("%Y-%m-%d"))
                for p, t in zip(old["player"], pd.to_datetime(old["time"], format="mixed"))}

    rows, planned_calls = [], 0
    for player, group, day, opp in GAMES:
        if (player, day) in have:
            print(f"skip {player} {day}: already in dataset")
            continue
        eid, ct, from_file = resolve_event(day, opp)
        if not eid:
            print(f"!! {player} {day} vs {opp}: event not found"); continue
        commence = pd.to_datetime(ct)
        open_date = (commence - _open_offset(player)).strftime(FMT)
        close_date = commence.strftime(FMT)
        planned_calls += (0 if from_file else 1)  # events lookup (0 if from file)
        planned_calls += sum(1 for d in (open_date, close_date) if not _cache_path(eid, d).exists())
        if dry:
            print(f"plan {player} {day} vs {opp}: event {eid[:8]} "
                  f"({'file' if from_file else 'API'}) {ct}")
            continue
        oresp, cresp = get_odds(eid, open_date), get_odds(eid, close_date)
        o, c = _player_ou(oresp, player), _player_ou(cresp, player)
        rows.append({
            "player": player, "group": group,
            "game": _matchup(oresp, cresp),
            "time": close_date,
            "start_snapshot": (oresp or {}).get("timestamp"),
            "start_line": o.get("point"), "start_over": o.get("over"), "start_under": o.get("under"),
            "close_snapshot": (cresp or {}).get("timestamp"),
            "close_line": c.get("point"), "close_over": c.get("over"), "close_under": c.get("under"),
        })
        print(f"added {player} {day}: start_line={o.get('point')} close_line={c.get('point')}")

    if dry:
        print(f"\nPLANNED API calls: {planned_calls}")
        print("DRY RUN: nothing written. Run with 'run' to execute.")
        return
    if rows:
        combined = pd.concat([pd.read_csv(OUT), pd.DataFrame(rows)], ignore_index=True)
        combined.to_csv(OUT, index=False)
        print(f"\nappended {len(rows)} rows -> {OUT.name} (now {len(combined)} total)")


def _matchup(oresp, cresp):
    d = ((cresp or oresp or {}).get("data")) or {}
    return f"{d.get('away_team','?')} @ {d.get('home_team','?')}"


if __name__ == "__main__":
    run(dry=("run" not in sys.argv))
