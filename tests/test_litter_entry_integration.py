from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from automouse.app import append_litter_to_inventory
from automouse.config import AppConfig, InventoryConfig, RConfig, TransnetyxConfig, TranslationConfig
from automouse.exceptions import ConfigurationError
from automouse.litter_entry import LitterSubmission
from automouse.models import AuditAction

_COLUMNS = {
    "mouse_id": 1, "strain": 4, "revised_strain": 6,
    "mother": 14, "father": 15, "dob": 16, "sex": 17, "wean_date": 18, "genotype": 21,
}
_EXPECTED_HEADERS = {
    "mouse_id": "Mouse", "strain": "Strain", "revised_strain": "Revised Strain",
    "mother": "Mother", "father": "Father", "dob": "DOB", "sex": "Sex",
    "wean_date": "Wean_By", "genotype": "Genotype",
}


class LitterEntryIntegrationTests(unittest.TestCase):
    def _build_config(self, root: Path, *, append_only: bool = True) -> tuple[AppConfig, Path]:
        executable = root / "Rscript"
        translation = root / "translation.R"
        wrapper = root / "wrapper.R"
        for path in (executable, translation, wrapper):
            path.write_text("fixture", encoding="utf-8")

        inventory_path = root / "inventory.csv"
        headers = [f"Column {index}" for index in range(1, 22)]
        for role, header in _EXPECTED_HEADERS.items():
            headers[_COLUMNS[role] - 1] = header
        existing_row = [""] * 21
        existing_row[0] = "CM1000"
        with inventory_path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(headers)
            writer.writerow(existing_row)

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
        )
        defaults.update(overrides)
        return LitterSubmission(**defaults)

    def test_adds_all_pups_with_correct_sex_and_blank_genotype(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            root = Path(directory_name)
            config, inventory_path = self._build_config(root)

            run_id, entries, artifacts = append_litter_to_inventory(
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

            # append_only mode copies the rebuilt inventory back onto the source.
            source_rows = list(csv.reader(inventory_path.read_text(encoding="utf-8").splitlines()))
            self.assertIn("CM2000", {row[0] for row in source_rows[1:]})

    def test_existing_mouse_id_becomes_a_conflict_not_an_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            root = Path(directory_name)
            config, inventory_path = self._build_config(root)
            original_bytes = inventory_path.read_bytes()

            run_id, entries, artifacts = append_litter_to_inventory(
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

            run_id, entries, artifacts = append_litter_to_inventory(
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


if __name__ == "__main__":
    unittest.main()
