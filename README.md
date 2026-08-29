# Möuseley Kräs

Möuseley Kräs 0.3.1 is a local, safety-first workflow for one or more manually downloaded Transnetyx CSV files. A batch produces one consolidated inventory copy, audit/exception report, and Live Label weaning-card workbook. Source CSVs, the source inventory, the existing R translator, and the cage-card template are never edited.

## Macintosh quick start

1. Double-click `AutoMouse_Setup.command` once.
2. Double-click `AutoMouse_Run.command` (Terminal) or `AutoMouse_WebApp.command` (browser) — see below.
3. Select one or more raw Transnetyx CSVs.
4. Review the exception report before using the updated inventory or Live Label output.

If an older editable installation exists or imports fail, double-click `AutoMouse_Clear_Old_Setup.command`. It moves the old `.venv` into a timestamped recoverable backup and creates a clean environment. A failed rebuild automatically restores the previous environment.

Requirements:

- macOS;
- Python 3.11 or newer (verified working: 3.11, 3.12, 3.13, 3.14);
- Rscript;
- R packages `dplyr` and `purrr`.

## Windows and Linux (implemented, not yet verified)

`launchers/windows/*.ps1` and `launchers/linux/*.sh` are PowerShell/shell equivalents of the
`.command` launchers above (Setup, Run, WebApp, for both this project and Xol-Pots-Xol). **Current
support boundary**: the Linux scripts have been smoke-tested via `bash` on macOS (a reasonable
syntax/logic proxy, not a real Linux machine); the Windows PowerShell scripts have not been
executed at all — no PowerShell interpreter was available in the environment that wrote them.
Neither platform has real-machine or CI verification yet (that's Phase 4). Do not treat "the
scripts exist" as "Windows/Linux are supported" — treat it as "the macOS-specific parts have been
identified and separated out, ready for that verification."

What's platform-neutral vs. macOS-specific:
- Dependency install, the lock-file reconciliation logic, the editable install, and R-executable
  discovery (`config.py` now branches on `platform.system()` for common Rscript install locations)
  are shared logic, unchanged in intent across all three platforms.
- `scripts/fix_hidden_venv.sh` and the `chflags -R nohidden .venv` step remain **macOS-only** —
  they address a macOS-specific file-flag interaction with Python 3.14's `site.py` (see the
  portability progress log) and are deliberately not present in the Windows/Linux launchers.
- The macOS AppleScript multi-file picker in `AutoMouse_Run.command` is replaced by a
  `System.Windows.Forms.OpenFileDialog` on Windows and a numbered-list terminal picker on Linux
  (no extra GUI-toolkit dependency assumed); passing file paths as command-line arguments works
  identically on every platform.

## Dependency locks

`requirements.lock.txt` (generated with `pip-tools` using the oldest supported Python, 3.11, as
the resolving interpreter — a lock generated on a newer interpreter can pin a package version with
no wheel for older supported versions, e.g. an early attempt here pinned a `numpy` release with no
Python 3.11 wheel at all; regenerate with
`"$HOME/miniconda3/envs/py311-test/bin/pip-compile" --extra inventory --extra webapp --extra sheets --extra dev pyproject.toml`,
or any Python 3.11 interpreter with `pip-tools` installed) pins the exact Python package versions
verified with this project, checked to install cleanly on Python 3.11–3.14. `AutoMouse_Setup.command`
reconciles to it on every run — an existing environment's installed versions are not assumed to
already match it.

`r_dependencies.lock.json` is a **verification record**, not an installable/managed environment
(there is no R equivalent of `pip install -r` run automatically) — it records the exact R and
package (`dplyr`, `purrr`) versions verified working with the translation script, so a future
mismatch is at least detectable. It does not identify the translation script itself by version or
checksum; the script lives outside this repo by design (see `r.translation_script` in
`config/pipeline_run.yaml`), so nothing here currently guarantees two machines are running the
*same* translation logic, only the same R/package versions. Regenerate the R part with:

```bash
Rscript -e 'cat(R.version.string, "\n"); for (p in c("dplyr","purrr")) cat(p, as.character(packageVersion(p)), "\n")'
```

