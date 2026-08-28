from __future__ import annotations

import csv
import re
from collections import Counter, defaultdict
from pathlib import Path

from automouse.config import TranslationConfig
from automouse.models import (
    RecordStatus,
    TranslatedGenotypeRecord,
    TranslationValidationReport,
)


def _normalize_name(value: str) -> str:
    return "".join(character.lower() for character in value.strip() if character.isalnum())


def _resolve_required(headers: list[str], expected: tuple[str, ...]) -> tuple[dict[str, str], list[str]]:
    buckets: dict[str, list[str]] = defaultdict(list)
    for header in headers:
        buckets[_normalize_name(header)].append(header)
    resolved: dict[str, str] = {}
    errors: list[str] = []
    for name in expected:
        matches = buckets.get(_normalize_name(name), [])
        if not matches:
            errors.append(f"Missing translated-output column: {name}")
        elif len(matches) > 1:
            errors.append(f"Ambiguous translated-output columns for {name}: {matches}")
        else:
            resolved[name] = matches[0]
    return resolved, errors


def _read_output(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        headers = reader.fieldnames or []
        rows = [
            {str(key): (value or "").strip() for key, value in row.items() if key is not None}
            for row in reader
        ]
    return headers, rows


def _unprotect_genotype(value: str) -> str:
    return value[1:] if value.startswith("'") else value


def validate_translated_records(
    path: Path,
    config: TranslationConfig,
    *,
    expected_raw_row_count: int | None = None,
    expected_sample_ids: list[str] | None = None,
) -> TranslationValidationReport:
    errors: list[str] = []
    warnings: list[str] = []
    records: list[TranslatedGenotypeRecord] = []

    if not path.exists() or not path.is_file():
        return TranslationValidationReport(
            False, [f"Translated output does not exist: {path}"], [], 0, [], {}
        )
    if path.stat().st_size == 0:
        return TranslationValidationReport(
            False, [f"Translated output is empty: {path}"], [], 0, [], {}
        )

    try:
        headers, rows = _read_output(path)
    except (OSError, UnicodeDecodeError, csv.Error) as error:
        return TranslationValidationReport(
            False, [f"Unable to read translated output {path}: {error}"], [], 0, [], {}
        )

    expected_columns = tuple(
        dict.fromkeys(
            (*config.required_columns, config.sample_id_column, config.genotype_column)
        )
    )
    resolved, column_errors = _resolve_required(headers, expected_columns)
    errors.extend(column_errors)
    sample_column = resolved.get(config.sample_id_column)
    genotype_column = resolved.get(config.genotype_column)

    if expected_raw_row_count is not None and len(rows) != expected_raw_row_count:
        errors.append(
            f"Row-count mismatch: raw input had {expected_raw_row_count} row(s), "
            f"translated output has {len(rows)} row(s)."
        )

    pattern = re.compile(config.approved_genotype_pattern) if config.approved_genotype_pattern else None
    failure_tokens = tuple(token.casefold() for token in config.failure_tokens)

    if sample_column and genotype_column:
        for source_row, row in enumerate(rows, start=2):
            sample_id = row.get(sample_column, "").strip()
            genotype = _unprotect_genotype(row.get(genotype_column, "").strip())
            row_warnings: list[str] = []

            if not sample_id:
                errors.append(f"Blank sample identifier at translated CSV row {source_row}.")
                status = RecordStatus.MANUAL_REVIEW
            elif not genotype:
                status = RecordStatus.NO_RESULT
                row_warnings.append("Translated genotype is blank.")
            elif any(token in genotype.casefold() for token in failure_tokens):
                status = RecordStatus.PENDING_RERUN
                row_warnings.append("Translated genotype contains a configured failure token.")
            elif config.approved_genotypes and genotype not in config.approved_genotypes:
                status = RecordStatus.MANUAL_REVIEW
                row_warnings.append("Translated genotype is not in the configured approved vocabulary.")
            elif pattern and not pattern.fullmatch(genotype):
                status = RecordStatus.MANUAL_REVIEW
                row_warnings.append("Translated genotype contains unexpected characters.")
            else:
                status = RecordStatus.READY

            records.append(
                TranslatedGenotypeRecord(
                    sample_id=sample_id,
                    mouse_id=sample_id or None,
                    assay=None,
                    raw_result=None,
                    translated_genotype=genotype or None,
                    status=status,
                    warnings=row_warnings,
                    source_row=source_row,
                    translated_strain=(row.get("Strain", "").strip() or None),
                    translated_sex=(row.get("Sex", "").strip() or None),
                )
            )

    by_sample: dict[str, list[TranslatedGenotypeRecord]] = defaultdict(list)
    for record in records:
        if record.sample_id:
            by_sample[record.sample_id].append(record)
    for sample_id, sample_records in by_sample.items():
        if len(sample_records) <= 1:
            continue
        genotypes = {record.translated_genotype for record in sample_records}
        conflict = len(genotypes) > 1
        replacement = RecordStatus.CONFLICT if conflict else RecordStatus.DUPLICATE
        for record in sample_records:
            record.status = replacement
            record.warnings.append(
                "Conflicting duplicate sample identifier."
                if conflict
                else "Agreeing duplicate sample identifier."
            )
        warnings.append(
            f"Sample {sample_id} appears {len(sample_records)} times with "
            f"{'conflicting' if conflict else 'agreeing'} genotype results."
        )

    actual_sample_ids = [record.sample_id for record in records]
    if expected_sample_ids is not None and Counter(actual_sample_ids) != Counter(expected_sample_ids):
        missing = list((Counter(expected_sample_ids) - Counter(actual_sample_ids)).elements())
        unexpected = list((Counter(actual_sample_ids) - Counter(expected_sample_ids)).elements())
        errors.append(
            "Sample identifiers changed or were lost during translation. "
            f"Missing: {missing[:20]}; unexpected: {unexpected[:20]}."
        )

    status_counts = Counter(record.status.value for record in records)
    if status_counts.get(RecordStatus.NO_RESULT.value):
        warnings.append(
            f"{status_counts[RecordStatus.NO_RESULT.value]} translated row(s) have no genotype result."
        )
    if status_counts.get(RecordStatus.PENDING_RERUN.value):
        warnings.append(
            f"{status_counts[RecordStatus.PENDING_RERUN.value]} translated row(s) require rerun/review."
        )
    if status_counts.get(RecordStatus.MANUAL_REVIEW.value):
        warnings.append(
            f"{status_counts[RecordStatus.MANUAL_REVIEW.value]} translated row(s) require manual review."
        )

    return TranslationValidationReport(
        valid=not errors,
        errors=errors,
        warnings=warnings,
        row_count=len(rows),
        records=records,
        status_counts=dict(sorted(status_counts.items())),
        metadata={
            "headers": headers,
            "sample_id_column": sample_column or config.sample_id_column,
            "genotype_column": genotype_column or config.genotype_column,
        },
    )
