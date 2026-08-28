from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from automouse.config import TransnetyxConfig
from automouse.transnetyx_validator import validate_transnetyx_csv


FIXTURES = Path(__file__).parent / "fixtures"


class InputValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = TransnetyxConfig()

    def test_valid_wide_transnetyx_csv(self) -> None:
        result = validate_transnetyx_csv(FIXTURES / "raw_valid.csv", self.config)
        self.assertTrue(result.valid, result.errors)
        self.assertEqual(result.row_count, 2)
        self.assertEqual(result.metadata["sample_ids"], ["CM0001", "CM0002"])

    def test_empty_csv_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "empty.csv"
            path.write_bytes(b"")
            result = validate_transnetyx_csv(path, self.config)
        self.assertFalse(result.valid)
        self.assertIn("empty", result.errors[0].lower())

    def test_missing_required_column_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "missing.csv"
            path.write_text("Sample,G12D mut\nCM1,+-\n", encoding="utf-8")
            result = validate_transnetyx_csv(path, self.config)
        self.assertFalse(result.valid)
        self.assertTrue(any("Strain" in error for error in result.errors))

    def test_duplicate_sample_id_warns(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "duplicate.csv"
            path.write_text(
                "Sample,Strain,G12D mut\nCM1,Kras,+-\nCM1,Kras,--\n",
                encoding="utf-8",
            )
            result = validate_transnetyx_csv(path, self.config)
        self.assertTrue(result.valid, result.errors)
        self.assertTrue(any("Duplicate sample" in warning for warning in result.warnings))

    def test_invalid_encoding_has_readable_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.csv"
            path.write_bytes(b"Sample,Strain,G12D mut\nCM1,Kras,\xff\n")
            result = validate_transnetyx_csv(path, self.config)
        self.assertFalse(result.valid)
        self.assertTrue(any("decode" in error.lower() for error in result.errors))


if __name__ == "__main__":
    unittest.main()

