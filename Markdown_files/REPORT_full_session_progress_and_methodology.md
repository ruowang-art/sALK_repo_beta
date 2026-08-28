# Möuseley Kräs & Xol-Pots-Xol — Full Session Report

A comprehensive account of the work done across this engagement: what the two projects are, the
full chronological narrative of changes, the working methodology applied throughout, and the
current state of both codebases. Companion documents: `mouseley-kras-and-xol-pots-xol-overview.md`
(architecture/CS deep-dive), `PROGRESS_phase2_portability_IN_PROGRESS.md` (detailed portability
log), `SUMMARY_progress_2026-08-27.md` (shorter summary). This report supersedes none of them —
it's the single place that ties the whole arc together, including *why* things were done the way
they were.

> **Current support boundary.** Everything below is verified on **macOS, Apple Silicon, Python
> 3.11–3.14, local CLI/browser use only**. Windows, Linux, Intel Macs, mobile devices, and
> alternative spreadsheet applications (Excel for Windows, LibreOffice) are **unverified** — Phase 3
> (cross-platform launchers) and Phase 4 (actual cross-platform verification) have not started.
> The single largest reproducibility gap is that the external R translation script is not
> identified by version or checksum anywhere — see the release-readiness checklist (§5).

---

## 0. Release-readiness table

| Area | Status | Evidence | Remaining risk |
|---|---|---|---|
| Core workflows (two portals) | Implemented | §2.1 | — |
| Python source tests | Independently verified | 83/83 + 34/34 on Python 3.11.16, 3.12.14, 3.13.15, 3.14.7 | CI not yet established; re-run per release |
| Installed console commands | Independently verified | `automouse`/`xolpotsxol`/`xolpotsxol-serve --help` smoke-tested via real editable installs on all 4 versions | Repeat on future releases; only `--help` was smoke-tested, not full command behavior, on 3.11–3.13 |
| Python dependencies | Locked | `requirements.lock.txt` (both projects), resolved on Python 3.11, verified installable on 3.11–3.14 | Cross-platform (Windows/Linux) wheel availability unverified |
| R dependencies | Version-recorded, **not a full lock** | `r_dependencies.lock.json` (R 4.5.2, dplyr 1.2.1, purrr 1.1.0) | Does not install/recreate an R environment |
| External R translation script | **Partially closed** | Every run manifest now records `translation_script_path` and a SHA-256 (`translation_script_sha256`) of the exact script content that ran; automated tests never invoke the real script (see §5) | Proves whether two runs used byte-identical script content, but still no version/commit/release identity — the script itself remains unversioned |
| macOS setup | Independently verified | Setup scripts + `scripts/fix_hidden_venv.sh` | Repair is macOS-`UF_HIDDEN`-specific, not a portability mechanism |
| Data safety | Implemented/verified | `.gitignore` built by directory walk + secrets grep before every commit; checksum-verified backups; explicit conflict/exception handling | Preserve as a release gate |
| Windows/Linux | **Implemented, not verified** | `launchers/windows/*.ps1` (unexecuted — no PowerShell available), `launchers/linux/*.sh` (smoke-tested via bash on macOS only) | Not supported until Phase 4's real-OS/CI verification |
| Cross-platform CI | Deferred | Phase 4 not started | Do not promise portability yet |

## 1. The two projects

**Möuseley Kräs** (`automouse`) is a local, safety-first pipeline for one laboratory's mouse
genotyping workflow. It turns manually downloaded Transnetyx genotyping-result CSVs into:
1. a reconciled copy of the mouse inventory (never the source file itself),
2. an audit/exception report explaining exactly what happened to every record, and
3. a "Live Label" weaning-card workbook for the vivarium.

It also has a second, independent feature for registering brand-new litters into the inventory
before they've been genotyped at all. It runs as a CLI and an optional local (127.0.0.1-only)
Flask web app, with an external R script (owned outside this repo) doing the actual genotype
probe-code translation via subprocess.

