from __future__ import annotations

import json
import platform
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from automouse.exceptions import ConfigurationError


def _common_r_executable_locations() -> tuple[Path, ...]:
    """Common install locations for Rscript, checked only as a fallback when
    the configured path doesn't already resolve to a real file — an explicit
    `r.executable` in config always wins. macOS locations are verified from
    this project's own actual setups (Homebrew on Apple Silicon and Intel,
    the official CRAN installer); Windows/Linux locations are the
    conventional install paths for the official R installers on those
    platforms, not yet verified against a real Windows/Linux R install
    (Phase 3/4 — see docs/MACOS_EXECUTABLE_PLAN.md and the portability
    progress log).
    """
    system = platform.system()
    if system == "Windows":
        candidates: list[Path] = []
        program_files_r = Path(r"C:\Program Files\R")
        if program_files_r.is_dir():
            for version_dir in sorted(program_files_r.iterdir(), reverse=True):
                candidates.append(version_dir / "bin" / "Rscript.exe")
        return tuple(candidates)
    if system == "Linux":
        return (
            Path("/usr/bin/Rscript"),
            Path("/usr/local/bin/Rscript"),
        )
    # Darwin (macOS) and any other/unknown platform default to the macOS set,
    # matching this project's only currently-verified environment.
    return (
        Path("/usr/local/bin/Rscript"),
        Path("/opt/homebrew/bin/Rscript"),
        Path("/Library/Frameworks/R.framework/Resources/bin/Rscript"),
    )


def _resolve_r_executable(value: str, project_root: Path) -> Path:
    """Resolve the configured R executable, falling back to a PATH lookup
    and a handful of common macOS install locations if the configured value
    doesn't exist as-is. Returns the configured path unchanged (for
    validate_config to report a clear error) if nothing else is found.
    """
    configured = _resolve_path(value, project_root)
    if configured.is_file():
        return configured

    found = shutil.which(value) or shutil.which("Rscript")
    if found:
        return Path(found).resolve()

    for candidate in _common_r_executable_locations():
        if candidate.is_file():
            return candidate

    return configured


@dataclass(frozen=True, slots=True)
class RConfig:
    executable: Path
    translation_script: Path
    wrapper_script: Path
    timeout_seconds: int = 300
    print_diagnostics: bool = True


@dataclass(frozen=True, slots=True)
class TransnetyxConfig:
    sample_id_column: str = "Sample"
    required_columns: tuple[str, ...] = ("Sample", "Strain")
    metadata_columns: tuple[str, ...] = (
        "WellPlate",
        "Strain",
        "Well",
        "Sample",
        "TranslatedResult",
    )
    supported_extensions: tuple[str, ...] = (".csv",)
    delimiter: str = ","
    encoding: str = "utf-8-sig"
    require_any_assay_value: bool = True


@dataclass(frozen=True, slots=True)
class TranslationConfig:
    sample_id_column: str = "Sample"
    genotype_column: str = "Genotype"
    required_columns: tuple[str, ...] = ("Sample", "Genotype")
    approved_genotypes: tuple[str, ...] = ()
    approved_genotype_pattern: str = r"^[A-Za-z0-9_+./;() -]+$"
    failure_tokens: tuple[str, ...] = ("Fail", "Undetected", "UD1", "UD4")


@dataclass(frozen=True, slots=True)
class InventoryConfig:
    file: Path
    format: str = "csv"
    output_sheet_name: str = "Mouse Inventory"
    append_only: bool = False
    # A convenience link to the primary inventory (e.g. a Google Sheet), shown
    # in the web app for lab staff to open in a new tab. This is a link only:
    # AutoMouse never reads from or writes to it automatically.
    source_sheet_url: str = ""
    columns: dict[str, int] = field(default_factory=dict)
    expected_headers: dict[str, str] = field(default_factory=dict)
    identifier_roles: tuple[str, ...] = ("mouse_id", "id", "sample")
    # Known strain names offered as a dropdown in the litter-entry portal
    # (Mouse Inventory Update). Purely a UI convenience list; does not
    # restrict what can be written to the inventory via other paths.
    known_strains: tuple[str, ...] = ()
    audit_column_names: dict[str, str] = field(
        default_factory=lambda: {
            "last_updated": "AutoMouse Last Updated",
            "genotype_source": "AutoMouse Genotype Source",
            "run_id": "AutoMouse Run ID",
        }
    )

    def column_index(self, role: str) -> int:
        if role not in self.columns:
            raise ConfigurationError(f"Inventory column role is not configured: {role}")
        return self.columns[role] - 1


