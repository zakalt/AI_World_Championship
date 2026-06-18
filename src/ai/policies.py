"""AI policies for the football simulator.

Provides pluggable policies that implement two methods:
- `decide_pre_match(team, opponent, context, rng)` -> dict of pre-match actions
- `decide_in_game(team, state, minute, rng)` -> dict of in-game actions

Actions are simple dictionaries, e.g. `{'change_tactic': 'attacking'}`.

Available policies
------------------
baseline        Simple rating-diff heuristic (original).
reactive        Possession + score aware (original).
strength_aware  Full strength-ratio strategy tree — recommended default.
"""
from __future__ import annotations
from typing import Any, Dict
import random


# ---------------------------------------------------------------------------
# Tactic helpers
# ---------------------------------------------------------------------------

def _strength_ratio(team: Any, opponent: Any) -> float:
    """Return team.rating / opponent.rating, clamped away from zero."""
    return team.rating / max(opponent.rating, 1.0)


def _tactic_from_ratio(ratio: float) -> str:
    """Pick a starting tactic purely from relative strength."""
    if ratio >= 1.20:
        return 'attacking'      # clearly dominant
    if ratio >= 1.08:
        return 'attacking'      # comfortably stronger
    if ratio >= 0.93:
        return 'balanced'       # evenly matched
    if ratio >= 0.80:
        return 'defensive'      # clear underdog — sit deep
    return 'defensive'          # heavy underdog — park the bus


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------

class BasePolicy:
    def decide_pre_match(self, team: Any, opponent: Any, context: Dict[str, Any], rng: random.Random) -> Dict[str, Any]:
        return {}

    def decide_in_game(self, team: Any, state: Dict[str, Any], minute: int, rng: random.Random) -> Dict[str, Any]:
        return {}


# ---------------------------------------------------------------------------
# Baseline policy (original, unchanged)
# ---------------------------------------------------------------------------

class BaselinePolicy(BasePolicy):
    """Simple heuristic policy.

    - Pre-match: choose tactic based on rating difference.
    - In-game: if losing late, switch to attacking; if leading, become defensive.
    """

    def decide_pre_match(self, team, opponent, context, rng: random.Random):
        diff = team.rating - opponent.rating
        if diff >= 8:
            tactic = 'attacking'
        elif diff <= -8:
            tactic = 'defensive'
        else:
            tactic = 'balanced'
        return {'set_tactic': tactic}

    def decide_in_game(self, team, state, minute, rng: random.Random):
        our_goals = state.get('our_goals', 0)
        opp_goals = state.get('opp_goals', 0)
        actions = {}
        if minute >= 75 and our_goals < opp_goals:
            actions['change_tactic'] = 'attacking'
        elif minute >= 80 and our_goals > opp_goals:
            actions['change_tactic'] = 'defensive'
        return actions


# ---------------------------------------------------------------------------
# Reactive policy (original, unchanged)
# ---------------------------------------------------------------------------

class ReactivePolicy(BasePolicy):
    """Reactive policy that uses match stats to decide.

    - Switch tactic based on possession and score.
    - Substitute if shots_on_target low late in game.
    """

    def decide_pre_match(self, team, opponent, context, rng: random.Random):
        return {'set_tactic': team.tactic}

    def decide_in_game(self, team, state, minute, rng: random.Random):
        our_goals = state.get('our_goals', 0)
        opp_goals = state.get('opp_goals', 0)
        our_pos = state.get('our_possession', 50)
        actions = {}
        if minute >= 70 and our_goals < opp_goals:
            if our_pos < 48:
                actions['change_tactic'] = 'attacking'
            else:
                actions['change_tactic'] = 'balanced'
        if minute >= 85 and state.get('our_shots_on_target', 0) < 2 and our_goals <= opp_goals:
            actions['make_sub'] = {'type': 'attacker'}
        return actions


