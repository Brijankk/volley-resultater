import pandas as pd
import numpy as np

def calculate_running_points(matches: pd.DataFrame) -> pd.DataFrame:
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
    df['cumulative_points'] = df.groupby('team')['points'].cumsum()
    df['game_number'] = df.groupby('team')['points'].cumcount()
    df.loc[df['game_number'].eq(0), 'match_time'] = pd.NaT

    return df

def set_results(matches: pd.DataFrame) -> pd.DataFrame:
    columns = ["match_id", "set_number", "home_points", "away_points", "home_set_won", "away_set_won"]
    if matches.empty:
        return pd.DataFrame(columns=columns)
    sets = pd.wide_to_long(
        df=matches[matches.columns[matches.columns.str.contains('match_id|balls')]],
        stubnames=["home_balls", "away_balls"],
        i="match_id",
        j="set_number",
    ).reset_index().rename(columns={"home_balls": "home_points", "away_balls": "away_points"})
    sets = sets.dropna(subset=["home_points", "away_points"], how="all")
    known = sets[["home_points", "away_points"]].notna().all(axis=1)
    sets["home_set_won"] = sets["home_points"].gt(sets["away_points"]).astype("Int64").where(known)
    sets["away_set_won"] = sets["away_points"].gt(sets["home_points"]).astype("Int64").where(known)

    return sets[columns].sort_values(["match_id", "set_number"])

def calculate_statistics(matches: pd.DataFrame) -> pd.DataFrame:
    score_columns = matches.columns[matches.columns.str.contains(r"_(?:sets|points|balls\d+)$")]
    played = matches.loc[
        matches[["home_sets", "away_sets"]].notna().all(axis=1) &
        matches["home_sets"].ne(matches["away_sets"]),
        score_columns.union(['home_team', 'away_team', 'match_id'])
    ].copy()

    pd.wide_to_long(played[score_columns.union(['match_id'])], stubnames=['home', 'away'], i='match_id', j='test')
    df = played.melt(
        id_vars=['home_team', 'away_team'],
        value_vars=['home_points', 'away_points', 'home_sets', 'away_sets'],
        # value_name='points'
    )
    df['team'] = df['home_team'].where(df['variable'].str.startswith('home'), df['away_team'])
    df[['temp', 'var']] = df['variable'].str.split('_', expand=True)
    
    return 

