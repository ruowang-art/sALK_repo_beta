from __future__ import annotations

import json
import os
from pathlib import Path

from automouse.models import RunContext


def write_run_summary(context: RunContext, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(context.to_summary(), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    os.replace(temporary, output_path)
    return output_path


def write_translation_validation(report: object, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = report.to_dict(include_records=True)  # type: ignore[attr-defined]
    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(temporary, output_path)
    return output_path

