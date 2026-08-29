from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from automouse.app import append_litter_to_inventory
from automouse.config import (
    AppConfig,
    InventoryConfig,
    RConfig,
    SheetsOverlayConfig,
    TransnetyxConfig,
    TranslationConfig,
)
from automouse.exceptions import ConfigurationError
from automouse.litter_entry import LitterSubmission
from automouse.models import AuditAction
from automouse.sheets_litter_writer import SheetState, SheetsLitterWriteError

_COLUMNS = {
    "mouse_id": 1, "strain": 4, "revised_strain": 6,
    "transnetyx_order_date": 8, "plate_id": 9,
    "mother": 14, "father": 15, "dob": 16, "sex": 17, "wean_date": 18, "genotype": 21,
}
_EXPECTED_HEADERS = {
    "mouse_id": "Mouse", "strain": "Strain", "revised_strain": "Revised Strain",
    "transnetyx_order_date": "Transnetyx Order Date", "plate_id": "Plate ID",
    "mother": "Mother", "father": "Father", "dob": "DOB", "sex": "Sex",
    "wean_date": "Wean_By", "genotype": "Genotype",
}
_BASELINE_EXISTING_IDS = ["CM1000", "CM0500", "CM0501", "CM0502"]


class LitterEntryIntegrationTests(unittest.TestCase):
    def _build_config(
        self,
        root: Path,
        *,
        append_only: bool = True,
        sheets_overlay: SheetsOverlayConfig | None = None,
    ) -> tuple[AppConfig, Path]:
        executable = root / "Rscript"
        translation = root / "translation.R"
        wrapper = root / "wrapper.R"
        for path in (executable, translation, wrapper):
            path.write_text("fixture", encoding="utf-8")

        inventory_path = root / "inventory.csv"
        headers = [f"Column {index}" for index in range(1, 22)]
        for role, header in _EXPECTED_HEADERS.items():
            headers[_COLUMNS[role] - 1] = header
        with inventory_path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(headers)
            # A handful of baseline rows, not just one, so a Sheet mock that's
            # missing a single ID (the "removed from the Sheet" scenario)
            # doesn't look like a suspiciously near-empty response to
            # append_litter_to_inventory's Sheet-response sanity guard.
            for mouse_id in _BASELINE_EXISTING_IDS:
                row = [""] * 21
                row[0] = mouse_id
                writer.writerow(row)

        config = AppConfig(
            project_root=root,
            runtime_root=root / "runtime",
            application_version="test",
            r=RConfig(executable, translation, wrapper),
            transnetyx=TransnetyxConfig(),
            translation=TranslationConfig(),
            inventory=InventoryConfig(
                file=inventory_path,
                append_only=append_only,
                columns=_COLUMNS,
                expected_headers=_EXPECTED_HEADERS,
            ),
            sheets_overlay=sheets_overlay,
        )
        return config, inventory_path

    def _submission(self, **overrides) -> LitterSubmission:
        defaults = dict(
            strain="Kras/Lkb1",
            dob="2026-01-19",
            mother="CM9001",
            father="CM9002",
            total_pups=3,
            female_count=1,
            male_count=2,
            first_mouse_id="CM2000",
            last_mouse_id="CM2002",
            plate_id="T1234567",
            transnetyx_order_date="2026-01-20",
        )
        defaults.update(overrides)
        return LitterSubmission(**defaults)

    def test_adds_all_pups_with_correct_sex_and_blank_genotype(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            root = Path(directory_name)
            config, inventory_path = self._build_config(root)

            run_id, entries, artifacts, warnings = append_litter_to_inventory(
                self._submission(), config
            )

            self.assertEqual(len(entries), 3)
            self.assertTrue(all(e.action == AuditAction.LITTER_ENTERED for e in entries))
            self.assertIn("updated_inventory_csv_file", artifacts)
            self.assertIn("inventory_backup_file", artifacts)

            updated_rows = list(
                csv.reader(
                    Path(artifacts["updated_inventory_csv_file"]).read_text(encoding="utf-8").splitlines()
                )
            )
            by_id = {row[0]: row for row in updated_rows[1:]}
            self.assertEqual(by_id["CM2000"][16], "Female")  # sex column (index 16 = col 17)
            self.assertEqual(by_id["CM2001"][16], "Male")
            self.assertEqual(by_id["CM2002"][16], "Male")
            self.assertEqual(by_id["CM2000"][20], "")  # genotype left blank
            self.assertEqual(by_id["CM2000"][3], "Kras/Lkb1")  # strain
            self.assertEqual(by_id["CM2000"][15], "2026-01-19")  # dob
            self.assertEqual(by_id["CM2000"][7], "2026-01-20")  # Transnetyx Order Date column
            self.assertEqual(by_id["CM2000"][8], "T1234567")  # Plate ID column

            # append_only mode copies the rebuilt inventory back onto the source.
            source_rows = list(csv.reader(inventory_path.read_text(encoding="utf-8").splitlines()))
            self.assertIn("CM2000", {row[0] for row in source_rows[1:]})

    def test_existing_mouse_id_becomes_a_conflict_not_an_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            root = Path(directory_name)
            config, inventory_path = self._build_config(root)
            original_bytes = inventory_path.read_bytes()

            run_id, entries, artifacts, warnings = append_litter_to_inventory(
                self._submission(
                    total_pups=1, female_count=1, male_count=0,
                    first_mouse_id="CM1000", last_mouse_id="CM1000",
                ),
                config,
            )

            self.assertEqual(entries[0].action, AuditAction.CONFLICT)
            self.assertNotIn("updated_inventory_csv_file", artifacts)
            self.assertEqual(inventory_path.read_bytes(), original_bytes)

    def test_dry_run_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            root = Path(directory_name)
            config, inventory_path = self._build_config(root)
            original_bytes = inventory_path.read_bytes()

            run_id, entries, artifacts, warnings = append_litter_to_inventory(
                self._submission(
                    total_pups=1, female_count=1, male_count=0,
                    first_mouse_id="CM2000", last_mouse_id="CM2000",
                ),
                config,
                dry_run=True,
            )

            self.assertEqual(entries[0].action, AuditAction.LITTER_ENTERED)
            self.assertIn("Would be added", entries[0].messages[0])
            self.assertNotIn("updated_inventory_csv_file", artifacts)
            self.assertEqual(inventory_path.read_bytes(), original_bytes)

    def test_requires_append_only_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            root = Path(directory_name)
            config, _ = self._build_config(root, append_only=False)
            with self.assertRaisesRegex(ConfigurationError, "append_only"):
                append_litter_to_inventory(
                    self._submission(
                        total_pups=1, female_count=1, male_count=0,
                        first_mouse_id="CM2000", last_mouse_id="CM2000",
                    ),
                    config,
                )

    def test_requires_inventory_section(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            root = Path(directory_name)
            config, _ = self._build_config(root)
            config = AppConfig(
                project_root=config.project_root,
                runtime_root=config.runtime_root,
                application_version=config.application_version,
                r=config.r,
                transnetyx=config.transnetyx,
                translation=config.translation,
                inventory=None,
            )
            with self.assertRaisesRegex(ConfigurationError, "inventory section"):
                append_litter_to_inventory(
                    self._submission(
                        total_pups=1, female_count=1, male_count=0,
                        first_mouse_id="CM2000", last_mouse_id="CM2000",
                    ),
                    config,
                )


class LitterEntrySheetWriteTests(unittest.TestCase):
    """sheets_overlay.write_new_litters: appending new litters to the live
    Google Sheet, in addition to the local inventory copy. See CLAUDE.md and
    sheets_litter_writer.py for the rules this is held to.
    """

    def _config_with_sheet_write(self, root: Path) -> tuple[AppConfig, Path]:
        base = LitterEntryIntegrationTests()
        credentials_file = root / "service_account.json"
        credentials_file.write_text("{}", encoding="utf-8")
        return base._build_config(
            root,
            sheets_overlay=SheetsOverlayConfig(
                enabled=True,
                spreadsheet_id="abc123",
                worksheet="Sheet1",
                credentials_file=credentials_file,
                write_new_litters=True,
            ),
        )

    def _submission(self, **overrides) -> LitterSubmission:
        return LitterEntryIntegrationTests()._submission(**overrides)

    @patch("automouse.app.append_litter_rows_to_sheet")
    @patch("automouse.app.fetch_sheet_state")
    def test_writes_new_litters_to_sheet_when_enabled(self, mock_fetch, mock_append) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            root = Path(directory_name)
            config, _ = self._config_with_sheet_write(root)
            # A healthy, fully-synced Sheet: everything already local is also
            # in the Sheet, and none of the freshly submitted IDs are yet.
            mock_fetch.return_value = SheetState(
                header_row=list(_EXPECTED_HEADERS.values()),
                existing_identifiers=set(_BASELINE_EXISTING_IDS),
            )

            run_id, entries, artifacts, warnings = append_litter_to_inventory(
                self._submission(), config
            )

            self.assertEqual(warnings, [])
            self.assertTrue(all(e.action == AuditAction.LITTER_ENTERED for e in entries))
            mock_append.assert_called_once()
            _, call_args, _ = mock_append.mock_calls[0]
            written_rows = call_args[-1]
            self.assertEqual({row["mouse_id"] for row in written_rows}, {"CM2000", "CM2001", "CM2002"})

    @patch("automouse.app.append_litter_rows_to_sheet")
    @patch("automouse.app.fetch_sheet_state")
    def test_sheet_conflict_blocks_only_that_mouse_id(self, mock_fetch, mock_append) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            root = Path(directory_name)
            config, _ = self._config_with_sheet_write(root)
            mock_fetch.return_value = SheetState(
                header_row=list(_EXPECTED_HEADERS.values()),
                existing_identifiers=set(_BASELINE_EXISTING_IDS) | {"CM2001"},
            )

            run_id, entries, artifacts, warnings = append_litter_to_inventory(
                self._submission(), config
            )

            by_id = {entry.mouse_id: entry for entry in entries}
            self.assertEqual(by_id["CM2001"].action, AuditAction.CONFLICT)
            self.assertIn("Google Sheet", by_id["CM2001"].messages[0])
            self.assertEqual(by_id["CM2000"].action, AuditAction.LITTER_ENTERED)
            self.assertEqual(by_id["CM2002"].action, AuditAction.LITTER_ENTERED)
            written_rows = mock_append.mock_calls[0][1][-1]
            self.assertEqual({row["mouse_id"] for row in written_rows}, {"CM2000", "CM2002"})

    @patch("automouse.app.append_litter_rows_to_sheet")
    @patch("automouse.app.fetch_sheet_state")
    def test_mouse_id_removed_from_sheet_frees_the_stale_local_row(self, mock_fetch, mock_append) -> None:
        # CM1000 already has a row in the local inventory fixture (see
        # _build_config), but is absent from the live Sheet's identifiers
        # below — as if someone deleted that litter from the primary Sheet.
        # Re-submitting CM1000 must not be blocked as a CONFLICT; instead
        # the stale local row is replaced by the fresh one.
        with tempfile.TemporaryDirectory() as directory_name:
            root = Path(directory_name)
            config, _ = self._config_with_sheet_write(root)
            # Everything else in the local baseline is still in the Sheet;
            # only CM1000 is missing, i.e. an ordinary single-litter deletion
            # rather than a suspiciously incomplete Sheet response.
            mock_fetch.return_value = SheetState(
                header_row=list(_EXPECTED_HEADERS.values()),
                existing_identifiers=set(_BASELINE_EXISTING_IDS) - {"CM1000"},
            )

            run_id, entries, artifacts, warnings = append_litter_to_inventory(
                self._submission(
                    first_mouse_id="CM1000", last_mouse_id="CM1000",
                    total_pups=1, female_count=1, male_count=0,
                ),
                config,
            )

            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0].action, AuditAction.LITTER_ENTERED)
            self.assertIn("Replaced a previous entry", entries[0].messages[0])
            self.assertEqual(len(warnings), 1)
            self.assertIn("CM1000", warnings[0])
            self.assertIn("removed from the Google Sheet", warnings[0])

            updated_rows = list(
                csv.reader(
                    Path(artifacts["updated_inventory_csv_file"]).read_text(encoding="utf-8").splitlines()
                )
            )
            matching_rows = [row for row in updated_rows[1:] if row[0] == "CM1000"]
            self.assertEqual(len(matching_rows), 1, "expected exactly one CM1000 row, not a duplicate")
            self.assertEqual(matching_rows[0][3], "Kras/Lkb1")  # the freshly submitted strain

            mock_append.assert_called_once()
            written_rows = mock_append.mock_calls[0][1][-1]
            self.assertEqual({row["mouse_id"] for row in written_rows}, {"CM1000"})

    @patch("automouse.app.append_litter_rows_to_sheet")
    @patch("automouse.app.fetch_sheet_state")
    def test_dry_run_previews_the_freed_row_without_mutating_anything(self, mock_fetch, mock_append) -> None:
        # A dry run now fetches the Sheet too (read-only), so the preview
        # matches what a real run would actually do.
        with tempfile.TemporaryDirectory() as directory_name:
            root = Path(directory_name)
            config, inventory_path = self._config_with_sheet_write(root)
            original_bytes = inventory_path.read_bytes()
            mock_fetch.return_value = SheetState(
                header_row=list(_EXPECTED_HEADERS.values()),
                existing_identifiers=set(_BASELINE_EXISTING_IDS) - {"CM1000"},
            )

            run_id, entries, artifacts, warnings = append_litter_to_inventory(
                self._submission(
                    first_mouse_id="CM1000", last_mouse_id="CM1000",
                    total_pups=1, female_count=1, male_count=0,
                ),
                config,
                dry_run=True,
            )

            self.assertEqual(entries[0].action, AuditAction.LITTER_ENTERED)
            self.assertIn("Would replace a previous entry", entries[0].messages[0])
            self.assertNotIn("updated_inventory_csv_file", artifacts)
            self.assertEqual(inventory_path.read_bytes(), original_bytes)
            mock_append.assert_not_called()

    @patch("automouse.app.fetch_sheet_state")
    def test_sheet_check_failure_still_writes_locally_with_warning(self, mock_fetch) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            root = Path(directory_name)
            config, inventory_path = self._config_with_sheet_write(root)
            mock_fetch.side_effect = SheetsLitterWriteError("offline")

            run_id, entries, artifacts, warnings = append_litter_to_inventory(
                self._submission(), config
            )

            self.assertTrue(all(e.action == AuditAction.LITTER_ENTERED for e in entries))
            self.assertIn("updated_inventory_csv_file", artifacts)
            self.assertEqual(len(warnings), 1)
            self.assertIn("offline", warnings[0])

    @patch("automouse.app.append_litter_rows_to_sheet")
    @patch("automouse.app.fetch_sheet_state")
    def test_sheet_write_failure_still_keeps_local_write_with_warning(self, mock_fetch, mock_append) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            root = Path(directory_name)
            config, _ = self._config_with_sheet_write(root)
            mock_fetch.return_value = SheetState(
                header_row=list(_EXPECTED_HEADERS.values()),
                existing_identifiers=set(_BASELINE_EXISTING_IDS),
            )
            mock_append.side_effect = SheetsLitterWriteError("quota exceeded")

            run_id, entries, artifacts, warnings = append_litter_to_inventory(
                self._submission(), config
            )

            self.assertTrue(all(e.action == AuditAction.LITTER_ENTERED for e in entries))
            self.assertIn("updated_inventory_csv_file", artifacts)
            self.assertEqual(len(warnings), 1)
            self.assertIn("quota exceeded", warnings[0])
            self.assertIn("CM2000", warnings[0])

    @patch("automouse.app.append_litter_rows_to_sheet")
    @patch("automouse.app.fetch_sheet_state")
    def test_suspiciously_empty_sheet_response_is_not_trusted(self, mock_fetch, mock_append) -> None:
        # A "successful" fetch that comes back with far fewer identifiers
        # than the local inventory already has (here: none at all) looks
        # like a wrong tab, a bad range, or a masked API error - not real
        # evidence that every local mouse ID was deleted from the Sheet.
        # CM1000 must stay a CONFLICT (local-only fallback), not get freed.
        with tempfile.TemporaryDirectory() as directory_name:
            root = Path(directory_name)
            config, _ = self._config_with_sheet_write(root)
            mock_fetch.return_value = SheetState(
                header_row=list(_EXPECTED_HEADERS.values()), existing_identifiers=set()
            )

            run_id, entries, artifacts, warnings = append_litter_to_inventory(
                self._submission(
                    first_mouse_id="CM1000", last_mouse_id="CM1000",
                    total_pups=1, female_count=1, male_count=0,
                ),
                config,
            )

            self.assertEqual(entries[0].action, AuditAction.CONFLICT)
            self.assertTrue(
                any("incomplete or wrong Sheet response" in warning for warning in warnings),
                warnings,
            )
            mock_append.assert_not_called()

    @patch("automouse.app.append_litter_rows_to_sheet")
    @patch("automouse.app.fetch_sheet_state")
    def test_suspiciously_small_sheet_response_is_not_trusted(self, mock_fetch, mock_append) -> None:
        # Same guard, triggered by a response that's merely far smaller than
        # expected (1 of 4 known local identifiers) rather than empty.
        with tempfile.TemporaryDirectory() as directory_name:
            root = Path(directory_name)
            config, _ = self._config_with_sheet_write(root)
            mock_fetch.return_value = SheetState(
                header_row=list(_EXPECTED_HEADERS.values()), existing_identifiers={"CM0500"}
            )

            run_id, entries, artifacts, warnings = append_litter_to_inventory(
                self._submission(
                    first_mouse_id="CM1000", last_mouse_id="CM1000",
                    total_pups=1, female_count=1, male_count=0,
                ),
                config,
            )

            self.assertEqual(entries[0].action, AuditAction.CONFLICT)
            self.assertTrue(
                any("incomplete or wrong Sheet response" in warning for warning in warnings),
                warnings,
            )
            mock_append.assert_not_called()


if __name__ == "__main__":
    unittest.main()
