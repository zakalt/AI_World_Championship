"""Post-match learning engine.

After every match each team's attributes are nudged based on how they
actually performed.  Changes are small, bounded, and seeded so the
simulation stays reproducible.

Stat update rules
-----------------
passing   : own pass accuracy vs league-average baseline (78 %)
shooting  : goals-scored / shots ratio vs baseline conversion (10 %)
defending : goals-conceded / opponent-shots ratio vs baseline (10 %)
pace      : win → small boost; loss → tiny decay
stamina   : high possession late-game boosts stamina slightly
rating    : weighted average of all five stat changes (±2 max per match)

All stats are clamped to [30, 99].
Growth shrinks as stats approach the cap (diminishing returns).
"""
from __future__ import annotations
import random
from typing import Dict
from .team import Team

# Baselines derived from realistic match averages
_PASS_BASELINE    = 0.78   # target pass completion we compare against
_CONV_BASELINE    = 0.10   # goals / shots baseline
_CONCEDE_BASELINE = 0.10   # goals-allowed / opponent-shots baseline

# Per-match learning rates (max change per attribute per game)
_LR_PASSING  = 0.40
_LR_SHOOTING = 0.35
_LR_DEFEND   = 0.35
_LR_PACE     = 0.20
_LR_STAMINA  = 0.15
_LR_RATING   = 0.50

_STAT_MIN = 30.0
_STAT_MAX = 99.0

# Small noise range so identical matches produce slightly different growth
_NOISE = 0.05


def _clamp(value: float) -> float:
    return max(_STAT_MIN, min(_STAT_MAX, value))


def _diminishing(stat: float, delta: float) -> float:
    """Scale positive delta down as the stat approaches the cap."""
    if delta <= 0:
        return delta
    room = (_STAT_MAX - stat) / (_STAT_MAX - _STAT_MIN)  # 0..1
    return delta * max(0.1, room)


def update_team(team: Team, result: dict, side: str, rng: random.Random) -> Dict[str, float]:
    """Apply one round of learning to *team* from *result*.

    Parameters
    ----------
    team   : Team object to update in-place.
    result : dict returned by Match.simulate().
    side   : 'home' or 'away'.
    rng    : seeded RNG for reproducibility.

    Returns
    -------
    A dict of {stat: delta} showing how much each attribute changed.
    """
    opp_side = 'away' if side == 'home' else 'home'
    s  = result['stats'][side]
    os = result['stats'][opp_side]

    noise = lambda: rng.uniform(-_NOISE, _NOISE)

    # ---- passing ----
    match_accuracy = s['pass_accuracy'] / 100.0
    pass_delta = (match_accuracy - _PASS_BASELINE) * _LR_PASSING + noise()

    # ---- shooting ----
    shots = max(s['shots'], 1)
    conv  = s['goals'] / shots
    shoot_delta = (conv - _CONV_BASELINE) * _LR_SHOOTING * 5 + noise()

    # ---- defending ----
    opp_shots = max(os['shots'], 1)
    opp_conv  = os['goals'] / opp_shots
    # good defending = low opponent conversion → positive delta
    def_delta = (_CONCEDE_BASELINE - opp_conv) * _LR_DEFEND * 5 + noise()

    # ---- pace ----
    won  = result[f'{side}_goals'] > result[f'{opp_side}_goals']
    lost = result[f'{side}_goals'] < result[f'{opp_side}_goals']
    if won:
        pace_delta = _LR_PACE * 0.6 + noise()
    elif lost:
        pace_delta = -_LR_PACE * 0.3 + noise()
    else:
        pace_delta = noise()

    # ---- stamina ----
    # Teams with high possession (>52 %) late improve stamina slightly
    high_pos = s['possession'] > 52
    stamina_delta = (_LR_STAMINA * 0.5 if high_pos else 0.0) + noise()

    # ---- rating: weighted combination ----
    rating_delta = (
        pass_delta   * 0.25 +
        shoot_delta  * 0.30 +
        def_delta    * 0.25 +
        pace_delta   * 0.10 +
        stamina_delta * 0.10
    ) * (_LR_RATING / _LR_PASSING)   # rescale to rating units

    # Apply with diminishing returns on positive gains
    deltas = {
        'passing':  pass_delta,
        'shooting': shoot_delta,
        'defending': def_delta,
        'pace':     pace_delta,
        'stamina':  stamina_delta,
        'rating':   rating_delta,
    }

    team.passing   = _clamp(team.passing   + _diminishing(team.passing,   pass_delta))
    team.shooting  = _clamp(team.shooting  + _diminishing(team.shooting,  shoot_delta))
    team.defending = _clamp(team.defending + _diminishing(team.defending, def_delta))
    team.pace      = _clamp(team.pace      + _diminishing(team.pace,      pace_delta))
    team.stamina   = _clamp(team.stamina   + _diminishing(team.stamina,   stamina_delta))
    team.rating    = _clamp(team.rating    + _diminishing(team.rating,    rating_delta))

    return deltas


def update_both(home: Team, away: Team, result: dict, rng: random.Random) -> Dict[str, Dict[str, float]]:
    """Convenience wrapper — updates both teams and returns their deltas."""
    return {
        'home': update_team(home, result, 'home', rng),
        'away': update_team(away, result, 'away', rng),
    }