@dataclass(frozen=True, slots=True)
class CageCardConfig:
    template: Path
    sheet_name: str = "Sheet1"
    max_mice_per_card: int = 5
    grouping_strategy: str = "weaning_compatible_cage"
    male_dob_window_days: int = 5
    female_dob_window_days: int = 7
    experiment_url: str = ""
    generate_for_actions: tuple[str, ...] = ("UPDATED", "CONFIRMED")
    expected_headers: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SheetsOverlayConfig:
    # Optional, explicitly opt-in, read-only overlay: fetches only DOB and
    # Wean_By from the primary Google Sheet inventory (via a read-only
    # service account) to fill blank DOB/Wean_By cells before cage cards are
    # built. Disabled unless `enabled: true` is set. Never used for
    # genotype matching or any other field; never writes to the sheet; a
    # fetch failure produces a run warning rather than failing the batch.
    enabled: bool = False
    spreadsheet_id: str = ""
    worksheet: str = "Sheet1"
    credentials_file: Path | None = None
    # Separate, narrower opt-in (requires `enabled: true` as well): lets the
    # Mouse Inventory Update portal (litter entry) also append new litters to
    # this same Google Sheet, in addition to the local inventory copy it
    # always writes. Off by default. Uses a read-write-scoped credential
    # request distinct from the read-only overlay above, even though both
    # come from the same service-account key file, so the DOB/Wean_By read
    # path can never write regardless of what this flag is set to. See
    # sheets_litter_writer.py and CLAUDE.md for the conflict-checking and
    # failure-handling rules this is held to.
    write_new_litters: bool = False


@dataclass(frozen=True, slots=True)
class AppConfig:
    project_root: Path
    runtime_root: Path
    application_version: str
    r: RConfig
    transnetyx: TransnetyxConfig = field(default_factory=TransnetyxConfig)
    translation: TranslationConfig = field(default_factory=TranslationConfig)
    inventory: InventoryConfig | None = None
    cage_card: CageCardConfig | None = None
    sheets_overlay: SheetsOverlayConfig | None = None
    config_path: Path | None = None


def _resolve_path(value: str, project_root: Path) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = project_root / path
    return path.resolve()


