"""Build a Jan-Mar 2024 test dataset: opening vs closing prop lines/prices.

Six players -- three flagged (Porter, Beasley, Rozier) and three control stars
(Jokic, Giannis, Tatum) -- capped at CAP games each in the window. For every
player-game we take TWO snapshots from the Odds API:
  - opening: OPEN_OFFSET_HOURS before tip
  - closing: at tip-off (last snapshot before the game)
...and record the line + Over/Under price at each.

COST: 2 calls per unique game. Overlapping games (teammates) are fetched once
thanks to caching, so actual calls == 2 x unique games. Raw responses are
cached under snapshot_cache/ (shared with price_movement.py), so re-runs and
CSV reshapes cost ZERO new calls.

    python test_dataset.py        # DRY: prints the call count, makes no calls
    python test_dataset.py run    # REAL: fetches (only uncached snapshots) + writes CSV
"""
import sys
import json
from pathlib import Path
from datetime import timedelta

import pandas as pd

import price_movement as pm   # reuse its CACHED get_event_odds + snapshot parser

FLAGGED = ["Jontay Porter", "Malik Beasley", "Terry Rozier"]
CONTROL = ["Nikola Jokic", "Giannis Antetokounmpo", "Jayson Tatum"]
GROUPS = {**{p: "flagged" for p in FLAGGED}, **{p: "control" for p in CONTROL}}

CAP = 5                       # first N games per player in the window
START, END = "2024-01-01", "2024-04-01"
OPEN_OFFSET_HOURS = 12        # "opening" snapshot = this many hours before tip
MARKET, BOOK, REGIONS = "player_points", "fanduel", "us"

HERE = Path(__file__).parent
CSV_IN = HERE / "Key Figures" / "closing_under_prices.csv"
EVENTS = HERE / "Key Figures" / "events_2023-2024_full_season.json"
OUT = HERE / "Key Figures" / "test_dataset_jan_mar.csv"

COLUMNS = ["player", "group", "game", "time",
           "start_snapshot", "start_line", "start_over", "start_under",
           "close_snapshot", "close_line", "close_over", "close_under"]


def build_selection():
    """First CAP games per player in the window, from the local closing CSV."""
    df = pd.read_csv(CSV_IN)
    df["time"] = pd.to_datetime(df["time"])
    win = df[(df["time"] >= START) & (df["time"] < END)]
    sel = []
    for player, grp in GROUPS.items():
        games = win[win["player"] == player].sort_values("time").head(CAP)
        for _, r in games.iterrows():
            sel.append({"player": player, "group": grp, "game": r["game"], "time": r["time"]})
    return sel


def event_lookup():
    """(game_str, commence_time) -> event_id, from the events JSON."""
    events = json.loads(EVENTS.read_text())
    return {(f"{e['away_team']} @ {e['home_team']}", pd.to_datetime(e["commence_time"])): e["id"]
            for e in events}


def _player_at(resp, player):
    """That player's {point, over, under} at a snapshot, or {} if absent."""
    return pm._players_at_snapshot(resp, MARKET, BOOK).get(player, {})


def run(dry=True):
    sel = build_selection()
    key2id = event_lookup()
    unique_events = {key2id[(s["game"], s["time"])] for s in sel
                     if (s["game"], s["time"]) in key2id}
    print(f"{len(sel)} player-games, {len(unique_events)} unique games "
          f"-> {2 * len(unique_events)} API calls (before cache hits)")
    if dry:
        print("DRY RUN: no API calls, no file written. Run with 'run' to execute.")
        return

    rows = []
    for s in sel:
        eid = key2id.get((s["game"], s["time"]))
        commence = s["time"]
        open_dt = (commence - timedelta(hours=OPEN_OFFSET_HOURS)).strftime(pm.FMT)
        close_dt = commence.strftime(pm.FMT)

        oresp = pm.get_event_odds(eid, open_dt, MARKET, BOOK, REGIONS)   # cached
        cresp = pm.get_event_odds(eid, close_dt, MARKET, BOOK, REGIONS)  # cached
        o, c = _player_at(oresp, s["player"]), _player_at(cresp, s["player"])

        rows.append({
            "player": s["player"], "group": s["group"], "game": s["game"],
            "time": close_dt,
            "start_snapshot": oresp.get("timestamp"),
            "start_line": o.get("point"), "start_over": o.get("over"), "start_under": o.get("under"),
            "close_snapshot": cresp.get("timestamp"),
            "close_line": c.get("point"), "close_over": c.get("over"), "close_under": c.get("under"),
        })

    OUT.parent.mkdir(exist_ok=True)
    pd.DataFrame(rows, columns=COLUMNS).to_csv(OUT, index=False)
    print(f"wrote {len(rows)} rows -> {OUT}")
    blanks = sum(1 for r in rows if r["start_line"] is None)
    print(f"({blanks} player-games had no opening data at -{OPEN_OFFSET_HOURS}h "
          "— expected for late-opening lines like Porter's)")


if __name__ == "__main__":
    run(dry=("run" not in sys.argv))
