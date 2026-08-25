from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import json
from pathlib import Path

from .models import League, Match, Pool, Season, SetResult, StandingRow


@dataclass(frozen=True)
class RuleProfile:
    id: str
    ranking_order: tuple[str, ...]
    winner_points: int
    loser_points: int
    five_set_winner_points: int
    five_set_loser_points: int


@dataclass(frozen=True)
class RuleContext:
    season_id: str | None = None
    season_value: str | None = None
    start_year: int | None = None
    gender: str | None = None
    division: str | None = None
    league_id: str | None = None
    raekke_id: int | None = None
    pool_id: str | None = None
    pool_name: str | None = None
    pulje_id: int | None = None


@dataclass(frozen=True)
class RuleAssignment:
    profile: str
    seasons: tuple[str, ...] = ()
    genders: tuple[str, ...] = ()
    divisions: tuple[str, ...] = ()
    league_ids: tuple[str, ...] = ()
    raekke_ids: tuple[int, ...] = ()
    pool_ids: tuple[str, ...] = ()
    pulje_ids: tuple[int, ...] = ()


FIVE_SET_THREE_ONE_RULES = RuleProfile(
    id="five_set_3_1",
    ranking_order=("points", "set_difference", "ball_difference"),
    winner_points=3,
    loser_points=0,
    five_set_winner_points=3,
    five_set_loser_points=1,
)

FIVE_SET_TWO_ONE_RULES = RuleProfile(
    id="five_set_2_1",
    ranking_order=("points", "set_difference", "ball_difference"),
    winner_points=3,
    loser_points=0,
    five_set_winner_points=2,
    five_set_loser_points=1,
)

HISTORIC_WINS_FIRST_RULES = RuleProfile(
    id="historic_wins_first",
    ranking_order=("games_won", "points", "set_difference", "ball_difference"),
    winner_points=3,
    loser_points=0,
    five_set_winner_points=3,
    five_set_loser_points=1,
)

CURRENT_RULES = FIVE_SET_THREE_ONE_RULES
VOLLEYLIGAEN_2025_RULES = FIVE_SET_TWO_ONE_RULES
HISTORIC_TWO_ONE_RULES = FIVE_SET_TWO_ONE_RULES

CONFIG_PATH = Path(__file__).with_name("rule_assignments.json")
RULE_PROFILES = {
    profile.id: profile
    for profile in (
        FIVE_SET_THREE_ONE_RULES,
        FIVE_SET_TWO_ONE_RULES,
        HISTORIC_WINS_FIRST_RULES,
    )
}


def rules_for_context(context: RuleContext) -> RuleProfile:
    assignments = matching_assignments(context)
    if not assignments:
        return CURRENT_RULES
    _, _, assignment = max(assignments, key=lambda item: (item[0], item[1]))
    return RULE_PROFILES[assignment.profile]


def rules_for_league(season: Season, league: League, pool: Pool | None = None) -> RuleProfile:
    return rules_for_context(
        RuleContext(
            season_id=season.id,
            season_value=season.value,
            start_year=season.start_year,
            gender=league.gender,
            division=league.division,
            league_id=league.id,
            raekke_id=league.raekke_id,
            pool_id=pool.id if pool else None,
            pool_name=pool.name if pool else None,
            pulje_id=pool.pulje_id if pool else None,
        )
    )


def rules_for_division(division: str) -> RuleProfile:
    return rules_for_context(RuleContext(season_id="2025", season_value="2025", start_year=2025, division=division))


def matching_assignments(context: RuleContext) -> list[tuple[int, int, RuleAssignment]]:
    return [
        (season_score, specificity(assignment), assignment)
        for assignment in rule_assignments()
        if filters_match(assignment, context)
        for season_score in [matching_season_score(assignment, context)]
        if season_score is not None
    ]


def filters_match(assignment: RuleAssignment, context: RuleContext) -> bool:
    return (
        matches_text_filter(assignment.genders, context.gender)
        and matches_text_filter(assignment.divisions, context.division)
        and matches_text_filter(assignment.league_ids, context.league_id)
        and matches_int_filter(assignment.raekke_ids, context.raekke_id)
        and matches_text_filter(assignment.pool_ids, context.pool_id)
        and matches_int_filter(assignment.pulje_ids, context.pulje_id)
    )


