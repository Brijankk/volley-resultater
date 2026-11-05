PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS leagues (
    league_id INTEGER PRIMARY KEY,
    league_name TEXT NOT NULL,
    district TEXT NOT NULL,
    gender TEXT NOT NULL,
    age_group TEXT NOT NULL,
    season INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS pools (
    pool_id INTEGER PRIMARY KEY,
    pool_name TEXT NOT NULL,
    league_id INTEGER NOT NULL REFERENCES leagues(league_id)
);

CREATE TABLE IF NOT EXISTS rankings (
    pool_id INTEGER NOT NULL REFERENCES pools(pool_id),
    rank INTEGER NOT NULL,
    team_name TEXT NOT NULL,
    games_played INTEGER NOT NULL,
    games_won INTEGER NOT NULL,
    games_lost INTEGER NOT NULL,
    sets_won INTEGER NOT NULL,
    sets_lost INTEGER NOT NULL,
    balls_won INTEGER NOT NULL,
    balls_lost INTEGER NOT NULL,
    points INTEGER NOT NULL,
    PRIMARY KEY (pool_id, team_name)
);

CREATE TABLE IF NOT EXISTS matches (
    pool_id INTEGER NOT NULL REFERENCES pools(pool_id),
    match_id INTEGER PRIMARY KEY,
    match_number INTEGER,
    match_time TEXT,
    home_team TEXT NOT NULL,
    away_team TEXT NOT NULL,
    venue TEXT,
    court TEXT,
    address TEXT,
    referee1 TEXT,
    referee2 TEXT,
    home_sets INTEGER,
    away_sets INTEGER,
    home_points INTEGER,
    away_points INTEGER,
    home_balls1 INTEGER,
    away_balls1 INTEGER,
    home_balls2 INTEGER,
    away_balls2 INTEGER,
    home_balls3 INTEGER,
    away_balls3 INTEGER,
    home_balls4 INTEGER,
    away_balls4 INTEGER,
    home_balls5 INTEGER,
    away_balls5 INTEGER,
    note TEXT
);