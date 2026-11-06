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
        model_columns = list(Leagues.to_schema().columns)
        query = self._create_upsert_query(
            table_name="leagues",
            columns=model_columns,
            conflict_columns=["league_id"],
        )

        self.connection.executemany(
            query,
            [row for row in leagues[model_columns].itertuples(index=False, name=None)],
        )

    @pa.check_types
    def upsert_pools(self, pools: DataFrame[Pools]) -> None:
        model_columns = list(Pools.to_schema().columns)
        query = self._create_upsert_query(
            table_name="pools",
            columns=model_columns,
            conflict_columns=["pool_id"],
        )

        self.connection.executemany(
            query,
            [row for row in pools[model_columns].itertuples(index=False, name=None)],
        )

    @pa.check_types
    def upsert_rankings(self, ranking: DataFrame[Rankings]) -> None:
        model_columns = list(Rankings.to_schema().columns)
        query = self._create_upsert_query(
            table_name="rankings",
            columns=model_columns,
            conflict_columns=["pool_id", "team_name"],
        )

        self.connection.executemany(
            query,
            [row for row in ranking[model_columns].itertuples(index=False, name=None)],
        )

    @pa.check_types
    def upsert_matches(self, matches: DataFrame[Matches]) -> None:
        model_columns = list(Matches.to_schema().columns)
        query = self._create_upsert_query(
            table_name="matches",
            columns=model_columns,
            conflict_columns=["match_id"],
        )

        df = matches.copy()
        int64_cols = df.loc[:, df.dtypes.eq('Int64')].columns
        df[int64_cols] = df[int64_cols].astype(object).fillna(None)
        df['match_time'] = df['match_time'].dt.strftime(date_format='%Y-%m-%dT%H:%M:%S')

        self.connection.executemany(
            query,
            [row for row in df[model_columns].itertuples(index=False, name=None)],
        )


    @pa.check_types
    def get_leagues(self) -> DataFrame[Leagues]:
        query = """
            SELECT *
            FROM leagues
        """

        df = pd.read_sql(
            sql=query,
            con=self.connection
        )

        return df

    @pa.check_types
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

    @pa.check_types
    def get_rankings(self) -> DataFrame[Rankings]:
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

    @pa.check_types
    def get_matches(self) -> DataFrame[Matches]:
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

    @staticmethod
    def _create_upsert_query(table_name: str, columns: list[str], conflict_columns: list[str]) -> str:
        exclude_columns = list(set(columns).difference(set(conflict_columns)))
        raw_query = """
            INSERT INTO {name_of_table} ({insert_columns})
            VALUES ({number_of_columns})
            ON CONFLICT ({conflicting_columns}) DO UPDATE SET
                {excluding_columns}
        """
        query_parameters = {
            "name_of_table": table_name,
            "insert_columns": ', '.join(columns),
            "number_of_columns": ', '.join(['?'] *  len(columns)),
            "conflicting_columns": ', '.join(conflict_columns),
            "excluding_columns": ', '.join(["{0}=excluded.{0}".format(col) for col in exclude_columns])
        }
        query = raw_query.format(**query_parameters)

        return query
