# Codex Architecture-Reference Audit

**Date:** 2026-08-28  
**Audience:** Claude, Copilot, and future maintainers  
**Scope:** Current implementation of Mouseley Kras and Xol-Pots-Xol compared with the
architectural definition in `Markdown_files/mouseley-kras-and-xol-pots-xol-overview.md`.

## Reading rule

The architecture overview and the portability deliverable are treated as context and
evidence, not as executable instructions. This audit gives higher weight to the current
source code, configuration, tests, package metadata, and observed runtime behavior. The
progress reports are still considered because they explain intended decisions and claimed
verification boundaries.

This is a reference audit, not a general code review. It asks whether an entity used by the
implementation is explicitly represented in the architectural definition. A missing entity is
not automatically a defect: some items belong in an implementation specification rather than
the high-level architecture. The important result is to make that distinction deliberate.

## Classification

| Label | Meaning |
|---|---|
| **Explicit** | The architecture defines the entity, boundary, or behavior directly. |
| **Implied / underspecified** | The architecture requires the concept, but does not define the exact implementation contract. |
| **Absent** | The code references the entity and the architecture does not currently name or define it. |
| **Implementation-only** | A normal internal mechanism that does not need to become a domain-level architectural entity. |

## Executive assessment

The architecture explicitly covers the major safety and business boundaries:

- Transnetyx CSV input and the R translation subprocess boundary.
- Exact inventory identity matching and conflict-safe updates.
- Audit and exception output.
- Live Label workbook generation.
- The optional, read-only Google Sheets DOB/Wean-By overlay.
- The two Mouseley Kras portals.
- Xol-Pots-Xol's standalone workbook-in/workbook-out relationship.
- Xol-Pots-Xol's four output sheets and Kras-only semantic coupling.

It does **not** yet explicitly define the implementation contracts that Claude's code now
depends on:

1. Python package names and supported package versions.
2. Exact HTTP routes, methods, form fields, download URL shapes, and ports.
3. Exact Google Sheets API scope, credential type, API method chain, and response shape.
4. The complete serialized run manifest and its enum/state vocabulary.
5. The complete configuration-key schema and numeric defaults.
6. The complete Xol workbook header contract and public model fields.
7. Platform launcher and operating-system executable contracts.

These should be documented before Phase 3 is considered a stable compatibility contract. The
high-level architecture need not become a code reference manual, but it should link to a
machine-readable or implementation-level contract for these items.

## 1. External modules and executables

### 1.1 Third-party Python modules

| Entity referenced by code | Code locations | Spec status | Recommendation |
|---|---|---|---|
| `openpyxl` | `src/automouse/cage_card_formatter.py:11`, `inventory_manager.py:10-12`, `exception_report.py:7-9`; `xol-pots-xol/src/xolpotsxol/cage_card_reader.py:10`, `writer.py:14-15` | **Implied / underspecified**: Excel workbooks are central, but the library is not named | Add an implementation contract stating that `.xlsx` processing uses `openpyxl`, with supported versions and workbook feature limits. |
| `PyYAML` (`yaml`) | `src/automouse/config.py:3` via dynamic import in config loading | **Absent**: the spec says YAML configuration, not the parser dependency | Name the parser and define whether JSON-compatible input is intentionally accepted. |
| `Flask` | `src/automouse/web/__init__.py:23`; `xol-pots-xol/src/xolpotsxol/web/__init__.py:20` | **Implied / underspecified**: the spec says local Flask web app | Record supported Flask/Python versions and that the web app is local, single-user, and not a production server. |
| `Werkzeug` / `secure_filename` | `src/automouse/web/__init__.py:24`; Xol web module:20 | **Absent** as a named dependency, though it arrives with Flask | Include it in the dependency bill of materials or explicitly classify it as a Flask transitive dependency. |
| `google-auth` service-account modules | `src/automouse/sheets_overlay.py:21` | **Implied / underspecified**: read-only Google Sheets is defined, credential implementation is not | Define credential type, local credential-file handling, and minimum scopes. |
| `google-api-python-client` | `src/automouse/sheets_overlay.py:21` | **Implied / underspecified** | Define the Sheets API client dependency and the supported API surface. |
| `pandas` | Declared in the root inventory extra and setup/import checks; no current Python source import found | **Absent as an active code dependency** | Either remove it from runtime/setup declarations or document the intended use. Do not treat declaration alone as proof that the pipeline uses it. |
| `pytest` | Development dependency | **Implementation-only** | Keep in the development/test contract, not the domain architecture. |
| `pip-tools` | Development/build dependency and lock-generation workflow | **Implied / underspecified** by the portability reports | Document it in the reproducibility workflow, not as a runtime architecture dependency. |

