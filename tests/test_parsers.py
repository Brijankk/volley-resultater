from __future__ import annotations

import unittest

from volleyball_resultater.parsers import parse_league_links, parse_pools, query_int


class ParserTests(unittest.TestCase):
    def test_query_int_reads_the_requested_value_and_handles_invalid_input(self) -> None:
        self.assertEqual(query_int("/schedule.aspx?PuljeId=3923", "PuljeId"), 3923)
        self.assertIsNone(query_int("/schedule.aspx?PuljeId=not-a-number", "PuljeId"))
        self.assertIsNone(query_int("/schedule.aspx", "PuljeId"))

    def test_league_links_extract_names_and_ids(self) -> None:
        html = """
        <a href="/Pulje-Oversigt.aspx?RaekkeId=2248">Volleyligaen Herrer</a>
        <a href="/Pulje-Oversigt.aspx?RaekkeId=2250">1. Division Herrer</a>
        <a href="/Pulje-Oversigt.aspx?RaekkeId=invalid">Invalid row</a>
        <a href="/no-id.aspx">Link without an id</a>
        """

        self.assertEqual(
            parse_league_links(html),
            [("Volleyligaen Herrer", 2248), ("1. Division Herrer", 2250)],
        )

    def test_pools_can_be_found_after_a_redirect_or_in_an_overview(self) -> None:
        redirected = parse_pools(
            "",
            "https://resultater.volleyball.dk/Pulje-Stilling.aspx?PuljeId=3923",
        )
        overview = parse_pools(
            '<h1>Oversigt</h1><a href="/Pulje-Stilling.aspx?PuljeId=4122">Øst</a>',
            "https://resultater.volleyball.dk/Pulje-Oversigt.aspx?RaekkeId=2372",
        )

        self.assertEqual(redirected, [{"pool_name": "Række 1", "pool_id": 3923}])
        self.assertEqual(overview, [{"pool_name": "Øst", "pool_id": 4122}])

    def test_pool_parser_ignores_team_links_on_a_standings_page(self) -> None:
        html = """
        <h1>Oversigt</h1>
        <a href="/Pulje-Stilling.aspx?PuljeId=3923">Stilling</a>
        <a href="/Hold-Information.aspx?PuljeId=3923&amp;HoldId=27920">Middelfart VK</a>
        """

        pools = parse_pools(
            html,
            "https://resultater.volleyball.dk/Pulje-Oversigt.aspx?RaekkeId=2248",
        )

        self.assertEqual(pools, [{"pool_name": "Række 1", "pool_id": 3923}])


if __name__ == "__main__":
    unittest.main()
