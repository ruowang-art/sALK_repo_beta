from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


class RunStage(str, Enum):
    INITIALIZED = "initialized"
    INPUT_ARCHIVED = "input_archived"
    RAW_VALIDATED = "raw_validated"
    TRANSLATED = "translated"
    TRANSLATION_VALIDATED = "translation_validated"
    INVENTORY_BACKED_UP = "inventory_backed_up"
    INVENTORY_UPDATED = "inventory_updated"
    EXCEPTIONS_WRITTEN = "exceptions_written"
    CAGE_CARDS_GENERATED = "cage_cards_generated"
    COMPLETED = "completed"
    FAILED = "failed"


class RecordStatus(str, Enum):
    READY = "READY"
    READY_WITH_WARNING = "READY_WITH_WARNING"
    PENDING_RERUN = "PENDING_RERUN"
    NO_RESULT = "NO_RESULT"
    AMBIGUOUS = "AMBIGUOUS"
    DUPLICATE = "DUPLICATE"
    MOUSE_NOT_FOUND = "MOUSE_NOT_FOUND"
    MULTIPLE_MATCHES = "MULTIPLE_MATCHES"
    CONFLICT = "CONFLICT"
    MANUAL_REVIEW = "MANUAL_REVIEW"


class AuditAction(str, Enum):
    UPDATED = "UPDATED"
    PROPOSED_UPDATE = "PROPOSED_UPDATE"
    CONFIRMED = "CONFIRMED"
    SKIPPED = "SKIPPED"
    NOT_FOUND = "NOT_FOUND"
    MULTIPLE_MATCHES = "MULTIPLE_MATCHES"
    DUPLICATE = "DUPLICATE"
    CONFLICT = "CONFLICT"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    ERROR = "ERROR"
    LITTER_ENTERED = "LITTER_ENTERED"


@dataclass(slots=True)
class ValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    row_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class RRunResult:
    command: list[str]
    exit_code: int
    stdout: str
    stderr: str
    output_path: Path
    duration_seconds: float


@dataclass(slots=True)
class TranslatedGenotypeRecord:
    sample_id: str
    mouse_id: str | None
    assay: str | None
    raw_result: str | None
    translated_genotype: str | None
    status: RecordStatus
    warnings: list[str]
    source_row: int
    translated_strain: str | None = None
    translated_sex: str | None = None
    source_file: str | None = None

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["status"] = self.status.value
        return result


@dataclass(slots=True)
class AuditEntry:
    run_id: str
    timestamp: str
    sample_id: str
    mouse_id: str | None
    inventory_row: int | None
    previous_genotype: str | None
    proposed_genotype: str | None
    final_genotype: str | None
    action: AuditAction
    status: RecordStatus
    source_file: str
    source_row: int
    messages: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["action"] = self.action.value
        result["status"] = self.status.value
        result["messages"] = " | ".join(self.messages)
        return result


@dataclass(slots=True)
class InventoryUpdateReport:
    audit_entries: list[AuditEntry]
    updated_mouse_ids: set[str] = field(default_factory=set)
    confirmed_mouse_ids: set[str] = field(default_factory=set)
    missing_cage_mouse_ids: set[str] = field(default_factory=set)
    card_eligible_mouse_ids: set[str] = field(default_factory=set)
    card_grouping_exception_mouse_ids: set[str] = field(default_factory=set)
    warnings: list[str] = field(default_factory=list)

    @property
    def action_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for entry in self.audit_entries:
            counts[entry.action.value] = counts.get(entry.action.value, 0) + 1
        return dict(sorted(counts.items()))


@dataclass(slots=True)
class CageCardRecord:
    cage_id: str
    experiment_url: str
    strain: str
    animal_count: int
    litter_count: int
    sex: str
    date_weaned: Any
    date_born: Any
    mouse_ids: list[str]
    genotypes: list[str]
    dam: str
    dam_genotype: str
    sire: str
    sire_genotype: str
    breeder: str = ""
    setup_date: Any = None
    warnings: list[str] = field(default_factory=list)

    def template_row(self, max_mice: int = 5) -> list[Any]:
        mice = (self.mouse_ids + [""] * max_mice)[:max_mice]
        genotypes = (self.genotypes + [""] * max_mice)[:max_mice]
        return [
            self.experiment_url,
            self.strain,
            self.animal_count,
            self.litter_count,
            self.sex,
            self.date_weaned,
            self.date_born,
            *mice,
            *genotypes,
            self.dam,
            self.dam_genotype,
            self.sire,
            self.sire_genotype,
            self.breeder,
            self.setup_date,
        ]


