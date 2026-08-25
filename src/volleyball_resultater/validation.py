from __future__ import annotations

from dataclasses import dataclass
import sqlite3


COMPARE_COLUMNS = (
    "rank",
    "games_played",
    "games_won",
    "games_lost",
    "sets_won",
    "sets_lost",
    "balls_won",
    "balls_lost",
    "points",
)


@dataclass(frozen=True)
class RankingMismatch:
    pool_id: str
    league_name: str
    pool_name: str
    rule_profile: str
    team_name: str
    field: str
    official: object
    computed: object


@dataclass(frozen=True)
class PoolValidationSummary:
    pool_id: str
    mismatch_count: int
    affected_teams: int
    affected_fields: list[str]


def validate_rankings(connection: sqlite3.Connection) -> list[RankingMismatch]:
    connection.row_factory = sqlite3.Row
    mismatches: list[RankingMismatch] = []
    pools = connection.execute(
        """
        SELECT p.id AS pool_id, p.name AS pool_name, l.name AS league_name, l.division
             , l.id AS league_id, l.season_id, l.gender, l.raekke_id, p.pulje_id
             , s.value AS season_value, s.start_year AS season_start_year
        FROM pools p
        JOIN leagues l ON l.id = p.league_id
        JOIN seasons s ON s.id = l.season_id
        ORDER BY l.season_id, l.gender, l.division, p.name
        """
    ).fetchall()
    for pool in pools:
        rule_profile = rule_profile_for_pool(pool)
        official = rows_by_team(
            connection,
            "source_standings",
            "pool_id = ?",
            (pool["pool_id"],),
        )
        computed = rows_by_team(
            connection,
            "computed_standings",
            "pool_id = ? AND rule_profile = ?",
            (pool["pool_id"], rule_profile),
        )
        for team_name in sorted(set(official) | set(computed)):
            if team_name not in official:
                mismatches.append(mismatch(pool, rule_profile, team_name, "team", None, "computed only"))
                continue
            if team_name not in computed:
                mismatches.append(mismatch(pool, rule_profile, team_name, "team", "official only", None))
                continue
            for column in COMPARE_COLUMNS:
                if official[team_name][column] != computed[team_name][column]:
                    mismatches.append(
                        mismatch(
                            pool,
                            rule_profile,
                            team_name,
                            column,
                            official[team_name][column],
                            computed[team_name][column],
                        )
                    )
    return mismatches


def validation_summary(connection: sqlite3.Connection) -> dict[str, PoolValidationSummary]:
    by_pool: dict[str, list[RankingMismatch]] = {}
    for item in validate_rankings(connection):
        by_pool.setdefault(item.pool_id, []).append(item)
    return {
        pool_id: PoolValidationSummary(
            pool_id=pool_id,
            mismatch_count=len(items),
            affected_teams=len({item.team_name for item in items}),
            affected_fields=sorted({item.field for item in items}),
        )
        for pool_id, items in by_pool.items()
    }


def rows_by_team(
    connection: sqlite3.Connection,
    table: str,
    where_sql: str,
    params: tuple[object, ...],
) -> dict[str, sqlite3.Row]:
    return {
        row["team_name"]: row
        for row in connection.execute(
            f"SELECT * FROM {table} WHERE {where_sql}",
            params,
        )
    }


def mismatch(
    pool: sqlite3.Row,
    rule_profile: str,
    team_name: str,
    field: str,
    official: object,
    computed: object,
) -> RankingMismatch:
    return RankingMismatch(
        pool_id=pool["pool_id"],
        league_name=pool["league_name"],
        pool_name=pool["pool_name"],
        rule_profile=rule_profile,
        team_name=team_name,
        field=field,
        official=official,
        computed=computed,
    )


def rule_profile_for_pool(pool: sqlite3.Row) -> str:
    from .rules import RuleContext, rules_for_context

    return rules_for_context(
        RuleContext(
            season_id=pool["season_id"],
            season_value=pool["season_value"],
            start_year=pool["season_start_year"],
            gender=pool["gender"],
            division=pool["division"],
            league_id=pool["league_id"],
            raekke_id=pool["raekke_id"],
            pool_id=pool["pool_id"],
            pool_name=pool["pool_name"],
            pulje_id=pool["pulje_id"],
        )
    ).id