def derive_pool_old(pool_id: int, rankings: pd.DataFrame, matches: pd.DataFrame,
                sets: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    #Old function. Optimize in calculate_statistics and delete
    
    STAT_FIELDS = [
        "games_played", "games_won", "games_lost", "sets_won", "sets_lost",
        "balls_won", "balls_lost", "points",
    ]
    teams = pd.Index(sorted(pd.concat([rankings["team_name"], matches["home_team"],
                                      matches["away_team"]]).dropna().unique()), name="team_name")
    played = matches.loc[matches[["home_sets", "away_sets"]].notna().all(axis=1)
                         & matches["home_sets"].ne(matches["away_sets"])].copy()
    played["match_order"] = range(len(played))
    balls = sets.dropna(subset=["home_points", "away_points"]).groupby("match_id")[["home_points", "away_points"]].sum()
    balls = balls.reindex(played["match_id"], fill_value=0)
    # Retain the administrative 25-0 convention when a forfeit has no set details.
    forfeits = played.loc[played["note"].str.contains("HHT|UHT", case=False)
                         & ~played["match_id"].isin(sets["match_id"])]
    home_won = forfeits["home_sets"].gt(forfeits["away_sets"])
    awarded_balls = forfeits[["home_sets", "away_sets"]].max(axis=1) * 25
    balls.loc[forfeits["match_id"], "home_points"] = awarded_balls.where(home_won, 0).to_numpy()
    balls.loc[forfeits["match_id"], "away_points"] = awarded_balls.where(~home_won, 0).to_numpy()
    sides = []
    for side_number, (side, opponent) in enumerate((("home", "away"), ("away", "home"))):
        team_matches = played[["match_id", "match_time", "match_order", f"{side}_team", f"{side}_points",
                               f"{side}_sets", f"{opponent}_sets"]].rename(columns={
            f"{side}_team": "team_name", f"{side}_points": "points",
            f"{side}_sets": "sets_won", f"{opponent}_sets": "sets_lost",
        })
        sides.append(team_matches.assign(
            side_order=side_number, games_played=1,
            games_won=team_matches["sets_won"].gt(team_matches["sets_lost"]).astype(int),
            games_lost=team_matches["sets_won"].lt(team_matches["sets_lost"]).astype(int),
            balls_won=team_matches["match_id"].map(balls[f"{side}_points"]),
            balls_lost=team_matches["match_id"].map(balls[f"{opponent}_points"]),
        ))
    team_matches = pd.concat(sides, ignore_index=True).sort_values(["match_order", "side_order"])
    team_matches[STAT_FIELDS] = team_matches[STAT_FIELDS].astype("Int64")
    grouped = team_matches.groupby("team_name", sort=False)
    stats = grouped[STAT_FIELDS].sum().reindex(teams, fill_value=0)
    # Missing scraped points make the total unknown; do not infer an award.
    incomplete = grouped["points"].count().lt(grouped.size())
    stats.loc[incomplete.index[incomplete], "points"] = pd.NA
    computed = stats.reset_index().assign(
        set_difference=lambda df: df["sets_won"] - df["sets_lost"],
        ball_difference=lambda df: df["balls_won"] - df["balls_lost"],
        sort_points=lambda df: df["points"].fillna(0),
    ).sort_values(["sort_points", "set_difference", "ball_difference", "team_name"],
                  ascending=[False, False, False, True]).drop(columns=["sort_points", "set_difference", "ball_difference"])
    computed = computed.assign(pool_id=pool_id, rank=range(1, len(computed) + 1))
    team_matches["game_number"] = grouped.cumcount() + 1
    team_matches["cumulative_points"] = grouped["points"].cumsum(skipna=False)
    baseline = pd.DataFrame({"team": teams, "date": pd.NaT, "game_number": 0,
                             "points": 0, "cumulative_points": 0, "match_id": pd.NA})
    events = pd.concat([baseline, team_matches.rename(columns={
        "team_name": "team", "match_time": "date",
    })[baseline.columns]], ignore_index=True)
    played["score"] = played["home_sets"].astype(str) + "-" + played["away_sets"].astype(str)
    matrix = played.groupby(["home_team", "away_team"])["score"].agg(", ".join).unstack("away_team")
    matrix = matrix.reindex(index=teams, columns=teams)
    diagonal = teams.to_numpy()[:, None] == teams.to_numpy()[None, :]
    matrix = matrix.mask(diagonal, "")
    return computed, events, matrix

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

    bouts = df.groupby(['round', 'league_name', 'home_team', 'away_team'], as_index=False)['match_number'].apply(list)
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
    bouts.loc[bouts['league_name'].str.contains('bronze', case=False), ['leg1', 'leg2']] = np.nan
    bouts[['leg1', 'leg2']] = bouts[['leg1', 'leg2']].astype('Int64')
    
    bouts.drop(columns=['key1', 'key2'], inplace=True)

    return bouts

def pokal_filter(df: pd.DataFrame) -> pd.DataFrame:
    df = df.loc[
        (
            df['league_name'].str.contains('Pokal', case=False) |
            df['league_name'].str.contains('LP')
        ) &
        ~df['league_name'].str.contains('Seed') &
        ~df['league_name'].str.contains('Kreds'),
    ].copy()

    return df

def slutspil_filter(df: pd.DataFrame) -> pd.DataFrame:
    df = df.loc[
        df['league_name'].str.contains('Volleyligaen', case=False) &
        (
            df['league_name'].str.contains('finale', case=False) |
            df['league_name'].str.contains('bronze', case=False)
        ),
    ].copy()

    return df