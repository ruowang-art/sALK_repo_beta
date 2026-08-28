from __future__ import annotations

import logging
import platform
import secrets
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path

from automouse.cage_card_formatter import build_cage_card_records, generate_cage_cards
from automouse.config import AppConfig
from automouse.exception_report import write_exception_report
from automouse.exceptions import (
    ConfigurationError,
    InputValidationError,
    TranslationValidationError,
)
from automouse.input_manager import (
    archive_input_file,
    calculate_sha256,
    update_archive_status,
)
from automouse.inventory_manager import (
    InventoryTable,
    backup_inventory,
    ensure_audit_columns,
    load_inventory,
    save_updated_inventory,
    write_audit_csv,
)
from automouse.litter_entry import LitterSubmission, expand_litter
from automouse.logging_setup import configure_run_logging
from automouse.models import (
    AuditAction,
    AuditEntry,
    CageCardRecord,
    InventoryUpdateReport,
    RecordStatus,
    RunContext,
    RunStage,
    TranslatedGenotypeRecord,
    TranslationValidationReport,
)
from automouse.paths import RuntimePaths, initialize_runtime_directories
from automouse.sheets_overlay import SheetsOverlayError, apply_dob_wean_overlay, fetch_dob_wean_overlay
from automouse.r_runner import run_r_translation
from automouse.record_matcher import apply_inventory_updates
from automouse.summary import write_run_summary, write_translation_validation
from automouse.translation_validator import validate_translated_records
from automouse.transnetyx_validator import validate_transnetyx_csv


def generate_run_id(now: datetime | None = None) -> str:
    timestamp = now or datetime.now().astimezone()
    return f"{timestamp.strftime('%Y%m%d_%H%M%S')}_{secrets.token_hex(2)}"


def _summary_path(paths: RuntimePaths, run_id: str) -> Path:
    return paths.completed_runs / f"run_summary_{run_id}.json"


def _safe_stem(path: Path) -> str:
    return (
        "".join(
            character if character.isalnum() or character in "-_" else "_"
            for character in path.stem
        ).strip("_")
        or "transnetyx"
    )


def _preflight_sources(
    sources: Sequence[Path], config: AppConfig
) -> tuple[list[Path], dict[str, str]]:
    if not sources:
        raise InputValidationError("Select at least one raw Transnetyx CSV file.")
    resolved: list[Path] = []
    checksums: dict[str, str] = {}
    checksum_sources: dict[str, Path] = {}
    for source in sources:
        path = source.expanduser().resolve()
        if not path.is_file():
            raise InputValidationError(f"Input file does not exist: {path}")
        if path.suffix.lower() not in config.transnetyx.supported_extensions:
            raise InputValidationError(
                f"Unsupported input extension {path.suffix!r} for {path}; expected "
                + ", ".join(config.transnetyx.supported_extensions)
            )
        checksum = calculate_sha256(path)
        if checksum in checksum_sources:
            raise InputValidationError(
                "The same raw file content was selected more than once in this batch: "
                f"{checksum_sources[checksum]} and {path}."
            )
        checksum_sources[checksum] = path
        checksums[str(path)] = checksum
        resolved.append(path)
    return resolved, checksums


