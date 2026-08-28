from __future__ import annotations

import logging
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

from automouse.config import InventoryConfig, SheetsOverlayConfig
from automouse.inventory_manager import InventoryTable
from automouse.sheets_overlay import (
    SheetsOverlayError,
    apply_dob_wean_overlay,
    fetch_dob_wean_overlay,
)

_LOGGER = logging.getLogger("test_sheets_overlay")
_LOGGER.addHandler(logging.NullHandler())


def _inventory_config() -> InventoryConfig:
    return InventoryConfig(
        file=Path("inventory.csv"),
        columns={"mouse_id": 1, "id": 2, "sample": 3, "dob": 4, "wean_date": 5, "genotype": 6},
        expected_headers={
            "mouse_id": "Mouse",
            "id": "ID",
            "sample": "Sample",
            "dob": "DOB",
            "wean_date": "Wean_By",
        },
        identifier_roles=("mouse_id", "id", "sample"),
    )


class ApplyDobWeanOverlayTests(unittest.TestCase):
    def test_fills_blank_cells_only(self) -> None:
        config = _inventory_config()
        inventory = InventoryTable(
            source_path=Path("inventory.csv"),
            headers=["Mouse", "ID", "Sample", "DOB", "Wean_By", "Genotype"],
            rows=[
                ["CM0001", "", "S1", "", "", "+/+"],
                ["CM0002", "", "S2", "01/01/26", "", "+/+"],
            ],
            config=config,
        )
        overlay = {
            "CM0001": {"dob": "01/02/26", "wean_date": "01/30/26"},
            "CM0002": {"dob": "12/25/25", "wean_date": "01/29/26"},
        }

        filled = apply_dob_wean_overlay(inventory, overlay, _LOGGER)

        self.assertEqual(inventory.value(0, "dob"), "01/02/26")
        self.assertEqual(inventory.value(0, "wean_date"), "01/30/26")
        # Row 2 already had a DOB; the overlay must not overwrite it.
        self.assertEqual(inventory.value(1, "dob"), "01/01/26")
        self.assertEqual(inventory.value(1, "wean_date"), "01/29/26")
        self.assertEqual(filled, 3)

    def test_unmatched_identifiers_are_ignored(self) -> None:
        config = _inventory_config()
        inventory = InventoryTable(
            source_path=Path("inventory.csv"),
            headers=["Mouse", "ID", "Sample", "DOB", "Wean_By", "Genotype"],
            rows=[["CM0001", "", "S1", "", "", "+/+"]],
            config=config,
        )
        filled = apply_dob_wean_overlay(
            inventory, {"CM9999": {"dob": "01/02/26"}}, _LOGGER
        )
        self.assertEqual(filled, 0)
        self.assertEqual(inventory.value(0, "dob"), "")


class _FakeCredentials:
    @classmethod
    def from_service_account_file(cls, path: str, scopes: list[str]) -> "_FakeCredentials":
        return cls()


class FetchDobWeanOverlayTests(unittest.TestCase):
    def _install_fake_google_modules(self, sheet_rows: list[list[str]]) -> None:
        google_module = types.ModuleType("google")
        oauth2_module = types.ModuleType("google.oauth2")
        service_account_module = types.ModuleType("google.oauth2.service_account")
        service_account_module.Credentials = _FakeCredentials
        googleapiclient_module = types.ModuleType("googleapiclient")
        discovery_module = types.ModuleType("googleapiclient.discovery")

        def _build(service_name: str, version: str, credentials=None, cache_discovery=True):
            class _Values:
                def get(self, spreadsheetId: str, range: str):
                    class _Request:
                        def execute(self) -> dict:
                            return {"values": sheet_rows}

                    return _Request()

            class _Spreadsheets:
                def values(self) -> _Values:
                    return _Values()

            class _Service:
                def spreadsheets(self) -> _Spreadsheets:
                    return _Spreadsheets()

            return _Service()

        discovery_module.build = _build

        self.enterContext(
            mock.patch.dict(
                sys.modules,
                {
                    "google": google_module,
                    "google.oauth2": oauth2_module,
                    "google.oauth2.service_account": service_account_module,
                    "googleapiclient": googleapiclient_module,
                    "googleapiclient.discovery": discovery_module,
                },
            )
        )

    def _sheets_config(self, credentials_file: Path) -> SheetsOverlayConfig:
        return SheetsOverlayConfig(
            enabled=True,
            spreadsheet_id="abc123",
            worksheet="Sheet1",
            credentials_file=credentials_file,
        )

    def test_libraries_not_installed_raises_clear_error(self) -> None:
        self.enterContext(
            mock.patch.dict(
                sys.modules,
                {"google": None, "google.oauth2": None, "googleapiclient.discovery": None},
            )
        )
        with tempfile.TemporaryDirectory() as directory_name:
            credentials_file = Path(directory_name) / "creds.json"
            credentials_file.write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(SheetsOverlayError, "not installed"):
                fetch_dob_wean_overlay(self._sheets_config(credentials_file), _inventory_config())

    def test_missing_credentials_file_raises_clear_error(self) -> None:
        self._install_fake_google_modules(sheet_rows=[["Mouse", "DOB", "Wean_By"]])
        config = self._sheets_config(Path("/nonexistent/creds.json"))
        with self.assertRaisesRegex(SheetsOverlayError, "credentials"):
            fetch_dob_wean_overlay(config, _inventory_config())

    def test_parses_rows_by_header_text_and_fills_first_matching_identifier(self) -> None:
        self._install_fake_google_modules(
            sheet_rows=[
                ["Mouse", "ID", "Sample", "DOB", "Wean_By"],
                ["CM0001", "", "S1", "01/02/26", "01/30/26"],
                ["", "", "", "", ""],
                ["CM0002", "", "S2", "", "12/29/25"],
            ]
        )
        with tempfile.TemporaryDirectory() as directory_name:
            credentials_file = Path(directory_name) / "creds.json"
            credentials_file.write_text("{}", encoding="utf-8")
            overlay = fetch_dob_wean_overlay(
                self._sheets_config(credentials_file), _inventory_config()
            )

        self.assertEqual(overlay["CM0001"], {"dob": "01/02/26", "wean_date": "01/30/26"})
        self.assertEqual(overlay["S1"], {"dob": "01/02/26", "wean_date": "01/30/26"})
        self.assertEqual(overlay["CM0002"], {"wean_date": "12/29/25"})
        self.assertNotIn("dob", overlay["CM0002"])

    def test_no_rows_raises_clear_error(self) -> None:
        self._install_fake_google_modules(sheet_rows=[])
        with tempfile.TemporaryDirectory() as directory_name:
            credentials_file = Path(directory_name) / "creds.json"
            credentials_file.write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(SheetsOverlayError, "no rows"):
                fetch_dob_wean_overlay(self._sheets_config(credentials_file), _inventory_config())


if __name__ == "__main__":
    unittest.main()