### 1.2 External executables, file formats, and platform facilities

| Entity | Code or launcher references | Spec status | Recommendation |
|---|---|---|---|
| `Rscript` | `src/automouse/config.py:30-48`; invoked by `src/automouse/r_runner.py:31-57` | **Explicit at boundary, underspecified operationally** | Define supported R versions, executable discovery rules, and the required R package set. |
| External translation script | `config/pipeline_run.yaml`; hashed and recorded by `src/automouse/app.py` | **Explicit conceptually, absent as a versioned artifact contract** | Give the script a stable name, release/version identity, ownership, and compatibility contract. SHA-256 detects drift but is not a human-readable release identity. |
| R packages `dplyr` and `purrr` | R translation environment/lock record | **Implied / underspecified** | Add a reproducible R environment definition or clearly state that the lock file is verification metadata only. |
| R wrapper flags `--translation-script`, `--input`, `--output`, `--quiet-diagnostics` | `src/automouse/r_runner.py:41-51` | **Absent** | Specify the Python-to-R CLI contract, exit-code meanings, required output columns, and timeout behavior. |
| `.csv` and `.xlsx` file formats | Validators, inventory manager, cage-card reader/writer | **Explicit**, but exact schemas vary | Link each artifact to a versioned schema: raw input, translated output, inventory, audit, exception, and Live Label workbook. |
| POSIX shell (`bash`/`zsh`) | macOS and Linux launchers | **Implied / underspecified** | State minimum shell versions and which scripts are tested on real Linux versus macOS proxy execution. |
| PowerShell and `System.Windows.Forms.OpenFileDialog` | Windows launchers | **Absent** from the architecture | Add Windows launcher prerequisites and verification status. The portability report correctly says these launchers were written but not executed in the current environment. |
| macOS `osascript` / AppleScript picker | Existing macOS launchers | **Absent** | Record this as a macOS-only launcher dependency, separate from core pipeline behavior. |
| Browser launch through Python `webbrowser` | Both local web interfaces | **Implementation-only / underspecified UX** | Define whether automatic browser opening is required or best-effort. |

Standard-library modules such as `csv`, `json`, `hashlib`, `pathlib`, `subprocess`, `platform`,
`secrets`, and `threading` are used throughout the code. They are implementation dependencies,
not external architectural services, and do not all need to be added to the high-level spec.

## 2. HTTP and network API references

### 2.1 Mouseley Kras local web API

| Method and route | Code location | Spec status | Contract gap |
|---|---|---|---|
| `GET /` | `src/automouse/web/__init__.py:138` | **Implied** by “local Flask web app” | Define the portal landing page and whether it is the Cage Card Production portal. |
| `POST /run` | `src/automouse/web/__init__.py:142` | **Implied** by Cage Card Production | Define multipart upload field `raw_files`, `dry_run`, validation behavior, and confirmation response. |
| `POST /run/confirm` | `src/automouse/web/__init__.py:189` | **Absent** | Define the pending-run confirmation token and lifecycle. |
| `POST /run/cancel` | `src/automouse/web/__init__.py:223` | **Absent** | Define cancellation semantics and cleanup guarantees. |
| `GET /download/<path:relative_path>` | `src/automouse/web/__init__.py:231` | **Absent** | Define which generated artifacts are downloadable and how path traversal is prevented. |
| `GET /inventory` | `src/automouse/web/__init__.py:241` | **Implied** by Mouse Inventory Update | Define the portal route and form-rendering contract. |
| `POST /inventory/submit` | `src/automouse/web/__init__.py:246` | **Implied** by litter entry | Define all form fields: `total_pups`, `female_count`, `male_count`, `strain`, `dob`, `mother`, `father`, `first_mouse_id`, `last_mouse_id`, and `dry_run`. |