def _merge_translation_reports(
    reports: list[TranslationValidationReport],
    source_paths: list[Path],
) -> TranslationValidationReport:
    records = [record for report in reports for record in report.records]
    warnings = [warning for report in reports for warning in report.warnings]
    errors = [error for report in reports for error in report.errors]

    by_sample: dict[str, list[TranslatedGenotypeRecord]] = defaultdict(list)
    for record in records:
        if record.sample_id:
            by_sample[record.sample_id].append(record)

    for sample_id, sample_records in by_sample.items():
        ready = [
            record
            for record in sample_records
            if record.status in {RecordStatus.READY, RecordStatus.READY_WITH_WARNING}
        ]
        if len(ready) <= 1:
            continue
        genotypes = {record.translated_genotype for record in ready}
        if len(genotypes) > 1:
            for record in ready:
                record.status = RecordStatus.CONFLICT
                record.warnings.append(
                    "Conflicting READY genotype result across batch inputs."
                )
            warnings.append(
                f"Sample {sample_id} has conflicting READY results across batch inputs."
            )
        else:
            for duplicate in ready[1:]:
                duplicate.status = RecordStatus.DUPLICATE
                duplicate.warnings.append(
                    "Agreeing READY result duplicated across batch inputs; first result used."
                )
            warnings.append(
                f"Sample {sample_id} has {len(ready)} agreeing READY results; "
                "the first result is canonical."
            )

    status_counts = Counter(record.status.value for record in records)
    return TranslationValidationReport(
        valid=not errors,
        errors=errors,
        warnings=sorted(set(warnings)),
        row_count=sum(report.row_count for report in reports),
        records=records,
        status_counts=dict(sorted(status_counts.items())),
        metadata={
            "batch_file_count": len(reports),
            "source_files": [str(path) for path in source_paths],
            "per_file": [report.metadata for report in reports],
        },
    )