def _read_mapping(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise ConfigurationError(f"Unable to read configuration {path}: {error}") from error

    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        try:
            import yaml  # type: ignore[import-not-found]
        except ImportError as error:
            raise ConfigurationError(
                "Configuration is not JSON-formatted YAML and PyYAML is not installed. "
                "Install the project dependencies or use the JSON-compatible example format."
            ) from error
        try:
            value = yaml.safe_load(text)
        except yaml.YAMLError as error:
            raise ConfigurationError(f"Invalid configuration syntax in {path}: {error}") from error

    if not isinstance(value, dict):
        raise ConfigurationError(f"Configuration root must be a mapping: {path}")
    return value


def load_config(path: Path) -> AppConfig:
    config_path = path.expanduser().resolve()
    raw = _read_mapping(config_path)
    project_root = config_path.parent.parent.resolve()
    errors: list[str] = []

    r_raw = raw.get("r") if isinstance(raw.get("r"), dict) else {}
    transnetyx_raw = (
        raw.get("transnetyx") if isinstance(raw.get("transnetyx"), dict) else {}
    )
    translation_raw = (
        raw.get("translation") if isinstance(raw.get("translation"), dict) else {}
    )
    inventory_raw = raw.get("inventory") if isinstance(raw.get("inventory"), dict) else None
    cage_card_raw = raw.get("cage_card") if isinstance(raw.get("cage_card"), dict) else None
    sheets_overlay_raw = (
        raw.get("sheets_overlay") if isinstance(raw.get("sheets_overlay"), dict) else None
    )
    for section, key in (
        (r_raw, "executable"),
        (r_raw, "translation_script"),
        (r_raw, "wrapper_script"),
    ):
        if not section.get(key):
            errors.append(f"Missing configuration value: r.{key}")

    if errors:
        raise ConfigurationError("Configuration errors:\n- " + "\n- ".join(errors))

    r_config = RConfig(
        executable=_resolve_r_executable(str(r_raw["executable"]), project_root),
        translation_script=_resolve_path(str(r_raw["translation_script"]), project_root),
        wrapper_script=_resolve_path(str(r_raw["wrapper_script"]), project_root),
        timeout_seconds=int(r_raw.get("timeout_seconds", 300)),
        print_diagnostics=bool(r_raw.get("print_diagnostics", True)),
    )
    transnetyx_config = TransnetyxConfig(
        sample_id_column=str(transnetyx_raw.get("sample_id_column", "Sample")),
        required_columns=tuple(transnetyx_raw.get("required_columns", ["Sample", "Strain"])),
        metadata_columns=tuple(
            transnetyx_raw.get(
                "metadata_columns",
                ["WellPlate", "Strain", "Well", "Sample", "TranslatedResult"],
            )
        ),
        supported_extensions=tuple(
            str(value).lower()
            for value in transnetyx_raw.get("supported_extensions", [".csv"])
        ),
        delimiter=str(transnetyx_raw.get("delimiter", ",")),
        encoding=str(transnetyx_raw.get("encoding", "utf-8-sig")),
        require_any_assay_value=bool(
            transnetyx_raw.get("require_any_assay_value", True)
        ),
    )
    translation_config = TranslationConfig(
        sample_id_column=str(translation_raw.get("sample_id_column", "Sample")),
        genotype_column=str(translation_raw.get("genotype_column", "Genotype")),
        required_columns=tuple(
            translation_raw.get("required_columns", ["Sample", "Genotype"])
        ),
        approved_genotypes=tuple(translation_raw.get("approved_genotypes", [])),
        approved_genotype_pattern=str(
            translation_raw.get(
                "approved_genotype_pattern", r"^[A-Za-z0-9_+./;() -]+$"
            )
        ),
        failure_tokens=tuple(
            translation_raw.get(
                "failure_tokens", ["Fail", "Undetected", "UD1", "UD4"]
            )
        ),
    )

    inventory_config = None
    if inventory_raw is not None:
        inventory_file = inventory_raw.get("file")
        if not inventory_file:
            errors.append("Missing configuration value: inventory.file")
        else:
            inventory_config = InventoryConfig(
                file=_resolve_path(str(inventory_file), project_root),
                format=str(inventory_raw.get("format", "csv")).lower(),
                output_sheet_name=str(
                    inventory_raw.get("output_sheet_name", "Mouse Inventory")
                ),
                append_only=bool(inventory_raw.get("append_only", False)),
                source_sheet_url=str(inventory_raw.get("source_sheet_url", "")),
                columns={
                    str(key): int(value)
                    for key, value in dict(inventory_raw.get("columns", {})).items()
                },
                expected_headers={
                    str(key): str(value)
                    for key, value in dict(
                        inventory_raw.get("expected_headers", {})
                    ).items()
                },
                identifier_roles=tuple(
                    inventory_raw.get(
                        "identifier_roles", ["mouse_id", "id", "sample"]
                    )
                ),
                known_strains=tuple(
                    str(value) for value in inventory_raw.get("known_strains", [])
                ),
                audit_column_names={
                    str(key): str(value)
                    for key, value in dict(
                        inventory_raw.get(
                            "audit_column_names",
                            {
                                "last_updated": "AutoMouse Last Updated",
                                "genotype_source": "AutoMouse Genotype Source",
                                "run_id": "AutoMouse Run ID",
                            },
                        )
                    ).items()
                },
            )

    cage_card_config = None
    if cage_card_raw is not None:
        template = cage_card_raw.get("template")
        if not template:
            errors.append("Missing configuration value: cage_card.template")
        else:
            cage_card_config = CageCardConfig(
                template=_resolve_path(str(template), project_root),
                sheet_name=str(cage_card_raw.get("sheet_name", "Sheet1")),
                max_mice_per_card=int(cage_card_raw.get("max_mice_per_card", 5)),
                grouping_strategy=str(
                    cage_card_raw.get("grouping_strategy", "weaning_compatible_cage")
                ),
                male_dob_window_days=int(cage_card_raw.get("male_dob_window_days", 5)),
                female_dob_window_days=int(
                    cage_card_raw.get("female_dob_window_days", 7)
                ),
                experiment_url=str(cage_card_raw.get("experiment_url", "")),
                generate_for_actions=tuple(
                    cage_card_raw.get(
                        "generate_for_actions", ["UPDATED", "CONFIRMED"]
                    )
                ),
                expected_headers=tuple(cage_card_raw.get("expected_headers", [])),
            )

    sheets_overlay_config = None
    if sheets_overlay_raw is not None:
        credentials_file = sheets_overlay_raw.get("credentials_file")
        sheets_overlay_config = SheetsOverlayConfig(
            enabled=bool(sheets_overlay_raw.get("enabled", False)),
            spreadsheet_id=str(sheets_overlay_raw.get("spreadsheet_id", "")),
            worksheet=str(sheets_overlay_raw.get("worksheet", "Sheet1")),
            credentials_file=(
                _resolve_path(str(credentials_file), project_root)
                if credentials_file
                else None
            ),
            write_new_litters=bool(sheets_overlay_raw.get("write_new_litters", False)),
        )

    if errors:
        raise ConfigurationError("Configuration errors:\n- " + "\n- ".join(errors))

    runtime_root = _resolve_path(str(raw.get("runtime_root", "runtime")), project_root)
    config = AppConfig(
        project_root=project_root,
        runtime_root=runtime_root,
        application_version=str(raw.get("application_version", "0.1.0")),
        r=r_config,
        transnetyx=transnetyx_config,
        translation=translation_config,
        inventory=inventory_config,
        cage_card=cage_card_config,
        sheets_overlay=sheets_overlay_config,
        config_path=config_path,
    )
    validate_config(config)
    return config


def validate_config(config: AppConfig) -> None:
    errors: list[str] = []
    if not config.r.executable.is_file():
        system = platform.system()
        install_url = {
            "Windows": "https://cran.r-project.org/bin/windows/base/",
            "Linux": "https://cran.r-project.org/bin/linux/",
        }.get(system, "https://cran.r-project.org/bin/macosx/")
        find_command = "where Rscript" if system == "Windows" else "which Rscript"
        errors.append(
            f"R executable not found: {config.r.executable} (also checked PATH and "
            f"{', '.join(str(p) for p in _common_r_executable_locations())}). "
            f"Install R from {install_url}, or set r.executable in your config to the "
            f"exact Rscript path (run `{find_command}` to find it)."
        )
    if not config.r.translation_script.is_file():
        errors.append(f"R translation script not found: {config.r.translation_script}")
    if not config.r.wrapper_script.is_file():
        errors.append(f"R wrapper script not found: {config.r.wrapper_script}")
    if config.r.timeout_seconds <= 0:
        errors.append("r.timeout_seconds must be positive")
    if len(config.transnetyx.delimiter) != 1:
        errors.append("transnetyx.delimiter must be exactly one character")
    if not config.transnetyx.sample_id_column.strip():
        errors.append("transnetyx.sample_id_column may not be blank")
    if not config.translation.genotype_column.strip():
        errors.append("translation.genotype_column may not be blank")
    if config.inventory is not None:
        if not config.inventory.file.is_file():
            errors.append(f"Inventory file not found: {config.inventory.file}")
        if config.inventory.format != "csv":
            errors.append("inventory.format currently supports only 'csv'")
        if config.inventory.source_sheet_url and not config.inventory.source_sheet_url.startswith(
            ("http://", "https://")
        ):
            errors.append("inventory.source_sheet_url must start with http:// or https://")
        required_roles = {
            "mouse_id",
            "genotype",
            "strain",
            "revised_strain",
            "mother",
            "father",
            "dob",
            "sex",
            "wean_date",
        }
        missing_roles = sorted(required_roles - set(config.inventory.columns))
        if missing_roles:
            errors.append(
                "Missing inventory column role(s): " + ", ".join(missing_roles)
            )
        invalid_positions = sorted(
            role
            for role, position in config.inventory.columns.items()
            if position < 1
        )
        if invalid_positions:
            errors.append(
                "Inventory column positions must be 1-based positive integers: "
                + ", ".join(invalid_positions)
            )
    if config.cage_card is not None:
        if not config.cage_card.template.is_file():
            errors.append(f"Cage-card template not found: {config.cage_card.template}")
        if config.cage_card.max_mice_per_card != 5:
            errors.append(
                "This Live Label template requires cage_card.max_mice_per_card = 5"
            )
        supported_grouping_strategies = {
            "weaning_compatible_cage",
            "weaning_litter_sex",
        }
        if config.cage_card.grouping_strategy not in supported_grouping_strategies:
            errors.append(
                "cage_card.grouping_strategy must be 'weaning_compatible_cage'"
            )
        if config.cage_card.male_dob_window_days < 0:
            errors.append("cage_card.male_dob_window_days may not be negative")
        if config.cage_card.female_dob_window_days < 0:
            errors.append("cage_card.female_dob_window_days may not be negative")
        supported_actions = {"UPDATED", "CONFIRMED", "PROPOSED_UPDATE"}
        unsupported_actions = sorted(
            set(config.cage_card.generate_for_actions) - supported_actions
        )
        if unsupported_actions:
            errors.append(
                "Unsupported cage_card.generate_for_actions value(s): "
                + ", ".join(unsupported_actions)
            )
    if config.sheets_overlay is not None and config.sheets_overlay.enabled:
        if config.inventory is None:
            errors.append(
                "sheets_overlay.enabled requires an inventory section in the configuration"
            )
        if not config.sheets_overlay.spreadsheet_id.strip():
            errors.append("sheets_overlay.spreadsheet_id may not be blank when enabled")
        if (
            config.sheets_overlay.credentials_file is None
            or not config.sheets_overlay.credentials_file.is_file()
        ):
            errors.append(
                "sheets_overlay.credentials_file must point to an existing "
                "service-account key file when enabled: "
                f"{config.sheets_overlay.credentials_file}"
            )
    if (
        config.sheets_overlay is not None
        and config.sheets_overlay.write_new_litters
        and not config.sheets_overlay.enabled
    ):
        errors.append("sheets_overlay.write_new_litters requires sheets_overlay.enabled = true")
    if errors:
        raise ConfigurationError("Configuration errors:\n- " + "\n- ".join(errors))
