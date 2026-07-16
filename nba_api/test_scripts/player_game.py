"""Get one player's box-score line from one specific NBA game.

Uses nba_api (https://github.com/swar/nba_api). You specify the player, the
season, and the game date; the script prints that game's full stat line.

    pip install nba_api
    python player_game.py

Change PLAYER_NAME / SEASON / GAME_DATE below to pick the player and game.

Note: stats.nba.com throttles/blocks datacenter IPs and can be slow, so the
call is retried a few times. Run it from a normal (residential) connection.
"""
from datetime import datetime

from nba_api.stats.static import players
from nba_api.stats.endpoints import playergamelog

# --- what to look up ---------------------------------------------------------
PLAYER_NAME = "LeBron James"
SEASON = "2023-24"        # season the game belongs to, e.g. "2024-25"
GAME_DATE = "2024-04-09"  # the game's date, YYYY-MM-DD
# -----------------------------------------------------------------------------

# The box-score fields worth printing, in a sensible order.
STAT_FIELDS = [
    "MATCHUP", "WL", "MIN", "PTS", "REB", "AST", "STL", "BLK", "TOV",
    "FGM", "FGA", "FG_PCT", "FG3M", "FG3A", "FG3_PCT", "FTM", "FTA", "FT_PCT",
    "PLUS_MINUS",
]


def find_player_id(name):
    """Return the nba.com player id for a full name, or exit if not found."""
    matches = players.find_players_by_full_name(name)
    if not matches:
        raise SystemExit(f"No player found matching {name!r}.")
    if len(matches) > 1:
        names = ", ".join(m["full_name"] for m in matches)
        print(f"Multiple matches for {name!r}, using the first: {names}")
    return matches[0]["id"], matches[0]["full_name"]


def get_season_log(player_id, season, retries=4):
    """Return the player's game-log DataFrame for a season (retries on timeout)."""
    last_err = None
    for _ in range(retries):
        try:
            endpoint = playergamelog.PlayerGameLog(
                player_id=player_id, season=season, timeout=60
            )
            return endpoint.get_data_frames()[0]
        except Exception as err:  # stats.nba.com timeouts are common
            last_err = err
    raise SystemExit(
        f"stats.nba.com did not respond after {retries} tries ({last_err}).\n"
        "It throttles non-residential IPs — try again on a normal connection."
    )


def main():
    player_id, full_name = find_player_id(PLAYER_NAME)
    target = datetime.strptime(GAME_DATE, "%Y-%m-%d").date()

    df = get_season_log(player_id, SEASON)
    # GAME_DATE comes back like "APR 09, 2024"; parse it to match on the date.
    df["_date"] = df["GAME_DATE"].apply(
        lambda s: datetime.strptime(s, "%b %d, %Y").date()
    )
    game = df[df["_date"] == target]

    if game.empty:
        raise SystemExit(
            f"{full_name} has no game on {GAME_DATE} in the {SEASON} season "
            "(check the date and that it's the right season)."
        )

    row = game.iloc[0]
    print(f"{full_name} — {GAME_DATE} ({SEASON})")
    for field in STAT_FIELDS:
        if field in row:
            print(f"  {field:<11} {row[field]}")


if __name__ == "__main__":
    main()