@dataclass(slots=True)
class TranslationValidationReport:
    valid: bool
    errors: list[str]
    warnings: list[str]
    row_count: int
    records: list[TranslatedGenotypeRecord]
    status_counts: dict[str, int]
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self, *, include_records: bool = True) -> dict[str, Any]:
        result: dict[str, Any] = {
            "valid": self.valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "row_count": self.row_count,
            "status_counts": self.status_counts,
            "metadata": self.metadata,
        }
        if include_records:
            result["records"] = [record.to_dict() for record in self.records]
        return result


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class RunContext:
    run_id: str
    started_at: datetime
    stage: RunStage = RunStage.INITIALIZED
    completed_at: datetime | None = None
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    artifacts: dict[str, Any] = field(default_factory=dict)
    counts: dict[str, int] = field(default_factory=dict)
    checksum: str | None = None
    checksums: dict[str, str] = field(default_factory=dict)
    environment: dict[str, Any] = field(default_factory=dict)
    dry_run: bool = False
    implementation_scope: str = "phase_1_and_phase_2"
    failed_stage: str | None = None
    stage_history: list[str] = field(
        default_factory=lambda: [RunStage.INITIALIZED.value]
    )

    def advance(self, stage: RunStage) -> None:
        self.stage = stage
        if not self.stage_history or self.stage_history[-1] != stage.value:
            self.stage_history.append(stage.value)

    def finish(self, stage: RunStage) -> None:
        self.advance(stage)
        self.completed_at = utc_now()

    def to_summary(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else "",
            "status": "failed" if self.stage == RunStage.FAILED else "completed",
            "last_stage": self.stage.value,
            "failed_stage": self.failed_stage or "",
            "stage_history": self.stage_history,
            "implementation_scope": self.implementation_scope,
            "dry_run": self.dry_run,
            "raw_input_file": self.artifacts.get("raw_input_file", ""),
            "raw_input_files": self.artifacts.get("raw_input_files", []),
            "archived_input_file": self.artifacts.get("archived_input_file", ""),
            "archived_input_files": self.artifacts.get("archived_input_files", []),
            "translated_output_file": self.artifacts.get("translated_output_file", ""),
            "translated_output_files": self.artifacts.get("translated_output_files", []),
            "translation_validation_file": self.artifacts.get("translation_validation_file", ""),
            "translation_validation_files": self.artifacts.get(
                "translation_validation_files", []
            ),
            "run_summary_file": self.artifacts.get("run_summary_file", ""),
            "log_file": self.artifacts.get("log_file", ""),
            "inventory_backup_file": self.artifacts.get("inventory_backup_file", ""),
            "updated_inventory_file": self.artifacts.get("updated_inventory_file", ""),
            "updated_inventory_csv_file": self.artifacts.get("updated_inventory_csv_file", ""),
            "exception_report_file": self.artifacts.get("exception_report_file", ""),
            "audit_file": self.artifacts.get("audit_file", ""),
            "cage_card_file": self.artifacts.get("cage_card_file", ""),
            "raw_record_count": self.counts.get("raw_record_count", 0),
            "input_file_count": self.counts.get("input_file_count", 0),
            "translated_record_count": self.counts.get("translated_record_count", 0),
            "inventory_records_updated": self.counts.get("inventory_records_updated", 0),
            "inventory_records_confirmed": self.counts.get("inventory_records_confirmed", 0),
            "mouse_not_found_count": self.counts.get("mouse_not_found_count", 0),
            "multiple_match_count": self.counts.get("multiple_match_count", 0),
            "conflict_count": self.counts.get("conflict_count", 0),
            "manual_review_count": self.counts.get("manual_review_count", 0),
            "proposed_update_count": self.counts.get("proposed_update_count", 0),
            "missing_cage_count": self.counts.get("missing_cage_count", 0),
            "cages_selected": self.counts.get("cages_selected", 0),
            "card_eligible_count": self.counts.get("card_eligible_count", 0),
            "card_grouping_exception_count": self.counts.get(
                "card_grouping_exception_count", 0
            ),
            "weaning_groups_selected": self.counts.get(
                "weaning_groups_selected", 0
            ),
            "cage_cards_generated": self.counts.get("cage_cards_generated", 0),
            "source_sha256": self.checksum or "",
            "source_sha256_by_file": self.checksums,
            "application_version": self.environment.get("application_version", ""),
            "python_version": self.environment.get("python_version", ""),
            "r_version": self.environment.get("r_version", ""),
            "os": self.environment.get("os", ""),
            "os_version": self.environment.get("os_version", ""),
            "machine_arch": self.environment.get("machine_arch", ""),
            "config_path": self.environment.get("config_path", ""),
            "config_sha256": self.environment.get("config_sha256", ""),
            "translation_script_path": self.environment.get("translation_script_path", ""),
            "translation_script_sha256": self.environment.get(
                "translation_script_sha256", ""
            ),
            "sheets_overlay_enabled": self.environment.get("sheets_overlay_enabled", False),
            "sheets_overlay_fills": self.environment.get("sheets_overlay_fills", []),
            "output_sha256_by_file": self.environment.get("output_sha256_by_file", {}),
            "warnings": self.warnings,
            "errors": self.errors,
        }
