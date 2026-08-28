from __future__ import annotations

import logging
import subprocess
import time
from pathlib import Path

from automouse.config import RConfig
from automouse.exceptions import RTranslationError
from automouse.models import RRunResult


def run_r_translation(
    input_path: Path,
    output_path: Path,
    config: RConfig,
    *,
    logger: logging.Logger | None = None,
) -> RRunResult:
    if not config.executable.is_file():
        raise RTranslationError(f"Rscript executable not found: {config.executable}")
    if not config.translation_script.is_file():
        raise RTranslationError(f"R translation script not found: {config.translation_script}")
    if not config.wrapper_script.is_file():
        raise RTranslationError(f"R wrapper script not found: {config.wrapper_script}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        raise RTranslationError(f"Refusing to overwrite translated output: {output_path}")

    command = [
        str(config.executable),
        str(config.wrapper_script),
        "--translation-script",
        str(config.translation_script),
        "--input",
        str(input_path),
        "--output",
        str(output_path),
    ]
    if not config.print_diagnostics:
        command.append("--quiet-diagnostics")

    if logger:
        logger.info("Starting R translation for %s", input_path)
        logger.debug("R command arguments: %r", command)

    started = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=config.timeout_seconds,
            check=False,
            shell=False,
        )
    except subprocess.TimeoutExpired as error:
        if logger:
            logger.debug("Partial R stdout before timeout:\n%s", error.stdout or "")
            logger.debug("Partial R stderr before timeout:\n%s", error.stderr or "")
        raise RTranslationError(
            f"R translation timed out after {config.timeout_seconds} seconds for {input_path}. "
            "The archived input remains valid; no inventory was modified."
        ) from error
    except OSError as error:
        raise RTranslationError(f"Unable to start R translation: {error}") from error

    duration = time.monotonic() - started
    if logger:
        logger.debug("R stdout:\n%s", completed.stdout)
        logger.debug("R stderr:\n%s", completed.stderr)
        logger.info("R translation exit code: %d", completed.returncode)

    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "No console output."
        raise RTranslationError(
            f"R translation failed with exit code {completed.returncode}: {detail} "
            "The archived input remains valid; no inventory was modified."
        )
    if not output_path.is_file():
        raise RTranslationError(
            f"R translation reported success but did not create {output_path}."
        )
    if output_path.stat().st_size == 0:
        raise RTranslationError(f"R translation created an empty output file: {output_path}")

    return RRunResult(
        command=command,
        exit_code=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        output_path=output_path,
        duration_seconds=duration,
    )
