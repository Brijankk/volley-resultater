from __future__ import annotations

import unittest

from volleyball_resultater.html_tools import clean_text


class EncodingTests(unittest.TestCase):
    def test_repairs_danish_mojibake(self) -> None:
        self.assertEqual(clean_text("AabyhÃ¸j IF"), "Aabyhøj IF")
        self.assertEqual(clean_text("Ã˜st"), "Øst")
        self.assertEqual(clean_text("RÃ¦kke 1"), "Række 1")

    def test_keeps_valid_danish_text(self) -> None:
        self.assertEqual(clean_text("Aabyhøj IF"), "Aabyhøj IF")
        self.assertEqual(clean_text("Øst"), "Øst")


if __name__ == "__main__":
    unittest.main()
