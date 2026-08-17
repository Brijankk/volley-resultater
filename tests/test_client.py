from __future__ import annotations

import unittest

from volleyball_resultater.client import FIELD_SEARCH_BUTTON, build_search_form


SEARCH_FORM_HTML = """
<form>
  <input type="hidden" name="__VIEWSTATE" value="state" />
  <input type="hidden" name="__EVENTVALIDATION" value="event" />
  <select name="ctl00$ContentPlaceHolder1$Soegning$ddlDistrict_Rows">
    <option value="1">Volleyball Danmark</option>
  </select>
  <select name="ctl00$ContentPlaceHolder1$Soegning$ddlGender">
    <option value="1">Mand</option>
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
    def test_search_button_text_is_utf8(self) -> None:
        form = build_search_form(SEARCH_FORM_HTML, "Volleyball Danmark", "Mand", "Senior", "2025")
        self.assertEqual(form[FIELD_SEARCH_BUTTON], "Søg")


if __name__ == "__main__":
    unittest.main()
