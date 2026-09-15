from pathlib import Path
from volleyball_resultater.client import ResultaterClient
from volleyball_resultater.scraper import VolleyballScraper
from volleyball_resultater.scraper_new import VolleyballScraper as VolleyballScraper2
from volleyball_resultater.paths import DEFAULT_CACHE_DIR

client = ResultaterClient(cache_dir=DEFAULT_CACHE_DIR, throttle_seconds=0)
scraper = VolleyballScraper(client)
scraper2 = VolleyballScraper2(client)

# scraper2.scrape_pool_schedule(4124)
m1 = scraper2.scrape_match_results(72486)
m2 = scraper2.scrape_match_results(72482)
m3 = scraper2.scrape_match_results(75954)

seasons = scraper.seasons()
season = next(s for s in seasons if s.id == "2025")

leagues = scraper.leagues_for(season, "Mand")
league = leagues[-1]

pool_data = scraper.scrape_league(league)