**Xol-Pots-Xol** (`xolpotsxol`) is a small, standalone sibling project — not part of Möuseley
Kräs, with its own source tree, tests, and (as of this session) its own virtual environment. It
consolidates the sparse Live Label cage-card workbooks Möuseley Kräs produces (one small batch at
a time) into fewer, fuller ones. It only ever reads uploaded `.xlsx` files and writes a brand-new
workbook; it never touches Möuseley Kräs's inventory, raw data, or template.

---

## 2. Chronological narrative

### 2.1 Two-portal restructuring

The starting request was to abolish the standalone `update-inventory`/`generate-cards` split-stage
CLI commands and replace them with a cleaner design: two independent "portals," in both the CLI
and the web app.

- **Cage Card Production** (`/`, `run`/`translate`) — kept byte-for-byte behaviorally unchanged:
  translate → match → update inventory → generate cards, as one step.
- **Mouse Inventory Update** (`/inventory`, `enter-litter`) — a new portal for registering a whole
  litter (strain, DOB, mother, father, pup/sex counts, a mouse-ID range) as brand-new,
  pre-genotyping inventory rows. The design went through one real correction: an initial proposal
  to require two form submissions for mixed-sex litters was explicitly rejected by the user in
  favor of a single submission with both sex counts and one contiguous ID range, auto-split
  (earliest IDs to females, remainder to males). Validation is strict: pup counts, sex counts, and
  the size of the ID range must all agree exactly, or the submission is rejected outright — no
  reconciliation, no guessing.

Later, a strain dropdown was added to this form, sourced from a lab-provided strain list
(transcribed carefully from a cropped screenshot — re-requested at higher resolution, then
double-checked for entries still cut off at the image edge, rather than guessing at the missing
characters) and wired into `config.inventory.known_strains`.

### 2.2 First external robustness review — audited, then acted on

