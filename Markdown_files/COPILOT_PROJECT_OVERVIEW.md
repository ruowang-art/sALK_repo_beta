# Project Overview for Copilot

This document is written for GitHub Copilot (or any AI assistant new to this repository) as a
fast, self-contained orientation. It assumes no prior context from this project's chat history. For
deep architectural detail, see `mouseley-kras-and-xol-pots-xol-overview.md` in this same directory;
for the portability work specifically, see `CODEX_DELIVERABLE_portability_phases_1-3.md`. This file
is the short version of both, written to be skimmed in a few minutes.

---

## System Debriefing

### What this repository is

A single repo hosting two related but independently-runnable tools used in a mouse genetics lab at
Salk. Both take genotyping data and turn it into inventory records and printable cage cards for a
mouse colony.

**Möuseley Kräs** (`automouse`, at the repo root, package in `src/automouse/`) is the primary tool.
A lab member manually downloads genotyping result CSVs from Transnetyx (a third-party genotyping
vendor) and feeds them in. Möuseley Kräs:
1. Runs an R script (external, not written by this project) that translates raw Transnetyx genotype
   codes into the lab's own strain/genotype shorthand.
2. Reconciles the translated results against the lab's existing mouse inventory spreadsheet —
   matching by mouse ID, flagging anything that doesn't cleanly match rather than guessing.
3. Produces three outputs: an updated inventory CSV, an audit/exception report (every mouse that
   needed a human decision, with the reason), and a "Live Label" cage-card workbook formatted for
   printing physical cage cards.

It exposes exactly two user-facing workflows — called "portals" throughout this project's docs —
and that boundary is intentionally protected and not to be blurred:
- **Cage Card Production**: the original, most-used workflow — CSV in, cage cards out.
- **Mouse Inventory Update**: a newer workflow for manually recording new litters (strain, DOB,
  mother, father, sex counts, auto-assigned mouse-ID ranges with females taking the earliest IDs).

**Xol-Pots-Xol** (`xolpotsxol`, in `xol-pots-xol/`) is a standalone sibling tool. Möuseley Kräs's
Live Label workbooks are often sparsely filled in day to day; Xol-Pots-Xol consolidates several of
those sparse workbooks into one fuller, more complete one. It has its own package, its own tests,
its own virtual environment, and its own web app — it is not a submodule of Möuseley Kräs, it just
consumes files that Möuseley Kräs produces.

### Design principles that show up everywhere in the code

- **No silent success.** Every ambiguous or unmatched record is surfaced in an explicit report, not
  swallowed or guessed at.
- **Copy-on-write, checksum-verified.** The tools never edit the lab's inventory file in place blind
  — they write a new copy and verify it, protecting against partial writes corrupting the only copy
  of colony records.
- **Two-portal boundary is load-bearing.** Cage Card Production and Mouse Inventory Update are kept
  deliberately separate; do not merge their code paths or their outputs without the user's explicit
  sign-off.
- **R/Python boundary via subprocess, argument lists only.** The R translation script is invoked as
  a subprocess with an explicit argument list — never a shell string — to avoid injection risk and
  keep the R and Python layers independently testable.
- **Local and manual by design.** There is no automated fetch from Transnetyx and no scheduled job;
  a human downloads the CSV and runs the tool. This was a deliberate choice (discussed and
  confirmed with the user, not a limitation to "fix").

### Current progress state (as of this writing)

Both tools are functionally complete for their original single-Mac use case and have been for
several sessions. The current work is a **portability initiative** — making both tools installable
and runnable by other lab members, on other operating systems, without changing what they do. It is
staged and partially complete:

| Phase | Content | Status |
|---|---|---|
| 1 | Git initialized, portability scoped as a real goal | Done, committed |
| 2 | Per-project virtual environments, locked dependencies, verified across Python 3.11–3.14 | Done, committed |
| 3 | Windows (`.ps1`) and Linux (`.sh`) launcher scripts, cross-platform R-executable discovery | Implemented and committed; Linux proxy-tested via bash on macOS, **Windows never executed** |
| 4 | Verification on real Windows/Linux machines or CI | Not started |

The macOS workflow (the original, still primary use case) is fully verified throughout — 89
passing tests for Möuseley Kräs, 35 for Xol-Pots-Xol, run on every phase. Nothing about the
portability work has changed either tool's behavior on macOS.

### What NOT to assume

- Windows and Linux support should be described as "implemented, not yet verified" — never as
  "supported" or "working" until Phase 4 actually runs on those platforms.
- The two-portal boundary in Möuseley Kräs is not incidental structure; treat it as a constraint,
  not a refactoring opportunity.
- `runtime/` and `outputs/` directories may contain real, current lab data. Any code change that
  touches file I/O should be tested against fixtures or a scratch directory, never those paths
  directly, unless the user has explicitly asked for a real run.

---

## Isolated Code Artifacts

### Repository layout (top level, abbreviated)

```
src/automouse/              Möuseley Kräs package (config.py, app.py, models.py, cli.py, ...)
xol-pots-xol/src/xolpotsxol/  Xol-Pots-Xol package (consolidator.py, writer.py, pipeline.py, ...)
tests/                       Möuseley Kräs test suite (89 tests)
xol-pots-xol/tests/          Xol-Pots-Xol test suite (35 tests)
launchers/linux/*.sh         Linux launchers (Phase 3, proxy-tested)
launchers/windows/*.ps1      Windows launchers (Phase 3, unexecuted)
*.command                    Original macOS launchers (fully verified, unchanged in behavior)
config/*.example.yaml        Config templates; real config.yaml/pipeline_run.yaml are gitignored
scripts/fix_hidden_venv.sh   macOS-only venv repair (UF_HIDDEN flag workaround)
Markdown_files/              All project documentation (see CLAUDE.md in this repo root for why)
```

### Entry points

```
automouse-webapp / automouse    (console scripts, from pyproject.toml, root project)
xolpotsxol-serve                (console script, xol-pots-xol/pyproject.toml)
AutoMouse_WebApp.command         (macOS launcher, verified)
launchers/linux/AutoMouse_WebApp.sh     (Linux launcher, proxy-tested)
launchers/windows/AutoMouse_WebApp.ps1  (Windows launcher, unexecuted)
```

### How to run the test suites

```
python -m unittest discover tests                 # Möuseley Kräs — expect: Ran 89 tests ... OK
python -m unittest discover xol-pots-xol/tests     # Xol-Pots-Xol — expect: Ran 35 tests ... OK
```

### Where the platform-branching logic lives

```
src/automouse/config.py
  _common_r_executable_locations()   # candidate Rscript paths, branches on platform.system()
  _resolve_r_executable()            # explicit configured path > shutil.which > candidates
```

### Git state

```
$ git log --oneline
1fdd68d Phase 3: cross-platform launchers implemented, NOT yet verified (Windows/Linux)
3824991 Correct progress docs to reflect Phase 2 is now committed
5864ec6 Phase 2 of portability initiative: separate venvs, dependency locks, fixed editable installs
bb5b398 Initial commit: Möuseley Kräs and Xol-Pots-Xol source, tests, and docs
```
