"""FastAPI application — exposes the football simulation engine as a REST API.

Endpoints
---------
POST /match          Simulate a single match between two custom teams.
POST /league         Run a full league season (round-robin or home+away).
POST /tournament     Run a knockout cup bracket.
GET  /policies       List available AI policy names.
GET  /tactics        List available tactic names.
GET  /health         Health check.

CORS is enabled for all origins in development.  Restrict
``allow_origins`` to your frontend URL in production.
"""
from __future__ import annotations
import random
from typing import Dict

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .team import Team
from .match import Match
from .league import League
from .tournament import KnockoutTournament
from .learning import update_both
from .schemas import (
    SimulateMatchRequest, SimulateMatchResponse,
    RunLeagueRequest, RunLeagueResponse, StandingsRow, TeamGrowth,
    RunTournamentRequest, RunTournamentResponse, TournamentFixture,
    MatchResult, MatchSideStats, TeamOut,
)

app = FastAPI(
    title='Football Simulator API',
    description='AI-powered football match & league simulator.',
    version='1.0.0',
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],   # ← restrict to your frontend origin in production
    allow_methods=['*'],
    allow_headers=['*'],
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_team(t_in) -> Team:
    return Team(
        name=t_in.name,
        rating=t_in.rating,
        tactic=t_in.tactic,
        ai_policy=t_in.ai_policy,
        pace=t_in.pace,
        passing=t_in.passing,
        shooting=t_in.shooting,
        defending=t_in.defending,
        stamina=t_in.stamina,
    )


def _team_out(team: Team) -> TeamOut:
    return TeamOut(
        name=team.name,
        rating=round(team.rating, 2),
        tactic=team.tactic,
        ai_policy=str(team.ai_policy),
        pace=round(team.pace, 2),
        passing=round(team.passing, 2),
        shooting=round(team.shooting, 2),
        defending=round(team.defending, 2),
        stamina=round(team.stamina, 2),
    )


def _match_result(res: dict) -> MatchResult:
    sides = {}
    for side in ('home', 'away'):
        s = res['stats'][side]
        sides[side] = MatchSideStats(
            goals=s['goals'],
            shots=s['shots'],
            shots_on_target=s['shots_on_target'],
            possession=s['possession'],
            passes_attempted=s['passes_attempted'],
            passes_completed=s['passes_completed'],
            pass_accuracy=s.get('pass_accuracy', 0.0),
        )
    return MatchResult(
        home_team=res['home_team'],
        away_team=res['away_team'],
        home_goals=res['home_goals'],
        away_goals=res['away_goals'],
        stats=sides,
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get('/health')
def health():
    return {'status': 'ok'}


@app.get('/policies')
def list_policies():
    return {'policies': ['baseline', 'reactive', 'strength_aware']}


@app.get('/tactics')
def list_tactics():
    return {'tactics': ['attacking', 'balanced', 'defensive']}


@app.post('/match', response_model=SimulateMatchResponse)
def simulate_match(req: SimulateMatchRequest):
    """Simulate a single match.  Returns full stats + post-learning team states."""
    home = _build_team(req.home)
    away = _build_team(req.away)

    result = Match(home, away, seed=req.seed).simulate()

    rng = random.Random(req.seed)
    update_both(home, away, result, rng)

    return SimulateMatchResponse(
        result=_match_result(result),
        home_after=_team_out(home),
        away_after=_team_out(away),
        learning_applied=True,
    )


@app.post('/league', response_model=RunLeagueResponse)
def run_league(req: RunLeagueRequest):
    """Run a full league season and return standings + growth."""
    if len(req.teams) < 2:
        raise HTTPException(status_code=422, detail='Need at least 2 teams.')

    teams = [_build_team(t) for t in req.teams]
    league = League(teams)

    if req.mode == 'season':
        league.run_season(seed=req.seed, learning=req.learning)
    else:
        league.run_round_robin(seed=req.seed, learning=req.learning)

    table = league.get_table()
    standings = [
        StandingsRow(position=i + 1, team=r['team'],
                     P=r['P'], W=r['W'], D=r['D'], L=r['L'],
                     GF=r['GF'], GA=r['GA'], GD=r['GD'], Pts=r['Pts'])
        for i, r in enumerate(table)
    ]

    growth: Dict[str, TeamGrowth] = {}
    for name, g in league.growth.items():
        if g.get('end'):
            growth[name] = TeamGrowth(start=g['start'], end=g['end'])

    return RunLeagueResponse(
        standings=standings,
        results=[_match_result(r) for r in league.results],
        growth=growth,
        champion=table[0]['team'],
        total_goals=sum(r['home_goals'] + r['away_goals'] for r in league.results),
        matches_played=len(league.results),
    )


@app.post('/tournament', response_model=RunTournamentResponse)
def run_tournament(req: RunTournamentRequest):
    """Run a knockout cup bracket."""
    if len(req.teams) < 2:
        raise HTTPException(status_code=422, detail='Need at least 2 teams.')

    teams = [_build_team(t) for t in req.teams]
    cup = KnockoutTournament(teams, seed=req.seed)
    cup.run()

    total_rounds = len(cup.rounds)
    bracket = []
    for round_results in cup.rounds:
        for r in round_results:
            rn = cup._round_name(r['round'], total_rounds)
            bracket.append(TournamentFixture(
                round=r['round'],
                round_name=rn,
                home_team=r['home_team'],
                away_team=r.get('away_team'),
                home_goals=r.get('home_goals'),
                away_goals=r.get('away_goals'),
                winner=r['winner'],
                bye=r.get('bye', False),
                penalty_winner=r.get('penalty_winner'),
            ))

    return RunTournamentResponse(
        bracket=bracket,
        champion=cup.champion.name,
    )