If `automouse`/`xolpotsxol` ever fails with `ModuleNotFoundError` right after a successful setup,
run `scripts/fix_hidden_venv.sh` — see the comment at the top of that file for why this can happen.

See `docs/MACOS_EXECUTABLE_PLAN.md` for the detailed procedure.

## Web app (recommended for non-technical use)

`AutoMouse_WebApp.command` starts a small local web server and opens a browser tab — no Terminal
commands or AppleScript file pickers involved. It runs only on `127.0.0.1` (this computer only);
nothing is uploaded anywhere else, and it is built for one person at a time, not shared/networked
use.

1. Double-click `AutoMouse_WebApp.command`.
2. In the browser tab that opens, choose or drag one or more raw Transnetyx CSV files.
3. Optionally check "Preview only (dry run)".
4. Click **Run Möuseley Kräs** and review the results page — counts, warnings, and download links for
   the updated inventory copy, exception workbook, audit log, Live Label cage cards, run summary,
   and log.
5. If a file was already processed before, a confirmation page explains this and asks whether to
   re-run intentionally; declining leaves everything untouched.
6. Close the browser tab and stop the script (Control-C, or just close the window) when done.

The page is built for lab staff who don't use a command line: plain-language labels and errors, a
visible focus outline and skip-to-content link for keyboard use, and no step that requires typing a
command. Equivalent to `automouse --config config/pipeline_run.yaml serve` (`--port` and
`--no-browser` are also available).

If `inventory.source_sheet_url` is set in the config, every page shows a link to open the primary
inventory (e.g. a Google Sheet) in a new tab. By default this is a convenience link only — Möuseley
Kräs does not read from or write to that sheet automatically, and it still works from a manually
exported/imported CSV as described above. Two narrow, explicitly opt-in exceptions exist and are
disabled by default: a read-only DOB/Wean_By overlay, and a Sheet write-back for newly entered
litters — see the two sections below.

## Google Sheet DOB/Wean_By overlay (optional)

By default, `DATE BORN`/`DATE WEANED` on Live Label cage cards come only from the local inventory
copy's `DOB`/`Wean_By` columns, and are blank whenever those cells are blank there. If the primary
inventory (the Google Sheet) has DOB/Wean_By data that hasn't made it into the local CSV yet,
Möuseley Kräs can optionally fetch just those two fields, read-only, to fill in blanks before cage
cards are built. This is the one deliberate, explicit exception to "the sheet link is display-only" —
everything else about the sheet remains untouched.

Scope and safety:

- Read-only: uses the Google Sheets API's `spreadsheets.readonly` scope. Möuseley Kräs never writes
  to the sheet.
