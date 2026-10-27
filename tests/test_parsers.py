from __future__ import annotations

import unittest

from volleyball_resultater.parsers import (
    parse_league_links,
    parse_pools,
)


SEARCH_HTML = """
<html><body>
<a href="/tms/Turneringer-og-resultater/Pulje-Oversigt.aspx?RaekkeId=2248">Volleyligaen Herrer</a>
<a href="/tms/Turneringer-og-resultater/Pulje-Oversigt.aspx?RaekkeId=2331">Volleyligaen Herrer DM Finaler</a>
<a href="/tms/Turneringer-og-resultater/Pulje-Oversigt.aspx?RaekkeId=2250">1. Division Herrer</a>
</body></html>
"""

STANDINGS_HTML = """
<table>
  <tr><th></th><th>Hold</th><th>K</th><th>V</th><th>T</th><th>Sæt</th><th></th><th></th><th>Bolde</th><th>P</th><th>V</th></tr>
  <tr><td>1</td><td>Middelfart VK</td><td>16</td><td>16</td><td>0</td><td>48</td><td>-</td><td>14</td><td>1458-1238</td><td>44</td><td>16</td></tr>
  <tr><td>2</td><td>ASV Elite</td><td>16</td><td>11</td><td>5</td><td>41</td><td>-</td><td>26</td><td>1545-1495</td><td>35</td><td>11</td></tr>
</table>
"""

SCHEDULE_HTML = """
<table>
  <tr><th>Kampnr.</th><th>Dato</th><th>Hjemmehold</th><th>Udehold</th><th>Spillested / bane</th><th>Resultat</th></tr>
  <tr>
    <td><a href="/tms/Turneringer-og-resultater/Kamp-Information.aspx?KampId=70726">144398</a></td>
    <td>03-10-25 kl.&nbsp;19:30</td>
    <td>VK Vestsjælland</td>
    <td>Amager Volley</td>
    <td>Korsørhallen 1</td>
    <td>3&nbsp;-&nbsp;1</td>
  </tr>
  <tr>
    <td><a href="/tms/Turneringer-og-resultater/Kamp-Information.aspx?KampId=1">1</a></td>
    <td>04-10-25 kl.&nbsp;14:30</td>
    <td>A</td><td>B</td><td>Hal</td><td></td>
  </tr>
  <tr>
    <td><a href="/tms/Turneringer-og-resultater/Kamp-Information.aspx?KampId=2">2</a></td>
    <td>05-10-25 kl.&nbsp;14:30</td>
    <td>C</td><td>D</td><td>Hal</td><td>3&nbsp;-&nbsp;0</td><td>UHT</td>
  </tr>
  <tr>
    <td><a href="/tms/Turneringer-og-resultater/Kamp-Information.aspx?KampId=3">3</a></td>
    <td>06-10-25 kl.&nbsp;14:30</td>
    <td>E</td><td>F</td><td>Hal</td><td>0&nbsp;-&nbsp;3</td><td>HHT</td>
  </tr>
  <tr>
    <td><a href="/tms/Turneringer-og-resultater/Kamp-Information.aspx?KampId=4">4</a></td>
    <td>07-10-25</td>
    <td>G</td><td>H</td><td>Hal</td><td></td>
  </tr>
  <tr>
    <td><a href="/tms/Turneringer-og-resultater/Kamp-Information.aspx?KampId=5">5</a></td>
    <td>08-10-25<br />kl.&nbsp;10:00</td>
    <td>I</td><td>J</td><td>Hal</td><td></td>
  </tr>
</table>
"""

MATCH_HTML = """
<table>
  <tr><th>Hold/spiller</th><th></th><th>Score</th><th></th><th>Resultat</th><th></th></tr>
  <tr><td>1. Sæt</td><td>VK Vestsjælland</td><td>Amager Volley</td><td>25</td><td>21</td><td>1</td><td>0</td></tr>
  <tr><td>2. Sæt</td><td>VK Vestsjælland</td><td>Amager Volley</td><td>25</td><td>22</td><td>1</td><td>0</td></tr>
  <tr><td>5. Sæt</td><td>VK Vestsjælland</td><td>Amager Volley</td><td></td><td></td><td></td><td></td></tr>
</table>
"""


class ParserTests(unittest.TestCase):
    def test_league_links(self) -> None:
        links = parse_league_links(SEARCH_HTML)
        self.assertEqual(links[0], ("Volleyligaen Herrer", 2248))
        self.assertIn(("1. Division Herrer", 2250), links)

    def test_pools_from_redirect_or_overview_links(self) -> None:
        redirected = parse_pools("", "https://resultater.volleyball.dk/tms/Turneringer-og-resultater/Pulje-Stilling.aspx?PuljeId=3923")
        self.assertEqual(redirected[0]["pool_id"], 3923)
        overview = '<a href="/tms/Turneringer-og-resultater/Pulje-Stilling.aspx?PuljeId=4122">Øst</a>'
        pools = parse_pools(overview, "https://resultater.volleyball.dk/tms/Turneringer-og-resultater/Pulje-Oversigt.aspx?RaekkeId=2372")
        self.assertEqual((pools[0]["pool_name"], pools[0]["pool_id"]), ("Øst", 4122))

    def test_pools_ignore_team_links_on_cached_redirect_page(self) -> None:
        standing_page_links = """
        <a href="/tms/Turneringer-og-resultater/Pulje-Stilling.aspx?PuljeId=3923">Stilling</a>
        <a href="/tms/Turneringer-og-resultater/Hold-Information.aspx?PuljeId=3923&HoldId=27920">Middelfart VK</a>
        """
        pools = parse_pools(
            standing_page_links,
            "https://resultater.volleyball.dk/tms/Turneringer-og-resultater/Pulje-Oversigt.aspx?RaekkeId=2248",
        )
        self.assertEqual(len(pools), 1)
        self.assertEqual((pools[0]["pool_name"], pools[0]["pool_id"]), ("Række 1", 3923))


if __name__ == "__main__":
    unittest.main()
