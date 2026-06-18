import unittest
from src.team import Team
from src.match import Match


class TestMatchDeterminism(unittest.TestCase):
    def test_same_seed_same_result(self):
        t1 = Team('A', 60, 'balanced', 'baseline')
        t2 = Team('B', 50, 'balanced', 'baseline')
        m1 = Match(t1, t2, seed=123)
        r1 = m1.simulate()

        t3 = Team('A', 60, 'balanced', 'baseline')
        t4 = Team('B', 50, 'balanced', 'baseline')
        m2 = Match(t3, t4, seed=123)
        r2 = m2.simulate()

        self.assertEqual(r1['home_goals'], r2['home_goals'])
        self.assertEqual(r1['away_goals'], r2['away_goals'])


if __name__ == '__main__':
    unittest.main()
