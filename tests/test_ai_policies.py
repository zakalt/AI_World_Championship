import unittest
from src.ai.policies import get_policy, BaselinePolicy, ReactivePolicy


class TestAIPolicies(unittest.TestCase):
    def test_get_policy_by_name(self):
        p = get_policy('baseline')
        self.assertIsInstance(p, BaselinePolicy)
        q = get_policy('reactive')
        self.assertIsInstance(q, ReactivePolicy)

    def test_unknown_policy(self):
        with self.assertRaises(KeyError):
            get_policy('no-such')


if __name__ == '__main__':
    unittest.main()
