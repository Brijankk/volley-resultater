from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Season:
    id: str
    label: str
    value: str
    start_year: int | None
    is_current: bool


@dataclass(frozen=True)
class League:
    id: str
    season_id: str
    gender: str
    division: str
    name: str
    raekke_id: int


@dataclass(frozen=True)
class Pool:
    id: str
    league_id: str
    name: str
    pulje_id: int


@dataclass(frozen=True)
class StandingRow:
    pool_id: str
    rank: int
    team_name: str
    games_played: int
    games_won: int
    games_lost: int
    sets_won: int
    sets_lost: int
    balls_won: int
    balls_lost: int
    points: int


@dataclass(frozen=True)
class Match:
    pool_id: str
    kamp_id: int
    match_number: int | None
    starts_at: datetime | None
    home_team: str
    away_team: str
    venue: str
    court: str
    result_home_sets: int | None
    result_away_sets: int | None
    result_note: str = ""
    starts_at_time_known: bool = True


@dataclass(frozen=True)
class SetResult:
    kamp_id: int
    set_number: int
    home_points: int | None
    away_points: int | None
    home_set_won: int | None
    away_set_won: int | None


@dataclass(frozen=True)
class PoolData:
    pool: Pool
    standings: list[StandingRow]
    matches: list[Match]
    set_results: list[SetResult]
