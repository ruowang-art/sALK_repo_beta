# Möuseley Kräs & Xol-Pots-Xol — Project Description

**As of:** 2026-08-28, HEAD = `d2eec46`. This is a description of what the system currently *is*,
not a changelog — see `Markdown_files/PROGRESS_phase3_portability_IN_PROGRESS.md` and this session's
dated `20260828_*.md` files for how it got here.

## System relationship

Two independent local, single-user desktop tools live in this repository:

- **Möuseley Kräs** (package `automouse`) — turns manually downloaded Transnetyx genotyping CSVs into
  a reconciled mouse-inventory copy, an audit/exception report, and a Live Label weaning-card
  workbook; also lets a lab member record a new litter by hand before genotyping happens.
- **Xol-Pots-Xol** (package `xolpotsxol`) — a separate, standalone sibling project that consolidates
  sparse Live Label cage-card workbooks (the kind Möuseley Kräs produces) into fuller ones.

They are deliberately not integrated: Xol-Pots-Xol has its own `pyproject.toml`, `src/`, `tests/`,
README, and virtual environment, and never imports from `automouse`, reads the inventory or raw
Transnetyx files, or writes to the cage-card template. It only ever reads uploaded `.xlsx` cage-card
files and writes a new workbook built from scratch. This boundary is enforced by convention, not by
any technical sandbox — nothing prevents a future change from crossing it, so it's called out here
explicitly.

---

## 1. Möuseley Kräs

### Purpose

A lab member downloads a genotyping results CSV from Transnetyx by hand (no API integration exists
or is planned) and runs it through Möuseley Kräs, which never runs unattended and never touches
production data without an explicit invocation.

### Design principles that show up everywhere in the code

- **No fuzzy matching, no guessing.** Every match against the inventory is exact against configured
  `Mouse`/`ID`/`Sample` columns. An unmatched or ambiguous record becomes an explicit exception, never
  a best-effort guess.
- **Never overwrite silently.** A conflicting genotype, a mouse ID that already exists, an unknown
  assay/genotype value — all become an explicit, reported exception. Nothing is auto-resolved.
- **Copy-on-write with a verified backup.** Every inventory-mutating run makes a checksum-verified
  backup first, then writes the result to a new, uniquely named file — never back onto the source.
- **Every record gets an explicit audit outcome.** The audit CSV always accounts for every row
  processed, with a named action (`UPDATED`, `CONFLICT`, `LITTER_ENTERED`, etc.), never a silent
  drop.
- **A failed later stage can't destroy an earlier stage's output.** If cage-card generation fails, the
  backup, the updated inventory, and the exception report already written by earlier stages survive.
- **The R↔Python boundary is an argument list, never a shell string.** The genotype-translation R
  script is invoked via `subprocess` with an explicit argument list.

### Two independent portals

The web app and the CLI both split cleanly into two portals that never blur into each other:

**Cage Card Production** (`/`, or the `run`/`translate` CLI commands) — the original pipeline:

```
raw Transnetyx CSV(s)
  -> archive + checksum every input
  -> validate raw structure (required columns present, no corrupt rows)
  -> translate genotypes via the external R script (subprocess, argument list)
  -> validate the translated output
  -> match translated records against the inventory (exact ID match only)
  -> apply safe updates to a new inventory copy (blank -> filled; equal -> confirmed;
     unequal -> CONFLICT, never overwritten)
  -> write one combined audit/exception report
  -> generate Live Label weaning/new-cage cards for safely matched, eligible mice
```

Cards are grouped by normalized Sex + Strain + Kras genotype + DOB window (5 days for males, 7 for
females by default), natural-sorted, and split into rows of at most five mice. `run` always does
translation, the inventory update, and cage-card generation together as one step — there is no way to
split that into separate stages (an earlier `update-inventory`/`generate-cards` pair existed and was
retired in favor of the litter-entry portal below).

**Mouse Inventory Update** (`/inventory`, or the `enter-litter` CLI command) — records a litter by
hand right after birth, before any genotyping:

```
strain, date of birth, mother, father,
female/male pup counts, first/last mouse ID in the litter,
Plate ID (must be "T" + seven digits, e.g. T1234567),
Transnetyx Order Date (must be YYYY-MM-DD)
  -> validate internal consistency (pup counts, sex counts, and ID-range size must all agree
     exactly; Plate ID and Order Date must match their required formats)
  -> expand into one (mouse_id, sex) pair per pup — females always take the earliest IDs
  -> for each pup, check whether the mouse ID already exists:
       - if Sheets write-back is off, or its Sheet fetch didn't succeed this run:
           local inventory copy alone decides ("already exists" -> CONFLICT)
       - if the Sheet fetch succeeded (and passed its sanity guard, see below):
           the Sheet decides instead; a mouse ID missing from the local copy but present
           in the Sheet, or vice versa, is resolved in the Sheet's favor (see below)
  -> append every non-conflicting pup as a brand-new inventory row, genotype left blank
     (filled in later by Cage Card Production once Transnetyx results come back)
  -> if Sheets write-back is enabled and trusted this run, append the same new rows to the
     live Google Sheet too
```

