# Möuseley Kräs & Xol-Pots-Xol — Progress Summary

**As of 2026-08-27.** A high-level summary of everything done across both projects so far. For
architecture/CS details see `mouseley-kras-and-xol-pots-xol-overview.md`; for the detailed,
blow-by-blow record of the portability work specifically, see
`PROGRESS_phase2_portability_IN_PROGRESS.md`.

## The two projects

- **Möuseley Kräs** (`automouse`) — turns manually downloaded Transnetyx genotyping CSVs into a
  reconciled mouse inventory, an audit/exception report, and Live Label cage-card workbooks.
- **Xol-Pots-Xol** (`xolpotsxol`) — a standalone downstream tool that consolidates the sparse
  cage-card workbooks Möuseley Kräs produces into fuller ones.

## Work completed, in order

### 1. Two-portal restructuring
Retired the old standalone `update-inventory`/`generate-cards` CLI commands for a clean split:
**Cage Card Production** (unchanged translate → match → update inventory → cards) and **Mouse
Inventory Update** (a new portal/CLI command for registering a whole litter — strain, DOB,
parents, pup/sex counts, mouse-ID range — as brand-new, pre-genotyping inventory rows, with a
strain dropdown sourced from a configured strain list).

### 2. External robustness review — audited, then acted on
Verified every item from an external review against the real code before building anything.
Added 5 new Möuseley Kräs regression tests for previously-uncovered branches, enriched the run
manifest (app/Python/R versions, config checksum, output-file hashes, per-mouse Sheets-overlay
audit trail). For Xol-Pots-Xol, fixed a real defect: unconsolidated mice no longer blend
invisibly into the same sheet as real consolidated cages — the output workbook now always has
four sheets (`Sheet1`, `Unconsolidated`, `Review Needed`, `Report`), and the Kras genotype
grammar became a named, versioned constant. 8 new tests added. Deliberately deferred: an
inventory approval-workflow step, new CLI subcommands, config schema versioning, dependency
locks (until Phase 2), and property-based testing.

### 3. Software version & device compatibility documentation
Documented Python/R/dependency version constraints and macOS/device compatibility for both
projects in the architecture overview doc.

### 4. Portability initiative — Phase 1 (packaging groundwork)
Triggered by deciding the projects need to eventually run on other lab members' machines/OSes,
not just this one Mac. Fixed a real version-drift bug in the setup script banner. Added a
scrubbed `config/pipeline_run.example.yaml` template (real config stays local and gitignored).
Made R-executable discovery portable (falls back from the exact configured path to `PATH`, then
common install locations). Added OS/architecture to the run manifest. **Initialized git for the
first time** in this project's history, with a carefully hand-built `.gitignore` protecting the
real inventory, raw lab data, and credentials — reviewed the file list, then made the initial
commit (93 files, verified no real data or secrets).

### 5. Portability initiative — Phase 2 (environment & verification)
- **Actually verified** Python 3.11/3.12/3.13/3.14 (not just documented) using real conda
  environments — full test suites pass on all four.
- **Found and fixed a genuine, previously-misdiagnosed bug**: editable installs
  (`pip install -e .`) had been abandoned project-wide after a `ModuleNotFoundError` under Python
  3.14. Root-caused it to macOS's `UF_HIDDEN` file flag being set on `.venv`'s contents (likely a
  one-time Finder/Time-Machine action, unrelated to the project's own scripts) combined with a
  new Python 3.14 `site.py` behavior that silently skips hidden `.pth` files — not a fundamental
  flaw in editable installs. Fixed with `chflags -R nohidden .venv`, now run defensively by both
  setup scripts. Editable installs work again: `automouse`, `xolpotsxol`, `xolpotsxol-serve` all
  run directly, no `PYTHONPATH` required.
- **Split into separate venvs**: Xol-Pots-Xol now has its own `.venv` and its own
  `XolPotsXol_Setup.command`, fully independent of Möuseley Kräs's.
- **Dependency locking**: `pip-tools`-generated `requirements.lock.txt` for both projects
  (verified installable into a fresh venv from scratch), used automatically by the setup scripts
  when present. Added `r_dependencies.lock.json` as a plain version record (not a full `renv`
  project, since the R script lives outside this repo by design).
- Fixed a real resource leak a peer review caught (an unclosed test response in Xol-Pots-Xol).

### A second peer review caught two more real problems, both fixed
1. The hidden-flag bug had **silently recurred** after an ad-hoc `pip install pip-tools` (run to
   build the lock files) re-applied the flag with nothing to clear it afterward. Fixed again, and
   this time backed by a standalone repair script (`scripts/fix_hidden_venv.sh`), since any future
   pip operation against either venv could reintroduce it.
2. The lock files, generated using Python 3.14, pinned a `numpy` release with **no wheel for
   Python 3.11 at all** — the lock wasn't actually installable on the full version matrix.
   Regenerated both using Python 3.11 (the oldest supported version) as the resolving interpreter,
   verified installable on 3.11–3.14. Also made both setup scripts reconcile to the lock file on
   every run (not just when something's missing) and fail visibly rather than silently falling
   back if the lock install fails.

One remaining open gap, correctly flagged and deliberately left unresolved: nothing currently
identifies the external R translation script itself by version or checksum — that's a real design
decision for the user, not something to solve unilaterally.

### A third review pass — final release-readiness checks
- Actually closed the "tests pass on 3.11–3.14 vs. installed commands work on 3.11–3.14" gap: built
  a real venv on each of 3.11/3.12/3.13, ran the actual editable install from each project's lock
  file, and confirmed `automouse`, `xolpotsxol`, and `xolpotsxol-serve` all work — not just
  documented as a limitation.
- Added short root `CLAUDE.md`/`README.md` **shims**: both now exist at the project root (so
  Claude Code's project-instruction auto-discovery and GitHub-style tooling both find something),
  each just pointing to the real, authoritative file in `Markdown_files/`. Nothing duplicated.
- Corrected the progress log's status line, which had inaccurately said Phase 2 was "complete and
  committed" while also saying it was awaiting commit.
- Documented the lock-verification strictness decision explicitly: recovery mode is intentional
  (visible warning, never silent), not a gap — no separate "strict" flag was requested or added.

## Current status

- **Committed to git**: Phase 1 (initial commit) and Phase 2 (second commit — separate Xol-Pots-Xol
  venv/setup script, dependency locks resolved against Python 3.11, the editable-install fix,
  root CLAUDE.md/README.md shims, doc updates).
- **Not started**: Phase 3 (Windows/Linux launcher equivalents) and Phase 4 (actual cross-platform
  verification, which needs CI since this session can only run/verify on macOS).

## Test status

Both projects' full suites pass: **83/83** (Möuseley Kräs) and **34/34** (Xol-Pots-Xol), verified
on Python 3.11, 3.12, 3.13, and 3.14.
