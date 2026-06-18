from __future__ import annotations
import random
from typing import List, Optional
from .team import Team
from .match import Match


class KnockoutTournament:
    """Single-elimination knockout tournament.

    Teams are randomly drawn into a bracket. If the number of teams is not a
    power of two, the excess teams at the end of the draw receive a bye in the
    first round (they advance automatically).

    Draws in 90 minutes are resolved by a simulated penalty shootout (random
    coin-flip with equal probability).
    """

    def __init__(self, teams: List[Team], seed: Optional[int] = None):
        if len(teams) < 2:
            raise ValueError('A tournament requires at least 2 teams.')
        self.teams = list(teams)
        self.seed = seed
        self.rounds: List[List[dict]] = []
        self.champion: Optional[Team] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> Team:
        """Run all knockout rounds and return the champion."""
        rng = random.Random(self.seed)
        contenders = list(self.teams)
        rng.shuffle(contenders)

        round_num = 1
        while len(contenders) > 1:
            next_round: List[Team] = []
            round_results: List[dict] = []

            # Give a bye to the last team when there is an odd number
            if len(contenders) % 2 == 1:
                bye_team = contenders.pop()
                next_round.append(bye_team)
                round_results.append({
                    'round': round_num,
                    'home_team': bye_team.name,
                    'away_team': None,
                    'home_goals': None,
                    'away_goals': None,
                    'winner': bye_team.name,
                    'bye': True,
                })

            # Pair remaining teams
            for i in range(0, len(contenders), 2):
                home = contenders[i]
                away = contenders[i + 1]
                match_seed = rng.randint(0, 2 ** 31) if self.seed is not None else None
                res = Match(home, away, seed=match_seed).simulate()

                hg, ag = res['home_goals'], res['away_goals']
                if hg > ag:
                    winner = home
                elif ag > hg:
                    winner = away
                else:
                    # Penalty shootout — random 50/50
                    winner = rng.choice([home, away])
                    res['penalty_winner'] = winner.name

                res['round'] = round_num
                res['winner'] = winner.name
                round_results.append(res)
                next_round.append(winner)

            self.rounds.append(round_results)
            contenders = next_round
            round_num += 1

        self.champion = contenders[0]
        return self.champion

    def print_bracket(self) -> None:
        """Pretty-print the bracket results to stdout."""
        total = len(self.rounds)
        for i, rnd in enumerate(self.rounds, 1):
            print(f'\n--- {self._round_name(i, total)} ---')
            for r in rnd:
                if r.get('bye'):
                    print(f'  {r["home_team"]:12} — BYE')
                else:
                    score = f"{r['home_team']} {r['home_goals']} - {r['away_goals']} {r['away_team']}"
                    suffix = f" (pens: {r['penalty_winner']})" if 'penalty_winner' in r else ''
                    print(f'  {score}{suffix}  → {r["winner"]}')
        if self.champion:
            print(f'\nChampion: {self.champion.name}')

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _round_name(round_num: int, total_rounds: int) -> str:
        remaining = total_rounds - round_num
        if remaining == 0:
            return 'Final'
        if remaining == 1:
            return 'Semi-Finals'
        if remaining == 2:
            return 'Quarter-Finals'
        return f'Round {round_num}'
