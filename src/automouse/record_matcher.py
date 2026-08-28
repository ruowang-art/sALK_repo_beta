from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from collections import defaultdict

from automouse.inventory_manager import InventoryTable, ensure_audit_columns
from automouse.models import (
    AuditAction,
    AuditEntry,
    InventoryUpdateReport,
    RecordStatus,
    TranslatedGenotypeRecord,
    TranslationValidationReport,
)


def _normalize_genotype(value: str | None) -> str:
    return " ".join((value or "").strip().lstrip("'").split())


def _register_identifier_row(
    inventory: InventoryTable,
    identifier_index: dict[str, list[int]],
    row_index: int,
) -> None:
    for role in inventory.config.identifier_roles:
        if role not in inventory.config.columns:
            continue
        identifier = inventory.value(row_index, role).strip()
        if identifier:
            identifier_index.setdefault(identifier, []).append(row_index)


def _append_inventory_row(
    inventory: InventoryTable,
    record: TranslatedGenotypeRecord,
    *,
    audit_columns: dict[str, int],
    timestamp: str,
    run_id: str,
    source_name: str,
) -> int:
    row = [""] * len(inventory.headers)
    sample_id = record.sample_id.strip()
    strain = (record.translated_strain or "").strip()
    sex = (record.translated_sex or "").strip()
    genotype = _normalize_genotype(record.translated_genotype)

    for role in ("mouse_id", "id", "sample"):
        if role in inventory.config.columns:
            row[inventory.config.column_index(role)] = sample_id
    for role, value in (
        ("strain", strain),
        ("revised_strain", strain),
        ("sex", sex),
        ("genotype", genotype),
    ):
        if role in inventory.config.columns:
            row[inventory.config.column_index(role)] = value

    row[audit_columns["last_updated"]] = timestamp
    row[audit_columns["genotype_source"]] = source_name
    row[audit_columns["run_id"]] = run_id
    inventory.rows.append(row)
    return len(inventory.rows) - 1


