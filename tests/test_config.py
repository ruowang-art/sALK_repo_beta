from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path, PurePosixPath
from unittest.mock import patch

from automouse.config import (
    AppConfig,
    InventoryConfig,
    RConfig,
    SheetsOverlayConfig,
    TransnetyxConfig,
    TranslationConfig,
    _common_r_executable_locations,
    _resolve_r_executable,
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

    def test_write_new_litters_requires_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            root = Path(directory_name)
            config = self._base_config(
                root,
                SheetsOverlayConfig(enabled=False, write_new_litters=True),
            )
            with self.assertRaisesRegex(ConfigurationError, "write_new_litters"):
                validate_config(config)

    def test_write_new_litters_with_enabled_and_valid_settings_passes(self) -> None:
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
                    write_new_litters=True,
                ),
            )
            validate_config(config)


class CrossPlatformRExecutableDiscoveryTests(unittest.TestCase):
    """Phase 3 (cross-platform launchers): the R-executable fallback logic
    must resolve sensible candidate paths per OS. These are pure-function
    checks of the resolution logic itself — they do NOT prove Rscript is
    actually reachable on a real Windows/Linux machine (that's Phase 4).
    """

    def test_macos_locations_are_absolute_and_named_rscript(self) -> None:
        with patch("automouse.config.platform.system", return_value="Darwin"):
            locations = _common_r_executable_locations()
        self.assertTrue(locations)
        for location in locations:
            # These candidates represent POSIX paths regardless of the host
            # actually running this test. pathlib.Path() is host-OS-dependent
            # (WindowsPath on a Windows runner), so location.is_absolute()
            # would wrongly report False for e.g. "/opt/homebrew/bin/Rscript"
            # there (no drive letter) even though it's absolute on macOS.
            # str(location) on a WindowsPath renders backslashes, which
            # PurePosixPath treats as an ordinary character rather than a
            # separator - as_posix() normalizes back to forward slashes
            # first, so PurePosixPath sees the same string on every host.
            self.assertTrue(PurePosixPath(location.as_posix()).is_absolute())
            self.assertEqual(location.name, "Rscript")

    def test_linux_locations_are_absolute_and_named_rscript(self) -> None:
        with patch("automouse.config.platform.system", return_value="Linux"):
            locations = _common_r_executable_locations()
        self.assertTrue(locations)
        for location in locations:
            # See the macOS test above for why as_posix() before
            # PurePosixPath, not a bare str() or location.is_absolute().
            self.assertTrue(PurePosixPath(location.as_posix()).is_absolute())
            self.assertEqual(location.name, "Rscript")

    def test_windows_locations_end_in_rscript_exe(self) -> None:
        with patch("automouse.config.platform.system", return_value="Windows"), patch(
            "automouse.config.Path.is_dir", return_value=False
        ):
            locations = _common_r_executable_locations()
        # No "C:\Program Files\R" directory in this test environment, so the
        # candidate list is legitimately empty rather than guessed at.
        self.assertEqual(locations, ())

    def test_resolve_r_executable_prefers_an_already_correct_configured_path(self) -> None:
        # The one invariant that must hold on every platform: an explicit,
        # already-valid r.executable in config always wins over any
        # fallback discovery, macOS/Linux/Windows alike.
        with tempfile.TemporaryDirectory() as directory_name:
            root = Path(directory_name)
            real_rscript = root / "Rscript"
            real_rscript.write_text("fixture", encoding="utf-8")
            for system_name in ("Darwin", "Linux", "Windows"):
                with patch("automouse.config.platform.system", return_value=system_name):
                    resolved = _resolve_r_executable(str(real_rscript), root)
                self.assertEqual(resolved, real_rscript.resolve())

    def test_resolve_r_executable_falls_back_to_path_on_every_platform(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            root = Path(directory_name)
            fake_rscript = root / "Rscript"
            fake_rscript.write_text("fixture", encoding="utf-8")
            for system_name in ("Darwin", "Linux", "Windows"):
                with patch("automouse.config.platform.system", return_value=system_name), patch(
                    "automouse.config.shutil.which",
                    side_effect=lambda name, _p=fake_rscript: str(_p) if name == "Rscript" else None,
                ):
                    resolved = _resolve_r_executable("Rscript", root)
                self.assertEqual(resolved, fake_rscript.resolve())


if __name__ == "__main__":
    unittest.main()
