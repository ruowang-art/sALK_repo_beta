from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from automouse.config import (
    AppConfig,
    InventoryConfig,
    RConfig,
    SheetsOverlayConfig,
    TransnetyxConfig,
    TranslationConfig,
    validate_config,
)
from automouse.exceptions import ConfigurationError


class InventorySourceSheetUrlTests(unittest.TestCase):
    def _config(self, root: Path, source_sheet_url: str) -> AppConfig:
        executable = root / "Rscript"
        translation = root / "translation.R"
        wrapper = root / "wrapper.R"
        for path in (executable, translation, wrapper):
            path.write_text("fixture", encoding="utf-8")

        inventory_path = root / "inventory.csv"
        headers = [f"Column {index}" for index in range(1, 22)]
        for index, value in {
            1: "Mouse", 4: "Strain", 6: "Revised Strain", 14: "Mother",
            15: "Father", 16: "DOB", 17: "Sex", 18: "Wean_By", 21: "Genotype",
        }.items():
            headers[index - 1] = value
        with inventory_path.open("w", encoding="utf-8", newline="") as stream:
            csv.writer(stream).writerow(headers)

        return AppConfig(
            project_root=root,
            runtime_root=root / "runtime",
            application_version="test",
            r=RConfig(executable, translation, wrapper),
            transnetyx=TransnetyxConfig(),
            translation=TranslationConfig(),
            inventory=InventoryConfig(
                file=inventory_path,
                columns={
                    "mouse_id": 1, "strain": 4, "revised_strain": 6,
                    "mother": 14, "father": 15, "dob": 16, "sex": 17,
                    "wean_date": 18, "genotype": 21,
                },
                source_sheet_url=source_sheet_url,
            ),
        )

    def test_valid_https_url_passes(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            config = self._config(
                Path(directory_name),
                "https://docs.google.com/spreadsheets/d/abc123/edit",
            )
            validate_config(config)

    def test_blank_url_passes(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            config = self._config(Path(directory_name), "")
            validate_config(config)

    def test_non_http_url_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            config = self._config(Path(directory_name), "javascript:alert(1)")
            with self.assertRaisesRegex(ConfigurationError, "source_sheet_url"):
                validate_config(config)


class SheetsOverlayConfigTests(unittest.TestCase):
    def _base_config(self, root: Path, sheets_overlay: SheetsOverlayConfig | None) -> AppConfig:
        executable = root / "Rscript"
        translation = root / "translation.R"
        wrapper = root / "wrapper.R"
        for path in (executable, translation, wrapper):
            path.write_text("fixture", encoding="utf-8")

        inventory_path = root / "inventory.csv"
        headers = [f"Column {index}" for index in range(1, 22)]
        for index, value in {
            1: "Mouse", 4: "Strain", 6: "Revised Strain", 14: "Mother",
            15: "Father", 16: "DOB", 17: "Sex", 18: "Wean_By", 21: "Genotype",
        }.items():
            headers[index - 1] = value
        with inventory_path.open("w", encoding="utf-8", newline="") as stream:
            csv.writer(stream).writerow(headers)

        return AppConfig(
            project_root=root,
            runtime_root=root / "runtime",
            application_version="test",
            r=RConfig(executable, translation, wrapper),
            transnetyx=TransnetyxConfig(),
            translation=TranslationConfig(),
            inventory=InventoryConfig(
                file=inventory_path,
                columns={
                    "mouse_id": 1, "strain": 4, "revised_strain": 6,
                    "mother": 14, "father": 15, "dob": 16, "sex": 17,
                    "wean_date": 18, "genotype": 21,
                },
            ),
            sheets_overlay=sheets_overlay,
        )

    def test_disabled_overlay_requires_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            config = self._base_config(Path(directory_name), SheetsOverlayConfig())
            validate_config(config)

    def test_missing_overlay_section_is_fine(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            config = self._base_config(Path(directory_name), None)
            validate_config(config)

    def test_enabled_overlay_requires_spreadsheet_id_and_credentials(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            config = self._base_config(
                Path(directory_name),
                SheetsOverlayConfig(enabled=True),
            )
            with self.assertRaisesRegex(ConfigurationError, "spreadsheet_id"):
                validate_config(config)

    def test_enabled_overlay_with_missing_credentials_file_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            root = Path(directory_name)
            config = self._base_config(
                root,
                SheetsOverlayConfig(
                    enabled=True,
                    spreadsheet_id="abc123",
                    credentials_file=root / "does_not_exist.json",
                ),
            )
            with self.assertRaisesRegex(ConfigurationError, "credentials_file"):
                validate_config(config)

    def test_enabled_overlay_with_valid_settings_passes(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            root = Path(directory_name)
            credentials_file = root / "service_account.json"
            credentials_file.write_text("{}", encoding="utf-8")
            config = self._base_config(
                root,
                SheetsOverlayConfig(
                    enabled=True,
                    spreadsheet_id="abc123",
                    credentials_file=credentials_file,
                ),
            )
            validate_config(config)


if __name__ == "__main__":
    unittest.main()
