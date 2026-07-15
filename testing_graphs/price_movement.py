"""Track player-prop Over/Under price movement before tip-off, and plot it.

General flow for one game (event_id + commence_time):
  1. Sample the historical event-odds endpoint backward from tip-off.
  2. Write one CSV per player: timestamp, line, over price, under price.
  3. Plot each player's Over/Under price over time.

    export ODDSAPI_KEY=your_key
    python price_movement.py

API calls == lookback_hours*60/step_minutes (one per sampled snapshot), so a
~13h lookback at 20-min steps is ~40 calls for a single game.
"""
import os
import csv
import json
import requests
from pathlib import Path
from datetime import datetime, timedelta

import matplotlib
matplotlib.use("Agg")            # headless: write PNGs, no display needed
import matplotlib.pyplot as plt

API_KEY = os.environ.get("ODDSAPI_KEY")
ODDS_URL = ("https://api.the-odds-api.com/v4/historical/sports/"
            "basketball_nba/events/{event_id}/odds")
FMT = "%Y-%m-%dT%H:%M:%SZ"
CACHE_DIR = Path(__file__).parent / "snapshot_cache"   # raw responses, per query


def get_event_odds(event_id, date, market="player_points",
                   bookmaker="fanduel", regions="us"):
    """One snapshot of a game's prop odds at `date` (nearest snapshot <= date).

    Cached by query params under CACHE_DIR: repeating the same request reads the
    saved response and makes NO new API call. Past odds never change, so the
    cache never goes stale.
    """
    tag = f"{date}_{market}_{bookmaker}_{regions}".replace(":", "").replace("/", "")
    cache = CACHE_DIR / f"{event_id}_{tag}.json"
    if cache.exists():
        return json.loads(cache.read_text())

    resp = requests.get(
        ODDS_URL.format(event_id=event_id),
        params={
            "apiKey": API_KEY, "regions": regions, "markets": market,
            "dateFormat": "iso", "oddsFormat": "decimal", "bookmakers": bookmaker,
            "date": date, "includeRotationNumbers": "true",
            "includeMultipliers": "true",
        },
    )
    resp.raise_for_status()
    payload = resp.json()
    CACHE_DIR.mkdir(exist_ok=True)
    cache.write_text(json.dumps(payload))
    return payload


def _players_at_snapshot(resp, market, bookmaker):
    """Return {player: {"point":.., "over":.., "under":..}} from one response."""
    players = {}
    data = resp.get("data") or {}
    for book in data.get("bookmakers", []):
        if book["key"] != bookmaker:
            continue
        for mkt in book.get("markets", []):
            if mkt["key"] != market:
                continue
            for outcome in mkt["outcomes"]:
                rec = players.setdefault(outcome["description"], {})
                rec["point"] = outcome.get("point")
                rec[outcome["name"].lower()] = outcome.get("price")  # over / under
    return players


def _safe(name):
    """Filesystem-safe version of a player name."""
    return "".join(c if c.isalnum() else "_" for c in name)


