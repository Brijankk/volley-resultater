from __future__ import annotations

import unittest
from unittest.mock import patch

import pandas as pd

from volleyball_resultater.client import FetchResult
from volleyball_resultater.scraper import VolleyballScraper


class FakeClient:
    def __init__(self, html: str = "") -> None:
        self.html = html

    def get(self, path: str) -> FetchResult:
        return FetchResult(url=f"https://example.test/{path.lstrip('/')}", html=self.html)


class ScraperTests(unittest.TestCase):
    def test_schedule_maps_source_match_links_and_parses_scores_and_venue(self) -> None:
        html = (
            '<a href="/Kamp-Information.aspx?KampId=70726">101</a>'
        )
        client = FakeClient(html)
        scraper = VolleyballScraper(client)  # type: ignore[arg-type]
        table = pd.DataFrame({
            "Kampnr.": [101],
            "Dato": ["04-10-25  kl. 14:30"],
            "Hjemmehold": ["Hold A"],
            "Udehold": ["Hold B"],
            "Spillested / bane": ["Arena  Court 1"],
            "Resultat": ["3 - 2"],
            "Unnamed: 6": ["UHT"],
        })

        with patch("volleyball_resultater.scraper.pd.read_html", return_value=[table]):
            schedule = scraper.scrape_pool_schedule(42)

        self.assertEqual(len(schedule), 1)
        match = schedule.iloc[0]
        self.assertEqual(match["pool_id"], 42)
        self.assertEqual(match["match_id"], 70726)
        self.assertEqual(match["match_number"], 101)
        self.assertEqual(match["home_team"], "Hold A")
        self.assertEqual(match["away_team"], "Hold B")
        self.assertEqual((match["venue"], match["court"]), ("Arena", "Court 1"))
        self.assertEqual((match["home_sets"], match["away_sets"]), (3, 2))
        self.assertEqual(match["match_time"], pd.Timestamp("2025-10-04 14:30"))
        self.assertEqual(match["note"], "UHT")

    def test_standings_split_ball_totals_and_keep_official_points(self) -> None:
        client = FakeClient("<table></table>")
        scraper = VolleyballScraper(client)  # type: ignore[arg-type]
        table = pd.DataFrame({
            "Unnamed: 0": [1],
            "Hold": ["Hold A"],
            "K": [4],
            "V": [3],
            "T": [1],
            "Sæt": [11],
            "Sæt.2": [6],
            "Bolde": ["390-345"],
            "P": [9],
        })

        with patch("volleyball_resultater.scraper.pd.read_html", return_value=[table]):
            standings = scraper.scrape_pool_ranking(42)

        row = standings.iloc[0]
        self.assertEqual(row["pool_id"], 42)
        self.assertEqual(row["team_name"], "Hold A")
        self.assertEqual((row["balls_won"], row["balls_lost"]), (390, 345))
        self.assertEqual(row["points"], 9)

    def test_match_detail_captures_set_scores_points_and_vacant_referee(self) -> None:
        client = FakeClient("match details")
        scraper = VolleyballScraper(client)  # type: ignore[arg-type]
        match_info = pd.DataFrame({
            0: ["Kamppoint", "Spillested", "Dommer 1", "Dommer 2"],
            1: ["2-3", "Arena, Court 1", "Vakant dommer", "Jane Referee"],
        })
        sets = pd.DataFrame({
            "Unnamed: 0": [f"{number}. Sæt" for number in range(1, 6)],
            "Score": ["25  20", "22  25", "25  21", "20  25", "12  15"],
        })

        with patch("volleyball_resultater.scraper.pd.read_html", return_value=[match_info, sets]):
            details = scraper.scrape_match_details(70726)

        row = details.iloc[0]
        self.assertEqual(row["match_id"], 70726)
        self.assertEqual((row["home_points"], row["away_points"]), (2, 3))
        self.assertEqual((row["home_balls5"], row["away_balls5"]), (12, 15))
        self.assertEqual(row["address"], "Arena, Court 1")
        self.assertTrue(pd.isna(row["referee1"]))
        self.assertEqual(row["referee2"], "Jane Referee")


if __name__ == "__main__":
    unittest.main()
