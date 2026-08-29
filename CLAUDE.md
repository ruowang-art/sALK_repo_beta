# Möuseley Kräs — Project Conventions

Möuseley Kräs is a local, safety-first pipeline that turns manually downloaded Transnetyx CSVs into a
reconciled mouse-inventory copy, an audit/exception report, and a Live Label weaning-card workbook.
Source code lives in `src/automouse/`; tests in `tests/`; behavior is documented in `README.md` and
`docs/MACOS_EXECUTABLE_PLAN.md`.

## Data-safety rules (mandatory)

- Never modify production laboratory data during development. Treat these as read-only, never
  overwrite/rename/move them, and never use them as test output destinations:
  - `test_mouse_inventory.csv` at the repo root — despite the name, this is the file
    `config/pipeline_run.yaml` points `inventory.file` at for real runs. It is the working master
    inventory, not a disposable test fixture.
  - `raw transnetyx csv/` — real downloaded Transnetyx exports.
  - `Live_Label_Salk_Cage_Card_Data_Template.xlsx` and `Live_Label_Salk_Cage_Card_Data_Template (1).xlsx`
    — cage-card templates (the `(1)` copy is the one currently referenced by config).
  - Anything under `outputs/019fb5fc-cfb6-7a51-9423-58940a90cde9/automouse_runtime/` — production run
    output.
  - Use `tests/fixtures/` or files you create yourself for development/testing, never the files above.
- Always create a checksum-verified backup before writing to the inventory (see
  `inventory_manager.py`). Inventory updates are written to a new, uniquely named copy — never back
  onto the source file.
- Never overwrite an existing genotype that conflicts with a new result. Conflicts are preserved and
  reported in the exception workbook, not resolved automatically.
- Never guess mouse identity. Matching is exact against the configured `Mouse`/`ID`/`Sample` columns;
  no fuzzy matching, no auto-created inventory rows.
- Unknown/unapproved genotype or assay values must become an explicit exception, never a silent
  default or a dropped row.
- Every translated/processed record must get an explicit audit outcome (see `exception_report.py`).
- A downstream stage failing (e.g. cage-card generation) must not invalidate or destroy artifacts
  already written by earlier successful stages (backup, updated inventory, exception report).

## Working conventions

- Run the full suite after changing matching, inventory, or translation-validation logic:
  `PYTHONPATH="$PWD/src" .venv/bin/python -m unittest discover -s tests -v`
- The R genotype translation script is external to this repo (see `r.translation_script` in
  `config/pipeline_run.yaml`) and is invoked via `scripts/transnetyx_cli_wrapper.R` /
  `r_runner.py` using `subprocess` with an argument list — never a shell string.
- Column/cell mappings (inventory columns, cage-card template cells) belong in
  `config/pipeline_run.yaml`, not hard-coded in application logic.
- `--dry-run` performs validation and matching without writing an inventory copy or cage cards; prefer
  it when testing changes against real-shaped data.
- `src/automouse/web/` is a thin local Flask UI over `app.run_batch` (started via `automouse serve`
  or `AutoMouse_WebApp.command`) — it must stay single-user/local (bind `127.0.0.1`) and must not
  duplicate matching/inventory/translation logic; add new pipeline behavior in `app.py` and its
  collaborators, not in the web layer. Its `/download/<path>` route must only ever serve files that
  resolve inside `config.runtime_root`; if you touch that route, keep the path-containment check and
  don't regress it into serving arbitrary filesystem paths.
- `inventory.source_sheet_url` (e.g. a Google Sheet URL) is a convenience link shown in the web app
  only — it is deliberately not a live data source for anything except the one explicitly-scoped
  exception below. Möuseley Kräs must not gain any broader automatic read/write access to that sheet
  (it's a real shared document other lab members may be editing, unlike the local inventory file,
  which Möuseley Kräs always writes to as a brand-new copy) without a further explicit decision from
  the user.
- The first exception is `sheets_overlay` (`config.py`'s `SheetsOverlayConfig`, implemented in
  `sheets_overlay.py`): an explicitly opt-in (`enabled: false` by default), read-only
  (`spreadsheets.readonly` scope, service-account credentials) fetch of only DOB and Wean_By from the
  primary Google Sheet, used only to fill *blank* DOB/Wean_By cells in the in-memory inventory table
  before Live Label cage cards are built (see `_apply_sheet_dob_wean_overlay` in `app.py`, called from
  both `_complete_inventory_and_cage_card_pipeline` and `run_generate_cards` right before cage-card
  generation). It never overwrites a DOB/Wean_By value already present locally, never touches any
  other field (especially not genotype or matching), never writes to the sheet, and a fetch failure
  (offline, bad credentials, renamed sheet/tab) must degrade to a run warning and let the batch
  finish — never fail the run. Sheet columns are located by matching the sheet's header row against
  the same `inventory.expected_headers` text already required of the local CSV, not by position or
  fuzzy matching. Do not widen *this* integration's scope (e.g. to genotype, to other fields) without
  another explicit decision from the user.
