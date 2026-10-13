from __future__ import annotations

import re

from .client import FIELD_SEASON, ResultaterClient, build_search_form
from .html_tools import parse_forms
from .models import League, PoolData, Season
from .parsers import parse_league_links, parse_match_sets, parse_pools, parse_schedule, parse_standings


DISTRICT = "Volleyball Danmark"
AGE_GROUP = "Senior"
GENDERS = ("Mand", "Kvinde")


class VolleyballScraper:
    def __init__(self, client: ResultaterClient) -> None:
        self.client = client
        self._search_html: str | None = None

    def seasons(self) -> list[Season]:
        html = self._get_search_html()
        form = parse_forms(html)
        options = form.selects[FIELD_SEASON]
        current_start_year = newest_numeric_season(options)
        has_current = any(option.text == "Nuværende" for option in options)
        seasons: list[Season] = []
        for option in options:
            if option.text == "Nuværende":
                season_id = str(current_start_year) if current_start_year is not None else "current"
                seasons.append(
                    Season(
                        id=season_id,
                        label=option.text,
                        value=option.value,
                        start_year=current_start_year,
                        is_current=True,
                    )
                )
            elif option.value.isdigit():
                start_year = int(option.value)
                if has_current and current_start_year == start_year:
                    continue
                seasons.append(
                    Season(
                        id=option.value,
                        label=option.text,
                        value=option.value,
                        start_year=start_year,
                        is_current=False,
                    )
                )
        return seasons

    def leagues_for(self, season: Season, gender: str) -> list[League]:
        search_html = self._get_search_html()
        form = build_search_form(search_html, DISTRICT, gender, AGE_GROUP, season.value)
        result = self.client.post_search(form)
        leagues: list[League] = []
        for name, raekke_id in parse_league_links(result.html):
            division = regular_season_division(name, gender)
            if division is None:
                continue
            league_id = f"{season.id}:{gender_key(gender)}:{division_key(division)}"
            leagues.append(
                League(
                    id=league_id,
                    season_id=season.id,
                    gender=gender,
                    division=division,
                    name=name,
                    raekke_id=raekke_id,
                )
            )
        return leagues

    def scrape_league(self, league: League) -> list[PoolData]:
        overview = self.client.get(f"/tms/Turneringer-og-resultater/Pulje-Oversigt.aspx?RaekkeId={league.raekke_id}")
        pools = parse_pools(overview.html, overview.url, league.id)
        data: list[PoolData] = []
        for pool in pools:
            standing_html = self.client.get(f"/tms/Turneringer-og-resultater/Pulje-Stilling.aspx?PuljeId={pool.pulje_id}").html
            schedule_html = self.client.get(
                f"/tms/Turneringer-og-resultater/Pulje-Komplet-Kampprogram.aspx?PuljeId={pool.pulje_id}"
            ).html
            standings = parse_standings(standing_html, pool.id)
            matches = parse_schedule(schedule_html, pool.id)
            set_results = []
            for match in matches:
                if match.result_home_sets is None or match.result_away_sets is None:
                    continue
                match_html = self.client.get(f"/tms/Turneringer-og-resultater/Kamp-Information.aspx?KampId={match.kamp_id}").html
                set_results.extend(parse_match_sets(match_html, match.kamp_id))
            data.append(PoolData(pool=pool, standings=standings, matches=matches, set_results=set_results))
        return data

    def _get_search_html(self) -> str:
        if self._search_html is None:
            self._search_html = self.client.initial_search_page().html
        return self._search_html


def regular_season_division(name: str, gender: str) -> str | None:
    expected_suffix = "Herrer" if gender == "Mand" else "Kvinder"
    if name.lower() == f"volleyligaen {expected_suffix}".lower():
        return "Volleyligaen"
    match = re.fullmatch(r"(\d+)\. Division " + re.escape(expected_suffix), name)
    if match:
        return f"{match.group(1)}. Division"
    return None


def newest_numeric_season(options: list[object]) -> int | None:
    years = []
    for option in options:
        value = getattr(option, "value", "")
        if value.isdigit():
            years.append(int(value))
    return max(years) if years else None


def gender_key(gender: str) -> str:
    return {"Mand": "men", "Kvinde": "women"}.get(gender, gender.lower())


def division_key(division: str) -> str:
    return division.lower().replace(".", "").replace(" ", "-")