# ---------------------------------------------------------------------------
# Strength-aware policy (new)
# ---------------------------------------------------------------------------

class StrengthAwarePolicy(BasePolicy):
    """Full strength-ratio strategy tree.

    Pre-match
    ---------
    Tactic is chosen from the team's strength ratio vs the opponent:
    - Dominant  (≥1.20x) → attacking
    - Favoured  (≥1.08x) → attacking
    - Even      (≥0.93x) → balanced
    - Underdog  (≥0.80x) → defensive
    - Heavy UDG (<0.80x) → defensive

    In-game — multi-phase logic
    ---------------------------
    Phase 1 (min 1–59):  only act if deficit is large (≥2 goals behind → attacking).
    Phase 2 (min 60–74): consolidate lead → defensive; chase goal → balanced/attacking.
    Phase 3 (min 75–84): winning by 1 → defensive; level or losing → attacking.
    Phase 4 (min 85–90): all-out attack if not winning; protect if leading by 2+.

    Substitutions
    -------------
    - Attacker sub triggered when chasing late and shots on target are low.
    - Defensive sub triggered when protecting a lead with <10 min left.
    """

    def decide_pre_match(self, team, opponent, context, rng: random.Random):
        ratio = _strength_ratio(team, opponent)
        tactic = _tactic_from_ratio(ratio)
        return {'set_tactic': tactic}

    def decide_in_game(self, team, state, minute, rng: random.Random):
        our_goals = state.get('our_goals', 0)
        opp_goals = state.get('opp_goals', 0)
        diff = our_goals - opp_goals          # positive = leading
        sot  = state.get('our_shots_on_target', 0)
        actions: Dict[str, Any] = {}

        # ---------- Phase 1: first hour ----------
        if minute < 60:
            if diff <= -2:
                actions['change_tactic'] = 'attacking'
            # otherwise hold starting tactic

        # ---------- Phase 2: 60-74 ----------
        elif minute < 75:
            if diff >= 2:
                actions['change_tactic'] = 'defensive'    # comfortable lead
            elif diff == 1:
                actions['change_tactic'] = 'balanced'     # protect without parking
            elif diff == 0:
                actions['change_tactic'] = 'balanced'     # push for winner
            else:
                actions['change_tactic'] = 'attacking'    # chasing

        # ---------- Phase 3: 75-84 ----------
        elif minute < 85:
            if diff >= 1:
                actions['change_tactic'] = 'defensive'
                if diff == 1 and minute >= 80:
                    actions['make_sub'] = {'type': 'defender'}
            elif diff == 0:
                actions['change_tactic'] = 'attacking'
            else:
                actions['change_tactic'] = 'attacking'
                if sot < 2:
                    actions['make_sub'] = {'type': 'attacker'}

        # ---------- Phase 4: 85-90 ----------
        else:
            if diff >= 2:
                actions['change_tactic'] = 'defensive'    # game safe
            elif diff >= 1:
                actions['change_tactic'] = 'defensive'
                actions['make_sub'] = {'type': 'defender'}
            elif diff == 0:
                actions['change_tactic'] = 'attacking'
                if sot < 3:
                    actions['make_sub'] = {'type': 'attacker'}
            else:
                actions['change_tactic'] = 'attacking'
                actions['make_sub'] = {'type': 'attacker'}

        return actions


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_POLICIES = {
    'baseline':       BaselinePolicy,
    'reactive':       ReactivePolicy,
    'strength_aware': StrengthAwarePolicy,
}


def get_policy(name: str | BasePolicy):
    """Return a policy instance by name or pass-through if already instance."""
    if isinstance(name, BasePolicy):
        return name
    if isinstance(name, str):
        cls = _POLICIES.get(name)
        if cls is None:
            raise KeyError(f'Unknown policy: {name!r}. Available: {list(_POLICIES)}')
        return cls()
    raise TypeError('policy must be a policy name (str) or BasePolicy instance')