The implementation also relies on HTTP status semantics that are not in the architecture:
successful HTML responses, `400` for invalid upload/form input, `404` for missing or unsafe
downloads, and `422` for expected pipeline errors. These should be recorded if the routes are
intended to be a supported interface rather than an internal UI detail.

### 2.2 Xol-Pots-Xol local web API

| Method and route | Code location | Spec status | Contract gap |
|---|---|---|---|
| `GET /` | `xol-pots-xol/src/xolpotsxol/web/__init__.py:48` | **Implied** by local Flask app | Define the upload portal. |
| `POST /consolidate` | Xol web module:52 | **Implied** by consolidation workflow | Define multipart field `cage_card_files`, accepted extensions, and error behavior. |
| `GET /download/<run_id>/<filename>` | Xol web module:98 | **Absent** | Define output naming, run retention, and download safety rules. |

The default local server addresses are `127.0.0.1:8765` for Mouseley Kras and
`127.0.0.1:8766` for Xol-Pots-Xol. The architecture says “local Flask web app” but does not
define these ports, host binding, or whether callers may override them. Add those decisions to
the compatibility contract.

### 2.3 Google Sheets API

| Reference | Code location | Spec status |
|---|---|---|
| Scope `https://www.googleapis.com/auth/spreadsheets.readonly` | `src/automouse/sheets_overlay.py:21` | **Explicit in spirit, absent in exact form** |
| `build("sheets", "v4", credentials=..., cache_discovery=False)` | `sheets_overlay.py` | **Absent** |
| `service.spreadsheets().values().get(...).execute()` | `sheets_overlay.py` | **Absent** |
| Request properties `spreadsheetId` and `range` | `sheets_overlay.py` | **Implied / underspecified** |
| Response property `values` | `sheets_overlay.py` | **Absent** |
| Config properties `spreadsheet_id`, `worksheet`, `credentials_file` | `src/automouse/config.py:148-160` | **Implied / underspecified** |

The architecture does define the important safety behavior: opt-in, read-only, exactly DOB and
Wean-By, fill blanks only, no genotype matching, and degrade to a warning on failure. It should
add the exact API/client contract so a future implementation cannot accidentally widen the
integration.

The configured `inventory.source_sheet_url` is a convenience browser link, not a data API
endpoint. The architecture defines the conceptual shared sheet but not its exact URL or ID;
that is appropriate for a deployment secret/configuration, not for the architecture document.

## 3. State, model, configuration, and serialized properties

This section lists public dataclass fields, enums, configuration properties, serialized summary
keys, and web state keys. Local temporary variables are intentionally excluded. The question is
whether each contract is represented in the architecture, not whether every Python attribute
must be documented.

### 3.1 Mouseley Kras enums and domain models

