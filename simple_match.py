from src.team import Team
from src.match import Match

# Create 2 AI teams with distinct player stats
home = Team(
    name='Lions', rating=70, tactic='attacking', ai_policy='strength_aware',
    pace=78, passing=72, shooting=80, defending=60, stamina=70,
)
away = Team(
    name='Tigers', rating=65, tactic='balanced', ai_policy='strength_aware',
    pace=68, passing=82, shooting=68, defending=68, stamina=74,
)

# Simulate the match
result = Match(home, away, seed=1).simulate()
h = result['stats']['home']
a = result['stats']['away']

# Output score + stats
print(f"Result       : {result['home_team']} {result['home_goals']} - {result['away_goals']} {result['away_team']}")
print(f"Possession   : {h['possession']}%  /  {a['possession']}%")
print(f"Shots        : {h['shots']}  /  {a['shots']}")
print(f"Shots on tgt : {h['shots_on_target']}  /  {a['shots_on_target']}")
print(f"Passes       : {h['passes_completed']}/{h['passes_attempted']} ({h['pass_accuracy']}%)"
      f"  /  {a['passes_completed']}/{a['passes_attempted']} ({a['pass_accuracy']}%)")
