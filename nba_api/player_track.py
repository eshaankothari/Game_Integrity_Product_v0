"""Player-tracking box score fetch (BoxScorePlayerTrackV3): speed, distance, touches.

Reusable helper: track_players(game_id) -> cached player_stats data frame
(nba_cache/track_<id>.csv), retried on nba.com stalls. Import track_players and
TRACK_COLS elsewhere; there is no __main__ pull here.
"""
import time
from pathlib import Path

import pandas as pd
import requests
from nba_api.stats.endpoints import boxscoreplayertrackv3

from box_scores import CACHE, TIMEOUT

TRACK_COLS = ["speed", "distance", "touches"]
RETRIES = 4


def track_players(game_id):
    """Cached BoxScorePlayerTrackV3 player_stats for a game (10-digit id, retried)."""
    cache = CACHE / f"track_{game_id}.csv"
    if cache.exists():
        return pd.read_csv(cache)
    last = None
    for attempt in range(1, RETRIES + 1):
        try:
            b = boxscoreplayertrackv3.BoxScorePlayerTrackV3(game_id=game_id, timeout=TIMEOUT)
            df = b.player_stats.get_data_frame()
            df.to_csv(cache, index=False)
            return df
        except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError) as e:
            last = e
            print(f"   track timeout on {game_id} (attempt {attempt}/{RETRIES}); waiting {5*attempt}s")
            time.sleep(5 * attempt)
    raise last
