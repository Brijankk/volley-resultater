from __future__ import annotations

from pathlib import Path
import sqlite3

import pandas as pd
import pandera.pandas as pa
from pandera.typing import DataFrame

from .paths import SCHEMA_PATH
from .models import Leagues, Pools, Rankings, Matches

with open(SCHEMA_PATH, "r", encoding="utf-8") as file:
    SCHEMA = file.read()

class Repository:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(SCHEMA)
    
    @classmethod
    def open_readonly(cls, path: Path) -> "Repository":
        repo = cls.__new__(cls)
        repo.path = path
        uri = path.resolve().as_uri() + "?mode=ro"
        repo.connection = sqlite3.connect(uri, uri=True)
        repo.connection.row_factory = sqlite3.Row
        repo.connection.execute("BEGIN")

        return repo

    def __enter__(self) -> "Repository":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

    def commit(self) -> None:
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    @pa.check_types
    def upsert_leagues(self, leagues: DataFrame[Leagues]) -> None:
        column_order = list(Leagues.to_schema().columns)

        self.connection.executemany(
            """
            INSERT INTO leagues (league_id, league_name, district, gender, age_group, season)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(league_id) DO UPDATE SET
                league_name=excluded.league_name,
                district=excluded.district,
                gender=excluded.gender,
                age_group=excluded.age_group,
                season=excluded.season
            """,
            [row for row in leagues[column_order].itertuples(index=False, name=None)],
        )

    @pa.check_types
    def upsert_pools(self, pools: DataFrame[Pools]) -> None:
        column_order = list(Pools.to_schema().columns)

        self.connection.executemany(
            """
            INSERT INTO pools (pool_id, pool_name, league_id)
            VALUES (?, ?, ?)
            ON CONFLICT(pool_id) DO UPDATE SET
                pool_name=excluded.pool_name,
                league_id=excluded.league_id                
            """,
            [row for row in pools[column_order].itertuples(index=False, name=None)],
        )

    @pa.check_types
    def upsert_rankings(self, ranking: DataFrame[Rankings]) -> None:
        column_order = list(Rankings.to_schema().columns)

        self.connection.executemany(
            """
            INSERT INTO rankings (
                pool_id,
                rank,
                team_name,
                games_played,
                games_won,
                games_lost,
                sets_won,
                sets_lost,
                balls_won,
                balls_lost,
                points
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(pool_id, team_name) DO UPDATE SET
                rank=excluded.rank,
                games_played=excluded.games_played,
                games_won=excluded.games_won,
                games_lost=excluded.games_lost,
                sets_won=excluded.sets_won,
                sets_lost=excluded.sets_lost,
                balls_won=excluded.balls_won,
                balls_lost=excluded.balls_lost,
                points=excluded.points
            """,
            [row for row in ranking[column_order].itertuples(index=False, name=None)],
        )

    @pa.check_types
    def upsert_matches(self, matches: DataFrame[Matches]) -> None:
        column_order = [
            'pool_id',
            'match_id',
            'match_number',
            'match_time',
            'home_team',
            'away_team',
            'venue',
            'court',
            'address',
            'referee1',
            'referee2',
            'home_sets',
            'away_sets',
            'home_points',
            'away_points',
            'home_balls1',
            'away_balls1',
            'home_balls2',
            'away_balls2',
            'home_balls3',
            'away_balls3',
            'home_balls4',
            'away_balls4',
            'home_balls5',
            'away_balls5',
            'note',
        ]

        df = matches.copy()
        int64_cols = df.loc[:, df.dtypes.eq('Int64')].columns
        df[int64_cols] = df[int64_cols].astype(object).fillna(None)
        df['match_time'] = df['match_time'].dt.strftime(date_format='%Y-%m-%dT%H:%M:%S')

        self.connection.executemany(
            """
            INSERT INTO matches (
                pool_id,
                match_id,
                match_number,
                match_time,
                home_team,
                away_team,
                venue,
                court,
                address,
                referee1,
                referee2,
                home_sets,
                away_sets,
                home_points,
                away_points,
                home_balls1,
                away_balls1,
                home_balls2,
                away_balls2,
                home_balls3,
                away_balls3,
                home_balls4,
                away_balls4,
                home_balls5,
                away_balls5,
                note
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(match_id) DO UPDATE SET
                pool_id=excluded.pool_id,
                match_number=excluded.match_number,
                match_time=excluded.match_time,
                home_team=excluded.home_team,
                away_team=excluded.away_team,
                venue=excluded.venue,
                court=excluded.court,
                address=excluded.address,
                referee1=excluded.referee1,
                referee2=excluded.referee2,
                home_sets=excluded.home_sets,
                away_sets=excluded.away_sets,
                home_points=excluded.home_points,
                away_points=excluded.away_points,
                home_balls1=excluded.home_balls1,
                away_balls1=excluded.away_balls1,
                home_balls2=excluded.home_balls2,
                away_balls2=excluded.away_balls2,
                home_balls3=excluded.home_balls3,
                away_balls3=excluded.away_balls3,
                home_balls4=excluded.home_balls4,
                away_balls4=excluded.away_balls4,
                home_balls5=excluded.home_balls5,
                away_balls5=excluded.away_balls5,
                note=excluded.note
            """,
            [row for row in df[column_order].itertuples(index=False, name=None)],
        )

    def get_leagues(self) -> pd.DataFrame:
        query = """
            SELECT *
            FROM leagues
        """

        df = pd.read_sql(
            sql=query,
            con=self.connection
        )

        return df

    def get_pools_with_leagues(self) -> pd.DataFrame:
        query = """
            SELECT 
                x.*,
                y.league_name,
                y.district,
                y.gender,
                y.season,
                y.age_group
            FROM pools x 
            JOIN leagues y
            ON x.league_id=y.league_id
        """
        df = pd.read_sql(
            sql=query,
            con=self.connection,
            dtype_backend="numpy_nullable"
        )
        df.sort_values(
            by=["league_id", "pool_name", "pool_id"],
            ignore_index=True,
            inplace=True
        )

        return df

    def get_rankings(self) -> pd.DataFrame:
        query = "SELECT * FROM rankings ORDER BY pool_id, rank, team_name"

        df = pd.read_sql(
            sql=query,
            con=self.connection,
            dtype_backend="numpy_nullable"
        )
        df.sort_values(
            by=["pool_id", "rank", "team_name"],
            ignore_index=True,
            inplace=True
        )

        return df

    def get_matches(self) -> pd.DataFrame:
        query = "SELECT * FROM matches ORDER BY pool_id, match_time IS NULL, match_time, match_number, match_id"
        df = pd.read_sql(
            sql=query,
            con=self.connection,
            dtype_backend="numpy_nullable",
        )
        # SQL cannot infer numeric dtypes from a column containing only NULL values.
        score_columns = df.columns[df.columns.str.contains(r"_(?:sets|points|balls\d+)$")]        
        df[score_columns] = df[score_columns].astype("Int64")
        df["match_time"] = pd.to_datetime(df["match_time"])
        df["note"] = df["note"].fillna("").replace(r"(?i)^\s*(nan|<na>)\s*$", "", regex=True)

        df.sort_values(
            by=["pool_id", "match_time", "match_number", "match_id"],
            ignore_index=True,
            inplace=True
        )

        return df
    def commit(self) -> None:
        self.connection.commit()

