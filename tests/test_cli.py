from __future__ import annotations

import contextlib
import csv
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from automouse import cli
from automouse.models import RRunResult


FIXTURES = Path(__file__).parent / "fixtures"


class CliDuplicateInputTests(unittest.TestCase):
    def _write_config(self, root: Path) -> Path:
        executable = root / "Rscript"
        translation = root / "translation.R"
        wrapper = root / "wrapper.R"
        for path in (executable, translation, wrapper):
            path.write_text("fixture", encoding="utf-8")
        config_dir = root / "config"
        config_dir.mkdir()
        config_path = config_dir / "pipeline_run.yaml"
        config_path.write_text(
            json.dumps(
                {
                    "runtime_root": "runtime",
                    "r": {
                        "executable": str(executable),
                        "translation_script": str(translation),
                        "wrapper_script": str(wrapper),
                    },
                }
            ),
            encoding="utf-8",
        )
        return config_path

    def test_duplicate_input_is_a_distinct_exit_code_and_the_allow_flag_bypasses_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            root = Path(directory_name)
            config_path = self._write_config(root)

            def fake_translation(
                input_path: Path, output_path: Path, *_: object, **__: object
            ) -> RRunResult:
                output_path.write_bytes((FIXTURES / "translated_valid.csv").read_bytes())
                return RRunResult([], 0, "", "", output_path, 0.01)

            with patch("automouse.app.run_r_translation", side_effect=fake_translation):
                first_status = cli.main(
                    ["--config", str(config_path), "translate", str(FIXTURES / "raw_valid.csv")]
                )
                self.assertEqual(first_status, 0)

                second_status = cli.main(
                    ["--config", str(config_path), "translate", str(FIXTURES / "raw_valid.csv")]
                )
                self.assertEqual(second_status, cli.DUPLICATE_INPUT_EXIT_CODE)

                third_status = cli.main(
                    [
                        "--config",
                        str(config_path),
                        "translate",
                        "--allow-duplicate-input",
                        str(FIXTURES / "raw_valid.csv"),
                    ]
                )
                self.assertEqual(third_status, 0)


class CliEnterLitterTests(unittest.TestCase):
    def _write_config_with_inventory(self, root: Path, *, append_only: bool = True) -> Path:
        executable = root / "Rscript"
        translation = root / "translation.R"
        wrapper = root / "wrapper.R"
        for path in (executable, translation, wrapper):
            path.write_text("fixture", encoding="utf-8")

        inventory_path = root / "master.csv"
        headers = [f"Column {index}" for index in range(1, 22)]
        for index, value in {
            1: "Mouse", 4: "Strain", 6: "Revised Strain",
            14: "Mother", 15: "Father", 16: "DOB", 17: "Sex",
            18: "Wean_By", 21: "Genotype",
        }.items():
            headers[index - 1] = value
        with inventory_path.open("w", encoding="utf-8", newline="") as stream:
            csv.writer(stream).writerow(headers)

        config_dir = root / "config"
        config_dir.mkdir()
        config_path = config_dir / "pipeline_run.yaml"
        config_path.write_text(
            json.dumps(
                {
                    "runtime_root": "runtime",
                    "r": {
                        "executable": str(executable),
                        "translation_script": str(translation),
                        "wrapper_script": str(wrapper),
                    },
                    "inventory": {
                        "file": str(inventory_path),
                        "append_only": append_only,
                        "columns": {
                            "mouse_id": 1, "strain": 4, "revised_strain": 6,
                            "mother": 14, "father": 15, "dob": 16, "sex": 17,
                            "wean_date": 18, "genotype": 21,
                        },
                        "expected_headers": {
                            "mouse_id": "Mouse", "strain": "Strain",
                            "revised_strain": "Revised Strain",
                            "mother": "Mother", "father": "Father", "dob": "DOB",
                            "sex": "Sex", "wean_date": "Wean_By", "genotype": "Genotype",
                        },
                    },
                }
            ),
            encoding="utf-8",
        )
        return config_path

    def test_enter_litter_adds_female_and_male_pups(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            root = Path(directory_name)
            config_path = self._write_config_with_inventory(root)

            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                status = cli.main(
                    [
                        "--config", str(config_path), "enter-litter",
                        "--strain", "Kras/Lkb1", "--dob", "2026-01-19",
                        "--mother", "CM9001", "--father", "CM9002",
                        "--total-pups", "3", "--female-count", "1", "--male-count", "2",
                        "--first-mouse-id", "CM1000", "--last-mouse-id", "CM1002",
                    ]
                )
            self.assertEqual(status, 0)
            summary = json.loads(stdout.getvalue())
            self.assertEqual(len(summary["entries"]), 3)
            self.assertEqual(
                {entry["mouse_id"] for entry in summary["entries"]},
                {"CM1000", "CM1001", "CM1002"},
            )
            self.assertTrue(Path(summary["artifacts"]["updated_inventory_csv_file"]).is_file())

    def test_enter_litter_reports_mismatch_as_a_clear_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            root = Path(directory_name)
            config_path = self._write_config_with_inventory(root)

            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                status = cli.main(
                    [
                        "--config", str(config_path), "enter-litter",
                        "--strain", "Kras/Lkb1", "--dob", "2026-01-19",
                        "--mother", "CM9001", "--father", "CM9002",
                        "--total-pups", "5", "--female-count", "1", "--male-count", "2",
                        "--first-mouse-id", "CM1000", "--last-mouse-id", "CM1002",
                    ]
                )
            self.assertEqual(status, 1)
            self.assertIn("does not equal", stderr.getvalue())

    def test_enter_litter_requires_append_only_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            root = Path(directory_name)
            config_path = self._write_config_with_inventory(root, append_only=False)

            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                status = cli.main(
                    [
                        "--config", str(config_path), "enter-litter",
                        "--strain", "Kras/Lkb1", "--dob", "2026-01-19",
                        "--mother", "CM9001", "--father", "CM9002",
                        "--total-pups", "1", "--female-count", "1", "--male-count", "0",
                        "--first-mouse-id", "CM1000", "--last-mouse-id", "CM1000",
                    ]
                )
            self.assertEqual(status, 1)
            self.assertIn("append_only", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
