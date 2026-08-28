"""Ties reading, consolidation, and writing together. Used by both the CLI
and the web app, so neither one duplicates this logic.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from xolpotsxol.cage_card_reader import read_cage_card_workbook
from xolpotsxol.consolidator import (
    DEFAULT_FEMALE_DOB_WINDOW_DAYS,
    DEFAULT_MALE_DOB_WINDOW_DAYS,
    consolidate,
)
from xolpotsxol.models import ConsolidationResult
from xolpotsxol.writer import build_consolidated_workbook


def run_consolidation(
    uploaded_files: list[tuple[Path, str]],
    output_path: Path,
    *,
    male_dob_window_days: int = DEFAULT_MALE_DOB_WINDOW_DAYS,
    female_dob_window_days: int = DEFAULT_FEMALE_DOB_WINDOW_DAYS,
) -> tuple[ConsolidationResult, list[str]]:
    """Read every uploaded workbook, consolidate across all of them
    together, and write one new Live Label-format workbook. Returns the
    consolidation result and any warnings raised while reading the inputs.
    """
    all_mice = []
    read_warnings: list[str] = []
    input_reports: list[dict] = []
    for path, filename in uploaded_files:
        mice, warnings = read_cage_card_workbook(path, filename)
        all_mice.extend(mice)
        read_warnings.extend(warnings)
        input_reports.append(
            {
                "filename": filename,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "row_count": len(mice),
            }
        )

    result = consolidate(
        all_mice,
        male_dob_window_days=male_dob_window_days,
        female_dob_window_days=female_dob_window_days,
    )
    build_consolidated_workbook(result, output_path, input_reports=input_reports)
    return result, read_warnings
