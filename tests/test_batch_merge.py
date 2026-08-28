from __future__ import annotations

import unittest
from pathlib import Path

from automouse.app import _merge_translation_reports
from automouse.models import (
    RecordStatus,
    TranslatedGenotypeRecord,
    TranslationValidationReport,
)


def _record(sample: str, genotype: str | None, status: RecordStatus, source: str) -> TranslatedGenotypeRecord:
    return TranslatedGenotypeRecord(
        sample_id=sample,
        mouse_id=sample,
        assay=None,
        raw_result=None,
        translated_genotype=genotype,
        status=status,
        warnings=[],
        source_row=2,
        source_file=source,
    )


class BatchMergeTests(unittest.TestCase):
    def test_ready_failed_agreeing_and_conflicting_results(self) -> None:
        first = TranslationValidationReport(
            True,
            [],
            [],
            3,
            [
                _record("CM1", "+/+", RecordStatus.READY, "first.csv"),
                _record("CM2", "+/+", RecordStatus.READY, "first.csv"),
                _record("CM3", "+/+", RecordStatus.READY, "first.csv"),
            ],
            {"READY": 3},
        )
        second = TranslationValidationReport(
            True,
            [],
            [],
            3,
            [
                _record("CM1", "UD1", RecordStatus.PENDING_RERUN, "second.csv"),
                _record("CM2", "+/+", RecordStatus.READY, "second.csv"),
                _record("CM3", "K/+", RecordStatus.READY, "second.csv"),
            ],
            {"PENDING_RERUN": 1, "READY": 2},
        )

        combined = _merge_translation_reports(
            [first, second],
            [Path("first.csv"), Path("second.csv")],
        )
        by_sample: dict[str, list[RecordStatus]] = {}
        for record in combined.records:
            by_sample.setdefault(record.sample_id, []).append(record.status)

        self.assertEqual(
            by_sample["CM1"],
            [RecordStatus.READY, RecordStatus.PENDING_RERUN],
        )
        self.assertEqual(
            by_sample["CM2"],
            [RecordStatus.READY, RecordStatus.DUPLICATE],
        )
        self.assertEqual(
            by_sample["CM3"],
            [RecordStatus.CONFLICT, RecordStatus.CONFLICT],
        )


if __name__ == "__main__":
    unittest.main()
