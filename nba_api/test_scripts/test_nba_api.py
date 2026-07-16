from nba_api.stats.static import teams as static_teams
from nba_api.stats.endpoints import scoreboardv2, boxscoretraditionalv3, boxscoreadvancedv3 

# teams = static_teams.get_teams()

# print([team['id'] for team in teams])

# game_id = "0022300446"

b = boxscoreadvancedv3.BoxScoreAdvancedV3(game_id='0022300446')
df = b.get_data_frames()
df = b.player_stats.get_data_frame()
print(df[['firstName','familyName','netRating','usagePercentage','PIE', 'turnoverRatio', 'trueShootingPercentage', 'usagePercentage', 'pace']])

