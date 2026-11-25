from __future__ import annotations

from email.message import Message
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from volleyball_resultater.client import (
    BASE_URL,
    FIELD_DISTRICT,
    FIELD_GENDER,
    FIELD_SEASON,
    FIELD_SEARCH_BUTTON,
    ResultaterClient,
    build_search_form,
)


SEARCH_FORM_HTML = """
<form>
  <input type="hidden" name="__VIEWSTATE" value="state" />
  <input type="hidden" name="__EVENTVALIDATION" value="event" />
  <select name="ctl00$ContentPlaceHolder1$Soegning$ddlDistrict_Rows">
    <option value="1">Volleyball Nordjylland</option>
    <option value="7">Volleyball Danmark</option>
  </select>
  <select name="ctl00$ContentPlaceHolder1$Soegning$ddlGender">
    <option value="0">Mand</option>
    <option value="1">Kvinde</option>
  </select>
  <select name="ctl00$ContentPlaceHolder1$Soegning$ddlDivision">
    <option value="2">Senior</option>
  </select>
  <select name="ctl00$ContentPlaceHolder1$Soegning$ddlSeason">
    <option value="2025">2025</option>
  </select>
</form>
"""


class ClientTests(unittest.TestCase):
    def test_search_form_uses_selected_source_values_and_hidden_fields(self) -> None:
        form = build_search_form(SEARCH_FORM_HTML, "Volleyball Danmark", "Mand", "Senior", "2025")

        self.assertEqual(form[FIELD_SEARCH_BUTTON], "Søg")
        self.assertEqual(form[FIELD_DISTRICT], "7")
        self.assertEqual(form[FIELD_GENDER], "0")
        self.assertEqual(form[FIELD_SEASON], "2025")
        self.assertEqual(form["__VIEWSTATE"], "state")
        self.assertEqual(form["__EVENTVALIDATION"], "event")

    def test_search_form_reports_a_missing_source_option(self) -> None:
        with self.assertRaisesRegex(ValueError, "Volleyball Syd"):
            build_search_form(SEARCH_FORM_HTML, "Volleyball Syd", "Mand", "Senior", "2025")

    def test_cached_page_is_returned_without_a_live_request(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            client = ResultaterClient(cache_dir=Path(directory), throttle_seconds=0)
            url = f"{BASE_URL}/cached-page"
            cache_path = client._cache_path("GET", url, None)
            assert cache_path is not None
            cache_path.write_text("cached page", encoding="utf-8")

            with patch.object(client.opener, "open", side_effect=AssertionError("unexpected request")):
                result = client.get("/cached-page")

        self.assertEqual(result.html, "cached page")

    def test_refresh_cache_replaces_cached_page_with_fetched_content(self) -> None:
        class FakeResponse:
            def __init__(self) -> None:
                self.headers = Message()
                self.headers.set_type("text/html")
                self.headers.set_param("charset", "utf-8")

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_value, traceback) -> None:
                return None

            def geturl(self) -> str:
                return f"{BASE_URL}/fresh-page"

            def read(self) -> bytes:
                return "frisk side".encode("utf-8")

        with tempfile.TemporaryDirectory() as directory:
            client = ResultaterClient(
                cache_dir=Path(directory),
                throttle_seconds=0,
                refresh_cache=True,
            )
            url = f"{BASE_URL}/fresh-page"
            cache_path = client._cache_path("GET", url, None)
            assert cache_path is not None
            cache_path.write_text("old page", encoding="utf-8")

            with patch.object(client.opener, "open", return_value=FakeResponse()) as open_page:
                result = client.get("/fresh-page")

            self.assertEqual(open_page.call_count, 1)
            self.assertEqual(cache_path.read_text(encoding="utf-8"), "frisk side")

        self.assertEqual(result.html, "frisk side")


if __name__ == "__main__":
    unittest.main()