| Entity | Code location | Spec status |
|---|---|---|
| `RunStage`: `INITIALIZED`, `INPUT_ARCHIVED`, `RAW_VALIDATED`, `TRANSLATED`, `TRANSLATION_VALIDATED`, `INVENTORY_BACKED_UP`, `INVENTORY_UPDATED`, `EXCEPTIONS_WRITTEN`, `CAGE_CARDS_GENERATED`, `COMPLETED`, `FAILED` | `src/automouse/models.py:10-21` | **Implied / underspecified**. The pipeline flow names most stages, but the closed enum and legal transitions are not defined. |
| `RecordStatus`: `READY`, `READY_WITH_WARNING`, `PENDING_RERUN`, `NO_RESULT`, `AMBIGUOUS`, `DUPLICATE`, `MOUSE_NOT_FOUND`, `MULTIPLE_MATCHES`, `CONFLICT`, `MANUAL_REVIEW` | `models.py:24-35` | **Implied / underspecified**. The architecture gives examples and says closed enum, but does not enumerate the complete set. |
| `AuditAction`: `UPDATED`, `PROPOSED_UPDATE`, `CONFIRMED`, `SKIPPED`, `NOT_FOUND`, `MULTIPLE_MATCHES`, `DUPLICATE`, `CONFLICT`, `MANUAL_REVIEW`, `ERROR`, `LITTER_ENTERED` | `models.py:37-49` | **Implied / underspecified**. Actions and transition rules are not a complete architectural contract. |
| `ValidationResult`: `valid`, `errors`, `warnings`, `row_count`, `metadata` | `models.py:52-61` | **Absent as an exact model**; conceptually covered by validation/reporting. |
| `RRunResult`: `command`, `exit_code`, `stdout`, `stderr`, `output_path`, `duration_seconds` | `models.py:64-72` | **Absent**; subprocess behavior is described only at a high level. |
| `TranslatedGenotypeRecord`: `sample_id`, `mouse_id`, `assay`, `raw_result`, `translated_genotype`, `status`, `warnings`, `source_row`, `translated_strain`, `translated_sex`, `source_file` | `models.py:74-91` | **Implied / underspecified**; core genotype fields are described, provenance fields are not. |
| `AuditEntry`: `run_id`, `timestamp`, `sample_id`, `mouse_id`, `inventory_row`, `previous_genotype`, `proposed_genotype`, `final_genotype`, `action`, `status`, `source_file`, `source_row`, `messages` | `models.py:94-115` | **Implied / underspecified**; auditability is explicit, exact schema is not. |
| `InventoryUpdateReport`: `audit_entries`, `updated_mouse_ids`, `confirmed_mouse_ids`, `missing_cage_mouse_ids`, `card_eligible_mouse_ids`, `card_grouping_exception_mouse_ids`, `warnings`; derived `action_counts` | `models.py:118-133` | **Absent as an exact public report contract**. |
| `CageCardRecord`: `cage_id`, `experiment_url`, `strain`, `animal_count`, `litter_count`, `sex`, `date_weaned`, `date_born`, `mouse_ids`, `genotypes`, `dam`, `dam_genotype`, `sire`, `sire_genotype`, `breeder`, `setup_date`, `warnings` | `models.py:136-175` | **Implied / underspecified**; most domain fields appear in the overview, but the complete record and warning semantics do not. |
| `TranslationValidationReport`: `valid`, `errors`, `warnings`, `row_count`, `records`, `status_counts`, `metadata` | `models.py:178-203` | **Absent as an exact report contract**. |

### 3.2 Mouseley Kras run context and manifest

`RunContext` is the most important undocumented state contract because it is persisted into run
summary JSON and is likely to be consumed by future tooling.

| Property group | Properties referenced in code | Spec status |
|---|---|---|
| Run identity/lifecycle | `run_id`, `started_at`, `stage`, `completed_at`, `failed_stage`, `stage_history` | **Implied / underspecified**; the spec describes audit stages but not the serialized lifecycle vocabulary or transition rules. |
| Outcome collections | `warnings`, `errors`, `artifacts`, `counts` | **Implied / underspecified**; exception and audit outputs are defined conceptually, not as a stable JSON schema. |
| Integrity | `checksum`, `checksums`, `source_sha256`, `source_sha256_by_file`, `config_sha256`, `output_sha256_by_file` | **Explicit in principle, underspecified in schema**; define which fields are legacy versus canonical and whether hashes are SHA-256 strings. |
| Execution mode | `dry_run`, `implementation_scope` | **Absent**. `implementation_scope` currently defaults to `phase_1_and_phase_2`, which appears stale after Phase 3 and should be either updated or removed. |
| Environment | `application_version`, `python_version`, `r_version`, `os`, `os_version`, `machine_arch`, `config_path` | **Implied / underspecified**; portability is a stated goal, but the exact manifest fields and value semantics are not. |
| Artifact paths | `raw_input_file(s)`, `archived_input_file(s)`, `translated_output_file(s)`, `translation_validation_file(s)`, `run_summary_file`, `log_file`, `inventory_backup_file`, `updated_inventory_file`, `updated_inventory_csv_file`, `exception_report_file`, `audit_file`, `cage_card_file` | **Implied / underspecified**; outputs are named conceptually, but this complete key set and singular/plural rules are absent. |
| Counts | `raw_record_count`, `input_file_count`, `translated_record_count`, `inventory_records_updated`, `inventory_records_confirmed`, `mouse_not_found_count`, `multiple_match_count`, `conflict_count`, `manual_review_count`, `proposed_update_count`, `missing_cage_count`, `cages_selected`, `card_eligible_count`, `card_grouping_exception_count`, `weaning_groups_selected`, `cage_cards_generated` | **Absent as a stable schema**. |
| Sheets overlay provenance | `sheets_overlay_enabled`, `sheets_overlay_fills` | **Implied / underspecified**. The architecture requires per-mouse fill auditing, but does not define the property shape. |
| R provenance | `translation_script_path`, `translation_script_sha256` | **Absent** from the architecture, although highly valuable for reproducibility. |

