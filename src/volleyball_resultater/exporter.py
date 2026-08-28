from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from pathlib import Path
import json
import sqlite3

from .models import Match
from . import __version__
from .rules import RuleContext, cumulative_points, result_matrix, rules_for_context
from .validation import validation_summary


def export_json(db_path: Path, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        exported_at = datetime.now().astimezone().isoformat(timespec="seconds")
        leagues = [dict(row) for row in connection.execute("SELECT * FROM leagues ORDER BY season_id DESC, gender, division")]
        pools = [
            dict(row)
            for row in connection.execute(
                """
                SELECT p.*, l.season_id, l.gender, l.division, l.name AS league_name,
                       l.raekke_id, s.value AS season_value, s.start_year AS season_start_year
                FROM pools p
                JOIN leagues l ON l.id = p.league_id
                JOIN seasons s ON s.id = l.season_id
                ORDER BY p.league_id, p.name
                """
            )
        ]
        summaries = validation_summary(connection)
        pool_validation = {
            pool_id: {
                "mismatch_count": summary.mismatch_count,
                "affected_teams": summary.affected_teams,
                "affected_fields": summary.affected_fields,
            }
            for pool_id, summary in summaries.items()
        }
        write_json(
            output_dir / "leagues.json",
            {
                "metadata": {
                    "schema_version": 1,
                    "exported_at": exported_at,
                    "scraper_version": __version__,
                    "seasons": sorted({league["season_id"] for league in leagues}, reverse=True),
                    "league_count": len(leagues),
                    "pool_count": len(pools),
                    "validation": {
                        "pools_with_mismatches": len(pool_validation),
                        "mismatch_count": sum(item["mismatch_count"] for item in pool_validation.values()),
                    },
                },
                "leagues": leagues,
                "pools": pools,
                "pool_validation": pool_validation,
            },
        )

        for pool in pools:
            pool_id = pool["id"]
            rule_profile = rules_for_context(
                RuleContext(
                    season_id=pool["season_id"],
                    season_value=pool["season_value"],
                    start_year=pool["season_start_year"],
                    gender=pool["gender"],
                    division=pool["division"],
                    league_id=pool["league_id"],
                    raekke_id=pool["raekke_id"],
                    pool_id=pool_id,
                    pool_name=pool["name"],
                    pulje_id=pool["pulje_id"],
                )
            )
            standings = [
                dict(row)
                for row in connection.execute(
                    "SELECT * FROM source_standings WHERE pool_id = ? ORDER BY rank",
                    (pool_id,),
                )
            ]
            computed = [
                dict(row)
                for row in connection.execute(
                    "SELECT * FROM computed_standings WHERE pool_id = ? AND rule_profile = ? ORDER BY rank",
                    (pool_id, rule_profile.id),
                )
            ]
            matches = [
                dict(row)
                for row in connection.execute(
                    "SELECT * FROM matches WHERE pool_id = ? ORDER BY starts_at, match_number",
                    (pool_id,),
                )
            ]
            for match in matches:
                match["starts_at_time_known"] = bool(match["starts_at_time_known"])
            sets = [
                dict(row)
                for row in connection.execute(
                    """
                    SELECT sr.* FROM set_results sr
                    JOIN matches m ON m.kamp_id = sr.kamp_id
                    WHERE m.pool_id = ?
                    ORDER BY sr.kamp_id, sr.set_number
                    """,
                    (pool_id,),
                )
            ]
            match_models = [
                Match(
                    pool_id=row["pool_id"],
                    kamp_id=row["kamp_id"],
                    match_number=row["match_number"],
                    starts_at=datetime.fromisoformat(row["starts_at"]) if row["starts_at"] else None,
                    home_team=row["home_team"],
                    away_team=row["away_team"],
                    venue=row["venue"],
                    court=row["court"],
                    result_home_sets=row["result_home_sets"],
                    result_away_sets=row["result_away_sets"],
                    result_note=row["result_note"],
                    starts_at_time_known=bool(row["starts_at_time_known"]),
                )
                for row in matches
            ]
            write_json(
                output_dir / f"{safe_filename(pool_id)}.json",
                {
                    "metadata": {
                        "schema_version": 1,
                        "exported_at": exported_at,
                        "scraper_version": __version__,
                        "rule_profile": rule_profile.id,
                        "validation": pool_validation.get(
                            pool_id,
                            {"mismatch_count": 0, "affected_teams": 0, "affected_fields": []},
                        ),
                    },
                    "pool": pool,
                    "source_standings": standings,
                    "computed_standings": computed,
                    "matches": matches,
                    "set_results": sets,
                    "rule_profile": rule_profile.id,
                    "cumulative_points": cumulative_points(match_models, rule_profile),
                    "result_matrix": result_matrix(match_models),
                },
            )
    finally:
        connection.close()


def write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=json_default), encoding="utf-8")


def json_default(value: object) -> object:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def safe_filename(value: str) -> str:
    return "".join(char if char.isalnum() or char in "-_" else "_" for char in value)
