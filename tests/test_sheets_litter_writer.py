from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock

from automouse.config import InventoryConfig, SheetsOverlayConfig
from automouse.sheets_litter_writer import (
    SheetState,
    SheetsLitterWriteError,
    append_litter_rows_to_sheet,
    fetch_sheet_state,
)


def _sheets_overlay_config() -> SheetsOverlayConfig:
    return SheetsOverlayConfig(
        enabled=True,
        spreadsheet_id="abc123",
        worksheet="Sheet1",
        credentials_file=Path("service_account.json"),
        write_new_litters=True,
    )


def _inventory_config() -> InventoryConfig:
    # Deliberately not in the sheet's own column order, to prove the writer
    # aligns by header text rather than by position.
    return InventoryConfig(
        file=Path("inventory.csv"),
        columns={
            "mouse_id": 1, "transnetyx_order_date": 2, "plate_id": 3,
            "mother": 4, "father": 5, "dob": 6, "sex": 7,
        },
        expected_headers={
            "mouse_id": "Mouse",
            "transnetyx_order_date": "Transnetyx Order Date",
            "plate_id": "Plate ID",
            "mother": "Mother",
            "father": "Father",
        },
        identifier_roles=("mouse_id",),
    )


class AppendLitterRowsToSheetTests(unittest.TestCase):
    def test_plate_id_and_order_date_land_in_the_correct_sheet_columns(self) -> None:
        # The live sheet's own column order: Mother, Mouse, Plate ID, Transnetyx Order Date.
        sheet_state = SheetState(
            header_row=["Mother", "Mouse", "Plate ID", "Transnetyx Order Date"],
            existing_identifiers=set(),
        )
        mice = [
            {
                "mouse_id": "CM2000",
                "mother": "CM9001",
                "father": "CM9002",
                "dob": "2026-01-19",
                "sex": "Female",
                "plate_id": "T1234567",
                "transnetyx_order_date": "2026-02-15",
            }
        ]

        with mock.patch("automouse.sheets_litter_writer._build_service") as build_service:
            service = build_service.return_value
            append_litter_rows_to_sheet(
                _sheets_overlay_config(), _inventory_config(), sheet_state, mice
            )
            append_call = service.spreadsheets.return_value.values.return_value.append
            written_row = append_call.call_args.kwargs["body"]["values"][0]

        self.assertEqual(written_row, ["CM9001", "CM2000", "T1234567", "2026-02-15"])

    def test_no_mice_makes_no_api_call(self) -> None:
        sheet_state = SheetState(header_row=["Mouse"], existing_identifiers=set())
        with mock.patch("automouse.sheets_litter_writer._build_service") as build_service:
            append_litter_rows_to_sheet(
                _sheets_overlay_config(), _inventory_config(), sheet_state, []
            )
            build_service.assert_not_called()


class FetchSheetStateTests(unittest.TestCase):
    def test_reads_header_row_and_identifiers(self) -> None:
        rows = [
            ["Mother", "Mouse", "Plate ID"],
            ["CM9001", "CM2000", "T1234567"],
            ["CM9001", "CM2001", "T1234567"],
        ]
        with mock.patch("automouse.sheets_litter_writer._build_service") as build_service:
            get_call = build_service.return_value.spreadsheets.return_value.values.return_value.get
            get_call.return_value.execute.return_value = {"values": rows}
            state = fetch_sheet_state(_sheets_overlay_config(), _inventory_config())

        self.assertEqual(state.header_row, rows[0])
        self.assertEqual(state.existing_identifiers, {"CM2000", "CM2001"})

    def test_no_identifier_column_raises(self) -> None:
        rows = [["Mother", "Father"], ["CM9001", "CM9002"]]
        with mock.patch("automouse.sheets_litter_writer._build_service") as build_service:
            get_call = build_service.return_value.spreadsheets.return_value.values.return_value.get
            get_call.return_value.execute.return_value = {"values": rows}
            with self.assertRaises(SheetsLitterWriteError):
                fetch_sheet_state(_sheets_overlay_config(), _inventory_config())


if __name__ == "__main__":
    unittest.main()