The architecture should define a versioned run-manifest schema, including whether unknown keys
are allowed and how the schema itself is versioned. This is more important than documenting
every internal Python object because it is the durable record of what happened to laboratory
data.

### 3.3 Mouseley Kras configuration properties

| Config object | Properties | Spec status |
|---|---|---|
| `RConfig` | `executable`, `translation_script`, `wrapper_script`, `timeout_seconds`, `print_diagnostics` | **Implied / underspecified**. R is defined, but these keys, defaults, and precedence rules are not. |
| `TransnetyxConfig` | `sample_id_column`, `required_columns`, `metadata_columns`, `supported_extensions`, `delimiter`, `encoding`, `require_any_assay_value` | **Implied / underspecified**. Input validation is defined conceptually; the exact schema is absent. |
| `TranslationConfig` | `sample_id_column`, `genotype_column`, `required_columns`, `approved_genotypes`, `approved_genotype_pattern`, `failure_tokens` | **Implied / underspecified**. Approved genotype grammar and failure-token behavior need a versioned contract. |
| `InventoryConfig` | `file`, `format`, `output_sheet_name`, `append_only`, `source_sheet_url`, `columns`, `expected_headers`, `identifier_roles`, `known_strains`, `audit_column_names` | **Implied / underspecified**. Inventory safety is explicit; exact key names and allowed formats are not. |
| `CageCardConfig` | `template`, `sheet_name`, `max_mice_per_card`, `grouping_strategy`, `male_dob_window_days`, `female_dob_window_days`, `experiment_url`, `generate_for_actions`, `expected_headers` | **Implied / underspecified**. The Live Label mapping is a core concept, but this complete configuration contract is absent. |
| `SheetsOverlayConfig` | `enabled`, `spreadsheet_id`, `worksheet`, `credentials_file` | **Implied / underspecified**. The opt-in integration is explicit, exact key semantics are not. |
| `AppConfig` | `project_root`, `runtime_root`, `application_version`, `r`, `transnetyx`, `translation`, `inventory`, `cage_card`, `sheets_overlay`, `config_path` | **Absent as a full aggregate schema**. |

The overview says configuration is data rather than code, so this gap deserves attention. A
configuration schema should be an explicit companion to the architecture, even if the values
remain deployment-specific.

### 3.4 Mouseley Kras web state

| State/property | Code location | Spec status |
|---|---|---|
| `PendingUpload`: `directory`, `file_paths`, `dry_run` | `src/automouse/web/__init__.py:33-39` | **Absent**; internal implementation state unless the confirmation workflow is supported as an API contract. |
| `PendingUploadStore`: `_lock`, `_pending`, random confirmation token | web module:41-76 | **Absent**; document cleanup, expiration, and single-user assumptions if retained. |
| Flask config keys `AUTOMOUSE_CONFIG`, `PENDING_UPLOADS` | web module:122-123 | **Implementation-only** unless extensions or tests are expected to use them. |
| Download labels for updated inventory, backup, exception, audit, cage card, summary, log | web module around the download helper | **Implied / underspecified**; map each label to a stable artifact type. |

### 3.5 Xol-Pots-Xol models and constants

