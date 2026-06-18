"""Pydantic schemas for request validation and response serialisation.

These are the data contracts between the Python simulation engine and
any frontend (React, Vue, plain JS, etc.).
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Shared enums / constants
# ---------------------------------------------------------------------------

VALID_TACTICS   = {'attacking', 'balanced', 'defensive'}
VALID_POLICIES  = {'baseline', 'reactive', 'strength_aware'}


# ---------------------------------------------------------------------------
# Team
# ---------------------------------------------------------------------------

class TeamIn(BaseModel):
    """Team definition sent by the frontend."""
    name:      str   = Field(..., min_length=1, max_length=40)
    rating:    float = Field(50.0, ge=1.0, le=99.0)
    tactic:    str   = Field('balanced')
    ai_policy: str   = Field('strength_aware')
    pace:      float = Field(65.0, ge=1.0, le=99.0)
    passing:   float = Field(65.0, ge=1.0, le=99.0)
    shooting:  float = Field(65.0, ge=1.0, le=99.0)
    defending: float = Field(65.0, ge=1.0, le=99.0)
    stamina:   float = Field(65.0, ge=1.0, le=99.0)

    @field_validator('tactic')
    @classmethod
    def tactic_valid(cls, v: str) -> str:
        if v not in VALID_TACTICS:
            raise ValueError(f'tactic must be one of {VALID_TACTICS}')
        return v

    @field_validator('ai_policy')
    @classmethod
    def policy_valid(cls, v: str) -> str:
        if v not in VALID_POLICIES:
            raise ValueError(f'ai_policy must be one of {VALID_POLICIES}')
        return v


class TeamOut(TeamIn):
    """Team state returned to the frontend (same fields, possibly updated by learning)."""
    pass


# ---------------------------------------------------------------------------
# Match
# ---------------------------------------------------------------------------

class MatchSideStats(BaseModel):
    goals:            int
    shots:            int
    shots_on_target:  int
    possession:       float
    passes_attempted: int
    passes_completed: int
    pass_accuracy:    float


class MatchResult(BaseModel):
    home_team:  str
    away_team:  str
    home_goals: int
    away_goals: int
    stats: Dict[str, MatchSideStats]


# ---------------------------------------------------------------------------
# Single-match endpoint
# ---------------------------------------------------------------------------

class SimulateMatchRequest(BaseModel):
    home: TeamIn
    away: TeamIn
    seed: Optional[int] = None


class SimulateMatchResponse(BaseModel):
    result: MatchResult
    home_after: TeamOut   # stats after learning (same as input if learning=False)
    away_after: TeamOut
    learning_applied: bool


# ---------------------------------------------------------------------------
# League
# ---------------------------------------------------------------------------

class RunLeagueRequest(BaseModel):
    teams:    List[TeamIn] = Field(..., min_length=2)
    seed:     Optional[int] = None
    learning: bool = True
    mode:     str  = Field('season', description="'season' (home+away) or 'round_robin'")

    @field_validator('mode')
    @classmethod
    def mode_valid(cls, v: str) -> str:
        if v not in ('season', 'round_robin'):
            raise ValueError("mode must be 'season' or 'round_robin'")
        return v


class StandingsRow(BaseModel):
    position: int
    team:     str
    P:  int
    W:  int
    D:  int
    L:  int
    GF: int
    GA: int
    GD: int
    Pts: int


class TeamGrowth(BaseModel):
    start: Dict[str, float]
    end:   Dict[str, float]


class RunLeagueResponse(BaseModel):
    standings:  List[StandingsRow]
    results:    List[MatchResult]
    growth:     Dict[str, TeamGrowth]   # keyed by team name; empty if learning=False
    champion:   str
    total_goals: int
    matches_played: int


# ---------------------------------------------------------------------------
# Tournament
# ---------------------------------------------------------------------------

class RunTournamentRequest(BaseModel):
    teams: List[TeamIn] = Field(..., min_length=2)
    seed:  Optional[int] = None


class TournamentFixture(BaseModel):
    round:      int
    round_name: str
    home_team:  str
    away_team:  Optional[str]   # None = bye
    home_goals: Optional[int]
    away_goals: Optional[int]
    winner:     str
    bye:        bool = False
    penalty_winner: Optional[str] = None


class RunTournamentResponse(BaseModel):
    bracket:  List[TournamentFixture]
    champion: str
