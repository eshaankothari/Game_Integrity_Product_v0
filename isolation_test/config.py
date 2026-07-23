"""Shared config + paths for the 5-player isolation-forest test.

Separate folder, but it REUSES the repo's existing helpers (nba_api/, OddsAPI/)
and SHARES the existing caches so already-pulled games cost 0 to re-read.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent            # isolation_test/
ROOT = HERE.parent                                # repo root
# make the existing helper modules importable from this folder
for _d in (ROOT, ROOT / "nba_api", ROOT / "OddsAPI"):
    if str(_d) not in sys.path:
        sys.path.insert(0, str(_d))

# --- test universe ---
PLAYERS = ["Malik Beasley", "Gary Trent Jr.", "Grayson Allen",
           "Shai Gilgeous-Alexander"]           # Chris Duarte dropped (props in 11/59 games)
SEASON = "2023-24"
MARKETS = ["player_points"]        # points-only for the cheap validation pass (718 credits)
# MARKETS = ["player_points", "player_rebounds", "player_assists"]   # full: 2,154 credits
STAT_OF = {"player_points": "points", "player_rebounds": "reboundsTotal",
           "player_assists": "assists"}          # box-score column each market predicts
MARKET_SHORT = {"player_points": "pts", "player_rebounds": "reb",
                "player_assists": "ast"}          # column prefix per market
REGIONS = "us"
BOOK = "fanduel"
# closing ladder (minutes before tip): try tip first, then a fallback for lines pulled at tip
CLOSE_LADDER_MIN = [0, 20, 40]
# opening ladder (hours before tip): EARLIEST first so we capture the true opening.
# 12 is already cached from the first pass -> reused free; the rest only fire when 12h is empty.
OPEN_LADDER_HOURS = [12, 6, 4, 3, 2]

# --- shared caches (reuse repo's -> saves OddsAPI credits + nba throttling) ---
SNAPSHOT_CACHE = ROOT / "snapshot_cache"          # OddsAPI raw responses
NBA_CACHE = ROOT / "nba_cache"                    # box/adv/hustle/track caches

# --- this test's outputs ---
DATA = HERE / "data"
GAMES_CSV = DATA / "games.csv"                    # A
GAMES_EVENTS_CSV = DATA / "games_events.csv"      # B (games + event_id)
EVENTS_CACHE = DATA / "events_cache"              # B: per-date events-endpoint responses
PROPS_CSV = DATA / "props_raw.csv"                # C
BOX_CSV = DATA / "boxscores_raw.csv"             # E
FEATURES_CSV = DATA / "features.csv"             # D+F
ANOMALY_CSV = DATA / "anomaly_scores.csv"        # G

# --- isolation forest ---
CONTAMINATION = 0.05
RANDOM_STATE = 42

# effort metrics: (name, per48?) -- speed is a rate, the rest are cumulative
EFFORT = [("speed", False), ("distance", True), ("touches", True),
          ("contestedShots", True), ("deflections", True)]


def ensure_data_dir():
    DATA.mkdir(parents=True, exist_ok=True)
