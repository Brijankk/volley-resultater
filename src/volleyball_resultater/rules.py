from __future__ import annotations

from dataclasses import dataclass

from .models import Match, SetResult, StandingRow


@dataclass(frozen=True)
class RuleProfile:
    id: str
    ranking_order: tuple[str, ...]
    winner_points: int
    loser_points: int
    five_set_winner_points: int
    five_set_loser_points: int


CURRENT_RULES = RuleProfile(
    id="dt_2025_division",
    ranking_order=("points", "set_difference", "ball_difference"),
    winner_points=3,
    loser_points=0,
    five_set_winner_points=3,
    five_set_loser_points=1,
)

VOLLEYLIGAEN_2025_RULES = RuleProfile(
    id="dt_2025_volleyligaen",
    ranking_order=("points", "set_difference", "ball_difference"),
    winner_points=3,
    loser_points=0,
    five_set_winner_points=2,
    five_set_loser_points=1,
)

HISTORIC_TWO_ONE_RULES = RuleProfile(
    id="historic_2_1_five_set",
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


def rules_for_division(division: str) -> RuleProfile:
    if division == "Volleyligaen":
        return VOLLEYLIGAEN_2025_RULES
    return CURRENT_RULES


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
        for set_row in set_lookup.get(match.kamp_id, []):
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
