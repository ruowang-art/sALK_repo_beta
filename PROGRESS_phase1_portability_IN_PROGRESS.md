# Möuseley Kräs & Xol-Pots-Xol — Progress Log

**Status: IN PROGRESS — Phase 1 of the portability initiative complete, awaiting review before staging/committing to git.**

This is a running progress log for two related-but-independent local tools:

- **Möuseley Kräs** (`automouse`) — turns manually downloaded Transnetyx genotyping CSVs into a
  reconciled mouse inventory, an audit/exception report, and Live Label cage-card workbooks.
- **Xol-Pots-Xol** (`xolpotsxol`) — a standalone downstream tool that consolidates the sparse
  cage-card workbooks Möuseley Kräs produces into fuller ones.

For the full architecture writeup (CS concepts, flowcharts, comparison table), see
`mouseley-kras-and-xol-pots-xol-overview.md` / `.html` in this same directory. This document is
specifically a progress/status log, meant to be picked back up later without re-deriving context.

---

## Timeline of work so far

### 1. Two-portal restructuring (complete)

Retired the old standalone `update-inventory`/`generate-cards` split-stage CLI commands in favor
of a clean two-portal design, both in the CLI and the local Flask web app:

- **Cage Card Production** (`/`, `run`/`translate`) — unchanged behavior, still does
  translate → match → update inventory → generate cards as one step.
- **Mouse Inventory Update** (`/inventory`, `enter-litter`) — a new portal for registering a
  whole litter (strain, DOB, mother, father, pup/sex counts, a mouse-ID range) as brand-new,
  pre-genotyping inventory rows. Females always take the earliest IDs in the range, males the
  rest; pup counts, sex counts, and ID-range size must all agree exactly or the submission is
  rejected outright.
- Added a strain dropdown (sourced from `config.inventory.known_strains`) to the litter-entry
  form, built from a lab-provided strain list rather than free text.

### 2. External robustness review — audited and acted on (complete)

An external review (via another coding assistant, "codex") produced a checklist of robustness
recommendations after reading only an architecture doc, not the code. Every item was verified
against the actual codebase first — several were already implemented (run manifests, dry-run
mode, atomic backup writes) — before deciding what to build:

- **Möuseley Kräs**: 5 new regression tests for branches that existed in code but had no test
  coverage (CONFLICT, NOT_FOUND, missing-translated-column, duplicate-inventory-ID, unicode
  safety). Enriched the run manifest with `application_version`, `python_version`, `r_version`,
  `config_path`, `config_sha256`, `sheets_overlay_enabled`, and a SHA-256 of every output
  artifact. The Sheets overlay now logs exactly which mouse IDs/fields it filled, not just a
  count.
- **Xol-Pots-Xol**: the real fix — unconsolidated mice no longer blend invisibly into the same
  sheet as real consolidated cages. The output workbook now always has four sheets: `Sheet1`
  (consolidated only), `Unconsolidated` (preserved cage rows), `Review Needed` (one row per
  unconsolidated mouse with source file/row, raw genotype, and a specific reason), and `Report`
  (grammar version, counts, per-input-file hash). The Kras genotype grammar became a named,
  versioned constant (`KRAS_GENOTYPE_GRAMMAR_VERSION`) instead of an inline dict duplicated in
  prose. 8 new tests added.
- Test count: 83/83 (Möuseley Kräs) + 34/34 (Xol-Pots-Xol) passing.
- **Deliberately deferred** (real design decisions, not bugs): an inventory
  propose→approve→promote workflow step, new CLI subcommands (`validate-config`, `inspect-run`,
  `summarize-audit`), a config schema-version field, dependency lock files, property-based
  testing.

### 3. Software version & device compatibility documentation (complete)

Documented current version constraints and macOS/device compatibility for both projects (see
the "Software versions & device compatibility" section of the architecture overview doc) —
Python `>=3.11`, R with `dplyr`/`purrr`, key dependency versions, macOS-only / Apple Silicon
verified, no Windows/Linux testing, local-Mac-only web server by default.

### 4. Portability initiative — Phase 1 (complete, this session)

A second external review proposed a much larger compatibility/portability checklist. Rather than
implementing it wholesale, each claim was checked against the real scripts first, and one
concrete decision point was raised explicitly: **is running on another machine or another lab
member's computer an actual goal, or is this permanently a personal tool for one Mac?** You
answered: **yes, it needs to run on other lab members' machines / other OSes eventually** — a
real scope change. Given that, the work was broken into four phases, and this session completed
**Phase 1 only** (by your choice):

- **Fixed a real, verified bug**: `AutoMouse_Setup.command` printed a hardcoded, stale version
  number (`0.3.0` vs. the actual `0.3.1`). Removed the redundant hardcoded copy — the script
  already prints the accurate live version a few lines later, once the venv exists.
- **Config template**: added `config/pipeline_run.example.yaml`, a scrubbed template with
  placeholder paths, credentials filename, and spreadsheet ID. Your real
  `config/pipeline_run.yaml` is untouched and now gitignored. Also found and gitignored an
  orphaned older config (`config/settings.yaml`) with the same real-path problem, and fixed
  `cli.py`'s stale default config path (it pointed at that dead file) to point at
  `config/pipeline_run.yaml` instead, matching how every real invocation already calls it.
- **Portable R executable discovery**: `config.py` now falls back from the exact configured
  `Rscript` path to a `PATH` lookup, then common Homebrew/CRAN-framework install locations, only
  if the configured path doesn't exist. Verified this doesn't change behavior on this machine
  (the real path still resolves immediately, unchanged) and produces a clear, actionable error
  (listing everywhere it checked) if R truly can't be found anywhere.
- **Run manifest**: added `os`, `os_version`, and `machine_arch` fields alongside the
  version fields from the earlier robustness pass.
- **Git repository initialized** for the first time (previously this project had no version
  control at all). Wrote a `.gitignore` by walking the entire directory rather than guessing —
  it excludes the real inventory CSV, all raw/training Transnetyx order CSVs, the Google
  service-account credentials JSON, generated run output, the `.venv`, and assorted personal
  scratch files. **Nothing has been staged or committed yet** — `git add -n -A` (dry run) was
  used to produce a review list of the ~90 files that would be tracked, and every file was
  grep-checked for the credentials filename and the real Sheets ID with zero hits. Awaiting your
  go-ahead to actually stage/commit.
- Confirmed the credentials file itself is untouched by any of this — gitignoring only affects
  what git tracks, not what's on disk or what the app reads.
- Full test suites re-verified passing after every change (83 + 34).

---

## What's next (not started yet)

Per your decision, only Phase 1 was done this session. Still ahead, in order:

- **Phase 2 — packaging/environment**: make `pip install -e .` the normal install path (instead
  of relying on `PYTHONPATH`), and decide separate-venvs-per-project vs. one shared workspace
  venv (currently shared, works, but undocumented as a deliberate choice) — then lock whichever
  is chosen with a real Python lock file and an R `renv.lock`.
- **Phase 3 — cross-platform launchers**: Windows (PowerShell) and Linux (shell) equivalents of
  the current macOS-only `.command` launchers, plus a documented non-interactive CLI path for
  automation.
- **Phase 4 — actual cross-platform verification**: this is the part that can't be done solo
  from this Mac — real Windows/Linux testing needs either physical/VM access or CI (e.g. GitHub
  Actions), which in turn depends on the git repo that now exists. Not started.

## Open decisions waiting on you

1. Review the `git add -n -A` file list (or run `git status` yourself) and confirm nothing looks
   wrong before anything is staged or committed.
2. Say when to start Phase 2, or whether to adjust the phase plan.
