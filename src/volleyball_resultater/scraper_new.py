from io import StringIO

import pandas as pd
import pandas.api.types as ptypes
import numpy as np

from .models import StandingRow
from .client import FIELD_SEASON, ResultaterClient, build_search_form


class VolleyballScraper:
    def __init__(self, client: ResultaterClient) -> None:
        self.client = client
        self._search_html: str | None = None

        self.league_url: str = f"/tms/Turneringer-og-resultater/Pulje-Oversigt.aspx?RaekkeId="
        self.scoreboard_url: str = f"/tms/Turneringer-og-resultater/Pulje-Stilling.aspx?PuljeId="
        self.schedule_url: str = f"/tms/Turneringer-og-resultater/Pulje-Komplet-Kampprogram.aspx?PuljeId="
        self.match_url: str = f"/tms/Turneringer-og-resultater/Kamp-Information.aspx?KampId="

    def _get_search_html(self) -> str:
        if self._search_html is None:
            self._search_html = self.client.initial_search_page().html
        return self._search_html

    def scrape_pool_scoreboard(self, pool_id: int):
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

        df = pd.read_html(StringIO(score_html))[0]
        df = df.dropna(axis=0, how='all').dropna(axis=1, how='all')
        df.rename(columns=column_rename, inplace=True)
        df[['balls_won', 'balls_lost']] = df['balls'].str.split('-', expand=True)

        df = df.astype(dtype=column_types)
        df = df[column_types.keys()]

        return df

    def scrape_pool_schedule(self, pool_id: int):
        column_rename = {
            'Kampnr.': 'game_id',
            'Hjemmehold': 'team_home',
            'Udehold': 'team_away',
            'Resultat': 'result',
        }
        schedule_html = self.client.get(f"{self.schedule_url}{pool_id}").html

        df = pd.read_html(StringIO(schedule_html))[0]

        return df

    def scrape_match_results(self, match_id: int):
        columns = [
            'set_number',
            'home_points',
            'away_points',
            'home_set_won',
            'away_set_won',
        ]
        match_html = self.client.get(f"{self.match_url}{match_id}").html

        df = pd.read_html(StringIO(match_html))[1]

        df['set_number'] = df['Unnamed: 0'].str.removesuffix('. Sæt').astype(int)
        if ptypes.is_numeric_dtype(df['Score']):
            df[['home_points', 'away_points', 'home_set_won', 'away_set_won']] = np.nan
        else:
            df[['home_points', 'away_points']] = df['Score'].str.split('  ', expand=True)
            df[['home_set_won', 'away_set_won']] = df['Resultat'].str.split('  ', expand=True)
        df[columns] = df[columns].astype('Int64')
        df = df[columns]

        return df