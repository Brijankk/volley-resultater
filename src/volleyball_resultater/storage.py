from __future__ import annotations

from pathlib import Path
import sqlite3

import pandas as pd

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS leagues (
    league_id INTEGER PRIMARY KEY,
    league_name TEXT NOT NULL,
    district TEXT NOT NULL,
    gender TEXT NOT NULL,
    age_group TEXT NOT NULL,
    season INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS pools (
    pool_id INTEGER PRIMARY KEY,
    pool_name TEXT NOT NULL,
    league_id INTEGER NOT NULL REFERENCES leagues(league_id)
);

CREATE TABLE IF NOT EXISTS rankings (
    pool_id INTEGER NOT NULL REFERENCES pools(pool_id),
    rank INTEGER NOT NULL,
    team_name TEXT NOT NULL,
    games_played INTEGER NOT NULL,
    games_won INTEGER NOT NULL,
    games_lost INTEGER NOT NULL,
    sets_won INTEGER NOT NULL,
    sets_lost INTEGER NOT NULL,
    balls_won INTEGER NOT NULL,
    balls_lost INTEGER NOT NULL,
    points INTEGER NOT NULL,
    PRIMARY KEY (pool_id, team_name)
);

CREATE TABLE IF NOT EXISTS matches (
    pool_id INTEGER NOT NULL REFERENCES pools(pool_id),
    match_id INTEGER PRIMARY KEY,
    match_number INTEGER,
    match_time TEXT,
    home_team TEXT NOT NULL,
    away_team TEXT NOT NULL,
    venue TEXT,
    court TEXT,
    address TEXT,
    referee1 TEXT,
    referee2 TEXT,
    home_sets INTEGER,
    away_sets INTEGER,
    home_points INTEGER,
    away_points INTEGER,
    home_balls1 INTEGER,
    away_balls1 INTEGER,
    home_balls2 INTEGER,
    away_balls2 INTEGER,
    home_balls3 INTEGER,
    away_balls3 INTEGER,
    home_balls4 INTEGER,
    away_balls4 INTEGER,
    home_balls5 INTEGER,
    away_balls5 INTEGER,
    note TEXT
);
"""

class Repository:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(SCHEMA)

    def close(self) -> None:
        self.connection.close()

    def upsert_leagues(self, leagues: pd.DataFrame) -> None:
        column_order = [
            'league_id',
            'league_name',
            'district',
            'gender',
            'age_group',
            'season'
        ]

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

    def upsert_pools(self, pools: pd.DataFrame) -> None:
        column_order = [
            'pool_id',
            'pool_name',
            'league_id',
        ]

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

    def upsert_rankings(self, ranking: pd.DataFrame) -> None:
        column_order = [
            'pool_id',
            'rank',
            'team_name',
            'games_played',
            'games_won',
            'games_lost',
            'sets_won',
            'sets_lost',
            'balls_won',
            'balls_lost',
            'points',
        ]

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

    def upsert_matches(self, matches: pd.DataFrame) -> None:
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
            # [row for row in matches.where(matches.notna(), None)[column_order].itertuples(index=False, name=None)],
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

    def commit(self) -> None:
        self.connection.commit()