- Only DOB and Wean_By are fetched — never genotype, never any other field, and never used for
  matching (matching stays exact against the local inventory's `Mouse`/`ID`/`Sample` columns).
- Fills blanks only: a DOB/Wean_By value already present in the local inventory copy is never
  overwritten by the sheet.
- If the sheet can't be reached (offline, bad credentials, renamed sheet/tab), the batch adds a
  warning and finishes using whatever DOB/Wean_By the local inventory already has — it never fails
  the run.
- Disabled by default (`sheets_overlay.enabled: false`); nothing changes unless a lab member opts in.

To enable it:

1. Install the extra dependency: `pip install -e '.[sheets]'` (or add it to setup).
2. In Google Cloud, create a service account and download its JSON key.
3. Share the Google Sheet with that service account's email address as **Viewer**.
4. In `config/pipeline_run.yaml`, set `sheets_overlay.enabled: true`, `spreadsheet_id` (from the
   sheet's URL), `worksheet` (the tab name, e.g. `"Sheet1"`), and `credentials_file` (path to the
   downloaded JSON key — keep this file out of version control).

The sheet's header row must contain the same header text already configured for `dob`/`wean_date`/
identifier roles in `inventory.expected_headers` (e.g. `"DOB"`, `"Wean_By"`, `"Mouse"`) — Möuseley
Kräs matches sheet columns by that exact header text, the same way it validates the local CSV's
headers.

## Batch behavior

All selected files share one run ID. Möuseley Kräs:

- preflights and archives every input before inventory work;
- validates every raw file, translates each sequentially with the existing R function, and validates every output;
- reconciles duplicate samples across files before changing inventory data;
- creates one checksum-verified inventory backup;
- applies safe updates to one new inventory copy;
- creates one combined audit, exception workbook, and Live Label workbook.

Duplicate-result policy:

- one READY result plus failed attempts: use the READY result and audit the failed attempts;
- multiple agreeing READY results: use the first canonical result and flag the rest as duplicates;
- conflicting READY results: update none and report the conflict.

## Weaning/new-cage cards

Safely matched `UPDATED` and `CONFIRMED` mice are eligible. Existing `Cage` values are not required. Cards are grouped by normalized:

```text
Sex + Strain + Kras genotype + DOB window
```

The default DOB windows are 5 days for males and 7 days for females. These values are configured as `male_dob_window_days` and `female_dob_window_days` in the `cage_card` section. Kras is normalized for grouping, so `LSL-G12D/+` and `K/+` are treated as `K/+`, but they are never mixed with `+/+` in the same cage.

Each compatible group is natural-sorted by DOB and mouse ID, then split into rows of at most five mice. Six compatible mice are split as 3 and 3 rather than 5 and 1. `DATE WEANED` is taken from the inventory when it is uniform; when `DATE BORN` spans a range, Möuseley Kräs uses `DATE BORN + 28 days` and shows the resulting wean-date range. `# IN CAGE` is the row's mouse count; `# IN LITTER` is the summed source-litter size represented on that row. Missing/invalid DOB, Sex, Strain, or Kras genotype data is reported and never silently grouped.

The empty header-only Live Label workbook is the expected template: rows 2 onward are populated by Möuseley Kräs.

## Commands

```bash
.venv/bin/automouse \
  --config config/pipeline_run.yaml run --verbose \
  "/path/to/first.csv" "/path/to/second.csv"
```

`translate` also accepts multiple files but stops before inventory/card generation. Useful options are `--dry-run`, `--allow-duplicate-input`, and `--verbose`.

## Two portals

The web app (see above) is split into two independent portals, and the CLI mirrors the same split:

- **Cage Card Production** (`/`, or the `run`/`translate` CLI commands) — unchanged: upload raw
  Transnetyx CSVs, and Möuseley Kräs translates them, updates the matching inventory rows' genotype,
  and produces Live Label cage cards.
- **Mouse Inventory Update** (`/inventory`, or the `enter-litter` CLI command) — records one litter
  by hand, right after birth and before any genotyping: strain, date of birth, mother, father, a
  female/male pup count, the first and last mouse ID assigned to the litter, a Plate ID, and a
  Transnetyx Order Date. Möuseley Kräs adds one new inventory row per pup — genotype is deliberately
  left blank, to be filled in later by Cage Card Production once Transnetyx results come back for
  these mice. If `sheets_overlay.write_new_litters` is enabled, it also appends the new litter to the
  live Google Sheet (see [Google Sheet litter write-back](#google-sheet-litter-write-back-optional)
  below); otherwise it writes only the local inventory copy.

### Entering a litter from the command line

```bash
.venv/bin/automouse \
  --config config/pipeline_run.yaml enter-litter \
  --strain "Kras/Lkb1/Tom/Cas9" --dob 2026-01-19 \
  --mother CM9001 --father CM9002 \
  --total-pups 13 --female-count 6 --male-count 7 \
  --first-mouse-id CM12000 --last-mouse-id CM12012 \
  --plate-id T1234567 --transnetyx-order-date 2026-01-19
```

Females always take the earliest mouse IDs in the range, males the rest — in this example
`CM12000`-`CM12005` are female and `CM12006`-`CM12012` are male. The number of pups, the
female/male counts, and the size of the mouse ID range must all agree; Plate ID must be `T` followed
by seven digits, and Transnetyx Order Date must be `YYYY-MM-DD`; any mismatch is reported as an
explicit error, never silently reconciled. `enter-litter` requires `inventory.append_only: true`,
since every submitted litter is always brand-new mice.

A mouse ID that already exists is never overwritten — it becomes an explicit conflict in the result
instead. If Sheet write-back is enabled and reachable, the live Sheet decides what counts as
"already exists" (see below); otherwise the local inventory copy alone does, exactly as always.

## Google Sheet litter write-back (optional)

This is a separate, narrower opt-in from the read-only DOB/Wean_By overlay above — it only affects
the Mouse Inventory Update portal, and it can write to the Sheet, not just read from it.

When enabled, submitting a litter also appends it to the live Google Sheet, in addition to the local
inventory copy (which is always written). Scope and safety:

- Opt-in and layered: requires both `sheets_overlay.enabled: true` and
  `sheets_overlay.write_new_litters: true`. It requests its own read-write-scoped credential
  (`https://www.googleapis.com/auth/spreadsheets`) separately from the read-only overlay's
  `spreadsheets.readonly` scope, so the DOB/Wean_By read path can never write regardless of this flag.
- Requires the service account to have **Editor** (not just Viewer) access to the sheet.
- Conflict detection re-fetches the Sheet's current identifiers immediately before writing, since
  another lab member may be editing it concurrently. Once that fetch succeeds, the Sheet — not the
  local inventory copy — decides whether a mouse ID is already taken, since the Sheet is the lab's
  actual primary inventory and the local file is only Möuseley Kräs's mirror of it. A mouse ID whose
  row still sits in the local copy but has since been deleted from the Sheet is therefore not a
  conflict: the stale local row is replaced by the freshly submitted one, rather than blocking the
  submission or creating a duplicate. This is the only place in the project where an existing local
  inventory row is ever removed automatically, and it only happens paired with immediately re-adding
  a fresh row for that same mouse ID; the removed row's prior values are always named in the audit
  trail and recoverable from that run's inventory backup.
- If the Sheet fetch fails, or comes back with far fewer identifiers than the local inventory already
  has (a strong sign of a wrong tab, a bad range, or a masked API error), the Sheet is not trusted for
  that run: the local inventory copy remains the only signal, exactly as when this feature is off,
  and the run degrades to a warning rather than failing.
- `--dry-run` fetches the Sheet too (read-only) so its preview matches what a real run would do; it
  never writes anywhere regardless of what the fetch finds.
- Any other failure (network, auth, quota) degrades to a run warning — the local inventory write
  always succeeds independently of whether the Sheet write does.

See `CLAUDE.md` and `Markdown_files/SHEETS_WRITE_ARCHITECTURE_DECISION.md` for the full design
record, including accepted risks (the conflict check and the write are two separate requests, so a
race between them is possible in principle) and what has and hasn't been verified against a real
Sheet.

## Safety behavior

- SHA-256 and byte-verified archives protect every raw input.
- Selecting identical content twice in one batch is rejected.
- Historical reprocessing is blocked unless `--allow-duplicate-input` is explicitly supplied. On the command line this failure returns exit code `3` (distinct from the generic `1`) so scripts can detect it. `AutoMouse_Run.command` catches this specifically and asks interactively whether to re-run with `--allow-duplicate-input`; declining or running non-interactively leaves everything untouched.
- Every raw and translated file must validate before inventory mutation starts.
- Matching is exact against configured `Mouse`, `ID`, and `Sample` columns.
- Blank genotype cells may be filled; equal existing values are confirmed; unequal values are preserved and reported as conflicts.
- Competing records targeting one inventory row are resolved before any write.
- The source inventory is backed up and all results are written to uniquely named new files.

## Runtime artifacts

Production output is under:

```text
outputs/019fb5fc-cfb6-7a51-9423-58940a90cde9/automouse_runtime/
```

It contains archived inputs/checksums, per-file translations and validations, one updated inventory copy, one audit/exception set, one Live Label workbook, a run-summary JSON, and a detailed log.

## Tests

```bash
.venv/bin/python -m unittest discover -s tests -v
```

`AutoMouse_Setup.command` registers `automouse` as a direct, editable-installed command in
`.venv/bin/` — no `PYTHONPATH` needed for normal use. (An earlier version of this project avoided
editable installs after hitting a `ModuleNotFoundError` under Python 3.14; the actual cause turned
out to be a stale `build/` directory combined with the macOS "hidden" file flag being set on
`.venv`'s contents — Python 3.14's `site.py` silently skips hidden `.pth` files. Setup now clears
that flag automatically, and the stale `build/` directory has been removed, so editable installs
work normally.) `PYTHONPATH="$PWD/src" .venv/bin/python -m automouse ...` still works as a fallback.
