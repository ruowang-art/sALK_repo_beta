from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

from openpyxl import Workbook

from xolpotsxol.cage_card_reader import read_cage_card_workbook
from xolpotsxol.exceptions import CageCardFormatError
from xolpotsxol.models import EXPECTED_HEADERS


def _build_workbook(path: Path, rows: list[list]) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Sheet1"
    sheet.append(EXPECTED_HEADERS)
    for row in rows:
        sheet.append(row)
    workbook.save(path)


class ReadCageCardWorkbookTests(unittest.TestCase):
    def test_reads_single_exact_dob_and_range_dob(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            path = Path(directory_name) / "cards.xlsx"
            _build_workbook(
                path,
                [
                    [
                        "", "Kras/Lkb1", 1, 1, "Male", "02/16/26", "01/19/26",
                        "CM0001", "", "", "", "", "+/+", "", "", "", "",
                        "", "", "", "", "", "",
                    ],
                    [
                        "", "Kras/Lkb1", 2, 2, "Female", "02/16/26 - 02/18/26",
                        "01/19/26 - 01/21/26", "CM0002", "CM0003", "", "", "",
                        "K/+", "K/+", "", "", "", "M1", "+/+", "F1", "+/+", "N", "",
                    ],
                ],
            )
            mice, warnings = read_cage_card_workbook(path, "cards.xlsx")

        self.assertEqual(warnings, [])
        self.assertEqual(len(mice), 3)
        first = mice[0]
        self.assertEqual(first.mouse_id, "CM0001")
        self.assertEqual(first.dob_min, date(2026, 1, 19))
        self.assertEqual(first.dob_max, date(2026, 1, 19))
        second = mice[1]
        self.assertEqual(second.dob_min, date(2026, 1, 19))
        self.assertEqual(second.dob_max, date(2026, 1, 21))
        self.assertEqual(second.dam, "M1")
        self.assertEqual(second.sire, "F1")

    def test_row_with_no_mice_is_skipped_with_a_warning(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            path = Path(directory_name) / "cards.xlsx"
            _build_workbook(
                path,
                [
                    [
                        "", "Kras/Lkb1", 0, 0, "Male", "", "",
                        "", "", "", "", "", "", "", "", "", "",
                        "", "", "", "", "", "",
                    ],
                ],
            )
            mice, warnings = read_cage_card_workbook(path, "cards.xlsx")

        self.assertEqual(mice, [])
        self.assertEqual(len(warnings), 1)
        self.assertIn("no mice found", warnings[0])

    def test_wrong_header_raises_clear_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            path = Path(directory_name) / "not_a_cage_card.xlsx"
            workbook = Workbook()
            sheet = workbook.active
            sheet.append(["Not", "The", "Right", "Headers"])
            workbook.save(path)

            with self.assertRaisesRegex(CageCardFormatError, "does not look like"):
                read_cage_card_workbook(path, "not_a_cage_card.xlsx")

    def test_missing_sex_or_strain_is_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            path = Path(directory_name) / "cards.xlsx"
            _build_workbook(
                path,
                [
                    [
                        "", "", 1, 1, "", "", "",
                        "CM0001", "", "", "", "", "+/+", "", "", "", "",
                        "", "", "", "", "", "",
                    ],
                ],
            )
            mice, warnings = read_cage_card_workbook(path, "cards.xlsx")

        self.assertEqual(len(mice), 1)
        self.assertTrue(any("missing sex/strain" in warning for warning in warnings))


if __name__ == "__main__":
    unittest.main()
