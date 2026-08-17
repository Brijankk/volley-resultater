from __future__ import annotations

from datetime import datetime
import re
from urllib.parse import parse_qs, urlparse

from .html_tools import Cell, Link, clean_text, parse_links, parse_tables
from .models import Match, Pool, SetResult, StandingRow


BASE_PATH = "/tms/Turneringer-og-resultater/"


def query_int(url: str, key: str) -> int | None:
    parsed = urlparse(url)
    values = parse_qs(parsed.query).get(key)
    if not values:
        return None
    try:
        return int(values[0])
    except ValueError:
        return None


def parse_league_links(html: str) -> list[tuple[str, int]]:
    leagues: list[tuple[str, int]] = []
    for link in parse_links(html):
        raekke_id = query_int(link.href, "RaekkeId")
        if link.text and raekke_id is not None:
            leagues.append((link.text, raekke_id))
    return leagues


def parse_pools(html: str, final_url: str, league_id: str) -> list[Pool]:
    pulje_id = query_int(final_url, "PuljeId")
    if pulje_id is not None:
        return [Pool(id=f"{league_id}:pulje-{pulje_id}", league_id=league_id, name="Række 1", pulje_id=pulje_id)]

    pools: list[Pool] = []
    for link in parse_links(html):
        if "Pulje-Stilling.aspx" not in link.href:
            continue
        link_pulje_id = query_int(link.href, "PuljeId")
        if link_pulje_id is None or not link.text:
            continue
        name = "Række 1" if link.text == "Stilling" else link.text
        if any(pool.pulje_id == link_pulje_id for pool in pools):
            continue
        pools.append(
            Pool(
                id=f"{league_id}:pulje-{link_pulje_id}",
                league_id=league_id,
                name=name,
                pulje_id=link_pulje_id,
            )
        )
    return pools


def parse_standings(html: str, pool_id: str) -> list[StandingRow]:
    rows: list[StandingRow] = []
    for table in parse_tables(html):
        for row in table:
            texts = [cell.text for cell in row if cell.text != ""]
            if len(texts) < 9 or not texts[0].isdigit():
                continue
            try:
                balls_index = next(index for index, text in enumerate(texts) if re.fullmatch(r"\d+\s*-\s*\d+", text))
                sets_won = int(texts[5])
                sets_lost = int(texts[7]) if texts[6] == "-" else int(texts[6])
                balls_won, balls_lost = split_score(texts[balls_index])
                rows.append(
                    StandingRow(
                        pool_id=pool_id,
                        rank=int(texts[0]),
                        team_name=texts[1],
                        games_played=int(texts[2]),
                        games_won=int(texts[3]),
                        games_lost=int(texts[4]),
                        sets_won=sets_won,
                        sets_lost=sets_lost,
                        balls_won=balls_won,
                        balls_lost=balls_lost,
                        points=int(texts[balls_index + 1]),
                    )
                )
            except (StopIteration, ValueError, IndexError):
                continue
    return rows


def parse_schedule(html: str, pool_id: str) -> list[Match]:
    matches: list[Match] = []
    for table in parse_tables(html):
        for row in table:
            texts = [cell.text for cell in row]
            compact = [text for text in texts if text]
            if len(compact) < 5 or not compact[0].isdigit():
                continue
            kamp_id = find_kamp_id(row[0].links)
            if kamp_id is None:
                continue
            result_home, result_away = parse_optional_score(compact[-1])
            venue, court = split_venue_court(compact[4] if len(compact) > 4 else "")
            matches.append(
                Match(
                    pool_id=pool_id,
                    kamp_id=kamp_id,
                    match_number=int(compact[0]),
                    starts_at=parse_danish_datetime(compact[1]),
                    home_team=compact[2],
                    away_team=compact[3],
                    venue=venue,
                    court=court,
                    result_home_sets=result_home,
                    result_away_sets=result_away,
                )
            )
    return matches


def parse_match_sets(html: str, kamp_id: int) -> list[SetResult]:
    sets: list[SetResult] = []
    for table in parse_tables(html):
        for row in table:
            texts = [cell.text for cell in row]
            if not texts:
                continue
            match = re.match(r"(\d+)\.\s*Sæt", texts[0], flags=re.IGNORECASE)
            if not match:
                continue
            numbers = numeric_cells(texts[1:])
            if len(numbers) >= 4:
                home_points, away_points, home_set_won, away_set_won = numbers[:4]
            elif len(numbers) >= 2:
                home_points, away_points = numbers[:2]
                home_set_won = 1 if home_points > away_points else 0
                away_set_won = 1 if away_points > home_points else 0
            else:
                home_points = away_points = home_set_won = away_set_won = None
            sets.append(
                SetResult(
                    kamp_id=kamp_id,
                    set_number=int(match.group(1)),
                    home_points=home_points,
                    away_points=away_points,
                    home_set_won=home_set_won,
                    away_set_won=away_set_won,
                )
            )
    return sets


def numeric_cells(values: list[str]) -> list[int]:
    numbers: list[int] = []
    for value in values:
        value = clean_text(value)
        if re.fullmatch(r"\d+(?:\s+\d+)?", value):
            numbers.extend(int(part) for part in value.split())
    return numbers


def split_score(value: str) -> tuple[int, int]:
    left, right = re.split(r"\s*-\s*", clean_text(value), maxsplit=1)
    return int(left), int(right)


def parse_optional_score(value: str) -> tuple[int | None, int | None]:
    value = clean_text(value)
    if not re.fullmatch(r"\d+\s*-\s*\d+", value):
        return None, None
    return split_score(value)


def parse_danish_datetime(value: str) -> datetime | None:
    value = clean_text(value).replace("kl. ", "kl.").replace(" kl.", " kl.")
    for fmt in ("%d-%m-%y kl.%H:%M", "%d-%m-%Y kl.%H:%M"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            pass
    return None


def split_venue_court(value: str) -> tuple[str, str]:
    value = clean_text(value)
    match = re.match(r"(.+?)\s+(\d+(?:[-,]\s*[\w\d]+)?)$", value)
    if match:
        return clean_text(match.group(1)), clean_text(match.group(2))
    return value, ""


def find_kamp_id(links: list[Link]) -> int | None:
    for link in links:
        kamp_id = query_int(link.href, "KampId")
        if kamp_id is not None:
            return kamp_id
    return None
