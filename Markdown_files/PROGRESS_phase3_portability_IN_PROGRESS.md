# Möuseley Kräs & Xol-Pots-Xol — Progress Log

**Status: Phase 1 and Phase 2 implemented, verified, and committed (macOS/Python 3.11–3.14). Phase 3 (cross-platform launchers) implemented — Linux scripts smoke-tested via bash on macOS, Windows PowerShell scripts written but not executed at all — not yet committed. Phase 4 (real Windows/Linux/CI verification) not started.**

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
  scratch files. Reviewed the `git add -n -A` (dry run) file list, grep-checked every file for
  the credentials filename and the real Sheets ID (zero hits), then staged and made the **initial
  commit** — 93 files, no real data or credentials.
- Confirmed the credentials file itself is untouched by any of this — gitignoring only affects
  what git tracks, not what's on disk or what the app reads.
- Also fixed a genuine resource leak flagged by a peer review of this work: a Xol-Pots-Xol test
  never closed a Flask test-client response, leaking an open file handle (harmless in production,
  where Flask's `send_file` closes it properly, but hidden behind a `ResourceWarning` in tests).
- Full test suites re-verified passing after every change (83 + 34).

---

## Phase 2 — packaging/environment (complete, this session)

Decisions made at the start of this phase: **separate venv per project** (not a shared workspace
venv), dependency locking via **pip-tools**, and **actually verify** Python 3.11–3.14 rather than
just document a range.

### Verified Python version matrix

Created real conda environments (`py311-test` through `py314-test`, via the Miniconda installed
earlier this session) and ran both full test suites against each. All four passed cleanly:
Python 3.11.16, 3.12.14, 3.13.15, and 3.14.7 — 83/83 and 34/34 on every version.

### A major, real bug found and fixed: editable installs were silently broken

While separating Xol-Pots-Xol into its own venv and wiring up `pip install -e .` for direct
commands (`automouse`, `xolpotsxol`, `xolpotsxol-serve` in `.venv/bin/`, no `PYTHONPATH` needed),
`automouse --help` failed with `ModuleNotFoundError: No module named 'automouse'` — the exact
symptom this project had previously documented and worked around (by abandoning editable installs
entirely, per `README.md`/`docs/MACOS_EXECUTABLE_PLAN.md`). Rather than accept that workaround at
face value, the actual root cause was tracked down:

1. A stale `build/` directory (from an old `python -m build`/`pip install .` run, dated **Jul 30**)
   was missing `litter_entry.py`, `sheets_overlay.py`, and the entire `web/` subpackage — a
   red herring that looked promising but wasn't the real cause once isolated and tested.
2. The actual cause: the `.venv` directory's contents had the **macOS "hidden" file flag**
   (`UF_HIDDEN`, checkable via `ls -lO`) set — most likely from a one-time manual
   Finder-declutter/Time-Machine-exclusion action at some point in this project's history, not
   from anything this project's own scripts do. **Python 3.14's `site.py` added a new check that
   silently skips any hidden `.pth` file** — which is exactly how editable installs register a
   package's source directory. So the venv's own legitimate editable-install file was being
   silently ignored by Python itself.
3. Verified with isolated reproductions (copying the exact `.pth` file into a fresh directory
   worked; the same file in the real, hidden-flagged `.venv` didn't) and confirmed the fix:
   `chflags -R nohidden .venv` immediately restored working editable installs, with zero other
   changes.

This was **not** a fundamental flaw in editable installs, and the original decision to abandon
them was a reasonable response to a genuinely confusing bug — but the actual fix is much smaller
than "never use editable installs again." Both `AutoMouse_Setup.command` and the new
`XolPotsXol_Setup.command` now run `chflags -R nohidden .venv` defensively after every install, so
this can't silently recur. `README.md` and `docs/MACOS_EXECUTABLE_PLAN.md` are updated to explain
the real cause instead of the old, more defeatist workaround.

### Separate venvs

Xol-Pots-Xol now has its own `.venv` (created via the new `XolPotsXol_Setup.command`, mirroring
`AutoMouse_Setup.command`'s pattern), completely independent of Möuseley Kräs's root `.venv`.
`XolPotsXol_WebApp.command` now uses `xol-pots-xol/.venv/bin/xolpotsxol-serve` directly instead of
reaching into the shared root venv. Both projects' `README.md`s document the direct-command style
as primary, with the `PYTHONPATH=...` style kept as a documented fallback.

### Dependency locking

Installed `pip-tools` (added to each project's `dev` extra) and generated `requirements.lock.txt`
for both projects, pinning exact versions of every dependency (verified by installing from each
lock file into a completely fresh venv). Both setup scripts now install from the lock file when
present, falling back to the existing version-range install otherwise. Also added
`r_dependencies.lock.json` — not a full `renv` project (the R script lives outside this repo by
design, so a renv-managed project doesn't cleanly apply), just a plain record of the exact R
(4.5.2) and package (`dplyr` 1.2.1, `purrr` 1.1.0) versions verified working.

Full test suites re-verified passing after every change in this phase (83 + 34), including a
full, clean end-to-end run of both setup scripts from scratch.

---

## Phase 2 peer review caught two real problems — both fixed

A peer review of the `SUMMARY_progress_2026-08-27.md` snapshot found the "direct commands work
without `PYTHONPATH`" claim didn't actually hold in the live workspace, and pushed on whether the
lock files were genuinely version-matrix-safe. Both turned out to be real:

1. **The hidden-flag bug had recurred.** After the original fix, an ad-hoc `pip install pip-tools`
   run directly against the real venvs (to build the lock files) re-applied the macOS hidden flag,
   and nothing re-cleared it afterward — so by the time the review checked, `automouse`/
   `xolpotsxol`/`xolpotsxol-serve` were broken again with the exact same `ModuleNotFoundError`.
   Confirmed and fixed again (`chflags -R nohidden` on both venvs), and this time backed by a
   standalone, documented repair script (`scripts/fix_hidden_venv.sh`) referenced from both
   READMEs, since **any** future pip operation against either venv (not just this project's own
   setup scripts) could reintroduce it.
2. **The lock file wasn't actually installable on the full version matrix.** It had been generated
   using Python 3.14 as the resolving interpreter, which pinned a `numpy` release (a `pandas`
   dependency) with no wheel published for Python 3.11 at all — so a from-scratch 3.11 install
   using the lock file would hard-fail. Regenerated both projects' lock files using Python 3.11 (the
   oldest supported version) as the resolving interpreter instead, then verified the new lock files
   install cleanly and import correctly on Python 3.11, 3.12, 3.13, and 3.14, using the same conda
   test environments as the earlier version-matrix testing.

Also tightened lock-file *enforcement*, per the review: both setup scripts previously only
consulted the lock file when a required import was missing, so an existing environment with
slightly different (but importable) versions never got reconciled. Both scripts now always
attempt `pip install -r requirements.lock.txt` on every run, and if that fails (e.g. offline with
nothing cached), say so explicitly and explain that the environment is not lock-verified, rather
than silently falling back to loose version ranges without comment.

Reframed `r_dependencies.lock.json` in the docs as a **verification record**, not a managed/
installable environment, and explicitly noted the still-open gap the review raised: nothing here
identifies the external translation script itself by version or checksum, so two machines with
identical R/package versions could still be running different translation logic. Left this
unaddressed for now — it's a real gap, but deciding how to identify/version an externally-owned
script is a design question for you, not something to solve unilaterally.

Re-verified end-to-end after every fix: both setup scripts run clean from scratch, direct commands
work, both test suites pass (83 + 34), and both lock files are now confirmed installable on
Python 3.11 through 3.14.

**Closed a gap a follow-up review caught**: the Python-version matrix testing (3.11–3.14) had only
ever run the test suites via source-path imports, never via a real editable install + installed
console-script entry point on each version — so "tests pass on 3.11–3.14" and "the installed
commands work on 3.11–3.14" were not actually the same claim (exactly the distinction that let the
hidden-flag regression slip through undetected on the *source-path* tests earlier in this phase).
Closed it directly rather than just documenting the limitation: built a fresh venv on 3.11, 3.12,
and 3.13 each, installed each project's regenerated lock file, ran the real
`pip install --no-deps --no-build-isolation -e .` editable install, and confirmed
`automouse --help`, `xolpotsxol --help`, and `xolpotsxol-serve --help` all succeed on every
version (3.14 was already covered by the real project venvs). Full installed-command matrix is
now genuinely verified, not just source-path tests.

## A note on file organization

Partway through this phase, top-level `.md` files (including this one, `README.md`, and
`CLAUDE.md`) were reorganized into a `Markdown_files/` subdirectory — a deliberate, standing
personal preference for this project (all future `.md` files should be saved there too), not
something done by this work. `pyproject.toml`'s `readme` field was updated to
`Markdown_files/README.md` to match, since setuptools reads that path when building the package.

A follow-up review correctly flagged that this created a real risk: Claude Code conventionally
auto-discovers project instructions from a root-level `CLAUDE.md`, and tooling/GitHub convention
expects a root-level `README.md`. Resolved with short root **shims**: `CLAUDE.md` and `README.md`
now exist at the project root as brief pointer files, each explicitly directing to the real,
authoritative content at `Markdown_files/CLAUDE.md` / `Markdown_files/README.md` — nothing is
duplicated, so there's no drift risk, and the organizational preference is fully preserved.

## A note on lock-file strictness

A follow-up review asked whether lock-file verification should be strict (fail if the pinned
versions can't be installed) or allow a recovery mode. The current, intentional design: setup
always attempts the lock install first; if that fails (offline, nothing cached), it explicitly
warns that the environment is not lock-verified and either continues with whatever's already
importable or falls back to loose version ranges — visibly, never silently. This is deliberately
recovery-mode-by-default with no silent path, rather than a hard failure, since this project's
actual failure mode to avoid is a lab member being stuck with no working environment at all, not
a slightly-off dependency version. No separate "strict" flag was added — not requested by the user,
and the existing behavior already surfaces the distinction rather than hiding it.

---

## Phase 3 — cross-platform launchers (implemented, awaiting commit)

Scope was set explicitly per both codex's and copilot's Phase 3 recommendations: Windows
PowerShell launchers, Linux shell launchers, platform-neutral path/Rscript-override handling,
launcher smoke tests that never touch laboratory data, and explicitly preserving the macOS
workflow unchanged — with no claim of Windows/Linux support until Phase 4's real verification.

### What was built

- `launchers/linux/*.sh` (5 scripts: `AutoMouse_Setup.sh`, `AutoMouse_Run.sh`,
  `AutoMouse_WebApp.sh`, `XolPotsXol_Setup.sh`, `XolPotsXol_WebApp.sh`) — same step order and
  logic as the macOS `.command` scripts, with macOS-only parts (AppleScript picker, `chflags`,
  Homebrew/Framework R paths) removed rather than superficially translated. The macOS file picker
  is replaced with a dependency-free numbered-list terminal picker.
- `launchers/windows/*.ps1` (the same 5, as PowerShell) — same logic, using
  `.venv\Scripts\python.exe`, a `py -3.x`/`python` launcher search, and a native
  `System.Windows.Forms.OpenFileDialog` multi-select picker in place of AppleScript.
- `config.py`'s R-executable discovery (`_common_r_executable_locations`) now branches on
  `platform.system()`: macOS keeps its existing Homebrew/Framework/`/usr/local/bin` candidates,
  Linux checks `/usr/bin` and `/usr/local/bin`, Windows enumerates versioned
  `C:\Program Files\R\R-x.y.z\bin\Rscript.exe` directories. The one invariant proven to hold on
  every platform (via a new pure-function test, not a real OS): an explicit, already-valid
  `r.executable` in config always wins over any fallback.
- `validate_config`'s R-not-found error message is now platform-aware (points at the right CRAN
  download page and the right "find it" command — `which` vs. `where`).
- 5 new tests in `tests/test_config.py` covering the discovery logic's per-platform behavior and
  the configured-path-always-wins invariant across all three platforms (mocked, not real OSes).

### What was actually verified vs. only implemented — kept strictly separate, per both reviews

- **Linux scripts**: smoke-tested for real, on this Mac, via `bash` — a reasonable syntax/logic
  proxy for a POSIX shell, but explicitly *not* the same as running on an actual Linux
  distribution. Verified: syntax (`bash -n` on all 5), a full `AutoMouse_Setup.sh` run (pinned
  install, editable install, direct command, full 83-test suite — all passed), a full
  `XolPotsXol_Setup.sh` run (same, 34-test suite passed), `AutoMouse_Run.sh`'s input-validation
  paths (missing file, wrong extension, no-TTY-no-args) without ever reaching the real pipeline
  call, the numbered-picker's file-discovery logic in isolation, and both web-app launchers
  actually starting a real local Flask server (GET-only, immediately killed after ~3 seconds,
  never touching production data or writing anything).
- **Windows scripts**: written but genuinely **not executed at all** — no PowerShell interpreter
  (`pwsh`) was available in this session's environment. These are implementation only, explicitly
  labeled as such in both the scripts' own header comments and `Markdown_files/README.md`. Nothing
  in this project claims otherwise.
- While testing the Linux launchers, the macOS hidden-`.pth`-flag issue recurred yet again (the
  fifth time this session) — purely an artifact of testing *on this Mac*, not a defect in the
  Linux scripts themselves. Fixed with the same `scripts/fix_hidden_venv.sh`, as expected; this is
  now a well-understood, recurring nuisance specific to this development machine, not a new
  finding.

### What was deliberately kept out of Phase 3

- No claim that Windows or Linux are "supported" — the README's new section header says
  "implemented, not yet verified" explicitly, matching both reviews' instruction not to conflate
  Phase 3 with Phase 4.
- `scripts/fix_hidden_venv.sh` / `chflags -R nohidden` were not generalized or ported — they stay
  macOS-only, since there's no known equivalent issue on the other platforms.
- No change to the two-portal behavior, no widened data access, no new laboratory-data touchpoints
  — the new launchers call the exact same CLI entry points the macOS ones already call.
- No CI setup yet (that's explicitly Phase 4's job, and needs the git repo this session already
  established).

---

## What's next (not started yet)

- **Phase 4 — actual cross-platform verification**: this is the part that can't be done solo
  from this Mac — real Windows/Linux testing needs either physical/VM access or CI (e.g. GitHub
  Actions), which in turn depends on the git repo that now exists. Not started.

## Phase 2 completion checklist (per the follow-up review)

- [x] Direct commands pass without `PYTHONPATH` on the production environment.
- [x] Both editable `.pth` files are free of the hidden flag after setup.
- [x] Python source-path tests pass on Python 3.11 through 3.14.
- [x] Installed-command smoke tests actually run (not just documented) on every supported Python
  version, for both projects.
- [x] Lock files install on every declared Python version.
- [x] Setup clearly distinguishes lock-verified from non-lock-verified operation.
- [ ] The external R translation script has a reproducible identity — still an open gap,
  deliberately left as a design decision for the user (see below), not solved unilaterally.
- [x] Root `CLAUDE.md`/`README.md` remain discoverable (via shims into `Markdown_files/`).
- [x] The progress status accurately distinguishes implemented, verified, staged, and committed
  work.
- [x] Phase 2 committed as one reviewable checkpoint.

## Follow-up: materializing the two review documents' feedback

Two more review passes (`REVIEW_full_session_report_feedback.md`,
`REVIEW_codex_feedback_and_claude_session_synthesis.md`) reviewed the full-session report itself
rather than the code, and were addressed by editing that report directly (support-boundary notice,
release-readiness table/checklist, exact provenance — see
`REPORT_full_session_progress_and_methodology.md`). One item from those reviews was a real,
implementable code change rather than a documentation fix, and was materialized directly: every
run manifest now records `translation_script_path` and `translation_script_sha256` (verified
against the real production config, via `_build_run_environment` in `app.py`, threaded through
`models.py`'s `to_summary()`). This partially closes the external-R-script-identity gap — it
proves whether two runs used byte-identical script content — but does not give the script an
actual version/commit identity, which remains the one open decision below.

(While making this change, the macOS hidden-`.pth`-flag issue recurred a fourth time — same
symptom, same `scripts/fix_hidden_venv.sh` fix. It's now a known, recurring nuisance on this
particular Mac tied to pip-adjacent file writes; each recurrence has been caught by the test
suite failing loudly, never silently.)

## Open decisions waiting on you

1. Decide whether/how to give the external R translation script an actual version or Git-commit
   identity (a checksum is now recorded automatically; the script itself is still unversioned) —
   the one remaining gap from the Phase 2 reviews that's a real design decision, not a bug fix.
2. Review and commit Phase 3 (currently implemented, smoke-tested where possible, but
   uncommitted).
3. Decide how/when to pursue Phase 4 (real Windows/Linux machines or CI) — this session cannot do
   that verification unassisted.