def _r_version(executable: Path) -> str:
    try:
        result = subprocess.run(
            [str(executable), "--version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except OSError:
        return ""
    first_line = (result.stdout or result.stderr or "").splitlines()
    return first_line[0].strip() if first_line else ""


def _build_run_environment(config: AppConfig) -> dict[str, object]:
    environment: dict[str, object] = {
        "application_version": config.application_version,
        "python_version": sys.version.split()[0],
        "r_version": _r_version(config.r.executable),
        "os": platform.system(),
        "os_version": platform.mac_ver()[0] or platform.release(),
        "machine_arch": platform.machine(),
        "sheets_overlay_enabled": bool(
            config.sheets_overlay and config.sheets_overlay.enabled
        ),
    }
    if config.config_path is not None:
        environment["config_path"] = str(config.config_path)
        try:
            environment["config_sha256"] = calculate_sha256(config.config_path)
        except OSError:
            environment["config_sha256"] = ""
    return environment


def run_phase_1_2(
    source: Path,
    config: AppConfig,
    *,
    allow_duplicate_input: bool = False,
    dry_run: bool = False,
    verbose: bool = False,
    complete_pipeline: bool = False,
) -> RunContext:
    """Backward-compatible one-file wrapper around the consolidated batch runner."""
    return run_batch(
        [source],
        config,
        allow_duplicate_input=allow_duplicate_input,
        dry_run=dry_run,
        verbose=verbose,
        complete_pipeline=complete_pipeline,
    )


def run_batch(
    sources: Sequence[Path],
    config: AppConfig,
    *,
    allow_duplicate_input: bool = False,
    dry_run: bool = False,
    verbose: bool = False,
    complete_pipeline: bool = True,
) -> RunContext:
    """Run the batch pipeline.

    ``complete_pipeline=False`` stops after translation validation (the
    ``translate`` command). ``complete_pipeline=True`` (the ``run`` command)
    also updates the inventory's genotype and generates the exception
    report and Live Label cage cards.
    """
    implementation_scope = (
        "complete_batch_genotype_inventory_and_weaning_card_pipeline"
        if complete_pipeline
        else "batch_translation"
    )

    source_paths, preflight_checksums = _preflight_sources(sources, config)
    paths = initialize_runtime_directories(config)
    context = RunContext(
        run_id=generate_run_id(),
        started_at=datetime.now(timezone.utc),
        dry_run=dry_run,
        implementation_scope=implementation_scope,
    )
    context.environment.update(_build_run_environment(config))
    context.counts["input_file_count"] = len(source_paths)
    context.checksums.update(preflight_checksums)
    context.artifacts["raw_input_files"] = [str(path) for path in source_paths]
    context.artifacts["raw_input_file"] = str(source_paths[0])

    log_path = paths.logs / f"automouse_{context.run_id}.log"
    logger = configure_run_logging(log_path, verbose=verbose)
    context.artifacts["log_file"] = str(log_path)
    logger.info("Möuseley Kräs run ID: %s", context.run_id)
    logger.info("Application version: %s", config.application_version)
    logger.info("Implementation scope: %s", context.implementation_scope)
    logger.info("Input file count: %d", len(source_paths))
    logger.info("Dry run: %s", dry_run)

    try:
        archived_paths: list[Path] = []
        for index, source in enumerate(source_paths, start=1):
            archived = archive_input_file(
                source,
                paths.raw_archive,
                context,
                supported_extensions=config.transnetyx.supported_extensions,
                allow_duplicate=allow_duplicate_input,
                archive_tag=f"{index:03d}",
            )
            archived_paths.append(archived)
            logger.info("Archived batch input %d/%d: %s", index, len(source_paths), archived)
        if len(source_paths) > 1:
            context.checksum = None
        context.artifacts["archived_input_files"] = [str(path) for path in archived_paths]
        context.artifacts["archived_input_file"] = str(archived_paths[0])
        context.advance(RunStage.INPUT_ARCHIVED)
        update_archive_status(paths.raw_archive, context.run_id, context.stage.value)

        raw_validations = []
        for source, archived in zip(source_paths, archived_paths, strict=True):
            validation = validate_transnetyx_csv(archived, config.transnetyx)
            context.warnings.extend(f"{source.name}: {item}" for item in validation.warnings)
            for warning in validation.warnings:
                logger.warning("Raw validation %s: %s", source.name, warning)
            if not validation.valid:
                raise InputValidationError(
                    f"Raw Transnetyx validation failed for {source}:\n- "
                    + "\n- ".join(validation.errors)
                )
            raw_validations.append(validation)
        context.counts["raw_record_count"] = sum(
            validation.row_count for validation in raw_validations
        )
        context.advance(RunStage.RAW_VALIDATED)
        update_archive_status(paths.raw_archive, context.run_id, context.stage.value)

        translated_paths: list[Path] = []
        r_results = []
        for index, (source, archived) in enumerate(
            zip(source_paths, archived_paths, strict=True), start=1
        ):
            translated_path = paths.translated_genotypes / (
                f"translated_genotypes_{context.run_id}_{index:03d}_"
                f"{_safe_stem(source)}.csv"
            )
            result = run_r_translation(
                archived,
                translated_path,
                config.r,
                logger=logger,
            )
            translated_paths.append(result.output_path)
            r_results.append(result)
            if "Warning message:" in result.stderr or "Warning messages:" in result.stderr:
                context.warnings.append(
                    f"{source.name}: R reported warning(s); review the run log."
                )
            logger.info(
                "Translated batch input %d/%d in %.3f seconds",
                index,
                len(source_paths),
                result.duration_seconds,
            )
        context.artifacts["translated_output_files"] = [
            str(path) for path in translated_paths
        ]
        context.artifacts["translated_output_file"] = str(translated_paths[0])
        context.advance(RunStage.TRANSLATED)
        update_archive_status(paths.raw_archive, context.run_id, context.stage.value)

        reports: list[TranslationValidationReport] = []
        per_file_validation_paths: list[Path] = []
        for index, (source, translated_path, raw_validation) in enumerate(
            zip(source_paths, translated_paths, raw_validations, strict=True), start=1
        ):
            report = validate_translated_records(
                translated_path,
                config.translation,
                expected_raw_row_count=raw_validation.row_count,
                expected_sample_ids=list(raw_validation.metadata.get("sample_ids", [])),
            )
            for record in report.records:
                record.source_file = str(translated_path)
            validation_path = paths.translated_genotypes / (
                f"translation_validation_{context.run_id}_{index:03d}_"
                f"{_safe_stem(source)}.json"
            )
            write_translation_validation(report, validation_path)
            per_file_validation_paths.append(validation_path)
            if not report.valid:
                raise TranslationValidationError(
                    f"Translated-output validation failed for {source}:\n- "
                    + "\n- ".join(report.errors)
                )
            reports.append(report)

        combined_report = _merge_translation_reports(reports, source_paths)
        combined_validation_path = paths.translated_genotypes / (
            f"translation_validation_{context.run_id}.json"
        )
        write_translation_validation(combined_report, combined_validation_path)
        context.artifacts["translation_validation_files"] = [
            str(path) for path in per_file_validation_paths
        ]
        context.artifacts["translation_validation_file"] = str(
            combined_validation_path
        )
        context.warnings.extend(combined_report.warnings)
        context.counts["translated_record_count"] = combined_report.row_count
        context.advance(RunStage.TRANSLATION_VALIDATED)
        update_archive_status(paths.raw_archive, context.run_id, context.stage.value)

        if complete_pipeline:
            _complete_inventory_and_cage_card_pipeline(
                config=config,
                paths=paths,
                context=context,
                translated_report=combined_report,
                translated_source=translated_paths[0],
                dry_run=dry_run,
                logger=logger,
            )

        context.finish(RunStage.COMPLETED)
        update_archive_status(paths.raw_archive, context.run_id, context.stage.value)
        logger.info("Möuseley Kräs batch workflow completed successfully.")
        return context
    except Exception as error:
        context.failed_stage = context.stage.value
        context.errors.append(str(error))
        context.finish(RunStage.FAILED)
        try:
            update_archive_status(paths.raw_archive, context.run_id, context.stage.value)
        except Exception:
            logger.exception("Unable to update archive status after failure.")
        logger.exception("Möuseley Kräs batch failed after stage %s", context.failed_stage)
        raise
    finally:
        output_hashes: dict[str, str] = {}
        for key in (
            "translated_output_file",
            "translation_validation_file",
            "audit_file",
            "exception_report_file",
            "updated_inventory_csv_file",
            "cage_card_file",
        ):
            artifact_path = context.artifacts.get(key)
            if artifact_path and Path(artifact_path).is_file():
                output_hashes[key] = calculate_sha256(Path(artifact_path))
        context.environment["output_sha256_by_file"] = output_hashes

        summary_path = _summary_path(paths, context.run_id)
        context.artifacts["run_summary_file"] = str(summary_path)
        write_run_summary(context, summary_path)
        logging.shutdown()


def _update_inventory_stage(
    *,
    config: AppConfig,
    paths: RuntimePaths,
    context: RunContext,
    translated_report: TranslationValidationReport,
    translated_source: Path,
    dry_run: bool,
    logger: logging.Logger,
) -> tuple[InventoryTable, InventoryUpdateReport]:
    """Load, back up, and match against the inventory. Shared by the combined
    pipeline and the standalone ``update-inventory`` command; neither writes
    the audit CSV, the updated inventory copy, nor cage cards here.
    """
    if config.inventory is None:
        raise ConfigurationError(
            "This command requires an inventory section in the configuration."
        )

    inventory = load_inventory(config.inventory.file, config.inventory)
    context.counts["inventory_record_count"] = len(inventory.rows)
    inventory_label = "inventory seed" if config.inventory.append_only else "master inventory"
    logger.info("Validated %s: %d rows", inventory_label, len(inventory.rows))

    backup_path = paths.inventory_backups / (
        f"mouse_inventory_backup_{context.run_id}{config.inventory.file.suffix}"
    )
    backup_inventory(config.inventory.file, backup_path)
    context.artifacts["inventory_backup_file"] = str(backup_path)
    context.advance(RunStage.INVENTORY_BACKED_UP)
    update_archive_status(paths.raw_archive, context.run_id, context.stage.value)

    update_report = apply_inventory_updates(
        inventory,
        translated_report,
        run_id=context.run_id,
        source_file=translated_source,
        append_only=config.inventory.append_only,
        dry_run=dry_run,
    )
    context.warnings.extend(update_report.warnings)
    action_counts = update_report.action_counts
    context.counts["inventory_records_updated"] = len(update_report.updated_mouse_ids)
    context.counts["inventory_records_confirmed"] = len(update_report.confirmed_mouse_ids)
    context.counts["mouse_not_found_count"] = action_counts.get(
        AuditAction.NOT_FOUND.value, 0
    )
    context.counts["multiple_match_count"] = action_counts.get(
        AuditAction.MULTIPLE_MATCHES.value, 0
    )
    context.counts["conflict_count"] = action_counts.get(AuditAction.CONFLICT.value, 0)
    context.counts["manual_review_count"] = action_counts.get(
        AuditAction.MANUAL_REVIEW.value, 0
    )
    proposed_update_count = action_counts.get(AuditAction.PROPOSED_UPDATE.value, 0)
    context.counts["proposed_update_count"] = proposed_update_count
    if proposed_update_count:
        # A dry run never appends the new row an append-only inventory would
        # otherwise gain, so there is no inventory row yet for these mice to
        # build a cage card from; without this warning a dry run over an
        # all-new batch silently produces a header-only cage-card workbook.
        context.warnings.append(
            f"{proposed_update_count} record(s) would append new inventory row(s) "
            "(preview only); cage cards for these mice are not previewed in a dry "
            "run and will only appear once the batch is run for real."
        )
    return inventory, update_report


def _save_inventory_stage_output(
    *,
    config: AppConfig,
    paths: RuntimePaths,
    context: RunContext,
    inventory: InventoryTable,
    update_report: InventoryUpdateReport,
    dry_run: bool,
    logger: logging.Logger,
) -> None:
    if dry_run:
        return
    inventory_csv_path = paths.updated_inventory / (
        f"mouse_inventory_updated_{context.run_id}.csv"
    )
    inventory_xlsx_path = paths.updated_inventory / (
        f"mouse_inventory_updated_{context.run_id}.xlsx"
    )
    updated_values = {
        entry.mouse_id: entry.final_genotype
        for entry in update_report.audit_entries
        if entry.action == AuditAction.UPDATED
        and entry.mouse_id
        and entry.final_genotype is not None
    }
    save_updated_inventory(
        inventory,
        inventory_csv_path,
        inventory_xlsx_path,
        updated_values=updated_values,
    )
    if config.inventory.append_only:
        config.inventory.file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(inventory_csv_path, config.inventory.file)
        logger.info("Copied rebuilt inventory back to %s", config.inventory.file)
    context.artifacts["updated_inventory_csv_file"] = str(inventory_csv_path)
    context.artifacts["updated_inventory_file"] = str(inventory_xlsx_path)
    context.advance(RunStage.INVENTORY_UPDATED)
    update_archive_status(paths.raw_archive, context.run_id, context.stage.value)
    logger.info(
        "Wrote one consolidated inventory copy with %d genotype update(s).",
        len(updated_values),
    )


def _compute_eligible_mouse_ids(
    audit_entries: list[AuditEntry],
    config: AppConfig,
) -> set[str]:
    eligible_actions = set(config.cage_card.generate_for_actions)
    eligible_statuses = {RecordStatus.READY, RecordStatus.READY_WITH_WARNING}
    if config.inventory.append_only:
        eligible_actions.add(AuditAction.DUPLICATE.value)
        eligible_statuses.add(RecordStatus.DUPLICATE)
    return {
        entry.mouse_id
        for entry in audit_entries
        if entry.mouse_id
        and entry.action.value in eligible_actions
        and entry.status in eligible_statuses
    }


def _apply_sheet_dob_wean_overlay(
    inventory: InventoryTable,
    config: AppConfig,
    logger: logging.Logger,
    *,
    fill_log: list[str] | None = None,
) -> list[str]:
    """Fill blank DOB/Wean_By cells in ``inventory`` from the primary Google
    Sheet, if ``sheets_overlay`` is configured and enabled. Never raises: a
    fetch failure is returned as a warning so the batch still completes,
    using whatever DOB/Wean_By values the local inventory copy already has.
    If ``fill_log`` is provided, a per-mouse-ID message is appended for every
    cell actually filled, for run-manifest auditability.
    """
    if config.sheets_overlay is None or not config.sheets_overlay.enabled:
        return []
    if config.inventory is None:
        return []
    try:
        overlay = fetch_dob_wean_overlay(config.sheets_overlay, config.inventory)
        apply_dob_wean_overlay(inventory, overlay, logger, fill_log=fill_log)
    except SheetsOverlayError as error:
        logger.warning("Google Sheet DOB/Wean_By overlay skipped: %s", error)
        return [
            f"Could not refresh DOB/Wean_By from the Google Sheet ({error}); "
            "cage cards were built from the local inventory copy only."
        ]
    return []


def _build_cage_cards_for_report(
    inventory: InventoryTable,
    update_report: InventoryUpdateReport,
    eligible_mouse_ids: set[str],
    config: AppConfig,
) -> tuple[list[CageCardRecord], dict[str, str], list[str], int]:
    """Build cage-card records and fold the grouping-issue feedback back
    into ``update_report`` (its exception-eligible sets, and the matching
    audit entries' messages) exactly as the combined pipeline always has.
    """
    update_report.card_eligible_mouse_ids.update(eligible_mouse_ids)
    cage_records, grouping_issues, cage_warnings = build_cage_card_records(
        inventory,
        eligible_mouse_ids,
        config.cage_card,
    )
    update_report.card_grouping_exception_mouse_ids.update(grouping_issues)
    for entry in update_report.audit_entries:
        if entry.mouse_id in grouping_issues:
            entry.messages.append(grouping_issues[entry.mouse_id])
    update_report.warnings.extend(cage_warnings)
    weaning_group_count = len({record.cage_id for record in cage_records})
    return cage_records, grouping_issues, cage_warnings, weaning_group_count


def _complete_inventory_and_cage_card_pipeline(
    *,
    config: AppConfig,
    paths: RuntimePaths,
    context: RunContext,
    translated_report: TranslationValidationReport,
    translated_source: Path,
    dry_run: bool,
    logger: logging.Logger,
) -> None:
    if config.cage_card is None:
        raise ConfigurationError(
            "The 'run' command requires a cage_card section in the configuration."
        )

    inventory, update_report = _update_inventory_stage(
        config=config,
        paths=paths,
        context=context,
        translated_report=translated_report,
        translated_source=translated_source,
        dry_run=dry_run,
        logger=logger,
    )

    sheets_overlay_fills: list[str] = []
    context.warnings.extend(
        _apply_sheet_dob_wean_overlay(
            inventory, config, logger, fill_log=sheets_overlay_fills
        )
    )
    context.environment["sheets_overlay_fills"] = sheets_overlay_fills

    eligible_mouse_ids = _compute_eligible_mouse_ids(update_report.audit_entries, config)
    cage_records, grouping_issues, cage_warnings, weaning_group_count = (
        _build_cage_cards_for_report(inventory, update_report, eligible_mouse_ids, config)
    )
    context.warnings.extend(cage_warnings)
    context.counts["missing_cage_count"] = 0
    context.counts["cages_selected"] = weaning_group_count
    context.counts["card_eligible_count"] = len(eligible_mouse_ids)
    context.counts["card_grouping_exception_count"] = len(grouping_issues)
    context.counts["weaning_groups_selected"] = weaning_group_count
    context.counts["cage_cards_generated"] = len(cage_records)

    audit_path = paths.exception_reports / f"inventory_audit_{context.run_id}.csv"
    write_audit_csv(update_report.audit_entries, audit_path)
    context.artifacts["audit_file"] = str(audit_path)

    _save_inventory_stage_output(
        config=config,
        paths=paths,
        context=context,
        inventory=inventory,
        update_report=update_report,
        dry_run=dry_run,
        logger=logger,
    )

    exception_path = paths.exception_reports / f"exceptions_{context.run_id}.xlsx"
    write_exception_report(
        update_report,
        exception_path,
        run_id=context.run_id,
        raw_record_count=context.counts.get("raw_record_count", 0),
        translated_record_count=context.counts.get("translated_record_count", 0),
        cage_cards_generated=len(cage_records),
        weaning_groups_generated=weaning_group_count,
    )
    context.artifacts["exception_report_file"] = str(exception_path)
    context.advance(RunStage.EXCEPTIONS_WRITTEN)
    update_archive_status(paths.raw_archive, context.run_id, context.stage.value)

    cage_card_path = paths.cage_cards / f"live_label_cage_cards_{context.run_id}.xlsx"
    generate_cage_cards(
        cage_records,
        config.cage_card.template,
        cage_card_path,
        config.cage_card,
    )
    context.artifacts["cage_card_file"] = str(cage_card_path)
    context.advance(RunStage.CAGE_CARDS_GENERATED)
    update_archive_status(paths.raw_archive, context.run_id, context.stage.value)
    logger.info(
        "Wrote %d weaning/new-cage card row(s) from %d compatible cage group(s); "
        "%d mouse/mice require grouping review.",
        len(cage_records),
        weaning_group_count,
        len(grouping_issues),
    )


def _append_litter_mouse_row(
    inventory: InventoryTable,
    submission: LitterSubmission,
    mouse_id: str,
    sex: str,
    *,
    audit_columns: dict[str, int],
    timestamp: str,
    run_id: str,
) -> int:
    row = [""] * len(inventory.headers)
    for role, value in (
        ("mouse_id", mouse_id),
        ("strain", submission.strain),
        ("revised_strain", submission.strain),
        ("mother", submission.mother),
        ("father", submission.father),
        ("dob", submission.dob),
        ("sex", sex),
    ):
        if role in inventory.config.columns:
            row[inventory.config.column_index(role)] = value
    row[audit_columns["last_updated"]] = timestamp
    row[audit_columns["genotype_source"]] = "litter_entry"
    row[audit_columns["run_id"]] = run_id
    inventory.rows.append(row)
    return len(inventory.rows) - 1


def append_litter_to_inventory(
    submission: LitterSubmission,
    config: AppConfig,
    *,
    dry_run: bool = False,
    verbose: bool = False,
) -> tuple[str, list[AuditEntry], dict[str, str]]:
    """Expand one litter submission into individual pup rows and append
    them to the inventory as brand-new mice.

    Every pup gets an explicit audit outcome, written to its own audit CSV.
    A pup whose mouse ID already exists in the inventory is never
    overwritten — it becomes an explicit ``CONFLICT`` audit entry instead,
    the same as any other inventory-safety exception in this project.
    Genotype is deliberately left blank: litters are entered before
    Transnetyx genotyping, which fills genotype in later via the normal
    ``run`` pipeline. Returns the run id, the audit entries, and the
    artifact paths written (empty on a dry run or if nothing was added).
    """
    if config.inventory is None:
        raise ConfigurationError(
            "Litter entry requires an inventory section in the configuration."
        )
    if not config.inventory.append_only:
        raise ConfigurationError(
            "Litter entry requires inventory.append_only = true, since every "
            "submitted litter is always brand-new mice, never a match against "
            "an existing row."
        )

    mice = expand_litter(submission)

    paths = initialize_runtime_directories(config)
    run_id = generate_run_id()
    log_path = paths.logs / f"automouse_{run_id}.log"
    logger = configure_run_logging(log_path, verbose=verbose)
    logger.info("Möuseley Kräs run ID: %s (litter entry)", run_id)

    inventory = load_inventory(config.inventory.file, config.inventory)
    backup_path = paths.inventory_backups / (
        f"mouse_inventory_backup_{run_id}{config.inventory.file.suffix}"
    )
    backup_inventory(config.inventory.file, backup_path)
    audit_columns = ensure_audit_columns(inventory)
    primary_index = inventory.primary_index()

    timestamp = datetime.now(timezone.utc).isoformat()
    entries: list[AuditEntry] = []
    added_mouse_ids: list[str] = []
    for source_row, mouse in enumerate(mice, start=1):
        if mouse.mouse_id in primary_index:
            entries.append(
                AuditEntry(
                    run_id=run_id,
                    timestamp=timestamp,
                    sample_id=mouse.mouse_id,
                    mouse_id=mouse.mouse_id,
                    inventory_row=primary_index[mouse.mouse_id][0],
                    previous_genotype=None,
                    proposed_genotype=None,
                    final_genotype=None,
                    action=AuditAction.CONFLICT,
                    status=RecordStatus.CONFLICT,
                    source_file="litter_entry",
                    source_row=source_row,
                    messages=[
                        f"{mouse.mouse_id} already exists in the inventory; "
                        "this litter submission was not applied to it."
                    ],
                )
            )
            continue
        if dry_run:
            entries.append(
                AuditEntry(
                    run_id=run_id,
                    timestamp=timestamp,
                    sample_id=mouse.mouse_id,
                    mouse_id=mouse.mouse_id,
                    inventory_row=None,
                    previous_genotype=None,
                    proposed_genotype=None,
                    final_genotype=None,
                    action=AuditAction.LITTER_ENTERED,
                    status=RecordStatus.MANUAL_REVIEW,
                    source_file="litter_entry",
                    source_row=source_row,
                    messages=["Would be added (dry run; nothing was written)."],
                )
            )
            continue
        row_index = _append_litter_mouse_row(
            inventory,
            submission,
            mouse.mouse_id,
            mouse.sex,
            audit_columns=audit_columns,
            timestamp=timestamp,
            run_id=run_id,
        )
        primary_index.setdefault(mouse.mouse_id, []).append(row_index)
        added_mouse_ids.append(mouse.mouse_id)
        entries.append(
            AuditEntry(
                run_id=run_id,
                timestamp=timestamp,
                sample_id=mouse.mouse_id,
                mouse_id=mouse.mouse_id,
                inventory_row=row_index,
                previous_genotype=None,
                proposed_genotype=None,
                final_genotype=None,
                action=AuditAction.LITTER_ENTERED,
                status=RecordStatus.MANUAL_REVIEW,
                source_file="litter_entry",
                source_row=source_row,
                messages=[
                    f"Added from litter entry ({mouse.sex}; strain={submission.strain}; "
                    f"DOB={submission.dob})."
                ],
            )
        )

    audit_path = paths.exception_reports / f"litter_entry_audit_{run_id}.csv"
    write_audit_csv(entries, audit_path)
    entered_count = sum(1 for entry in entries if entry.action == AuditAction.LITTER_ENTERED)
    logger.info(
        "Litter entry: %d pup(s) %s, %d conflicting, out of %d pups.",
        entered_count,
        "added" if not dry_run else "would be added (dry run)",
        len(entries) - entered_count,
        len(mice),
    )

    artifacts: dict[str, str] = {"audit_file": str(audit_path), "log_file": str(log_path)}
    if not dry_run and added_mouse_ids:
        artifacts["inventory_backup_file"] = str(backup_path)
        inventory_csv_path = paths.updated_inventory / f"mouse_inventory_updated_{run_id}.csv"
        inventory_xlsx_path = paths.updated_inventory / f"mouse_inventory_updated_{run_id}.xlsx"
        save_updated_inventory(inventory, inventory_csv_path, inventory_xlsx_path)
        config.inventory.file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(inventory_csv_path, config.inventory.file)
        logger.info("Copied rebuilt inventory back to %s", config.inventory.file)
        artifacts["updated_inventory_csv_file"] = str(inventory_csv_path)
        artifacts["updated_inventory_file"] = str(inventory_xlsx_path)
    logging.shutdown()
    return run_id, entries, artifacts