def matching_season_score(assignment: RuleAssignment, context: RuleContext) -> int | None:
    if not assignment.seasons:
        return 0
    context_year = context.start_year or year_from_text(context.season_value) or year_from_text(context.season_id)
    context_values = {value for value in (context.season_id, context.season_value) if value}
    best_score: int | None = None
    for season in assignment.seasons:
        assignment_year = year_from_text(season)
        if context_year is not None and assignment_year is not None:
            if assignment_year <= context_year:
                best_score = max(best_score or 0, assignment_year)
            continue
        if season in context_values:
            best_score = max(best_score or 0, 1)
    return best_score


def specificity(assignment: RuleAssignment) -> int:
    score = 0
    score += 1 if assignment.genders else 0
    score += 2 if assignment.divisions else 0
    score += 4 if assignment.raekke_ids else 0
    score += 8 if assignment.league_ids else 0
    score += 16 if assignment.pulje_ids else 0
    score += 32 if assignment.pool_ids else 0
    return score


def matches_text_filter(values: tuple[str, ...], candidate: str | None) -> bool:
    if not values:
        return True
    return candidate in values


def matches_int_filter(values: tuple[int, ...], candidate: int | None) -> bool:
    if not values:
        return True
    return candidate in values


def year_from_text(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(value[:4])
    except ValueError:
        return None


@lru_cache(maxsize=1)
def rule_assignments() -> tuple[RuleAssignment, ...]:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return tuple(parse_assignment(row) for row in config.get("assignments", []))


def parse_assignment(row: dict[str, object]) -> RuleAssignment:
    profile = str(row["profile"])
    if profile not in RULE_PROFILES:
        raise ValueError(f"Unknown rule profile: {profile}")
    return RuleAssignment(
        profile=profile,
        seasons=text_values(row.get("season")),
        genders=text_values(row.get("gender")),
        divisions=text_values(row.get("division")),
        league_ids=text_values(row.get("league_id")),
        raekke_ids=int_values(row.get("raekke_id")),
        pool_ids=text_values(row.get("pool_id")),
        pulje_ids=int_values(row.get("pulje_id")),
    )


def text_values(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, list):
        return tuple(str(item) for item in value)
    return (str(value),)


def int_values(value: object) -> tuple[int, ...]:
    if value is None:
        return ()
    if isinstance(value, list):
        return tuple(int(item) for item in value)
    return (int(value),)


def match_points(home_sets: int, away_sets: int, rules: RuleProfile = CURRENT_RULES) -> tuple[int, int]:
    if home_sets == away_sets:
        return 0, 0
    is_five_set = sorted((home_sets, away_sets)) == [2, 3]
    winner_points = rules.five_set_winner_points if is_five_set else rules.winner_points
    loser_points = rules.five_set_loser_points if is_five_set else rules.loser_points
    if home_sets > away_sets:
        return winner_points, loser_points
    return loser_points, winner_points


def computed_standings(
    pool_id: str,
    matches: list[Match],
    set_results: list[SetResult],
    rules: RuleProfile = CURRENT_RULES,
) -> list[StandingRow]:
    teams = sorted({match.home_team for match in matches} | {match.away_team for match in matches})
    stats = {
        team: {
            "games_played": 0,
            "games_won": 0,
            "games_lost": 0,
            "sets_won": 0,
            "sets_lost": 0,
            "balls_won": 0,
            "balls_lost": 0,
            "points": 0,
        }
        for team in teams
    }
    set_lookup: dict[int, list[SetResult]] = {}
    for result in set_results:
        set_lookup.setdefault(result.kamp_id, []).append(result)

    for match in matches:
        if match.result_home_sets is None or match.result_away_sets is None:
            continue
        home = stats[match.home_team]
        away = stats[match.away_team]
        home["games_played"] += 1
        away["games_played"] += 1
        home["sets_won"] += match.result_home_sets
        home["sets_lost"] += match.result_away_sets
        away["sets_won"] += match.result_away_sets
        away["sets_lost"] += match.result_home_sets
        if match.result_home_sets > match.result_away_sets:
            home["games_won"] += 1
            away["games_lost"] += 1
        else:
            away["games_won"] += 1
            home["games_lost"] += 1
        home_points, away_points = match_points(match.result_home_sets, match.result_away_sets, rules)
        home["points"] += home_points
        away["points"] += away_points
        match_sets = usable_or_default_set_results(match, set_lookup.get(match.kamp_id, []))
        for set_row in match_sets:
            if set_row.home_points is None or set_row.away_points is None:
                continue
            home["balls_won"] += set_row.home_points
            home["balls_lost"] += set_row.away_points
            away["balls_won"] += set_row.away_points
            away["balls_lost"] += set_row.home_points

    def sort_key(team: str) -> tuple[int, int, int, int, str]:
        row = stats[team]
        values = {
            "points": row["points"],
            "games_won": row["games_won"],
            "set_difference": row["sets_won"] - row["sets_lost"],
            "ball_difference": row["balls_won"] - row["balls_lost"],
        }
        return (*(-values[name] for name in rules.ranking_order), team)

    standings: list[StandingRow] = []
    for rank, team in enumerate(sorted(teams, key=sort_key), start=1):
        row = stats[team]
        standings.append(
            StandingRow(
                pool_id=pool_id,
                rank=rank,
                team_name=team,
                games_played=row["games_played"],
                games_won=row["games_won"],
                games_lost=row["games_lost"],
                sets_won=row["sets_won"],
                sets_lost=row["sets_lost"],
                balls_won=row["balls_won"],
                balls_lost=row["balls_lost"],
                points=row["points"],
            )
        )
    return standings


def usable_or_default_set_results(match: Match, set_results: list[SetResult]) -> list[SetResult]:
    if any(row.home_points is not None and row.away_points is not None for row in set_results):
        return set_results
    if not is_default_win(match):
        return set_results
    return default_win_set_results(match)


def is_default_win(match: Match) -> bool:
    note = match.result_note.upper()
    return "HHT" in note or "UHT" in note


def default_win_set_results(match: Match) -> list[SetResult]:
    if match.result_home_sets is None or match.result_away_sets is None:
        return []
    if match.result_home_sets > match.result_away_sets:
        return [
            SetResult(match.kamp_id, set_number, 25, 0, 1, 0)
            for set_number in range(1, match.result_home_sets + 1)
        ]
    if match.result_away_sets > match.result_home_sets:
        return [
            SetResult(match.kamp_id, set_number, 0, 25, 0, 1)
            for set_number in range(1, match.result_away_sets + 1)
        ]
    return []


def cumulative_points(matches: list[Match], rules: RuleProfile = CURRENT_RULES) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    totals: dict[str, int] = {}
    games: dict[str, int] = {}
    teams = sorted({match.home_team for match in matches} | {match.away_team for match in matches})
    for team in teams:
        totals[team] = 0
        games[team] = 0
        events.append({"team": team, "date": None, "game_number": 0, "points": 0, "cumulative_points": 0})

    played = [
        match
        for match in matches
        if match.starts_at is not None and match.result_home_sets is not None and match.result_away_sets is not None
    ]
    for match in sorted(played, key=lambda item: (item.starts_at, item.match_number or 0)):
        home_points, away_points = match_points(match.result_home_sets or 0, match.result_away_sets or 0, rules)
        for team, points in ((match.home_team, home_points), (match.away_team, away_points)):
            totals[team] += points
            games[team] += 1
            events.append(
                {
                    "team": team,
                    "date": match.starts_at.isoformat() if match.starts_at else None,
                    "game_number": games[team],
                    "points": points,
                    "cumulative_points": totals[team],
                    "kamp_id": match.kamp_id,
                }
            )
    return events


def result_matrix(matches: list[Match]) -> dict[str, dict[str, str | None]]:
    teams = sorted({match.home_team for match in matches} | {match.away_team for match in matches})
    matrix: dict[str, dict[str, str | None]] = {
        home: {away: None if home != away else "" for away in teams} for home in teams
    }
    for match in matches:
        if match.result_home_sets is None or match.result_away_sets is None:
            continue
        value = f"{match.result_home_sets}-{match.result_away_sets}"
        existing = matrix[match.home_team][match.away_team]
        matrix[match.home_team][match.away_team] = value if not existing else f"{existing}, {value}"
    return matrix
