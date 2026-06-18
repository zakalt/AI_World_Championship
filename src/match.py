from __future__ import annotations
import random
from typing import Dict, Optional
from .team import Team
from .ai.policies import get_policy


class Match:
    """Minute-by-minute football match simulator.

    Each minute the engine:
      1. Decides who has possession (weighted by rating + tactic + home advantage).
      2. Simulates a pass chain; pass quality gates the shot probability.
      3. Rolls for shot → shot on target → goal using player stats.
      4. Applies stamina degradation after minute 70.
      5. Calls AI policies at key moments to trigger tactic/sub changes.
    """

    _SUB_BOOSTS: Dict[str, float] = {'attacker': 2.5, 'midfielder': 1.2, 'defender': 0.0}
    _MAX_SUBS = 3
    _HOME_ADV = 1.05          # home possession advantage multiplier

    # Passes attempted per possession minute per tactic
    _PASS_RANGE = {'defensive': (4, 6), 'balanced': (5, 7), 'attacking': (6, 9)}

    def __init__(self, home: Team, away: Team, minutes: int = 90,
                 seed: Optional[int] = None):
        self.home = home
        self.away = away
        self.minutes = minutes
        self.seed = seed
        self.rng = random.Random(seed)
        self.stats: Dict = {
            side: {
                'goals': 0, 'shots': 0, 'shots_on_target': 0,
                'possession': 0,
                'passes_attempted': 0, 'passes_completed': 0,
            }
            for side in ('home', 'away')
        }
        # Per-match rating boosts from substitutions — Team objects are never mutated
        self._boosts: Dict[str, float] = {'home': 0.0, 'away': 0.0}
        self._subs:   Dict[str, int]   = {'home': 0,   'away': 0}
        # Policies are stored once simulate() is called
        self._policies: Dict[str, object] = {}

    # ------------------------------------------------------------------
    # Player-stat helpers  (all return probabilities or factors)
    # ------------------------------------------------------------------

    def _stamina_factor(self, team: Team, minute: int) -> float:
        """Linear fatigue from minute 70. Higher stamina stat = smaller drop."""
        if minute <= 70:
            return 1.0
        fatigue = (minute - 70) / 90.0 * (1.0 - team.stamina / 100.0)
        return max(0.75, 1.0 - fatigue)

    def _pass_completion_rate(self, team: Team, minute: int) -> float:
        """Pass success probability.

        Influenced by:
        - passing stat      (range 50-90 → 77%-90% base)
        - tactic            (defensive = safer/shorter, attacking = riskier)
        - stamina           (degrades after minute 70)
        """
        tactic_mod = {'defensive': 1.04, 'balanced': 1.00, 'attacking': 0.94}.get(team.tactic, 1.0)
        base = 0.60 + (team.passing / 100.0) * 0.32    # 50→0.76, 65→0.808, 80→0.856
        return min(0.93, base * tactic_mod * self._stamina_factor(team, minute))

    def _shot_on_target_prob(self, team: Team, opponent: Team, minute: int) -> float:
        """Probability a shot is on target.

        Shooting stat pushes it up; opponent defending + tactic push it down.
        """
        base = 0.38
        shooting_bonus  = (team.shooting   - 65.0) * 0.003
        defending_pen   = (opponent.defending - 65.0) * 0.0025 * opponent.defense_modifier()
        return max(0.14, min(0.62, (base + shooting_bonus - defending_pen)
                             * self._stamina_factor(team, minute)))

    def _goal_prob(self, team: Team, opponent: Team, minute: int) -> float:
        """Probability a shot on target results in a goal."""
        base = 0.22
        shooting_bonus  = (team.shooting   - 65.0) * 0.0028
        defending_pen   = (opponent.defending - 65.0) * 0.0028 * opponent.defense_modifier()
        return max(0.06, min(0.40, (base + shooting_bonus - defending_pen)
                             * self._stamina_factor(team, minute)))

    def _attack_chance(self, attacking: Team, defending: Team,
                       atk_bonus: float, def_bonus: float,
                       minute: int) -> float:
        """Probability of a shot attempt during a possession minute.

        Calibrated so equal teams average ~11-13 shots per game each.
        """
        atk_str = attacking.rating + atk_bonus
        def_str = defending.rating + def_bonus
        # Rating ratio: dominant team creates more, underdog creates fewer
        ratio = atk_str / max(def_str, 1.0)
        rating_mod = max(0.70, min(1.40, ratio * 0.90 + 0.10))
        # Tactic: attacking gets more chances, defensive fewer
        tactic_mod = attacking.attack_modifier()
        # Pace: quick teams exploit transitions better
        pace_bonus = 1.0 + (attacking.pace - 65.0) * 0.0008
        return 0.20 * rating_mod * tactic_mod * pace_bonus * self._stamina_factor(attacking, minute)

    # ------------------------------------------------------------------
    # Substitution handler
    # ------------------------------------------------------------------

    def _apply_sub(self, side: str, action: Dict) -> None:
        if self._subs[side] >= self._MAX_SUBS:
            return
        sub_type = action.get('type', 'midfielder')
        self._boosts[side] += self._SUB_BOOSTS.get(sub_type, 0.0)
        self._subs[side] += 1

    # ------------------------------------------------------------------
    # AI decision tick
    # ------------------------------------------------------------------

    def _ai_tick(self, minute: int) -> None:
        for side, team, opp in (('home', self.home, self.away),
                                 ('away', self.away, self.home)):
            policy = self._policies.get(side)
            if policy is None:
                continue
            opp_side = 'away' if side == 'home' else 'home'
            poss_mins = self.stats[side]['possession']
            state = {
                'our_goals':           self.stats[side]['goals'],
                'opp_goals':           self.stats[opp_side]['goals'],
                'our_possession':      poss_mins / max(minute - 1, 1) * 100 if minute > 1 else 50.0,
                'our_shots_on_target': self.stats[side]['shots_on_target'],
                'our_shots':           self.stats[side]['shots'],
            }
            act = policy.decide_in_game(team, state, minute, self.rng)
            if 'change_tactic' in act:
                team.set_tactic(act['change_tactic'])
            if 'make_sub' in act:
                self._apply_sub(side, act['make_sub'])

    # ------------------------------------------------------------------
    # Main simulate method
    # ------------------------------------------------------------------

    def simulate(self) -> Dict:
        # Load policies and apply pre-match decisions
        for side, team, opp in (('home', self.home, self.away),
                                 ('away', self.away, self.home)):
            try:
                policy = get_policy(team.ai_policy)
            except Exception:
                policy = get_policy('baseline')
            self._policies[side] = policy
            pre = policy.decide_pre_match(team, opp, {}, self.rng)
            if 'set_tactic' in pre:
                team.set_tactic(pre['set_tactic'])

        for minute in range(1, self.minutes + 1):
            if minute % 5 == 0 or minute in (60, 75, 85):
                self._ai_tick(minute)

            # ---- Possession ----
            home_w = (self.home.rating + self._boosts['home']) * self.home.attack_modifier() * self._HOME_ADV
            away_w = (self.away.rating + self._boosts['away']) * self.away.attack_modifier()
            if self.rng.random() < home_w / (home_w + away_w):
                att, defn, att_s, def_s = self.home, self.away, 'home', 'away'
            else:
                att, defn, att_s, def_s = self.away, self.home, 'away', 'home'

            self.stats[att_s]['possession'] += 1

            # ---- Pass chain ----
            lo, hi = self._PASS_RANGE.get(att.tactic, (5, 7))
            attempts  = self.rng.randint(lo, hi)
            pcr       = self._pass_completion_rate(att, minute)
            completed = sum(1 for _ in range(attempts) if self.rng.random() < pcr)
            self.stats[att_s]['passes_attempted'] += attempts
            self.stats[att_s]['passes_completed'] += completed

            # ---- Shot opportunity ----
            # Pass chain quality (0-1) scales how dangerous the chance is
            chain_quality = completed / max(attempts, 1)
            shot_prob = self._attack_chance(att, defn, self._boosts[att_s],
                                            self._boosts[def_s], minute)
            # Fluent passing builds better chances; poor passing reduces threat
            shot_prob *= 0.55 + 0.90 * chain_quality

            if self.rng.random() < shot_prob:
                self.stats[att_s]['shots'] += 1
                if self.rng.random() < self._shot_on_target_prob(att, defn, minute):
                    self.stats[att_s]['shots_on_target'] += 1
                    if self.rng.random() < self._goal_prob(att, defn, minute):
                        self.stats[att_s]['goals'] += 1

        # ---- Finalise possession % ----
        total_mins = sum(self.stats[s]['possession'] for s in ('home', 'away'))
        raw_h = self.stats['home']['possession']
        self.stats['home']['possession'] = round(raw_h / max(total_mins, 1) * 100, 1)
        self.stats['away']['possession'] = round(100.0 - self.stats['home']['possession'], 1)

        # ---- Pass accuracy % ----
        for side in ('home', 'away'):
            att  = self.stats[side]['passes_attempted']
            comp = self.stats[side]['passes_completed']
            self.stats[side]['pass_accuracy'] = round(comp / att * 100, 1) if att else 0.0

        return {
            'home_team':  self.home.name,
            'away_team':  self.away.name,
            'home_goals': self.stats['home']['goals'],
            'away_goals': self.stats['away']['goals'],
            'stats':      self.stats,
        }
