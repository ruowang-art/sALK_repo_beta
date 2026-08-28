from __future__ import annotations

import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from automouse.exceptions import DuplicateInputError, InputValidationError
from automouse.models import RunContext


def calculate_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_index(index_path: Path) -> dict[str, Any]:
    if not index_path.exists():
        return {"version": 1, "entries": []}
    try:
        value = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise InputValidationError(f"Unable to read checksum index {index_path}: {error}") from error
    if not isinstance(value, dict) or not isinstance(value.get("entries"), list):
        raise InputValidationError(f"Checksum index has an invalid structure: {index_path}")
    return value


def _write_index(index_path: Path, value: dict[str, Any]) -> None:
    temporary = index_path.with_suffix(index_path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(temporary, index_path)


def archive_input_file(
    source: Path,
    archive_directory: Path,
    run_context: RunContext,
    *,
    supported_extensions: tuple[str, ...] = (".csv",),
    allow_duplicate: bool = False,
    archive_tag: str | None = None,
) -> Path:
    source = source.expanduser().resolve()
    if not source.exists():
        raise InputValidationError(f"Input file does not exist: {source}")
    if not source.is_file():
        raise InputValidationError(f"Input path is not a regular file: {source}")
    if source.suffix.lower() not in supported_extensions:
        raise InputValidationError(
            f"Unsupported input extension {source.suffix!r}; expected one of "
            f"{', '.join(supported_extensions)}"
        )

    archive_directory.mkdir(parents=True, exist_ok=True)
    checksum = calculate_sha256(source)
    index_path = archive_directory / "checksum_index.json"
    index = _load_index(index_path)
    previous = [entry for entry in index["entries"] if entry.get("sha256") == checksum]
    if previous and not allow_duplicate:
        previous_runs = ", ".join(str(entry.get("run_id", "unknown")) for entry in previous)
        raise DuplicateInputError(
            f"This exact raw file was already archived in run(s): {previous_runs}. "
            "Use --allow-duplicate-input only for an intentional retry."
        )

    safe_stem = "".join(
        character if character.isalnum() or character in "-_" else "_"
        for character in source.stem
    ).strip("_") or "transnetyx"
    safe_tag = ""
    if archive_tag:
        safe_tag_value = "".join(
            character if character.isalnum() or character in "-_" else "_"
            for character in archive_tag
        ).strip("_")
        safe_tag = f"_{safe_tag_value}" if safe_tag_value else ""
    destination = archive_directory / (
        f"transnetyx_raw_{run_context.run_id}{safe_tag}_{safe_stem}"
        f"{source.suffix.lower()}"
    )
    if destination.exists():
        raise InputValidationError(f"Refusing to overwrite archive file: {destination}")

    shutil.copy2(source, destination)
    if calculate_sha256(destination) != checksum:
        destination.unlink(missing_ok=True)
        raise InputValidationError(f"Checksum mismatch after archiving {source}")

    index["entries"].append(
        {
            "run_id": run_context.run_id,
            "sha256": checksum,
            "source_path": str(source),
            "archived_path": str(destination),
            "archived_at": datetime.now(timezone.utc).isoformat(),
            "status": "archived",
        }
    )
    _write_index(index_path, index)
    run_context.checksum = checksum
    run_context.checksums[str(source)] = checksum
    return destination


def update_archive_status(
    archive_directory: Path,
    run_id: str,
    status: str,
) -> None:
    index_path = archive_directory / "checksum_index.json"
    index = _load_index(index_path)
    for entry in index["entries"]:
        if entry.get("run_id") == run_id:
            entry["status"] = status
            entry["updated_at"] = datetime.now(timezone.utc).isoformat()
    _write_index(index_path, index)