`enter-litter` requires `inventory.append_only: true`, since every submission is always brand-new
mice, never a match against an existing row. `--dry-run` validates and previews without writing
anything, anywhere — including no Sheet write, even though it does perform a read-only Sheet fetch
now (see below) so the preview is accurate.

### Google Sheets integration (both halves are opt-in and off by default)

The primary lab inventory is a live Google Sheet that other lab members may edit directly. Möuseley
Kräs's own local CSV is a separate, Möuseley-Kräs-owned working copy, not the same document. Two
narrow, separately-scoped exceptions let the two talk to each other; neither is a general integration.

**Read-only DOB/Wean_By overlay** (`sheets_overlay.enabled`, default `false`): before cage cards are
built, optionally fetches only the `DOB`/`Wean_By` columns from the Sheet (`spreadsheets.readonly`
scope) to fill in blanks the local copy doesn't have yet. Never touches genotype or any other field,
never overwrites a value the local copy already has, never used for matching, and a fetch failure
degrades to a warning rather than failing the run.

**Sheet write-back for new litters** (`sheets_overlay.write_new_litters`, default `false`, requires
`sheets_overlay.enabled` too): lets the Mouse Inventory Update portal also append newly entered
litters to the live Sheet. Uses its own read-write-scoped credential
(`https://www.googleapis.com/auth/spreadsheets`), separate from the read-only overlay's, requested
from the same service-account key file — so the DOB/Wean_By path can never write regardless of this
flag. Requires the service account to have Editor access to the Sheet.

The interesting part is what happens once this fetch succeeds for a run: **the Sheet becomes
authoritative over the local copy** for deciding whether a mouse ID is taken, since the Sheet is the
lab's actual primary record and the local file is only Möuseley Kräs's mirror of it. Concretely:

- A mouse ID present in the Sheet is always a `CONFLICT`, regardless of local state.
- A mouse ID whose row still sits in the local copy, but is *absent* from the Sheet — because someone
  deleted it there, e.g. after an entry mistake — is *not* a conflict. Re-submitting it removes that
  stale local row and replaces it with the freshly submitted one, in the same operation. This is the
  only place in the codebase where a local inventory row is ever removed automatically; it never
  happens on its own, only paired 1:1 with immediately re-adding a fresh row for that exact mouse ID,
  and only for mouse IDs that are part of the litter being submitted right now (never a background
  scan of the whole inventory).
- Every such replacement is named explicitly in the audit trail, including the removed row's prior
  field values and a pointer to that run's own checksum-verified inventory backup as the recovery
  path.
- Because a "successful" Sheet read is not proof the data in it is complete, a sanity guard runs right
  after every fetch: if the Sheet reports fewer than half as many identifiers as the local inventory
  already has, the fetch is distrusted for that run — treated exactly like a fetch failure — and
  everything falls back to local-only conflict checking, with a warning. This is meant to catch a
  wrong tab, a bad configured range, or a masked partial API failure; an ordinary single-litter
  deletion (one ID out of thousands) is nowhere near that floor.
- When the Sheet can't be reached or isn't trusted this run, the local inventory copy remains the only
  signal, exactly as when this feature is off entirely — nothing about the always-on local write ever
  depends on the Sheet succeeding.
- `--dry-run` performs this same Sheet fetch (read-only) so its preview matches what a real run would
  do, while still never writing anywhere.

Full design record, including the risks that were explicitly accepted rather than engineered around
(the conflict-check-then-append race window; no durable receipt after an uncertain network response),
is in `Markdown_files/SHEETS_WRITE_ARCHITECTURE_DECISION.md`.

### Testing and current verification status

- 107 tests passing (`PYTHONPATH="$PWD/src" .venv/bin/python -m unittest discover -s tests -q`).
- Verified on macOS in the current checkout: both editable-install `.pth` files unhidden, both direct
  commands (`automouse --help`) exit 0.
