from __future__ import annotations

from pathlib import Path
import sqlite3

from .models import League, Match, Pool, Season, SetResult, StandingRow


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS seasons (
    id TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    value TEXT NOT NULL,
    start_year INTEGER,
    is_current INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS leagues (
    id TEXT PRIMARY KEY,
    season_id TEXT NOT NULL REFERENCES seasons(id),
    gender TEXT NOT NULL,
    division TEXT NOT NULL,
    name TEXT NOT NULL,
    raekke_id INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS pools (
    id TEXT PRIMARY KEY,
    league_id TEXT NOT NULL REFERENCES leagues(id),
    name TEXT NOT NULL,
    pulje_id INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS source_standings (
    pool_id TEXT NOT NULL REFERENCES pools(id),
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
    kamp_id INTEGER PRIMARY KEY,
    pool_id TEXT NOT NULL REFERENCES pools(id),
    match_number INTEGER,
    starts_at TEXT,
    home_team TEXT NOT NULL,
    away_team TEXT NOT NULL,
    venue TEXT NOT NULL,
    court TEXT NOT NULL,
    result_home_sets INTEGER,
    result_away_sets INTEGER
);

CREATE TABLE IF NOT EXISTS set_results (
    kamp_id INTEGER NOT NULL REFERENCES matches(kamp_id),
    set_number INTEGER NOT NULL,
    home_points INTEGER,
    away_points INTEGER,
    home_set_won INTEGER,
    away_set_won INTEGER,
    PRIMARY KEY (kamp_id, set_number)
);

CREATE TABLE IF NOT EXISTS computed_standings (
    pool_id TEXT NOT NULL REFERENCES pools(id),
    rule_profile TEXT NOT NULL,
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
    PRIMARY KEY (pool_id, rule_profile, team_name)
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

    def save_season(self, season: Season) -> None:
        self.connection.execute(
            """
            INSERT INTO seasons (id, label, value, start_year, is_current)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                label=excluded.label,
                value=excluded.value,
                start_year=excluded.start_year,
                is_current=excluded.is_current
            """,
            (season.id, season.label, season.value, season.start_year, int(season.is_current)),
        )

    def save_league(self, league: League) -> None:
        self.connection.execute(
            """
            INSERT INTO leagues (id, season_id, gender, division, name, raekke_id)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                season_id=excluded.season_id,
                gender=excluded.gender,
                division=excluded.division,
                name=excluded.name,
                raekke_id=excluded.raekke_id
            """,
            (league.id, league.season_id, league.gender, league.division, league.name, league.raekke_id),
        )

    def save_pool(self, pool: Pool) -> None:
        self.connection.execute(
            """
            INSERT INTO pools (id, league_id, name, pulje_id)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                league_id=excluded.league_id,
                name=excluded.name,
                pulje_id=excluded.pulje_id
            """,
            (pool.id, pool.league_id, pool.name, pool.pulje_id),
        )

    def replace_source_standings(self, pool_id: str, rows: list[StandingRow]) -> None:
        self.connection.execute("DELETE FROM source_standings WHERE pool_id = ?", (pool_id,))
        self.connection.executemany(
            """
            INSERT INTO source_standings (
                pool_id, rank, team_name, games_played, games_won, games_lost,
                sets_won, sets_lost, balls_won, balls_lost, points
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [standing_tuple(row) for row in rows],
        )

    def replace_matches(self, pool_id: str, matches: list[Match], set_results: list[SetResult]) -> None:
        kamp_ids = [match.kamp_id for match in matches]
        if kamp_ids:
            placeholders = ",".join("?" for _ in kamp_ids)
            self.connection.execute(f"DELETE FROM set_results WHERE kamp_id IN ({placeholders})", kamp_ids)
        self.connection.execute("DELETE FROM matches WHERE pool_id = ?", (pool_id,))
        self.connection.executemany(
            """
            INSERT INTO matches (
                kamp_id, pool_id, match_number, starts_at, home_team, away_team,
                venue, court, result_home_sets, result_away_sets
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    match.kamp_id,
                    match.pool_id,
                    match.match_number,
                    match.starts_at.isoformat() if match.starts_at else None,
                    match.home_team,
                    match.away_team,
                    match.venue,
                    match.court,
                    match.result_home_sets,
                    match.result_away_sets,
                )
                for match in matches
            ],
        )
        self.connection.executemany(
            """
            INSERT INTO set_results (
                kamp_id, set_number, home_points, away_points, home_set_won, away_set_won
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    row.kamp_id,
                    row.set_number,
                    row.home_points,
                    row.away_points,
                    row.home_set_won,
                    row.away_set_won,
                )
                for row in set_results
            ],
        )

    def replace_computed_standings(self, pool_id: str, rule_profile: str, rows: list[StandingRow]) -> None:
        self.connection.execute(
            "DELETE FROM computed_standings WHERE pool_id = ? AND rule_profile = ?",
            (pool_id, rule_profile),
        )
        self.connection.executemany(
            """
            INSERT INTO computed_standings (
                pool_id, rule_profile, rank, team_name, games_played, games_won, games_lost,
                sets_won, sets_lost, balls_won, balls_lost, points
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [(row.pool_id, rule_profile, *standing_tuple(row)[1:]) for row in rows],
        )

    def commit(self) -> None:
        self.connection.commit()


def standing_tuple(row: StandingRow) -> tuple[object, ...]:
    return (
        row.pool_id,
        row.rank,
        row.team_name,
        row.games_played,
        row.games_won,
        row.games_lost,
        row.sets_won,
        row.sets_lost,
        row.balls_won,
        row.balls_lost,
        row.points,
    )
