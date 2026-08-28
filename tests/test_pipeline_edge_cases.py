from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from openpyxl import Workbook

from automouse.app import run_batch
from automouse.config import (
    AppConfig,
    CageCardConfig,
    InventoryConfig,
    RConfig,
    TransnetyxConfig,
    TranslationConfig,
)
from automouse.exceptions import InventoryValidationError, TranslationValidationError
from automouse.inventory_manager import load_inventory
from automouse.models import RRunResult, RunStage

_TEMPLATE_HEADERS = (
    "Experiment URL", "Strain", "# IN CAGE", "# IN LITTER", "SEX",
    "DATE WEANED", "DATE BORN", "MOUSE 1", "MOUSE 2", "MOUSE 3",
    "MOUSE 4", "MOUSE 5", "MOUSE 1 GENOTYPE", "MOUSE 2 GENOTYPE",
    "MOUSE 3 GENOTYPE", "MOUSE 4 GENOTYPE", "MOUSE 5 GENOTYPE",
    "DAM", "DAM GENOTYPE", "SIRE", "SIRE GENOTYPE", "BREEDER? (B)",
    "Set up date",
)


_COLUMNS = {
    "mouse_id": 1, "strain": 4, "revised_strain": 6,
    "mother": 14, "father": 15, "dob": 16, "sex": 17, "wean_date": 18,
    "sample": 20, "genotype": 21,
}
_EXPECTED_HEADERS = {
    "mouse_id": "Mouse", "strain": "Strain", "revised_strain": "Revised Strain",
    "mother": "Mother", "father": "Father", "dob": "DOB", "sex": "Sex",
    "wean_date": "Wean_By", "sample": "Sample", "genotype": "Genotype",
}


