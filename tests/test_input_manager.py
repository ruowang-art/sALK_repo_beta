from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from automouse.exceptions import DuplicateInputError
from automouse.input_manager import archive_input_file, calculate_sha256
from automouse.models import RunContext


FIXTURES = Path(__file__).parent / "fixtures"


class InputManagerTests(unittest.TestCase):
    def test_archive_is_verified_and_duplicate_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "archive"
            first_context = RunContext("20260730_120000_abcd", datetime.now(timezone.utc))
            destination = archive_input_file(
                FIXTURES / "raw_valid.csv", archive, first_context
            )
            self.assertEqual(
                calculate_sha256(FIXTURES / "raw_valid.csv"),
                calculate_sha256(destination),
            )

            second_context = RunContext("20260730_120001_ef12", datetime.now(timezone.utc))
            with self.assertRaises(DuplicateInputError):
                archive_input_file(FIXTURES / "raw_valid.csv", archive, second_context)


if __name__ == "__main__":
    unittest.main()

