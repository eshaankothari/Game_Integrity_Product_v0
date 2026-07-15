import os
import re
import json
import requests
from pathlib import Path
from datetime import datetime, timedelta

API_KEY = os.environ.get("ODDSAPI_KEY")
BASE = "https://api.the-odds-api.com/v4/historical/sports/basketball_nba/events"

YEAR_RANGE = "2023-2024"

def convert_year_range(year_range):
    """Rough ISO start/end of an NBA season from any year-range string."""
    match = re.search(r"\d{4}", year_range)
    if not match:
        raise ValueError(f"No 4-digit year found in {year_range!r}")
    start_year = int(match.group())
    return (
        f"{start_year}-09-09T00:00:00Z",
        f"{start_year + 1}-04-05T00:00:00Z",
    )

# 1 API call per snapshot
def get_all_events(year_range, snapshot="2023-10-10T12:15:00Z", save=True,
                   commence_from=None, commence_to=None):
    start, end = convert_year_range(year_range)
    params = {
        "apiKey": API_KEY,
        "dateFormat": "iso",
        "commenceTimeFrom": commence_from or start,
        "commenceTimeTo": commence_to or end,
        "date": snapshot,                  # required snapshot timestamp
        "includeRotationNumbers": "false",
    }
    response = requests.get(BASE, params=params)
    response.raise_for_status()
    data = response.json()

    # Save the snapshot to a JSON file next to this script (skipped during the
    # season sweep, which would otherwise write ~200 files).
    if save:
        out_file = Path(__file__).parent / f"events_{year_range}_{snapshot[:10]}.json"
        out_file.write_text(json.dumps(data, indent=2))
        print(f"Wrote {out_file.name}")

    return data


def default_snapshots(year_range):
    """A handful of noon-UTC snapshots spread across the season (1 call each).

    Placement note from measured data: an early-season snapshot returns a big
    batch reaching ~3 months ahead, while mid-season snapshots only reveal the
    next ~1-2 days of games. So these few calls capture the early batch plus a
    few day-windows -- roughly ~130 of the season's ~1,200 games, NOT all of
    them. Add more dates here to trade API calls for coverage.
    """
    y = int(re.search(r"\d{4}", year_range).group())
    return [
        f"{y}-10-24T12:00:00Z",      # opening night -> grabs the early batch
        f"{y}-12-20T12:00:00Z",
        f"{y + 1}-02-05T12:00:00Z",
        f"{y + 1}-03-20T12:00:00Z",
    ]


def get_season_event_ids(year_range, snapshots=None):
    """Fetch events across a few snapshots; save each, then a combined file.

    Each snapshot is one API call, saved as events_<season>_<date>.json. Their
    deduped union (one entry per game id) is written to
    events_<season>_season.json and returned.

    Coverage scales with the number of snapshots -- see default_snapshots. Pass
    your own `snapshots` list to control exactly how many calls are made.
    """
    snapshots = snapshots or default_snapshots(year_range)
    combined = {}  # id -> event, dedupes across snapshots
    for snapshot in snapshots:
        data = get_all_events(year_range, snapshot, save=True)  # saves per-snap JSON
        for event in data["data"]:
            combined[event["id"]] = event

    games = sorted(combined.values(), key=lambda e: e["commence_time"])
    out_file = Path(__file__).parent / f"events_{year_range}_season.json"
    out_file.write_text(json.dumps(games, indent=2))
    print(f"{len(games)} unique games from {len(snapshots)} snapshots -> {out_file.name}")
    return games


def season_window(year_range):
    """Tight commence window covering the full regular season.

    The rough convert_year_range window (Sep 9 -> Apr 5) both misses the last
    ~10 days of the regular season and wastes calls on the empty Sep/early-Oct
    preseason. This brackets the real slate: opening night -> end of April.
    """
    y = int(re.search(r"\d{4}", year_range).group())
    return (f"{y}-10-22T00:00:00Z", f"{y + 1}-04-16T00:00:00Z")


def daily_snapshots(start_iso, end_iso, step_days=1):
    """Noon-UTC snapshot timestamps every `step_days` across a window."""
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    cur = datetime.strptime(start_iso, fmt)
    end = datetime.strptime(end_iso, fmt)
    out = []
    while cur <= end:
        out.append(cur.strftime("%Y-%m-%dT12:00:00Z"))
        cur += timedelta(days=step_days)
    return out


def get_full_season_event_ids(year_range, step_days=2, save_snapshots=False):
    """Sweep snapshots across the season and write every game to one JSON.

    A snapshot only reveals the next ~1-2 days of games, so ~2 days is the
    LARGEST step that still catches ~every game -- this is the practical floor
    for full coverage. NUMBER OF API CALLS == number of snapshots: ~89 at
    step_days=2 (default), or ~178 at step_days=1 for a belt-and-suspenders
    daily sweep. Stepping wider than 2 starts dropping games. Writes the
    deduped union of all games to events_<season>_full_season.json.
    """
    c_from, c_to = season_window(year_range)
    snaps = daily_snapshots(c_from, c_to, step_days)
    print(f"This will make {len(snaps)} API calls (one per snapshot).")

    combined = {}  # id -> event, dedupes across snapshots
    for i, snapshot in enumerate(snaps, 1):
        try:
            data = get_all_events(year_range, snapshot, save=save_snapshots,
                                  commence_from=c_from, commence_to=c_to)
            for event in data["data"]:
                combined[event["id"]] = event
        except requests.HTTPError as err:
            # Snapshots on off-days (e.g. All-Star break) may 404; skip them.
            print(f"  skipped {snapshot}: {err}")
        if i % 25 == 0 or i == len(snaps):
            print(f"  {i}/{len(snaps)} calls, {len(combined)} unique games so far")

    games = sorted(combined.values(), key=lambda e: e["commence_time"])
    out_file = Path(__file__).parent / f"events_{year_range}_full_season.json"
    out_file.write_text(json.dumps(games, indent=2))
    print(f"{len(games)} unique games from {len(snaps)} API calls -> {out_file.name}")
    return games



# if __name__ == "__main__":
#     get_full_season_event_ids(YEAR_RANGE)