class PipelineEdgeCaseTests(unittest.TestCase):
    """Regression tests for branches that existed in code but had no test coverage
    (surfaced by an external robustness review; see mouseley-kras-and-xol-pots-xol-overview.md)."""

    def _build_config(self, root: Path, inventory_rows: list[list[str]]) -> AppConfig:
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
            writer.writerows(inventory_rows)

        template_path = root / "template.xlsx"
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Sheet1"
        sheet.append(_TEMPLATE_HEADERS)
        sheet.append([""] * len(_TEMPLATE_HEADERS))
        workbook.save(template_path)

        return AppConfig(
            project_root=root,
            runtime_root=root / "runtime",
            application_version="test",
            r=RConfig(executable, translation, wrapper),
            transnetyx=TransnetyxConfig(),
            translation=TranslationConfig(),
            inventory=InventoryConfig(
                file=inventory_path,
                columns=_COLUMNS,
                expected_headers=_EXPECTED_HEADERS,
            ),
            cage_card=CageCardConfig(
                template=template_path,
                expected_headers=_TEMPLATE_HEADERS,
            ),
        )

    def _row(self, mouse_id: str, genotype: str, sex: str = "Male") -> list[str]:
        row = [""] * 21
        row[0] = mouse_id
        row[3] = "Kras"
        row[19] = mouse_id
        row[16] = sex
        row[20] = genotype
        return row

    def test_conflicting_genotype_is_flagged_not_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            root = Path(directory_name)
            config = self._build_config(root, [self._row("CM0001", "+/+")])

            raw = root / "raw.csv"
            raw.write_text(
                "WellPlate,Strain,Well,Sample,TranslatedResult,G12D mut,Y\n"
                "T1,Kras,A1,CM0001,,+-,+\n",
                encoding="utf-8",
            )

            def fake_translation(input_path: Path, output_path: Path, *_: object, **__: object) -> RRunResult:
                output_path.write_text(
                    "WellPlate,Strain,Well,Sample,TranslatedResult,G12D.mut,Y,Kras,Sex,Genotype\n"
                    "T1,Kras,A1,CM0001,,+-,+,LSL-G12D/+,Male,LSL-G12D/+\n",
                    encoding="utf-8",
                )
                return RRunResult([], 0, "", "", output_path, 0.01)

            original_bytes = config.inventory.file.read_bytes()
            with patch("automouse.app.run_r_translation", side_effect=fake_translation):
                context = run_batch([raw], config, complete_pipeline=True)

            self.assertEqual(context.stage, RunStage.COMPLETED)
            self.assertEqual(context.counts["conflict_count"], 1)
            self.assertEqual(context.counts["inventory_records_updated"], 0)
            # The existing genotype on disk must be untouched.
            self.assertEqual(config.inventory.file.read_bytes(), original_bytes)

            with Path(context.artifacts["audit_file"]).open(newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(rows[0]["action"], "CONFLICT")
            self.assertEqual(rows[0]["previous_genotype"], "+/+")
            self.assertEqual(rows[0]["proposed_genotype"], "LSL-G12D/+")

    def test_unknown_mouse_id_is_reported_not_found(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            root = Path(directory_name)
            config = self._build_config(root, [self._row("CM0001", "+/+")])

            raw = root / "raw.csv"
            raw.write_text(
                "WellPlate,Strain,Well,Sample,TranslatedResult,G12D mut,Y\n"
                "T1,Kras,A1,CM9999,,+-,+\n",
                encoding="utf-8",
            )

            def fake_translation(input_path: Path, output_path: Path, *_: object, **__: object) -> RRunResult:
                output_path.write_text(
                    "WellPlate,Strain,Well,Sample,TranslatedResult,G12D.mut,Y,Kras,Sex,Genotype\n"
                    "T1,Kras,A1,CM9999,,+-,+,LSL-G12D/+,Male,LSL-G12D/+\n",
                    encoding="utf-8",
                )
                return RRunResult([], 0, "", "", output_path, 0.01)

            with patch("automouse.app.run_r_translation", side_effect=fake_translation):
                context = run_batch([raw], config, complete_pipeline=True)

            self.assertEqual(context.stage, RunStage.COMPLETED)
            self.assertEqual(context.counts["mouse_not_found_count"], 1)
            self.assertEqual(context.counts["inventory_records_updated"], 0)

            with Path(context.artifacts["audit_file"]).open(newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(rows[0]["action"], "NOT_FOUND")
            self.assertEqual(rows[0]["status"], "MOUSE_NOT_FOUND")

    def test_missing_translated_genotype_column_is_a_clear_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            root = Path(directory_name)
            config = self._build_config(root, [self._row("CM0001", "")])

            raw = root / "raw.csv"
            raw.write_text(
                "WellPlate,Strain,Well,Sample,TranslatedResult,G12D mut,Y\n"
                "T1,Kras,A1,CM0001,,+-,+\n",
                encoding="utf-8",
            )

            def fake_translation(input_path: Path, output_path: Path, *_: object, **__: object) -> RRunResult:
                # Deliberately omits the required "Genotype" column.
                output_path.write_text(
                    "WellPlate,Strain,Well,Sample,TranslatedResult,G12D.mut,Y,Kras,Sex\n"
                    "T1,Kras,A1,CM0001,,+-,+,LSL-G12D/+,Male\n",
                    encoding="utf-8",
                )
                return RRunResult([], 0, "", "", output_path, 0.01)

            with patch("automouse.app.run_r_translation", side_effect=fake_translation):
                with self.assertRaisesRegex(
                    TranslationValidationError, "Missing translated-output column: Genotype"
                ):
                    run_batch([raw], config, complete_pipeline=True)

    def test_duplicate_mouse_id_in_inventory_raises_at_load(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            root = Path(directory_name)
            config = self._build_config(
                root,
                [self._row("CM0001", "+/+"), self._row("CM0001", "K/+")],
            )

            with self.assertRaisesRegex(InventoryValidationError, "Duplicate primary mouse identifiers"):
                load_inventory(config.inventory.file, config.inventory)

    def test_unicode_strain_and_genotype_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            root = Path(directory_name)
            config = self._build_config(root, [self._row("CM0001", "")])

            raw = root / "raw.csv"
            raw.write_text(
                "WellPlate,Strain,Well,Sample,TranslatedResult,G12D mut,Y\n"
                "T1,Kräs/Söx9,A1,CM0001,,--,+\n",
                encoding="utf-8",
            )

            def fake_translation(input_path: Path, output_path: Path, *_: object, **__: object) -> RRunResult:
                output_path.write_text(
                    "WellPlate,Strain,Well,Sample,TranslatedResult,G12D.mut,Y,Kras,Sex,Genotype\n"
                    "T1,Kräs/Söx9,A1,CM0001,,--,+,+/+,Male,'+/+\n",
                    encoding="utf-8",
                )
                return RRunResult([], 0, "", "", output_path, 0.01)

            with patch("automouse.app.run_r_translation", side_effect=fake_translation):
                context = run_batch([raw], config, complete_pipeline=True)

            self.assertEqual(context.stage, RunStage.COMPLETED)
            self.assertEqual(context.counts["inventory_records_updated"], 1)

            with Path(context.artifacts["audit_file"]).open(newline="", encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(rows[0]["action"], "UPDATED")
            self.assertEqual(rows[0]["proposed_genotype"], "+/+")


if __name__ == "__main__":
    unittest.main()