def apply_inventory_updates(
    inventory: InventoryTable,
    translated_report: TranslationValidationReport,
    *,
    run_id: str,
    source_file: Path,
    append_only: bool = False,
    dry_run: bool = False,
) -> InventoryUpdateReport:
    identifier_index = inventory.identifier_index()
    audit_columns = ensure_audit_columns(inventory)
    timestamp = datetime.now(timezone.utc).isoformat()
    entries: list[AuditEntry] = []
    updated_mouse_ids: set[str] = set()
    confirmed_mouse_ids: set[str] = set()
    missing_cage_mouse_ids: set[str] = set()
    report_warnings: list[str] = []

    # Resolve all READY records before mutating the inventory. This prevents the
    # first of two aliases/results targeting one inventory row from being written
    # before the conflict is discovered.
    ready_by_inventory_row: dict[int, list[TranslatedGenotypeRecord]] = defaultdict(list)
    for record in translated_report.records:
        if record.status not in {RecordStatus.READY, RecordStatus.READY_WITH_WARNING}:
            continue
        matches = sorted(set(identifier_index.get(record.sample_id.strip(), [])))
        proposed = _normalize_genotype(record.translated_genotype)
        if len(matches) == 1 and proposed:
            ready_by_inventory_row[matches[0]].append(record)
    for row_index, records in ready_by_inventory_row.items():
        if len(records) <= 1:
            continue
        proposed_values = {
            _normalize_genotype(record.translated_genotype)
            for record in records
        }
        mouse_id = inventory.value(row_index, "mouse_id")
        if len(proposed_values) > 1:
            for record in records:
                record.status = RecordStatus.CONFLICT
                record.warnings.append(
                    "Multiple READY batch records target the same inventory row "
                    "with conflicting genotypes."
                )
            report_warnings.append(
                f"{mouse_id}: conflicting batch records target one inventory row."
            )
        else:
            for duplicate in records[1:]:
                duplicate.status = RecordStatus.DUPLICATE
                duplicate.warnings.append(
                    "Agreeing READY batch record targets an inventory row already "
                    "represented by an earlier record."
                )

    for record in translated_report.records:
        messages = list(record.warnings)
        record_source = Path(record.source_file) if record.source_file else source_file
        matches = sorted(set(identifier_index.get(record.sample_id.strip(), [])))
        action = AuditAction.SKIPPED
        status = record.status
        mouse_id: str | None = None
        inventory_row: int | None = None
        previous: str | None = None
        proposed = _normalize_genotype(record.translated_genotype) or None
        final: str | None = None

        if record.status == RecordStatus.DUPLICATE:
            action = AuditAction.DUPLICATE
        elif record.status == RecordStatus.CONFLICT:
            action = AuditAction.CONFLICT
        elif record.status not in {RecordStatus.READY, RecordStatus.READY_WITH_WARNING}:
            action = AuditAction.MANUAL_REVIEW
        elif not matches:
            if append_only:
                if dry_run:
                    action = AuditAction.PROPOSED_UPDATE
                    messages.append("Would append a new inventory row from translated data.")
                else:
                    row_index = _append_inventory_row(
                        inventory,
                        record,
                        audit_columns=audit_columns,
                        timestamp=timestamp,
                        run_id=run_id,
                        source_name=record_source.name,
                    )
                    _register_identifier_row(inventory, identifier_index, row_index)
                    inventory_row = row_index + 2
                    mouse_id = inventory.value(row_index, "mouse_id") or record.sample_id
                    previous = None
                    final = proposed
                    action = AuditAction.UPDATED
                    updated_mouse_ids.add(mouse_id)
                    entries.append(
                        AuditEntry(
                            run_id=run_id,
                            timestamp=timestamp,
                            sample_id=record.sample_id,
                            mouse_id=mouse_id,
                            inventory_row=inventory_row,
                            previous_genotype=previous,
                            proposed_genotype=proposed,
                            final_genotype=final,
                            action=action,
                            status=status,
                            source_file=str(record_source),
                            source_row=record.source_row,
                            messages=messages + [
                                "Appended a new inventory row from translated data."
                            ],
                        )
                    )
                    continue
            else:
                action = AuditAction.NOT_FOUND
                status = RecordStatus.MOUSE_NOT_FOUND
                messages.append("No exact inventory identifier match.")
        elif len(matches) > 1:
            action = AuditAction.MULTIPLE_MATCHES
            status = RecordStatus.MULTIPLE_MATCHES
            messages.append(
                "Identifier matched multiple inventory rows: "
                + ", ".join(str(index + 2) for index in matches)
            )
        else:
            row_index = matches[0]
            inventory_row = row_index + 2
            mouse_id = inventory.value(row_index, "mouse_id") or record.sample_id
            previous_value = inventory.value(row_index, "genotype")
            previous = _normalize_genotype(previous_value) or None
            final = previous

            inventory_sex = inventory.value(row_index, "sex")
            if (
                record.translated_sex
                and inventory_sex
                and record.translated_sex.casefold() != inventory_sex.casefold()
            ):
                messages.append(
                    f"Sex mismatch: inventory={inventory_sex!r}, "
                    f"translated={record.translated_sex!r}."
                )
                status = RecordStatus.READY_WITH_WARNING
                report_warnings.append(
                    f"{mouse_id}: inventory sex {inventory_sex!r} differs from "
                    f"translated sex {record.translated_sex!r}."
                )

            if append_only:
                if previous and previous == proposed:
                    action = AuditAction.DUPLICATE
                    status = RecordStatus.DUPLICATE
                    messages.append(
                        "Sample already exists in the append-only inventory with the same genotype."
                    )
                else:
                    action = AuditAction.CONFLICT
                    status = RecordStatus.CONFLICT
                    messages.append(
                        "Sample already exists in the append-only inventory; new raw data is not repeated."
                    )
            elif not proposed:
                action = AuditAction.MANUAL_REVIEW
                status = RecordStatus.NO_RESULT
                messages.append("No translated genotype is available.")
            elif not previous:
                if dry_run:
                    action = AuditAction.PROPOSED_UPDATE
                    final = previous
                else:
                    action = AuditAction.UPDATED
                    inventory.set_value(row_index, "genotype", proposed)
                    final = proposed
                    updated_mouse_ids.add(mouse_id)
                    inventory.rows[row_index][audit_columns["last_updated"]] = timestamp
                    inventory.rows[row_index][audit_columns["genotype_source"]] = (
                        record_source.name
                    )
                    inventory.rows[row_index][audit_columns["run_id"]] = run_id
            elif previous == proposed:
                action = AuditAction.CONFIRMED
                final = previous
                confirmed_mouse_ids.add(mouse_id)
            else:
                action = AuditAction.CONFLICT
                status = RecordStatus.CONFLICT
                final = previous
                messages.append("Existing genotype conflicts with translated genotype.")

        entries.append(
            AuditEntry(
                run_id=run_id,
                timestamp=timestamp,
                sample_id=record.sample_id,
                mouse_id=mouse_id,
                inventory_row=inventory_row,
                previous_genotype=previous,
                proposed_genotype=proposed,
                final_genotype=final,
                action=action,
                status=status,
                source_file=str(record_source),
                source_row=record.source_row,
                messages=messages,
            )
        )

    return InventoryUpdateReport(
        audit_entries=entries,
        updated_mouse_ids=updated_mouse_ids,
        confirmed_mouse_ids=confirmed_mouse_ids,
        missing_cage_mouse_ids=missing_cage_mouse_ids,
        warnings=sorted(set(report_warnings)),
    )
