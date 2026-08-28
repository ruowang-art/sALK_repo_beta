from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from automouse.config import TranslationConfig
from automouse.models import RecordStatus
from automouse.translation_validator import validate_translated_records


FIXTURES = Path(__file__).parent / "fixtures"


class TranslationValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = TranslationConfig()

    def test_valid_output_preserves_plus_genotype_as_text(self) -> None:
        report = validate_translated_records(
            FIXTURES / "translated_valid.csv",
            self.config,
            expected_raw_row_count=2,
            expected_sample_ids=["CM0001", "CM0002"],
        )
        self.assertTrue(report.valid, report.errors)
        self.assertEqual(report.records[0].translated_genotype, "+/+")
        self.assertEqual(report.records[0].status, RecordStatus.READY)

    def test_row_loss_is_an_error(self) -> None:
        report = validate_translated_records(
            FIXTURES / "translated_valid.csv",
            self.config,
            expected_raw_row_count=3,
        )
        self.assertFalse(report.valid)
        self.assertTrue(any("Row-count mismatch" in error for error in report.errors))

    def test_blank_and_failure_results_get_explicit_statuses(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "translated.csv"
            path.write_text(
                "Sample,Genotype\nCM1,\nCM2,Fail\n",
                encoding="utf-8",
            )
            report = validate_translated_records(path, self.config)
        self.assertTrue(report.valid, report.errors)
        self.assertEqual(report.records[0].status, RecordStatus.NO_RESULT)
        self.assertEqual(report.records[1].status, RecordStatus.PENDING_RERUN)

    def test_conflicting_duplicate_is_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "translated.csv"
            path.write_text(
                "Sample,Genotype\nCM1,K/+\nCM1,+/+\n",
                encoding="utf-8",
            )
            report = validate_translated_records(path, self.config)
        self.assertTrue(report.valid, report.errors)
        self.assertEqual(report.status_counts[RecordStatus.CONFLICT.value], 2)


if __name__ == "__main__":
    unittest.main()

