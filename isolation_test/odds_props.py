"""Stage C: fetch opening + closing prop lines per game (points), scrupulous + cheap.

Levers:
  - CLOSING-FIRST: fetch the closing snapshot first; a game with no closing line has
    no prop -> we never pay for its opening. (Gates all opening spend.)
  - OPENING LADDER: to get an opening for every prop game, try earliest-first
    (OPEN_LADDER_HOURS = 12,6,4,3,2h before tip); stop at the first snapshot with a
    line = the true opening. 12h is already cached from the first pass -> reused free;
    later rungs fire only when 12h is empty.
  - CLOSING LADDER: try tip, then 20/40 min before, to catch a line pulled at tip.
  - Chris Duarte dropped in config (props in 11/59 games).

DRY reads the cache to report the EXACT additional-call bound before you spend.

    python odds_props.py            # DRY: report additional calls, write nothing
    python odds_props.py run        # REAL: fetch + write props_raw.csv
"""
import os
import sys
import json
from datetime import timedelta

import pandas as pd
import requests

import config
from box_scores import _ascii

API_KEY = os.environ.get("ODDSAPI_KEY")
ODDS_URL = ("https://api.the-odds-api.com/v4/historical/sports/basketball_nba/"
            "events/{event_id}/odds")
FMT = "%Y-%m-%dT%H:%M:%SZ"
MARKETS_PARAM = ",".join(config.MARKETS)
_MTAG = "-".join(config.MARKETS)                 # matches existing snapshot_cache key
_MKT = config.MARKETS[0]                          # single market (points) for now
_calls = 0


def _snap_path(event_id, snap):
    tag = f"{snap}_{_MTAG}_{config.BOOK}_{config.REGIONS}".replace(":", "").replace("/", "")
    return config.SNAPSHOT_CACHE / f"{event_id}_{tag}.json"


def _read_cache(event_id, snap):
    p = _snap_path(event_id, snap)
    return json.loads(p.read_text()) if p.exists() else None


def get_snapshot(event_id, snap):
    """Cached odds snapshot; fetches (and bills) only on a cache miss."""
    global _calls
    cached = _read_cache(event_id, snap)
    if cached is not None:
        return cached
    r = requests.get(ODDS_URL.format(event_id=event_id), params={
        "apiKey": API_KEY, "regions": config.REGIONS, "markets": MARKETS_PARAM,
        "oddsFormat": "decimal", "dateFormat": "iso", "bookmakers": config.BOOK,
        "date": snap})
    if r.status_code == 404:
        return None
    r.raise_for_status()
    _calls += len(config.MARKETS)
    payload = r.json()
    config.SNAPSHOT_CACHE.mkdir(exist_ok=True)
    _snap_path(event_id, snap).write_text(json.dumps(payload))
    return payload


def _line(resp, player):
    """The player's line dict {line, over, under} for the market, or {}."""
    for bk in ((resp or {}).get("data") or {}).get("bookmakers", []):
        if bk["key"] != config.BOOK:
            continue
        for mk in bk.get("markets", []):
            if mk["key"] != _MKT:
                continue
            for o in mk.get("outcomes", []):
                if _ascii(o.get("description", "")) == _ascii(player):
                    return {"line": o.get("point"), o["name"].lower(): o.get("price")}
    return {}


def _close_snaps(commence):
    return [(commence - timedelta(minutes=m)).strftime(FMT) for m in config.CLOSE_LADDER_MIN]


def _open_snaps(commence):
    return [(commence - timedelta(hours=h)).strftime(FMT) for h in config.OPEN_LADDER_HOURS]


def _resolve_run(event_id, snaps, player):
    """RUN: try snaps in order, fetch on miss, stop at first with a line -> (line, snap)."""
    for snap in snaps:
        resp = get_snapshot(event_id, snap)
        ln = _line(resp, player)
        if ln.get("line") is not None:
            return ln, snap
    return {}, None


