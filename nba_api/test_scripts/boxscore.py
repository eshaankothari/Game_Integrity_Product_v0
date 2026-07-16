from nba_api.stats.endpoints import playergamelogs

# One player, one season — every game he played
playergamelogs.PlayerGameLogs(
    player_id_nullable=1627736, season_nullable="2024-25"
).get_data_frames()[0]

# One player, a date range — a slice of games
playergamelogs.PlayerGameLogs(
    player_id_nullable=pid, season_nullable="2024-25",
    date_from_nullable="01/01/2025", date_to_nullable="02/01/2025"
).get_data_frames()[0]

# EVERY player, one season — one row per player-game, league-wide
playergamelogs.PlayerGameLogs(season_nullable="2024-25").get_data_frames()[0]

