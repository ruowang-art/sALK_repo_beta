from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from automouse.config import AppConfig


@dataclass(frozen=True, slots=True)
class RuntimePaths:
    root: Path
    incoming: Path
    validated: Path
    inventory_current: Path
    inventory_backups: Path
    translated_genotypes: Path
    updated_inventory: Path
    cage_cards: Path
    exception_reports: Path
    raw_archive: Path
    completed_runs: Path
    logs: Path


def initialize_runtime_directories(config: AppConfig) -> RuntimePaths:
    root = config.runtime_root
    paths = RuntimePaths(
        root=root,
        incoming=root / "input" / "incoming",
        validated=root / "input" / "validated",
        inventory_current=root / "inventory" / "current",
        inventory_backups=root / "inventory" / "backups",
        translated_genotypes=root / "output" / "translated_genotypes",
        updated_inventory=root / "output" / "updated_inventory",
        cage_cards=root / "output" / "cage_cards",
        exception_reports=root / "output" / "exception_reports",
        raw_archive=root / "archive" / "raw_transnetyx_files",
        completed_runs=root / "archive" / "completed_runs",
        logs=root / "logs",
    )
    for path in (
        paths.root,
        paths.incoming,
        paths.validated,
        paths.inventory_current,
        paths.inventory_backups,
        paths.translated_genotypes,
        paths.updated_inventory,
        paths.cage_cards,
        paths.exception_reports,
        paths.raw_archive,
        paths.completed_runs,
        paths.logs,
    ):
        path.mkdir(parents=True, exist_ok=True)
    return paths