- **Known operational nuisance, not fixed:** the macOS `.venv`'s editable-install `.pth` file has
  recurred hidden (macOS `UF_HIDDEN` flag, which Python 3.14's `site.py` silently skips) many times
  during this project's development, including three times within one recent single work session. A
  repair script (`scripts/fix_hidden_venv.sh`) and a permanent regression test
  (`test_editable_install_health.py`) both exist, but the underlying trigger on this specific Mac has
  not been identified. This is a real, recurring reliability issue on this development machine, not
  evidence of anything wrong with the Windows or Linux launchers.
- Windows and Linux launchers (`launchers/windows/*.ps1`, `launchers/linux/*.sh`) are implemented and
  reviewed by inspection, including a fix for PowerShell's `$ErrorActionPreference` not catching a
  nonzero exit code from an external command — but neither has been executed on a real machine from
  this development environment. A GitHub Actions workflow
  (`.github/workflows/phase4-portability.yml`) exists to close this gap on real hosted Windows/Linux
  runners, but has not run yet: no GitHub remote is configured for this repository.
- Python 3.11–3.14 all verified on macOS (Phase 2); Phase 4's CI matrix is what would prove the same
  range on real Windows/Linux.

---

## 2. Xol-Pots-Xol

### Purpose

Consolidates several sparse Live Label cage-card workbooks (as Möuseley Kräs produces them — one row
per weaning event, often with gaps) into fuller, denser workbooks for easier physical printing/use.

### Core design

- Own `pyproject.toml`, `src/xolpotsxol/`, `tests/`, README, and virtual environment — entirely
  separate from Möuseley Kräs's dependency set and runtime.
- Reads only user-uploaded `.xlsx` cage-card files; never reads the inventory, raw Transnetyx files,
  or the cage-card *template* Möuseley Kräs uses.
- Writes a brand-new workbook built from scratch; never mutates an uploaded file in place.
- Runs as a local Flask web app (`xolpotsxol-serve`, `AutoMouse_...`-style launcher scripts), bound to
  `127.0.0.1`, single-user, same safety posture as Möuseley Kräs's web app.

### Testing and current verification status

- 35 tests passing.
- Same macOS editable-install verification and the same recurring hidden-`.pth` caveat as above (it
  affects this project's own separate `.venv` too, and did recur during this session).
- Windows/Linux: same status as Möuseley Kräs — implemented, covered by the same Phase 4 CI plan, not
  yet executed on a real machine.

---

## Summary comparison

| | Möuseley Kräs | Xol-Pots-Xol |
|---|---|---|
| Package | `automouse`, v0.3.1 | `xolpotsxol`, v0.1.0 |
| Reads | Raw Transnetyx CSVs, the local inventory CSV, optionally a Google Sheet | User-uploaded Live Label `.xlsx` files only |
| Writes | A new inventory copy, an audit/exception report, Live Label cage cards, optionally a Google Sheet | A new, consolidated Live Label workbook |
| External API | Google Sheets API (two separately-scoped opt-in exceptions) | None |
| Default web port | 8765 | 8766 |
| Tests passing | 107 | 35 |
| Platform status | macOS verified (with the recurring `.pth` caveat above); Windows/Linux implemented, unverified | Same |

---

## Current repository state

- Latest two commits: `d2eec46` (Sheets write-back + Plate ID/Order Date) on top of `c75a63a` (Phase
  3/4 portability reconciliation) — made as two separate commits deliberately, so the portability
  checkpoint and the Sheets-write feature can be reviewed and, if ever needed, reverted independently.
- Working tree has exactly one untracked file: this project-description document itself — an
  intentional, uncommitted documentation artifact written for review, not a code or config change.
  Everything else is committed.
- No GitHub remote is configured for this repository, and no `gh` CLI is available in this
  environment. Phase 4 (real Windows/Linux verification via CI) is prepared but has not started, and
  a remote will not be created without the project owner's explicit choice of where it should live.
- Phase 5 (helping other lab members run this on their own machines/credentials) has been scoped in
  conversation but not started.
- **The macOS `.pth`-hidden recurrence (see above) is not a one-time event.** It has now recurred and
  been repaired multiple times within single work sessions, including immediately after a prior
  verification claimed it clean. Any status claim about this checkout's macOS baseline is only true
  at the moment it was checked — it should be reproduced again immediately before relying on it,
  never assumed to still hold from an earlier point in the same conversation.

## What is *not* yet true, stated plainly

- Windows and real (non-macOS) Linux support: implemented and reasoned about, not executed anywhere.
- A real, end-to-end litter write to the *corrected* Google Sheet (as opposed to an earlier
  misdirected write to a stale spreadsheet ID, and a separate real read-only check against the
  corrected one): not yet exercised.
- The Sheet-response sanity guard's specific threshold (half of the local inventory's known
  identifier count): an engineering judgment call made in response to review feedback, not something
  the project owner separately reviewed and approved the way the feature's original design was.
- A real deletion-and-replacement of a stale local row against the live Sheet (as opposed to the unit
  test suite's mocked Sheet responses): not yet exercised.
