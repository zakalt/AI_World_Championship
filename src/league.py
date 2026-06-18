from __future__ import annotations
import random
from .team import Team
from .match import Match
from .learning import update_both
from typing import List, Optional


class League:
    """League manager supporting single or home-and-away round-robin seasons.

    Points system: Win = 3, Draw = 1, Loss = 0.
    Tiebreakers:   Points → Goal Difference → Goals For → Name (alphabetical).

    Pass ``learning=True`` to any run method to enable the post-match
    learning engine: teams' stats evolve across the season based on results.
    """

    def __init__(self, teams: List[Team]):
        self.teams = teams
        self.standings = {
            t.name: {'P': 0, 'W': 0, 'D': 0, 'L': 0, 'GF': 0, 'GA': 0, 'GD': 0, 'Pts': 0}
            for t in teams
        }
        self.results: List[dict] = []
        self.matchdays: List[List[dict]] = []   # grouped by matchday
        # Records starting and final stats for each team when learning is on
        self.growth: dict = {}

    # ------------------------------------------------------------------
    # Season runners
    # ------------------------------------------------------------------

    def run_round_robin(self, seed: Optional[int] = None, learning: bool = False):
        """Single round-robin: every pair plays once."""
        rng = random.Random(seed)
        self._snapshot_start()
        n = len(self.teams)
        matchday: List[dict] = []
        for i in range(n):
            for j in range(i + 1, n):
                res = self._play(self.teams[i], self.teams[j], rng, learning)
                matchday.append(res)
        if matchday:
            self.matchdays.append(matchday)
        self._snapshot_end()

    def run_season(self, seed: Optional[int] = None, learning: bool = False):
        """Home-and-away double round-robin: every pair plays twice."""
        rng = random.Random(seed)
        self._snapshot_start()
        n = len(self.teams)
        fixtures: List[tuple] = []
        for i in range(n):
            for j in range(n):
                if i != j:
                    fixtures.append((self.teams[i], self.teams[j]))
        rng.shuffle(fixtures)
        md_size = n - 1
        for start in range(0, len(fixtures), md_size):
            matchday = []
            for home, away in fixtures[start:start + md_size]:
                matchday.append(self._play(home, away, rng, learning))
            if matchday:
                self.matchdays.append(matchday)
        self._snapshot_end()

    # ------------------------------------------------------------------
    # Results & table
    # ------------------------------------------------------------------

    def get_table(self) -> List[dict]:
        table = [{'team': name, **s} for name, s in self.standings.items()]
        table.sort(key=lambda x: (-x['Pts'], -x['GD'], -x['GF'], x['team']))
        return table

    def print_table(self) -> None:
        """Print a formatted standings table to stdout."""
        table = self.get_table()
        header = f"{'#':>2}  {'Team':<12} {'P':>3} {'W':>3} {'D':>3} {'L':>3} {'GF':>4} {'GA':>4} {'GD':>4} {'Pts':>4}"
        divider = '-' * len(header)
        print(divider)
        print(header)
        print(divider)
        for i, row in enumerate(table, 1):
            gd = f"{row['GD']:+d}"
            print(
                f"{i:>2}. {row['team']:<12} {row['P']:>3} {row['W']:>3}"
                f" {row['D']:>3} {row['L']:>3} {row['GF']:>4} {row['GA']:>4}"
                f" {gd:>4} {row['Pts']:>4}"
            )
        print(divider)

    def print_matchday(self, matchday_index: int) -> None:
        """Print all results from a specific matchday (0-indexed)."""
        if matchday_index >= len(self.matchdays):
            print(f'Matchday {matchday_index + 1} not found.')
            return
        print(f'\n  Matchday {matchday_index + 1}')
        for r in self.matchdays[matchday_index]:
            print(
                f"  {r['home_team']:>12} {r['home_goals']} - {r['away_goals']} {r['away_team']:<12}"
                f"  poss {r['stats']['home']['possession']}% / {r['stats']['away']['possession']}%"
                f"  shots {r['stats']['home']['shots']}-{r['stats']['away']['shots']}"
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _play(self, home: Team, away: Team, rng: random.Random,
              learning: bool = False) -> dict:
        match_seed = rng.randint(0, 2 ** 31)
        res = Match(home, away, seed=match_seed).simulate()
        self._apply_result(res)
        self.results.append(res)
        if learning:
            update_both(home, away, res, rng)
        return res

    # ------------------------------------------------------------------
    # Growth snapshots (populated when learning=True)
    # ------------------------------------------------------------------

    _TRACKED = ('rating', 'pace', 'passing', 'shooting', 'defending', 'stamina')

    def _snapshot_start(self) -> None:
        self.growth = {
            t.name: {
                'start': {s: round(getattr(t, s), 2) for s in self._TRACKED},
                'end':   {},
            }
            for t in self.teams
        }

    def _snapshot_end(self) -> None:
        for t in self.teams:
            if t.name in self.growth:
                self.growth[t.name]['end'] = {
                    s: round(getattr(t, s), 2) for s in self._TRACKED
                }

    def print_growth(self) -> None:
        """Print a per-team attribute growth table after a learning season."""
        if not self.growth or not any(g['end'] for g in self.growth.values()):
            print('No growth data — run with learning=True first.')
            return
        cols = self._TRACKED
        header = f"  {'Team':<12}" + ''.join(f"  {c.capitalize()[:6]:>8}" for c in cols)
        print(header)
        print('  ' + '-' * (len(header) - 2))
        for name, g in self.growth.items():
            row = f"  {name:<12}"
            for c in cols:
                start = g['start'].get(c, 0)
                end   = g['end'].get(c, start)
                diff  = end - start
                sign  = '+' if diff >= 0 else ''
                row  += f"  {end:>5.1f}({sign}{diff:+.1f})"
            print(row)

    def _apply_result(self, r: dict) -> None:
        h, a = r['home_team'], r['away_team']
        hg, ag = r['home_goals'], r['away_goals']
        for name, gf, ga in ((h, hg, ag), (a, ag, hg)):
            self.standings[name]['P']  += 1
            self.standings[name]['GF'] += gf
            self.standings[name]['GA'] += ga
        if hg > ag:
            self.standings[h]['W']   += 1
            self.standings[a]['L']   += 1
            self.standings[h]['Pts'] += 3
        elif hg < ag:
            self.standings[a]['W']   += 1
            self.standings[h]['L']   += 1
            self.standings[a]['Pts'] += 3
        else:
            self.standings[h]['D']   += 1
            self.standings[a]['D']   += 1
            self.standings[h]['Pts'] += 1
            self.standings[a]['Pts'] += 1
        for name in (h, a):
            self.standings[name]['GD'] = (
                self.standings[name]['GF'] - self.standings[name]['GA']
            )
