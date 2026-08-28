# Möuseley Kräs Macintosh executable plan

## Objective

Process one or more raw Transnetyx CSV files as one logical batch, safely reconcile genotypes with the master inventory, and produce new weaning-cage Live Label rows grouped by litter and sex. All supplied source files remain read-only.

## Install or upgrade

1. Install Python 3.11 or newer and R for macOS.
2. Ensure the R packages `dplyr` and `purrr` are installed.
3. Double-click `AutoMouse_Setup.command`.

Setup creates or reuses the virtual environment, installs third-party libraries only when missing, checks the R packages, invokes Möuseley Kräs 0.3.1 directly from this project's `src` directory, and runs the complete automated test suite. The run command therefore does not depend on a stale editable install or `.venv/bin/automouse` launcher.

### Clearing the old setup

Double-click `AutoMouse_Clear_Old_Setup.command`. This runs setup with `--reset`:

1. validate that the current directory is the Möuseley Kräs project;
2. move `.venv` to `AutoMouse_legacy_environments/.venv_YYYYMMDD_HHMMSS`;
3. create a fresh `.venv`, install the required libraries, and test Möuseley Kräs 0.3.1 from this project;
4. restore the previous `.venv` automatically if rebuilding or testing fails.

The old environment is moved rather than immediately deleted, so it is recoverable. After confirming normal operation, its timestamped directory may be moved to Trash manually.

If macOS blocks a command file, Control-click it, choose **Open**, and confirm once.

## Routine batch run

1. Manually download one or more raw Transnetyx CSVs.
2. Double-click `AutoMouse_Run.command`.
3. In the file chooser, use Command-click or Shift-click to select all CSVs belonging to the batch.
4. Confirm the numbered file list printed in Terminal.
5. Wait for one consolidated run summary.
6. Review the exception workbook before promoting the inventory copy or importing Live Label data.

Equivalent Terminal command:

```bash
cd "/Users/ruoxiwang/Documents/Salk_Genotype_Troubleshoot"
PYTHONPATH="$PWD/src" .venv/bin/python -m automouse \
  --config config/pipeline_run.yaml run --verbose \
  "/path/to/first.csv" "/path/to/second.csv"
```

## Routine batch run (browser, no Terminal)

For lab staff who prefer not to use Terminal or the AppleScript file picker, `AutoMouse_WebApp.command`
starts a local-only web app (`127.0.0.1`, single user) instead:

1. Double-click `AutoMouse_WebApp.command`; a browser tab opens automatically.
2. Choose or drag one or more raw Transnetyx CSVs onto the page.
3. Click **Run Möuseley Kräs** and read the results page (counts, warnings, and download links).
4. If a file was already processed before, the page explains this and asks for an explicit decision
   instead of silently reprocessing or silently refusing.

This is a presentation layer only — it calls the same `run_batch` pipeline as `AutoMouse_Run.command`
and provides no separate matching/inventory logic of its own. Equivalent Terminal command:

```bash
PYTHONPATH="$PWD/src" .venv/bin/python -m automouse --config config/pipeline_run.yaml serve
```

## Consolidated pipeline

1. **Batch preflight**: require at least one regular `.csv`, compute checksums, and reject duplicate content inside the selected batch.
2. **Archive all inputs**: create uniquely indexed byte-verified archives and checksum-index entries.
3. **Validate all raw files**: stop before inventory work if any schema, encoding, row, or sample-ID check fails.
4. **Translate all files**: invoke the existing R function sequentially with explicit paths, timeouts, exit-code checks, and per-file output names.
5. **Validate and reconcile translations**: preserve per-file provenance; use a sole READY result over failed attempts; collapse agreeing READY duplicates; block conflicting READY results.
6. **Inventory safety gate**: validate positional headers, reject duplicate primary IDs, and make one checksum-verified source-inventory backup.
7. **Two-pass exact matching**: resolve all `Mouse`/`ID`/`Sample` matches and competing results before applying any update. Fill only blank composite `Genotype` cells; confirm equal values; preserve conflicts.
8. **Weaning-card grouping**: select safely `UPDATED` and `CONFIRMED` mice; group by normalized Sex, Strain, Kras genotype, and configurable DOB windows; natural-sort by DOB and ID; split at five mice while avoiding avoidable one-mouse splits.
9. **Combined outputs**: write one updated inventory copy, audit CSV, exception workbook, Live Label workbook, run-summary JSON, and log.

## Weaning-card field rules

| Live Label field | Rule |
|---|---|
| `# IN CAGE` | Number of mice on the current row, maximum five |
| `# IN LITTER` | Sum of the source-litter sizes represented on the row; unchanged from the old litter count when the row contains one source litter |
| `SEX` | Normalized Male/Female partition |
| `DATE WEANED` | Uniform inventory `Wean_By`; when `DATE BORN` is a range, use `DATE BORN + 28 days` and show the resulting range |
| `DATE BORN` | Canonical inventory `DOB`; shown as a date range when compatible cage-mates have different DOBs |
| Mouse/genotype pairs | Natural-sorted eligible IDs and final inventory genotypes |
| DAM/SIRE | Inventory Mother/Father values when uniform; blank plus warning if mixed |
| Parent genotypes | Filled only when parent lookup is unique and unambiguous |

Existing `Cage` is not required for these new cages. Compatible cages require the same Sex, same Strain, and same normalized Kras genotype. `LSL-G12D/+` and `K/+` are grouped together as `K/+`, but `K/+` and `+/+` are never mixed. The default DOB span is at most 5 days for males and 7 days for females; adjust `male_dob_window_days` and `female_dob_window_days` in `config/pipeline_run.yaml` if the lab wants tighter windows. Missing or invalid DOB, Sex, Strain, or Kras genotype prevents automatic grouping and appears in `Card Grouping Issues`.

## Master-inventory mapping

The source CSV has repeated headers, so mappings are positional. The composite update target is the first `Genotype` column at position 21.

| Role | Header | Column |
|---|---|---:|
| Primary mouse ID | Mouse | 1 |
| Secondary ID | ID | 13 |
| Dam | Mother | 14 |
| Sire | Father | 15 |
| Date born | DOB | 16 |
| Sex | Sex | 17 |
| Date weaned | Wean_By | 18 |
| Sample ID | Sample | 20 |
| Composite genotype | Genotype | 21 |

## Recovery

- A failure before inventory backup means no inventory output was created.
- A failure later still leaves the source inventory unchanged; inspect the run summary and retained artifacts.
- A previously processed raw file is blocked. Use `--allow-duplicate-input` only for an intentional retry.
- Use `--dry-run` for validation/audit without an updated inventory copy.
- Change paths or positional mappings in `config/pipeline_run.yaml` if source files move or schemas change.