def track_prop_movement(event_id, commence_time, lookback_hours=13,
                        step_minutes=20, market="player_points",
                        bookmaker="fanduel", regions="us", out_dir=None):
    """Sample odds backward from tip-off and write one CSV per player.

    Returns (series, out_dir) where series is
        {player: [ {timestamp, point, over, under}, ... ]}  # sorted by time
    """
    commence = datetime.strptime(commence_time, FMT)
    steps = int(lookback_hours * 60 / step_minutes)
    targets = [(commence - timedelta(minutes=step_minutes * i)).strftime(FMT)
               for i in range(steps + 1)]
    print(f"{len(targets)} API calls for {event_id[:8]}... ({bookmaker}/{market})")

    series = {}          # player -> {snapshot_ts: row}
    seen_ts = set()
    for date in targets:
        resp = get_event_odds(event_id, date, market, bookmaker, regions)
        ts = resp.get("timestamp")
        if not ts or ts in seen_ts:
            continue     # no snapshot, or a duplicate of one we already have
        seen_ts.add(ts)
        for player, rec in _players_at_snapshot(resp, market, bookmaker).items():
            series.setdefault(player, {})[ts] = {
                "timestamp": ts,
                "point": rec.get("point"),
                "over": rec.get("over"),
                "under": rec.get("under"),
            }

    out_dir = Path(out_dir or Path(__file__).parent / f"prop_movement_{event_id[:8]}")
    out_dir.mkdir(exist_ok=True)

    result = {}
    for player, rows_by_ts in series.items():
        rows = [rows_by_ts[t] for t in sorted(rows_by_ts)]
        result[player] = rows
        with open(out_dir / f"{_safe(player)}.csv", "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["timestamp", "point", "over", "under"])
            writer.writeheader()
            writer.writerows(rows)
    print(f"Wrote {len(result)} player CSVs -> {out_dir.name}/")
    return result, out_dir


def _load_existing(out_dir):
    """Load already-saved player CSVs back into {sanitized_name: {ts: row}}."""
    series = {}
    for path in Path(out_dir).glob("*.csv"):
        rows = {}
        with open(path) as f:
            for r in csv.DictReader(f):
                rows[r["timestamp"]] = {
                    "timestamp": r["timestamp"],
                    "point": float(r["point"]) if r["point"] else None,
                    "over": float(r["over"]) if r["over"] else None,
                    "under": float(r["under"]) if r["under"] else None,
                }
        series[path.stem] = rows
    return series


def add_fine_window(event_id, commence_time, out_dir, fine_minutes=90,
                    fine_step=5, market="player_points", bookmaker="fanduel",
                    regions="us"):
    """Sample the last `fine_minutes` at fine resolution and MERGE into the
    existing per-player CSVs. Catches late/short-lived lines (e.g. props posted
    minutes before tip) that a coarse sweep samples at most once. Only about
    fine_minutes/fine_step new API calls. Returns (series, out_dir) to plot.
    """
    out_dir = Path(out_dir)
    existing = _load_existing(out_dir)   # keyed by sanitized name
    display = {}                         # sanitized -> real name (for titles)

    commence = datetime.strptime(commence_time, FMT)
    steps = int(fine_minutes / fine_step)
    targets = [(commence - timedelta(minutes=fine_step * i)).strftime(FMT)
               for i in range(steps + 1)]
    print(f"{len(targets)} fine API calls (last {fine_minutes} min @ {fine_step}-min)")

    seen = set()
    for date in targets:
        resp = get_event_odds(event_id, date, market, bookmaker, regions)
        ts = resp.get("timestamp")
        if not ts or ts in seen:
            continue
        seen.add(ts)
        for player, rec in _players_at_snapshot(resp, market, bookmaker).items():
            key = _safe(player)
            display[key] = player
            existing.setdefault(key, {})[ts] = {
                "timestamp": ts, "point": rec.get("point"),
                "over": rec.get("over"), "under": rec.get("under"),
            }

    series = {}
    for key, rows_by_ts in existing.items():
        rows = [rows_by_ts[t] for t in sorted(rows_by_ts)]
        name = display.get(key, key.replace("_", " "))
        series[name] = rows
        with open(out_dir / f"{key}.csv", "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["timestamp", "point", "over", "under"])
            writer.writeheader()
            writer.writerows(rows)
    print(f"Merged; {len(series)} players now in {out_dir.name}/")
    return series, out_dir


def plot_players(series, out_dir, title_prefix=""):
    """One PNG per player: Over & Under price over time."""
    plotted = 0
    for player, rows in series.items():
        if len(rows) < 2:
            continue  # need at least two points to show movement
        times = [datetime.strptime(r["timestamp"], FMT) for r in rows]
        over = [r["over"] for r in rows]
        under = [r["under"] for r in rows]

        fig, ax = plt.subplots(figsize=(9, 4.5))
        ax.plot(times, over, marker=".", label="Over")
        ax.plot(times, under, marker=".", label="Under")
        line = rows[-1]["point"]
        ax.set_title(f"{title_prefix}{player} — points O/U (line {line})")
        ax.set_xlabel("snapshot (UTC)")
        ax.set_ylabel("decimal odds")
        ax.grid(True, alpha=0.3)
        ax.legend()
        fig.autofmt_xdate()
        fig.savefig(out_dir / f"{_safe(player)}.png", dpi=110, bbox_inches="tight")
        plt.close(fig)
        plotted += 1
    print(f"Wrote {plotted} plots -> {out_dir}/")


if __name__ == "__main__":
    EVENT = "54ea91772461bba4c4e2eee9ca0f5f0f"
    COMMENCE = "2024-03-20T23:40:00Z"        # Raptors vs Kings
    series, out_dir = track_prop_movement(EVENT, COMMENCE)
    plot_players(series, out_dir, title_prefix="TOR v SAC — ")
