from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path
from typing import Iterable

from automouse.config import TransnetyxConfig
from automouse.models import ValidationResult


def _normalize_name(value: str) -> str:
    return "".join(character.lower() for character in value.strip() if character.isalnum())


def _resolve_columns(headers: Iterable[str], expected: Iterable[str]) -> tuple[dict[str, str], list[str]]:
    header_list = list(headers)
    normalized: dict[str, list[str]] = {}
    for header in header_list:
        normalized.setdefault(_normalize_name(header), []).append(header)

    resolved: dict[str, str] = {}
    errors: list[str] = []
    for name in expected:
        matches = normalized.get(_normalize_name(name), [])
        if not matches:
            errors.append(f"Missing required column: {name}")
        elif len(matches) > 1:
            errors.append(f"Ambiguous columns for {name}: {', '.join(matches)}")
        else:
            resolved[name] = matches[0]
    return resolved, errors


def read_csv_rows(path: Path, config: TransnetyxConfig) -> tuple[list[str], list[dict[str, str]]]:
    try:
        with path.open("r", encoding=config.encoding, newline="") as stream:
            reader = csv.DictReader(stream, delimiter=config.delimiter, strict=True)
            headers = reader.fieldnames or []
            rows = []
            for row_number, row in enumerate(reader, start=2):
                if None in row:
                    raise ValueError(
                        f"CSV row {row_number} has more fields than the header; "
                        "check the delimiter and quoting."
                    )
                rows.append(
                    {str(key): (value or "").strip() for key, value in row.items()}
                )
    except UnicodeDecodeError as error:
        raise ValueError(
            f"Unable to decode CSV as {config.encoding}; byte offset {error.start}."
        ) from error
    except csv.Error as error:
        raise ValueError(f"Unable to parse CSV: {error}") from error
    return headers, rows


def validate_transnetyx_csv(path: Path, config: TransnetyxConfig) -> ValidationResult:
    errors: list[str] = []
    warnings: list[str] = []
    metadata: dict[str, object] = {}

    if not path.exists():
        return ValidationResult(False, [f"File does not exist: {path}"])
    if not path.is_file():
        return ValidationResult(False, [f"Path is not a regular file: {path}"])
    if path.stat().st_size == 0:
        return ValidationResult(False, [f"CSV is empty: {path}"])
    if path.suffix.lower() not in config.supported_extensions:
        errors.append(
            f"Unsupported extension {path.suffix!r}; expected one of "
            f"{', '.join(config.supported_extensions)}"
        )

    try:
        headers, rows = read_csv_rows(path, config)
    except (OSError, ValueError) as error:
        errors.append(str(error))
        return ValidationResult(False, errors, warnings, 0, metadata)

    if not headers:
        errors.append("CSV has no header row.")
    if not rows:
        errors.append("CSV has no data rows.")

    expected = tuple(dict.fromkeys((*config.required_columns, config.sample_id_column)))
    resolved, column_errors = _resolve_columns(headers, expected)
    errors.extend(column_errors)

    sample_column = resolved.get(config.sample_id_column)
    sample_ids: list[str] = []
    if sample_column:
        sample_ids = [row.get(sample_column, "").strip() for row in rows]
        blank_rows = [index + 2 for index, value in enumerate(sample_ids) if not value]
        if blank_rows:
            errors.append(
                "Blank sample identifiers at CSV row(s): "
                + ", ".join(map(str, blank_rows[:20]))
            )
        duplicates = sorted(
            sample for sample, count in Counter(sample_ids).items() if sample and count > 1
        )
        if duplicates:
            warnings.append(
                "Duplicate sample identifiers detected: " + ", ".join(duplicates[:20])
            )
            metadata["duplicate_sample_ids"] = duplicates

    row_signatures = [tuple(row.get(header, "") for header in headers) for row in rows]
    duplicate_row_count = sum(count - 1 for count in Counter(row_signatures).values() if count > 1)
    if duplicate_row_count:
        warnings.append(f"Detected {duplicate_row_count} duplicate data row(s).")

    metadata_normalized = {_normalize_name(value) for value in config.metadata_columns}
    assay_columns = [
        header for header in headers if _normalize_name(header) not in metadata_normalized
    ]
    if not assay_columns:
        errors.append("No assay columns were found after excluding configured metadata columns.")
    elif config.require_any_assay_value and not any(
        row.get(column, "").strip() for row in rows for column in assay_columns
    ):
        errors.append("All inferred assay-result fields are blank.")

    metadata.update(
        {
            "headers": headers,
            "sample_id_column": sample_column or config.sample_id_column,
            "sample_ids": sample_ids,
            "assay_columns": assay_columns,
            "assay_column_count": len(assay_columns),
            "duplicate_row_count": duplicate_row_count,
            "delimiter": config.delimiter,
            "encoding": config.encoding,
        }
    )
    return ValidationResult(not errors, errors, warnings, len(rows), metadata)
