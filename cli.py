from src.team import Team
from src.league import League
from src.tournament import KnockoutTournament


# ---------------------------------------------------------------------------
# Team roster
# Each team has distinct player stats that reflect a playing identity:
#   pace | passing | shooting | defending | stamina
# ---------------------------------------------------------------------------
TEAMS = [
    #                  name      rat  tactic       policy           pac  pas  sho  def  sta
    Team('Lions',       70, 'attacking',  'strength_aware', pace=78, passing=72, shooting=80, defending=60, stamina=70),
    Team('Tigers',      65, 'balanced',   'strength_aware', pace=68, passing=82, shooting=68, defending=68, stamina=74),
    Team('Bears',       60, 'defensive',  'strength_aware', pace=55, passing=65, shooting=58, defending=85, stamina=80),
    Team('Wolves',      68, 'balanced',   'strength_aware', pace=72, passing=75, shooting=72, defending=72, stamina=68),
    Team('Eagles',      55, 'attacking',  'strength_aware', pace=85, passing=60, shooting=65, defending=50, stamina=62),
    Team('Sharks',      50, 'balanced',   'strength_aware', pace=58, passing=58, shooting=55, defending=58, stamina=60),
]


def _sep(char: str = '=', width: int = 60) -> None:
    print(char * width)


def _print_match(r: dict) -> None:
    h, a = r['stats']['home'], r['stats']['away']
    print(
        f"  {r['home_team']:>12} {r['home_goals']} - {r['away_goals']} {r['away_team']:<12}"
        f"  poss {h['possession']}%/{a['possession']}%"
        f"  shots {h['shots']}/{a['shots']}"
        f"  SoT {h['shots_on_target']}/{a['shots_on_target']}"
        f"  pass% {h['pass_accuracy']}/{a['pass_accuracy']}"
    )


def run_league() -> None:
    teams = [Team(t.name, t.rating, t.tactic, t.ai_policy,
                  pace=t.pace, passing=t.passing, shooting=t.shooting,
                  defending=t.defending, stamina=t.stamina)
             for t in TEAMS]

    _sep()
    print('  PREMIER LEAGUE SEASON  (home & away)')
    _sep()

    league = League(teams)
    league.run_season(seed=42, learning=True)

    # Show first 3 matchdays as a sample
    print('\n[Sample matchdays]')
    for md_idx in range(min(3, len(league.matchdays))):
        print(f'\n  -- Matchday {md_idx + 1} --')
        for r in league.matchdays[md_idx]:
            _print_match(r)

    # Full standings table
    print('\n[Final Standings]')
    league.print_table()

    table = league.get_table()
    total_goals   = sum(r['home_goals'] + r['away_goals'] for r in league.results)
    total_matches = len(league.results)
    avg_goals     = total_goals / total_matches if total_matches else 0
    total_passes  = sum(r['stats']['home']['passes_attempted'] + r['stats']['away']['passes_attempted']
                        for r in league.results)

    print(f"\n  Champion  : {table[0]['team']}  ({table[0]['Pts']} pts)")
    print(f"  Relegated : {table[-1]['team']}  ({table[-1]['Pts']} pts)")
    print(f"  Goals     : {total_goals} in {total_matches} matches  (avg {avg_goals:.2f}/game)")
    print(f"  Passes    : {total_passes} total across the season")

    print('\n[Team Growth after learning season]')
    league.print_growth()


def run_cup() -> None:
    teams = [Team(t.name, t.rating, t.tactic, t.ai_policy,
                  pace=t.pace, passing=t.passing, shooting=t.shooting,
                  defending=t.defending, stamina=t.stamina)
             for t in TEAMS]

    _sep()
    print('  KNOCKOUT CUP')
    _sep()

    cup = KnockoutTournament(teams, seed=7)
    cup.run()
    cup.print_bracket()


def main() -> None:
    run_league()
    print()
    run_cup()


if __name__ == '__main__':
    main()
