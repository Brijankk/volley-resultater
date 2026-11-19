# Volleyball Danmark Resultater

This project collects results from [resultater.volleyball.dk](https://resultater.volleyball.dk), stores them in SQLite, and exports JSON for a browser app. The app presents the available league standings, match schedules, results, and season data.

## What the app includes

- Filters for district, gender, age group, season, league, and pool.
- Official standings and a chart of each team's cumulative match points, shown by match or date.
- A home/away results matrix with set-by-set match details.
- Tournament brackets for knockout formats, with controls to focus on selected rounds.
- Schedule filters for upcoming or all matches and for a selected team's home and away games.
- Calendar export (`.ics`) for the matches currently shown by the schedule filters.
- Installable progressive web app support. The service worker caches the app and data so previously loaded content can be used offline.

The frontend is static and reads the JSON files in `data/json`; it does not call the results site directly. Scrape and export data before expecting newly collected results to appear in the app.

## Requirements and installation

Python 3.11 or newer is required. Install the project and its dependencies from the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e .
```

## Run the app locally

Serve the repository over HTTP so the browser can load the JSON files and register the service worker:

```powershell
.\.venv\Scripts\python -m http.server 8000
```

Then open <http://localhost:8000/frontend/>. Stop the server with `Ctrl+C`.

## Scrape and export results

The scraper handles senior competitions for the selected districts and seasons. Pass `--district` and `--season` at least once; repeat either option to include more than one value. District names must match the options on the source website.

For the same districts refreshed by the scheduled workflow, run:

```powershell
.\.venv\Scripts\python -m volleyball_resultater.cli `
  --district "Volleyball Danmark" `
  --district "Volleyball Nordjylland" `
  --district "Midtjysk Volleyball" `
  --season current
```

To select a season by its start year, replace `current` with a year such as `2025`. `current` selects the source site's `Nuværende` season and uses the year inferred from the first men's Volleyligaen schedule. The scraper reuses cached source HTML by default; add `--refresh-cache` to fetch fresh pages.

The scraper's default files are:

- `data/volleyball.sqlite` — normalized SQLite database.
- `data/raw-html/` — cached source pages used by the scraper.
- `data/json/leagues.json` and `data/json/<pool-id>.json` — metadata and pool data read by the frontend. Exports retain data for seasons not included in the latest scrape.

The main command options are:

| Option | Purpose |
| --- | --- |
| `--district NAME` | District to scrape; repeat to select multiple districts. |
| `--season YEAR` | Season start year or `current`; repeat to select multiple seasons. |
| `--refresh-cache` | Fetch fresh HTML instead of reusing cached pages. |
| `--no-export` | Update SQLite without regenerating frontend JSON. |
| `--db PATH` | Override the SQLite database path. |
| `--export-dir PATH` | Override the JSON export directory. |
| `--cache-dir PATH` | Override the raw HTML cache directory. |
| `--config PATH` | Use a different league filter configuration. |
| `--throttle SECONDS` | Set the pause after live requests (default: `0.25`). |

The default configuration in `src/volleyball_resultater/config.json` limits which scraped leagues are stored and exported. The GitHub Actions workflow refreshes the current season for Volleyball Danmark, Volleyball Nordjylland, and Midtjysk Volleyball, then commits changed JSON exports.

## Data and validation

Standings are kept as reported by the source website. The exporter also derives cumulative match-point data, results matrices, and tournament brackets from scraped schedules and match details. For round-robin pools, it compares the final cumulative match points with the official standings and records whether they match; this check validates points, not the full ranking order. Match details include set scores and, when available, venue and referee information.

## Project structure

```text
frontend/                   Static browser app
src/volleyball_resultater/  Scraper, storage, and JSON exporter
data/json/                  Frontend data exports
data/raw-html/              Cached pages from the source website
tests/                      Python test suite
```
