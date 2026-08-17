# Danish Volleyball Results Scraper

This project scrapes selected senior Danish volleyball league data from
`resultater.volleyball.dk` and prepares it for a future mobile-friendly app.

The first milestone is data only:

- discover available seasons
- scrape men/women senior regular-season leagues under Volleyball Danmark
- support Volleyligaen plus numbered divisions
- store official source standings in SQLite
- store match schedules and set-by-set match details
- export JSON for standings, schedules, cumulative points, and home/away matrices

The scraper uses only Python's standard library.

## Run

From this folder:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e .
.\.venv\Scripts\scrape-volleyball --season 2025
```

If `scrape-volleyball` is not on PATH, run:

```powershell
.\.venv\Scripts\python -m volleyball_resultater.cli --season 2025
```

By default, output is written to:

- `data/volleyball.sqlite`
- `data/json`
- `data/raw-html`

Use `--all-seasons` to scrape every season discovered from the search page. That can take a while because match detail pages are fetched for played matches.

## Data Rules

Official standings from the website are stored as source truth.

Derived standings and running-point charts use the 2025 Danmarksturneringen rule profiles from §13:

- ranking: match points, set difference, ball difference, then head-to-head
- Volleyligaen: 3-0 and 3-1 give 3/0 points; 3-2 gives 2/1 points
- 1. and 2. division: 3-0 and 3-1 give 3/0 points; 3-2 gives 3/1 points

Head-to-head is represented as the final unresolved tie-breaker; official source standings remain stored as source truth.
Historical rule profiles are represented in code so older seasons can be handled later without changing the database shape.