- The second, separate exception is `sheets_overlay.write_new_litters` (`config.py`, default `false`,
  requires `sheets_overlay.enabled = true` as well — see `validate_config`): lets the Mouse Inventory
  Update portal below also append newly entered litters to the live Google Sheet, in addition to the
  local inventory copy it always writes (see `sheets_litter_writer.py` and
  `app.append_litter_to_inventory`). It requests its own read-write-scoped credential
  (`https://www.googleapis.com/auth/spreadsheets`) from the same service-account key file, separate
  from the read-only overlay above, so the DOB/Wean_By read path can never write regardless of this
  flag. Immediately before appending, it re-fetches the sheet's current identifier column(s) and
  checks the new litter's mouse IDs against them — a mouse ID that already exists there (e.g. another
  lab member added it by hand moments earlier) becomes a `CONFLICT` audit entry and is written to
  neither target. Once this fetch has succeeded for a run, the Sheet — not the local inventory copy —
  is the source of truth for whether a mouse ID is taken, since the Sheet is the lab's actual primary
  inventory and the local file is only Möuseley Kräs's own mirror of it: a mouse ID whose row still
  sits in the local copy but has since been deleted from the Sheet (e.g. because it was entered by
  mistake and someone removed it there) is *not* a conflict, and re-submitting it replaces that stale
  local row rather than creating a second one or refusing the submission. This is the one place in
  the project where an existing local inventory row is ever removed automatically; it only happens
  for a mouse ID that is part of the litter being submitted right now, only when this feature's Sheet
  fetch has actually succeeded that run, and it is always paired with re-adding a fresh row for the
  same ID in the same operation — it is never a bare deletion. When the Sheet can't be reached this
  run (`write_new_litters` off, or the fetch failed), the local inventory copy remains the only signal,
  exactly as before, and a mouse ID present there still blocks the submission as a `CONFLICT`. This
  Sheet-fetch (read-only) now also runs during `--dry-run`, so a preview accurately reflects what a
  real run would do; a dry run still never writes anywhere regardless of what the fetch finds. Any
  other failure (network, auth, quota, a missing identifier column) degrades to a run warning — the
  local inventory write must still succeed independently; the two targets are never coupled such that
  a Sheet failure blocks or reverts the local write, or vice versa. Requires the service account to
  have Editor (not just Viewer) access to the sheet. Do not widen *this* integration's scope (e.g. to
  editing existing rows other than this specific stale-ID replacement, to genotype, to Cage Card
  Production) without another explicit decision from the user.
- The webapp (and the CLI) is split into two independent portals — do not blur this boundary:
  - **Cage Card Production** (`/`, and the `run`/`translate` CLI commands): unchanged. `run` always
    does translation, the inventory genotype update, and cage-card generation together as one step;
    there is no longer a way to split that into separate stages (an earlier `update-inventory` /
    `generate-cards <run-id>` pair of commands existed for this and was retired in favor of the
    litter-entry portal below — do not reintroduce that split without an explicit decision from the
    user).
  - **Mouse Inventory Update** (`/inventory`, and the `enter-litter` CLI command,
    `litter_entry.py`/`app.append_litter_to_inventory`): adds one litter (strain, DOB, mother,
    father, a female/male pup count, and a first/last mouse-ID range) to the inventory as brand-new
    mice, before any Transnetyx genotyping — genotype is deliberately left blank, filled in later by
    Cage Card Production. Females always take the earliest mouse IDs in the range, males the rest.
    The pup counts and the ID-range size must all agree exactly; any mismatch is an explicit
    `InputValidationError`, never silently reconciled. A mouse ID already present in the inventory is
    never overwritten — it becomes an explicit `CONFLICT` audit entry instead, the same as any other
    inventory-safety exception in this project. Requires `inventory.append_only = true`, since every
    submitted litter is always brand-new rows, never a match against an existing one. Always writes
    the local inventory copy; also appends to the live Google Sheet if
    `sheets_overlay.write_new_litters` is enabled (see the `sheets_overlay.write_new_litters`
    exception above) — otherwise it writes only to the local inventory copy.
- `xol-pots-xol/` is a separate, standalone sibling project (its own `pyproject.toml`, `src/`,
  `tests/`, and README), not part of Möuseley Kräs: it consolidates sparse Live Label cage-card
  workbooks that Möuseley Kräs already produced into fuller ones. It only ever reads uploaded
  `.xlsx` cage-card files and writes a new workbook built from scratch — it must never import from
  `automouse`, read the inventory or raw Transnetyx files, or write to the cage-card template. Its
  own conventions live in `xol-pots-xol/README.md`, not here.

## Documentation layout

`CLAUDE.md` and `README.md` live at the repo root — not in `Markdown_files/` — because Claude Code,
GitHub, and most other tooling only auto-discover project instructions and repo-landing-page READMEs
at the root; a copy nested in a subdirectory would not be found automatically. Every other `.md` file
in this project (progress logs, review responses, architecture write-ups, phase reports) still
belongs in `Markdown_files/` per this project's standing convention — this is a deliberate, narrow
exception for exactly these two files, not a reversal of that convention.