def _classify_dry(event_id, snaps, player):
    """DRY (cache only): ('known',0) if a cached snap has a line;
    ('need', n_uncached) if new calls required; ('noprop',0) if all cached & lineless."""
    uncached = 0
    for snap in snaps:
        resp = _read_cache(event_id, snap)
        if resp is None:
            uncached += 1
        elif _line(resp, player).get("line") is not None:
            return "known", 0
    return ("need", uncached) if uncached else ("noprop", 0)


def fetch_props(dry=True):
    games = pd.read_csv(config.GAMES_EVENTS_CSV, dtype={"game_id": str})
    games = games[(games["event_id"].notna()) & (games["player"].isin(config.PLAYERS))].reset_index(drop=True)

    if dry:
        cl_known = cl_noprop = cl_need = 0
        op_best = op_worst = op_need_games = 0
        for _, g in games.iterrows():
            commence = pd.to_datetime(g["commence_time"])
            cs, cu = _classify_dry(g["event_id"], _close_snaps(commence), g["player"])
            if cs == "noprop":
                cl_noprop += 1; continue
            if cs == "need":
                cl_need += cu
            else:
                cl_known += 1
            os_, ou = _classify_dry(g["event_id"], _open_snaps(commence), g["player"])
            if os_ == "need":
                op_need_games += 1; op_best += 1; op_worst += ou
        print(f"players: {config.PLAYERS}")
        print(f"games (Duarte dropped): {len(games)}\n")
        print(f"closing lines already cached (free): {cl_known}")
        print(f"cached & lineless (no prop, skipped): {cl_noprop}")
        print(f"closing snapshots still to fetch    : {cl_need}")
        print(f"\ngames w/ closing line but opening missing: {op_need_games}")
        print(f"==> ADDITIONAL billed calls: between {cl_need + op_best} (best) "
              f"and {cl_need + op_worst} (worst)")
        print(f"    (opening ladder stops at first hit, so actual is near the low end)")
        print("\nDRY RUN: 0 calls made, nothing written. Re-run with 'run' to execute.")
        return

    rows = []
    for _, g in games.iterrows():
        commence = pd.to_datetime(g["commence_time"])
        c_line, c_snap = _resolve_run(g["event_id"], _close_snaps(commence), g["player"])
        if c_line.get("line") is None:
            o_line, o_snap = {}, None                     # no prop -> skip opening entirely
        else:
            o_line, o_snap = _resolve_run(g["event_id"], _open_snaps(commence), g["player"])
        s = config.MARKET_SHORT[_MKT]
        rows.append({
            "player": g["player"], "player_id": g["player_id"], "date": g["date"],
            "matchup": g["MATCHUP"], "game_id": str(g["game_id"]).zfill(10), "event_id": g["event_id"],
            "start_snapshot": o_snap, "close_snapshot": c_snap,
            f"{s}_start_line": o_line.get("line"), f"{s}_start_over": o_line.get("over"),
            f"{s}_start_under": o_line.get("under"),
            f"{s}_close_line": c_line.get("line"), f"{s}_close_over": c_line.get("over"),
            f"{s}_close_under": c_line.get("under")})

    out = pd.DataFrame(rows)
    config.ensure_data_dir()
    out.to_csv(config.PROPS_CSV, index=False)
    s = config.MARKET_SHORT[_MKT]
    print(f"\nACTUAL billed credits spent: {_calls}")
    print(f"wrote {config.PROPS_CSV.name} ({len(out)} games)")
    print(f"  closing line: {out[f'{s}_close_line'].notna().sum()}/{len(out)}")
    print(f"  opening line: {out[f'{s}_start_line'].notna().sum()}/{len(out)}")
    print(f"  both (line movement): {(out[f'{s}_close_line'].notna() & out[f'{s}_start_line'].notna()).sum()}")


if __name__ == "__main__":
    fetch_props(dry=("run" not in sys.argv))
