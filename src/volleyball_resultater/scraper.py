from io import StringIO
from functools import wraps
import inspect
from enum import Enum

import pandas as pd
import pandas.api.types as ptypes
import numpy as np
import pandera.pandas as pa
from pandera.typing import DataFrame

from .client import FIELD_SEASON, FIELD_AGE_GROUP, FIELD_DISTRICT, FIELD_GENDER, ResultaterClient, build_search_form
from .html_tools import parse_forms
from .parsers import parse_league_links, parse_pools, parse_links, query_int
from .models import Leagues, Pools, Schedules, Rankings, MatchDetails

DISTRICT = "Volleyball Danmark"
AGE_GROUP = "Senior"
GENDERS = ("Mand", "Kvinde")

class LeagueFilters(Enum):
    District = FIELD_DISTRICT
    Gender = FIELD_GENDER
    Age_group = FIELD_AGE_GROUP
    Season = FIELD_SEASON

class VolleyballScraper:
    def __init__(self, client: ResultaterClient) -> None:
        self.client = client
        self._search_html: str | None = None
        self._season_overview: pd.DataFrame = pd.DataFrame()

        self.league_url: str = f"/tms/Turneringer-og-resultater/Pulje-Oversigt.aspx?RaekkeId="
        self.scoreboard_url: str = f"/tms/Turneringer-og-resultater/Pulje-Stilling.aspx?PuljeId="
        self.schedule_url: str = f"/tms/Turneringer-og-resultater/Pulje-Komplet-Kampprogram.aspx?PuljeId="
        self.match_url: str = f"/tms/Turneringer-og-resultater/Kamp-Information.aspx?KampId="

    def _get_action_parameters(self, func: callable, args: tuple, kwargs: dict) -> dict:
        bound = inspect.signature(func).bind(func, *args, **kwargs)
        bound.apply_defaults()
        new_kwargs = bound.arguments
        new_kwargs.pop("self", None)
        
        return new_kwargs
    
    def append_parameters(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            parameters = self._get_action_parameters(func, args, kwargs)
            df = func(self, *args, **kwargs)
            df = df.assign(**parameters)
            return df
        return wrapper

    def _get_search_html(self) -> str:
        if self._search_html is None:
            self._search_html = self.client.initial_search_page().html
        return self._search_html

    def _get_season_overview(self) -> pd.DataFrame:
        if self._season_overview.empty:
            search_html = self._get_search_html()
            form = build_search_form(search_html, DISTRICT, GENDERS[0], AGE_GROUP, '0')
            result = self.client.post_search(form)

            current_leagues = pd.DataFrame(
                data=parse_league_links(result.html),
                columns=["league_name", "league_id"],
            )

            liga_id = current_leagues.set_index('league_name')['league_id']['Volleyligaen Herrer']
            liga_pool = self.get_pool_ids(liga_id)
            liga_schedule = self.scrape_pool_schedule(liga_pool.loc[0, 'pool_id'])

            seasons = self.get_filter_options(LeagueFilters.Season)
            seasons['year'] = pd.to_numeric(seasons['value'])
            seasons.loc[seasons['text'].eq('Nuværende'), 'year'] = liga_schedule['match_time'].min().year

            self._season_overview = seasons
        return self._season_overview

    def get_filter_options(self, filter: LeagueFilters) -> pd.DataFrame:
        html = self._get_search_html()
        form = parse_forms(html)
        options = form.selects[filter.value]

        options_df = pd.DataFrame(options)

        return options_df

    @pa.check_types
    @append_parameters
    def get_league_ids(self, district: str, gender: str, season: int, age_group: str='Senior') -> DataFrame[Leagues]:
        search_html = self._get_search_html()
        season_overview = self._get_season_overview()
        
        league_list = list()
        for season_value in season_overview.loc[season_overview['year'].eq(season), "value"]:
            form = build_search_form(search_html, district, gender, age_group, season_value)
            result = self.client.post_search(form)
    
            league = pd.DataFrame(
                data=parse_league_links(result.html),
                columns=["league_name", "league_id"],
            )
            league_list.append(league)
        leagues = pd.concat(league_list).astype({'league_name': str, 'league_id': int})
        
        return leagues

    @pa.check_types
    @append_parameters
    def get_pool_ids(self, league_id: int) -> DataFrame[Pools]:
        overview = self.client.get(f"/tms/Turneringer-og-resultater/Pulje-Oversigt.aspx?RaekkeId={league_id}")
        pools = pd.DataFrame(
            data=parse_pools(overview.html, overview.url),
        )

        return pools

    @pa.check_types
    @append_parameters
    def scrape_pool_ranking(self, pool_id: int) -> DataFrame[Rankings]:
        column_types = {
            'rank': int,
            'team_name': str,
            'games_played': int,
            'games_won': int,
            'games_lost': int,
            'sets_won': int,
            'sets_lost': int,
            'balls_won': int,
            'balls_lost': int,
            'points': int,
        }
        column_rename = {
            'Unnamed: 0': 'rank',
            'Hold': 'team_name',
            'K': 'games_played',
            'V': 'games_won',
            'T': 'games_lost',
            'Sæt': 'sets_won',
            'Sæt.2': 'sets_lost',
            'Bolde': 'balls',
            'P': 'points',
        }
        score_html = self.client.get(f"{self.scoreboard_url}{pool_id}").html
        if "Ingen stilling fundet" in score_html:
            print(f"No scoreboard found for pool id {pool_id}")
            return Rankings.empty()

        df = pd.read_html(StringIO(score_html))[0]
        df = df.dropna(axis=0, how='all').dropna(axis=1, how='all')
        df.rename(columns=column_rename, inplace=True)
        df[['balls_won', 'balls_lost']] = df['balls'].str.split('-', expand=True)
        df['rank'] = df['rank'].fillna(-1)

        df = df.astype(dtype=column_types)
        df = df[column_types.keys()]

        return df

    @pa.check_types
    @append_parameters
    def scrape_pool_schedule(self, pool_id: int) -> DataFrame[Schedules]:
        column_rename = {
            'Kampnr.': 'match_number',
            'Hjemmehold': 'home_team',
            'Udehold': 'away_team',
        }
        schedule_html = self.client.get(f"{self.schedule_url}{pool_id}").html
        if "Ingen kampe fundet" in schedule_html:
            print(f"No schedule found for pool id {pool_id}")
            return Schedules.empty()
        
        links = parse_links(schedule_html)
        match_ids = {link.text:query_int(link.href, "KampId") for link in links if link.text.isdigit()}

        df = pd.read_html(StringIO(schedule_html))[0]
        df['match_id'] = df['Kampnr.'].astype(str).map(match_ids)
        df['note'] = df['Unnamed: 6'].astype(str)
        # Following is complicated, but will work unless there is no court.
        df[['venue', 'court']] = df['Spillested / bane'].str.split('  ', n=1, expand=True).where(
            df['Spillested / bane'].str.contains('  '),
            df['Spillested / bane'].str.rsplit(' ', n=1, expand=True)
        ).apply(lambda x: x.str.strip())

        if not ptypes.is_numeric_dtype(df['Dato']):
            df.loc[~df['Dato'].str.contains('kl.'), 'Dato'] = df.loc[~df['Dato'].str.contains('kl.'), 'Dato'] + '  kl. 00:00'
        df['match_time'] = pd.to_datetime(df['Dato'], format='%d-%m-%y  kl. %H:%M')

        if ptypes.is_numeric_dtype(df['Resultat']):
            df[['home_sets', 'away_sets']] = np.nan
        else:
            df[['home_sets', 'away_sets']] = df['Resultat'].str.split('-', expand=True)
        df[['home_sets', 'away_sets']] = df[['home_sets', 'away_sets']].astype('Int64')

        df = df.rename(columns=column_rename)[[
            'match_id',
            'match_number',
            'match_time',
            'home_team',
            'away_team',
            'venue',
            'court',
            'home_sets',
            'away_sets',
            'note',
        ]]

        return df

    @pa.check_types
    @append_parameters
    def scrape_match_details(self, match_id: int) -> DataFrame[MatchDetails]:
        match_html = self.client.get(f"{self.match_url}{match_id}").html

        html_tables = pd.read_html(StringIO(match_html))

        match_info = html_tables[0].set_index(0)[1]
        df = html_tables[1]
        df['set_number'] = df['Unnamed: 0'].str.removesuffix('. Sæt').astype(int)
        if ptypes.is_numeric_dtype(df['Score']):
            df[['home', 'away']] = np.nan
        else:
            df[['home', 'away']] = df['Score'].str.split('  ', expand=True)
        df = df.melt(id_vars='set_number', value_vars=['home', 'away'])
        df['name'] = df['variable'] + '_balls' + df['set_number'].astype(str)
        df.set_index('name')['value']
        df = df.set_index('name')['value'].to_frame().T
        df = df.apply(pd.to_numeric)

        if match_info['Kamppoint'] in ['Ikke angivet', 'KU', 'ANN']:
            df[['home_points', 'away_points']] = np.nan
        else:
            dash_idx = match_info['Kamppoint'].find('-')
            df[['home_points', 'away_points']] = list(map(int, match_info['Kamppoint'][:dash_idx+2].split('-')))
        df = df.astype('Int64').reset_index(drop=True)
        df['address'] = match_info['Spillested']
        df['referee1'] = match_info['Dommer 1'] if 'Dommer 1' in match_info.index else 'Vakant dommer'
        df['referee2'] = match_info['Dommer 2'] if 'Dommer 2' in match_info.index else 'Vakant dommer'

        return df