Another AI ("codex," per the user's naming) produced a checklist of robustness recommendations
after reading only an architecture writeup, not the actual code. Rather than implementing the
list wholesale, every claim was checked against the real codebase first — via a dedicated audit
(two parallel research agents, one per project, each required to cite exact file:line evidence for
every "already exists" claim). This found several recommendations were already implemented (run
manifests, dry-run mode, atomic backup writes) and confirmed the rest as genuine gaps.

What was actually built as a result:
- **Möuseley Kräs**: 5 new regression tests for branches that existed in code but had zero test
  coverage (an existing-genotype CONFLICT, an unknown mouse ID, a missing translated-CSV column, a
  duplicate inventory ID, a unicode-safety case). The run manifest (`run_summary_<id>.json`) was
  enriched with app/Python/R versions, the config file's path and checksum, whether the Sheets
  overlay is enabled, and a SHA-256 of every output artifact. The Google Sheets DOB/Wean-By overlay
  was changed to log exactly which mouse IDs and fields it filled, not just an aggregate count.
- **Xol-Pots-Xol**: the standout real defect — unconsolidated mice had been blending invisibly into
  the same worksheet as genuinely consolidated cages. Fixed by giving the output workbook four
  clearly separated sheets: `Sheet1` (consolidated only), `Unconsolidated` (preserved cage rows),
  `Review Needed` (one row per unconsolidated mouse with source file/row, raw genotype text, and a
  specific reason), and `Report` (grammar version, counts, per-input-file hash). The Kras genotype
  grammar — previously an anonymous inline dict — became a named, versioned constant. 8 new tests
  were added covering previously-blind spots (an unrecognized Kras string flowing end-to-end into
  the unconsolidated bucket, a reordered header row, duplicate mouse IDs, input-file immutability).
- **Deliberately deferred** (flagged as real design decisions, not bugs to silently fix): an
  inventory propose→approve→promote workflow step, new CLI subcommands, a config schema-version
  field, dependency lock files (until later), and property-based testing.

An architecture/CS-underpinnings writeup (`mouseley-kras-and-xol-pots-xol-overview.md`) was
produced and published as a designed Artifact, covering both projects' design philosophy in terms
a technical reader (including another AI) could pick up cold — functional-core/imperative-shell,
lenient parsing vs. zero-tolerance identity matching, checksum-verified copy-on-write, idempotency
via content hashing, and the corresponding Xol-Pots-Xol principles (narrow domain coupling,
fail-open-to-"don't-merge", equivalence-class grouping).

### 2.3 Compatibility documentation, then a portability decision

Software-version and device-compatibility sections were added to that same overview doc: exact
Python/R/dependency versions in use, and an honest statement that both projects were macOS-only,
Apple-Silicon-verified, with no Windows/Linux testing at all.

A second external review then proposed a much larger portability/compatibility checklist
(dependency locking, cross-platform launchers, a full OS/Python test matrix, removing hard-coded
paths). Rather than implementing any of it, the first move was to surface the actual fork in the
road directly to the user: **is running on another machine or another lab member's computer an
actual goal, or is this permanently a personal tool for this one Mac?** The user's answer — yes,
it needs to eventually run on other lab members' machines/OSes — turned this from a speculative
"nice to have" into a real, scoped initiative, broken into four phases up front, with the user
explicitly choosing to do Phase 1 only in that session.

### 2.4 Phase 1 — packaging groundwork

- Fixed a genuinely real, verified bug: `AutoMouse_Setup.command` printed a hardcoded, stale
  version banner (`0.3.0` vs. the actual `0.3.1`) — removed the redundant hardcoded copy rather
  than adding a second source of truth.
- Added a scrubbed `config/pipeline_run.example.yaml` template (placeholder paths, credentials
  filename, spreadsheet ID); the real config stays local and became gitignored.
- Made R-executable discovery portable: falls back from the exact configured path to a `PATH`
  lookup, then common macOS install locations, only if the configured path doesn't already exist —
  verified this didn't change behavior on the real, working setup.
- Added `os`, `os_version`, `machine_arch` to the run manifest.
- **Initialized git for the first time** in this project's history. The `.gitignore` was built by
  actually walking the entire directory rather than guessing — protecting the real inventory CSV,
  every raw/training Transnetyx CSV, the Google service-account credentials JSON, generated run
  output, and assorted personal scratch files. Every file in the resulting ~93-file review list was
  grep-checked for the credentials filename and the real Sheets ID before staging, with zero hits,
  before the initial commit.

### 2.5 Phase 2 — environment and verification, with a real bug hunt in the middle

Three deliberate decisions were made up front for this phase: separate venvs per project (not a
shared workspace venv), dependency locking via `pip-tools`, and **actually verifying** Python
3.11–3.14 with real conda environments rather than just documenting a version range.

The version-matrix testing (conda environments for each of 3.11/3.12/3.13/3.14, both projects' full
suites run against each) passed cleanly on the first attempt — but while separating Xol-Pots-Xol
into its own venv and wiring up `pip install -e .` for direct commands, the exact
`ModuleNotFoundError` this project had *previously* worked around by abandoning editable installs
entirely reappeared. Rather than accept the existing workaround at face value, the actual root
cause was traced methodically:

1. A stale `build/` directory (dated three-plus weeks earlier, missing entire later-added
   submodules) looked like a promising explanation but, once isolated and tested, turned out to be
   a red herring.
2. The real cause: `.venv`'s contents had macOS's `UF_HIDDEN` file flag set (most likely a one-time
   Finder-declutter or Time-Machine-exclusion action, unrelated to the project's own scripts), and
   Python 3.14 had added a new check to `site.py` that silently skips any hidden `.pth` file —
   exactly the mechanism editable installs use to register a package's source directory.
3. This was confirmed with isolated reproductions (copying the exact `.pth` file to a fresh, non-
   hidden directory worked; the same file in the real, flagged directory didn't) before declaring
   it fixed, and the fix (`chflags -R nohidden .venv`) was verified to restore working editable
   installs with zero other changes.

This was **not** a fundamental flaw in editable installs, and the project's earlier decision to
abandon them had been a reasonable response to a genuinely confusing bug — but the real fix was
much smaller than "never use editable installs." Both setup scripts were updated to run this
`chflags` clearing defensively, and the docs were corrected to explain the real cause instead of
the more defeatist original workaround.

Xol-Pots-Xol was then given its own `.venv` and its own `XolPotsXol_Setup.command`, mirroring the
existing pattern; `XolPotsXol_WebApp.command` was updated to use it directly instead of reaching
into the shared root venv. `pip-tools`-generated `requirements.lock.txt` files were added for both
projects, installed automatically by the setup scripts when present. A lightweight
`r_dependencies.lock.json` recorded the exact R/`dplyr`/`purrr` versions verified working — framed
explicitly as a verification record, not a managed `renv` environment, since the translation
script lives outside this repo by design.

### 2.6 Three rounds of external peer review, each catching something real

A pattern repeated three times in this phase: an external review of the work-in-progress caught a
genuine problem, which was verified (never taken on faith) and then actually fixed, not argued
with or rationalized away.

- **Round 1** (reviewing the initial Phase 1 work): caught a `ResourceWarning` in a Xol-Pots-Xol
  test (an unclosed Flask test-client response — harmless in production, since `send_file` closes
  properly under a real server, but a real test-hygiene gap). Fixed. Also prompted the actual git
  commit of Phase 1, after one more file-list review and secrets scan.
- **Round 2** (reviewing the Phase 2 summary): flagged that the "direct commands work without
  `PYTHONPATH`" claim didn't actually hold in the live workspace anymore. Verified independently
  first — it was right: an ad-hoc `pip install pip-tools` run afterward (to build the lock files)
  had re-triggered the hidden-flag bug, and nothing had re-cleared it. Fixed again, this time
  backed by a standalone, documented repair script (`scripts/fix_hidden_venv.sh`) rather than a
  fix that only lived inside the setup scripts' own pip calls. The same review also caught that the
  lock files, resolved using Python 3.14, pinned a `numpy` release with **no wheel for Python 3.11
  at all** — regenerated both projects' locks using Python 3.11 (the oldest supported version) as
  the resolving interpreter instead, then verified installability on all four versions directly
  (not just trusted the regeneration). Lock-file *enforcement* was also tightened: setup now
  reconciles to the lock on every run, not just when something's missing, and says so explicitly
  if that fails rather than silently falling back.
- **Round 3** (a final release-readiness pass): raised that `CLAUDE.md` and `README.md` had moved
  into a `Markdown_files/` subdirectory (a genuine, separately-confirmed personal reorganization by
  the user, saved as a standing preference), which risked breaking Claude Code's own
  project-instruction auto-discovery and GitHub-style tooling expectations. Resolved with short
  root **shims** — `CLAUDE.md` and `README.md` at the project root, each just pointing to the real,
  authoritative file in `Markdown_files/`, so nothing is duplicated and nothing can drift out of
  sync. The same pass also caught an internally contradictory progress-log status line ("complete
  and committed" while also asking for a commit) and asked whether the "tests pass on 3.11–3.14"
  claim was the same as "the installed commands work on 3.11–3.14" — it wasn't (that exact gap is
  what let the hidden-flag regression slip through undetected earlier), so real venvs were built on
  3.11/3.12/3.13 and the actual editable-installed commands were smoke-tested on each, closing the
  gap for real rather than just disclaiming it in the docs.

Phase 2 was committed only after every item above was independently re-verified — not just marked
resolved in prose — with a commit message stating plainly what was verified (macOS/Python
3.11–3.14) and what remains deferred (Windows/Linux, Phases 3–4). One small correction (fixing two
progress-doc status lines that had gone stale the moment the commit succeeded) was folded into an
immediate follow-up commit rather than left inconsistent.

---

## 3. The underlying work logic

A few principles were applied consistently across all of the above, worth naming explicitly since
they're the actual "how," not just the "what":

**Verify before building, and re-verify after.** Every external review — whether proposing new
work or reviewing work already done — was treated as a claim to check against the real code, not
an instruction to execute or a verdict to accept. This caught real discrepancies multiple times:
recommendations already implemented, a claimed fix that had silently regressed, a "verified"
lock file that actually failed on part of its declared version range. The habit of running the
actual test suite, the actual installed command, the actual lock-file install — rather than
reasoning about whether it *should* work — is what surfaced the hidden-flag bug's root cause and
its later recurrence, both times.

**Root-cause investigation over accepting a documented workaround.** When a `ModuleNotFoundError`
matching a previously-documented, previously-worked-around bug reappeared, the response was to
actually diagnose it (isolate variables, reproduce in a clean directory, compare working vs. broken
states byte-for-byte) rather than reapply the existing workaround and move on. This is what
revealed the bug was a fixable, narrow environmental issue, not a fundamental flaw — a materially
different and more useful conclusion than the project's own prior documentation had reached.

**Phased scope with explicit decision points, not silent scope creep.** Before any large
initiative (the two-portal redesign, the portability work), the actual goal was confirmed directly
rather than assumed — "is this really needed?", "which of these four phases do you want done now?"
— and big architecture-affecting choices (separate vs. shared venvs, lock-file tooling, whether to
actually test multiple Python versions) were put to the user as explicit questions rather than
decided unilaterally. Work already explicitly deferred by the user (e.g. the propose/approve/
promote inventory workflow, new CLI subcommands, a config schema version) was named and left alone
even when a later review suggested it again, rather than re-litigated.

**Data safety as a hard constraint, not a guideline.** Real production data (the master inventory
CSV, raw Transnetyx exports, the cage-card template, the Google service-account credentials) was
never used as a test fixture, never edited in place, and explicitly protected in the `.gitignore`
before the first commit. When a verification run wrote unintended files into the protected
production-output directory, it was caught, disclosed, and cleaned up precisely rather than left
or hidden — including a leftover from an earlier point in the same session that had gone unnoticed
until a later check.

**Honesty about what was and wasn't tested.** Distinctions that could have been glossed over —
"source-path tests pass" vs. "the installed console command works," "the lock file was generated"
vs. "the lock file was verified installable," "this is deferred" vs. "this is done" — were called
out explicitly, including in the project's own progress documentation, and corrected the moment
they were shown to be stale (as with the post-commit status-line fix).

**Respecting the user's own conventions once stated.** When the user revealed a personal
organizational preference (all `.md` files live in `Markdown_files/`) mid-session, it was adopted
going forward and saved as a durable memory — while still surfacing the one real, concrete
consequence (`CLAUDE.md`/`README.md` discoverability) as something to resolve together rather than
silently overriding the preference or silently accepting the risk.

---

## 4. Current state

- **Git**: initialized this session; three commits on `main` (initial commit, Phase 2, a small
  doc-status correction). Working tree clean as of the last check. Current commit:
  `3824991e0a511830338a757745a9f6aa6453ec6d`.
- **Application versions**: `automouse` 0.3.1, `xolpotsxol` 0.1.0 (per `pyproject.toml`/
  `config/pipeline_run.yaml`).
- **Tests**: 83/83 (Möuseley Kräs) and 34/34 (Xol-Pots-Xol) passing, verified on Python 3.11.16,
  3.12.14, 3.13.15, and 3.14.7 — both as source-path test suites and as real editable-installed
  console commands (`automouse --help`, `xolpotsxol --help`, `xolpotsxol-serve --help`) built from
  scratch in a fresh venv per version. The two claims are kept separate deliberately: source-path
  tests passing does not imply the installed command works, and vice versa — that exact gap
  (tests green, installed command broken) is what let a real regression slip through undetected
  earlier in this same session.
- **Operating system verified**: macOS 26.6.2 (build 25G83), Apple Silicon (arm64). No other OS or
  architecture has been tested.
- **Environments**: each project has its own `.venv` and setup script; both reconcile to a
  Python-3.11-resolved `requirements.lock.txt` on every setup run.
  - `requirements.lock.txt` (Möuseley Kräs) SHA-256: `9257043099b51464115e6d936a34498fd866240f15048b082eab662ffe598949`
  - `xol-pots-xol/requirements.lock.txt` SHA-256: `e268fad451286bd13ffa9eadf544fe1216a1f150ae5410ae54ba7ea0162136e1`
  - `r_dependencies.lock.json` SHA-256: `5f4ea447d32e62dd8b4f8cda580182a0c59e0f3fe3719f6a4feb18dd2905fec9`
- **Whether the real R translator ran**: the automated test suites (all 83 + 34 tests above) never
  invoke the real `Rscript`/translation script — `tests/test_r_runner.py` and every integration
  test patch `subprocess.run` (or provide a fake translation function) instead, by design, so the
  suite runs without R installed at all. The real external R script *was* exercised earlier in
  this engagement, but only via ad hoc, manual `--dry-run` invocations against real production
  config/data (never as part of the repeatable, automated test suite, and never writing to
  production files). Anyone re-verifying this work should treat "tests pass" and "the real R
  translator was exercised" as two separate, unlinked claims.
- **Partially closed, still an open decision**: following both reviews' top-priority finding, every
  run manifest now records `translation_script_path` and a `translation_script_sha256` (verified
  against the real production config) — proving whether two runs used byte-identical script
  content. What's still missing, and remains a decision for the user, is any actual
  version/Git-commit/release identity for the script itself (see the checklist below) — a
  checksum tells you *whether* two runs matched, not *which* known-good version either one was.
- **Not started**: Phase 3 (Windows/Linux launcher equivalents) and Phase 4 (actual cross-platform
  verification via CI, since this session can only run/verify on macOS). `scripts/fix_hidden_venv.sh`
  addresses a macOS-specific `UF_HIDDEN` condition only — it is not, and should not be read as, a
  step toward Windows/Linux portability.

## 5. Release-readiness checklist

- [x] Release explicitly bounded to macOS + the verified Apple Silicon environment, Python
  3.11–3.14 stated (see the boundary notice at the top of this report).
- [x] Source-path tests and installed-command verification reported separately, with exact
  versions/commands/checksums (§4).
- [x] Content-checksum recorded per run (`translation_script_sha256` in every run manifest).
- [ ] **Decision needed**: external R translation script identified by an exact, recorded version
  or Git commit (checksum alone proves sameness, not which known-good version) before release.
- [x] `r_dependencies.lock.json` described as a version record, not a full lock, throughout this
  report and the project's own README.
- [ ] **Decision needed**: which OS/architecture/Python combinations are actually supported beyond
  the current macOS/Apple-Silicon/3.11–3.14 boundary, vs. deferred to Phases 3–4.
- [x] Platform-specific lock limitations and the macOS-only hidden-flag repair are clearly
  documented as macOS-specific, not general portability mechanisms.
- [x] Production inputs, credentials, templates, and prior artifacts protected per this project's
  data-safety rules (checked before every commit this session).
- [ ] **Decision needed**: are the intentionally deferred inventory promotion workflow, new CLI
  subcommands, config schema versioning, and property-based testing release blockers, or later
  work? (Current stance, unchanged since first raised: later work, not blockers — but this is the
  user's call to finalize, not something to decide unilaterally here.)
