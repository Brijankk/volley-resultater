import pandera.pandas as pa
from pandera.typing import Series

class Leagues(pa.DataFrameModel):
    league_id: Series[int]
    league_name: Series[str]
    district: Series[str]
    gender: Series[str]
    age_group: Series[str]
    season: Series[int]

class Pools(pa.DataFrameModel):
    pool_id: Series[int]
    pool_name: Series[str]
    league_id: Series[int]

class Rankings(pa.DataFrameModel):
    pool_id: Series[int]
    rank: Series[int]
    team_name: Series[str]
    games_played: Series[int]
    games_won: Series[int]
    games_lost: Series[int]
    sets_won: Series[int]
    sets_lost: Series[int]
    balls_won: Series[int]
    balls_lost: Series[int]
    points: Series[int]

class Schedules(pa.DataFrameModel):
    pool_id: Series[int]
    match_id: Series[int]
    match_number: Series[int]
    match_time: Series[pa.DateTime] = pa.Field(nullable=True)
    home_team: Series[str]
    away_team: Series[str]
    venue: Series[str] = pa.Field(nullable=True)
    court: Series[str] = pa.Field(nullable=True)
    home_sets: Series[int] = pa.Field(nullable=True)
    away_sets: Series[int] = pa.Field(nullable=True)
    note: Series[str] = pa.Field(nullable=True)

class MatchDetails(pa.DataFrameModel):
    match_id: Series[int]
    address: Series[str] = pa.Field(nullable=True)
    referee1: Series[str] = pa.Field(nullable=True)
    referee2: Series[str] = pa.Field(nullable=True)
    home_points: Series[int] = pa.Field(nullable=True)
    away_points: Series[int] = pa.Field(nullable=True)
    home_balls1: Series[int] = pa.Field(nullable=True)
    away_balls1: Series[int] = pa.Field(nullable=True)
    home_balls2: Series[int] = pa.Field(nullable=True)
    away_balls2: Series[int] = pa.Field(nullable=True)
    home_balls3: Series[int] = pa.Field(nullable=True)
    away_balls3: Series[int] = pa.Field(nullable=True)
    home_balls4: Series[int] = pa.Field(nullable=True)
    away_balls4: Series[int] = pa.Field(nullable=True)
    home_balls5: Series[int] = pa.Field(nullable=True)
    away_balls5: Series[int] = pa.Field(nullable=True)

class Matches(Schedules, MatchDetails):
    pass