| Entity | Code location | Spec status |
|---|---|---|
| `EXPECTED_HEADERS` complete 23-column tuple | `xol-pots-xol/src/xolpotsxol/models.py:15-22` | **Implied / underspecified**. The architecture says strict header validation and describes the output shape, but does not enumerate the complete fixed contract. |
| `MAX_MICE_PER_CAGE = 5` | Xol models:24 | **Explicit in examples/behavior, but not clearly a versioned invariant**. |
| `SourceMouse`: `mouse_id`, `genotype`, `sex`, `strain`, `dob_min`, `dob_max`, `dam`, `dam_genotype`, `sire`, `sire_genotype`, `breeder`, `experiment_url`, `source_file`, `source_row`, `source_in_litter` | Xol models:28-55 | **Implied / underspecified**. Domain fields are visible in the overview; source provenance fields are not. |
| `source_cage_key` | Xol models:49-55 | **Absent**; internal grouping aid unless exposed in reports. |
| `ConsolidatedCage`: `mice`, `warnings` | Xol models:57-63 | **Absent as an exact model contract**. |
| `ConsolidationResult`: `consolidated_cages`, `unconsolidated_mice`, `warnings`, `input_cage_count`, `input_mouse_count` | Xol models:65-70 | **Implied / underspecified**; output categories are explicit, exact model fields are not. |
| `DEFAULT_MALE_DOB_WINDOW_DAYS = 2`, `DEFAULT_FEMALE_DOB_WINDOW_DAYS = 7` | `xol-pots-xol/src/xolpotsxol/consolidator.py:28-29` | **Absent as named defaults**. Add them to the consolidation contract or move them into configuration. |
| `KRAS_GENOTYPE_GRAMMAR_VERSION = 1` and `KRAS_ALLELE_SHORTHAND` | Xol consolidator:83-84 | **Implied / underspecified**. The narrow Kras grammar is explicit, but the exact allowlist and version semantics should be documented. |

### 3.6 Xol-Pots-Xol web state

| State/property | Code location | Spec status |
|---|---|---|
| Flask config `RUNTIME_ROOT` | `xol-pots-xol/src/xolpotsxol/web/__init__.py:45-46` | **Absent**; implementation-only unless runtime retention is a supported behavior. |
| Upload field `cage_card_files` | Xol web module:53 | **Absent** from the architecture. |
| Random `run_id` and output path `run_id/consolidated_cage_cards.xlsx` | Xol web module:68-73 | **Absent** as a web artifact contract. |
| Result properties `input_cage_count`, `input_mouse_count`, `consolidated_cage_count`, `preserved_cage_count`, `warnings`, `download_url` | Xol web module:79-96 | **Implied / underspecified**; the workbook report concept is explicit, the HTML response contract is not. |

## 4. Highest-priority specification gaps

These are the gaps most likely to create a future compatibility or safety problem:

1. **Run manifest schema.** Define a versioned JSON schema for `RunContext.to_summary()`, including enum values, artifact keys, count keys, hash fields, and environment fields. Resolve the apparently stale `implementation_scope` default.
2. **R boundary contract.** Define the wrapper flags, exit codes, required input/output columns, R version, package requirements, timeout semantics, and translation-script versioning.
3. **Google Sheets boundary contract.** Define the exact read-only scope, credential type, API version/methods, response shape, allowed columns, and failure behavior.
4. **Workbook schemas.** Enumerate the complete input/output headers and sheet names for the inventory, Live Label, audit, exception, translated, and Xol workbooks. Include date/value conventions.
5. **Web interface contract.** Decide whether the Flask routes are supported interfaces or merely UI implementation details. If supported, document routes, methods, fields, status codes, ports, host binding, download retention, and token lifecycle.
6. **Configuration schema.** Publish the YAML key schema, defaults, allowed values, and precedence rules. This is especially important because the architecture explicitly promises configuration as data.
7. **Portability prerequisites.** Document Python, R, shell, PowerShell, Excel-file, and browser prerequisites. Keep the current verification distinction: Linux launcher proxy checks are not real Linux verification, and Windows launchers remain unexecuted until a PowerShell environment is available.

## 5. Recommended next action for Claude

Claude can continue Phase 3 work, but before declaring the portability contract complete it should
add or link an implementation-contract document covering the seven items above. The most useful
order is:

1. Freeze the run-manifest and workbook schemas.
2. Freeze the R and Google Sheets external boundaries.
3. Freeze the local web route/field contract, or explicitly label it internal.
4. Generate a dependency and platform support matrix from the actual lock files and launchers.
5. Add tests that assert the frozen contracts, especially serialized keys, headers, route methods,
   and external-call arguments.

## Bottom line

Claude's current code does not show an architectural contradiction in the major business flow.
The main risk is undocumented surface area: the implementation has become more precise than the
architecture. That is a healthy sign for engineering progress, but it means future agents could
mistake implementation details for established design, or invent replacements for contracts that
already exist implicitly in the code. The next documentation step should make those contracts
explicit and versioned, with the run manifest, external boundaries, and workbook schemas first.
