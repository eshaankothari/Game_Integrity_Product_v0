"""Stage A: resolve each player's 2023-24 regular-season games -> games.csv.

Free (nba_api LeagueGameFinder, 5 calls). Reuses fetch_player_all.all_games,
which already filters to regular season (game_id prefix 002).
"""
import pandas as pd
from nba_api.stats.static import players

import config
from fetch_player_all import all_games


def resolve_games():
    frames = []
    for name in config.PLAYERS:
        hit = players.find_players_by_full_name(name)
        if not hit:
            print(f"!! could not resolve player: {name}"); continue
        pid = hit[0]["id"]
        g = all_games(pid)                                  # game_id, date, MATCHUP, season
        g = g[g["season"] == config.SEASON].copy()
        g.insert(0, "player", name)
        g.insert(1, "player_id", pid)
        frames.append(g)
        print(f"{name:26s} {len(g)} games")
    df = pd.concat(frames, ignore_index=True)
    config.ensure_data_dir()
    df.to_csv(config.GAMES_CSV, index=False)
    print(f"\nwrote {config.GAMES_CSV.name} ({len(df)} player-games)")
    return df


if __name__ == "__main__":
    resolve_games()
