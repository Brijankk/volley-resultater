import pandas as pd
import numpy as np

def calculate_running_rankings(matches: pd.DataFrame) -> pd.DataFrame:
    df = matches.melt(
        id_vars=['match_time', 'home_team', 'away_team'],
        value_vars=['home_points', 'away_points'],
        value_name='points'
    )
    df['team'] = df['home_team'].where(df['variable'].eq('home_points'), df['away_team'])

    df0 = pd.DataFrame(
        data={
            'match_time': df['match_time'].min().normalize(),
            'team': df['team'].unique(), 
            'points': 0,
            }
    )
    df = pd.concat([df0, df], axis=0).sort_values('match_time')[['match_time', 'team', 'points']]
    df['cum_points'] = df.groupby('team')['points'].cumsum()
    df['game_number'] = df.groupby('team')['points'].cumcount()

    return df

def result_matrix(matches: pd.DataFrame) -> pd.DataFrame:
    df = matches.copy()

    teams = df[['home_team', 'away_team']].melt()['value'].drop_duplicates()
    idx = pd.MultiIndex.from_product([teams, teams], names=['home_team', 'away_team'])

    df['set_score'] = df[['home_sets', 'away_sets']].astype(str).fillna('').apply('-'.join, axis=1)
    
    matrix = df.dropna(subset=['home_sets', 'away_sets']).groupby(['home_team', 'away_team'])['set_score'].apply(', '.join)
    matrix = matrix.reindex(idx, fill_value='').sort_index()

    # table = df.pivot_table(
    #     index='home_team',
    #     columns='away_team',
    #     values='set_score',
    #     aggfunc=list,
    # ).fillna('').map(', '.join)

    return matrix

def order_tournament(tournament_names: pd.Series[str]) -> pd.Series[int]:
    df = tournament_names.to_frame('name')

    df['is_final'] = df['name'].str.contains('finale', case=False)
    df['final_prefix'] = df['name'].str.lower().str.extract(
        pat=r"(?:^|\s)([^\s-]+)-?finaler?\b"
    ).fillna('1/1').replace({'semi': '1/2', 'kvart': '1/4'})
    df['runde_prefix'] = df['name'].str.lower().str.extract(r"\b(\d+)\.\s*runde\b")
    
    df = df.sort_values(by=['is_final', 'final_prefix', 'runde_prefix'], ascending=[False, True, False])
    df['round'] = range(df.shape[0])
    df.loc[df['name'].str.contains('bronze', case=False), 'round'] = 0

    df['round'] = df['round'].max() - df['round']

    return df['round']

def deduct_tournament(schedule):
    df = schedule.copy()
    df[['home_team', 'away_team']] = df[['home_team', 'away_team']].apply(sorted, axis=1).to_list()

    bouts = df.groupby(['round', 'name_league', 'home_team', 'away_team'], as_index=False)['match_number'].apply(list)
    bouts = bouts.reset_index(names=['bout_id'])

    mapping = bouts.explode('match_number')
    mapping['match_number'] = mapping['match_number'].astype(str)
    mapping['round'] += 1
    mapping = mapping.melt(
        id_vars=['bout_id', 'round'],
        value_vars=['home_team', 'away_team', 'match_number'],
        value_name='key'
    ).drop_duplicates(['round', 'key'])
    mapping = mapping.set_index(['round', 'key'])['bout_id']

    bouts['key1'] = bouts['home_team'].str.rsplit('#').apply(lambda x: x[-1])
    bouts['key2'] = bouts['away_team'].str.rsplit('#').apply(lambda x: x[-1])

    bouts['leg1'] = bouts[['round', 'key1']].apply(tuple, axis=1).map(mapping)
    bouts['leg2'] = bouts[['round', 'key2']].apply(tuple, axis=1).map(mapping)
    bouts.loc[bouts['name_league'].str.contains('bronze', case=False), ['leg1', 'leg2']] = np.nan
    bouts[['leg1', 'leg2']] = bouts[['leg1', 'leg2']].astype('Int64')
    
    bouts.drop(columns=['key1', 'key2'], inplace=True)

    return bouts

def deduct_tournament2(schedule):
    df = schedule.copy()


    df[['home_team', 'away_team']] = df[['home_team', 'away_team']].apply(sorted, axis=1).to_list()
    # df = df.groupby(['round', 'name_league', 'home_team', 'away_team'], as_index=False)['match_number'].max()
    
    runder = list(df['round'].drop_duplicates())

    bracket = []
    for round in sorted(runder, reverse=True)[:-1]:
        df1 = df.loc[df['round'].eq(round)]
        df0 = df.loc[df['round'].eq(round - 1)]
        df0 = df0.melt(
            id_vars='match_number',
            value_vars=['home_team', 'away_team'],
            value_name='team'
        ).set_index('team')['match_number'].astype(str)

        #Leg1 (hjemmehold)
        df1['leg1'] = df1['home_team'].str.rsplit('#').apply(lambda x: x[-1])
        df1['leg1'] = df1['leg1'].replace(df0)
        df1.loc[df1['leg1'].str.isdigit().eq(False), 'leg1'] = 'NaN'

        #Leg2 (udehold)
        df1['leg2'] = df1['away_team'].str.rsplit('#').apply(lambda x: x[-1])
        df1['leg2'] = df1['leg2'].replace(df0)
        df1.loc[df1['leg2'].str.isdigit().eq(False), 'leg2'] = 'NaN'

        bracket.append(df1)
    bracket.append(
        df.loc[df['round'].eq(0)].assign(
            leg1='NaN',
            leg2='NaN',
        )
    )
    bracket = pd.concat(bracket)
    bracket.loc[bracket['name_league'].str.contains('bronze', case=False), ['leg1', 'leg2']] = 'NaN'

    return bracket
