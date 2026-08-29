# Phase 4 Execution Plan — Real Windows/Linux Verification

**Status:** prepared, not yet run. This document exists because this session's environment cannot
execute PowerShell or run on real Linux hardware — the only way to actually close Phase 4 from here
is to hand the same setup scripts to real machines via GitHub Actions, which are real Windows and
Linux runners, not proxies. Nothing in this document has executed yet; it needs a GitHub remote and
one manual click to run for the first time.

**Reconstruction note (2026-08-28):** this file, and `.github/workflows/phase4-portability.yml`,
were deleted from the working tree by something outside this session between their original
creation and a later review pass — neither was ever committed, so there was no git history to
recover them from. Both are rebuilt here from scratch. The rebuilt workflow also fixes a real bug a
review caught in the original: the `bare-command-selection` job's Linux and Windows steps
previously replaced `PATH` wholesale to hide versioned Python aliases, which would have silently
taken `bash`, `mkdir`, `sleep`, and other required system tools down with it. The fix builds an
explicit, complete `PATH` (shim directory plus the standard system binary directories plus R's own
directory) in one step, and each platform's step now self-checks that the versioned alias is
actually hidden before running the setup script, so a failed hide fails loudly instead of silently
producing a false-positive pass.

## What was prepared

`.github/workflows/phase4-portability.yml` — a GitHub Actions workflow, triggered manually
(`workflow_dispatch`, not on every push, since this is unproven and shouldn't burn CI minutes before
it's known to work). It has two jobs:

**`setup-and-tests`** — a 2×2 matrix (`ubuntu-latest` / `windows-latest` × Python 3.11 / 3.14, the
oldest and newest supported versions — the full 3.11–3.14 range was already verified on macOS in
Phase 2, so Phase 4 only needs to prove the *platform*, not repeat that matrix). Each job:
1. Installs the matrix Python and a release R via `actions/setup-python` / `r-lib/actions/setup-r`.
2. Installs `dplyr` and `purrr`.
3. Runs `AutoMouse_Setup.sh`/`.ps1` and `XolPotsXol_Setup.sh`/`.ps1` for real — these already run the
   direct console commands and the full test suite internally, so a green job here means real,
   on-platform 95/35 test passes plus working `automouse`/`xolpotsxol` commands, not just "the script
   ran with no syntax error."
4. Starts both web-app launchers and makes a real HTTP request to each (`127.0.0.1:8765` for
   Möuseley Kräs, `127.0.0.1:8766` for Xol-Pots-Xol — the actual configured defaults, not a guess),
   then stops the process.

**`bare-command-selection`** — the specific scenario codex's and copilot's reviews called out by
name: only an unversioned `python3`/`python` (Linux) or `python`/`py` (Windows) on `PATH`, no
`python3.1x` siblings. This is the exact shape of input that exposed the array-slicing bug fixed in
commit `012d454` (`$parts[1..($parts.Length - 1)]` on a single-element array). Each platform's step
now: (a) resolves the real interpreter and, on Linux, R's directory, before touching `PATH`; (b)
builds one explicit `PATH` covering the shim plus standard system directories, deliberately
excluding the directory that provides the versioned alias; (c) asserts the versioned alias is
actually unreachable, failing the job with a clear message if not; (d) only then runs the setup
script.

## Test-plan coverage — what CI closes vs. what's still open

| Item from codex's/copilot's Phase 4 test plan | Covered by this workflow? |
|---|---|
| Windows setup under real PowerShell | Yes — `setup-and-tests`, `windows-latest` |
| Real Linux setup (not bash-on-macOS) | Yes — `setup-and-tests`, `ubuntu-latest` |
| Versioned `py -3.11` / `python3.11` available | Yes — `setup-and-tests` (setup-python provides both aliases) |
| Only bare `py` / `python` available | Yes — `bare-command-selection`, covering both projects, with a self-check that the hide actually worked |
| PowerShell silently reporting success after a failed native command | Yes — fixed after review; both Windows setup scripts now route every required native call (venv creation, editable install, direct-command checks, both test suites) through an `Invoke-RequiredCommand` helper that checks `$LASTEXITCODE` and exits nonzero on failure, instead of relying on `$ErrorActionPreference = "Stop"` alone (which does not catch a nonzero exit code from an external command) |
| Both web launchers answer a real HTTP request | Yes — `setup-and-tests` |
| Rscript discovery via the standard install path | Yes, implicitly — `r-lib/actions/setup-r` installs R the standard way and `config.py`'s discovery finds it |
| Lock-file installation on Linux/Windows | Yes, implicitly — both setup scripts reconcile to `requirements.lock.txt` as part of the run |
| Linux `PATH`/shim safety (bash, mkdir, Rscript, sleep still reachable) | Yes — fixed after review; explicit PATH construction, not wholesale replacement |
| Python below 3.11 present | **Not covered.** Left as a manual/exploratory case — simulating "the only Python present is too old" on a fresh hosted runner is more contortion than value; if this matters, the cheapest real test is a local VM or container image pinned to an old Python. |
| Virtual-environment creation failure | **Not covered.** Genuinely hard to induce honestly in CI (would mean sabotaging `venv` itself); better exercised by hand once a maintainer has real Windows/Linux access, e.g. by revoking write permission on the target directory. |
| Interactive input paths in `AutoMouse_Run.sh`/`.ps1` (file picker) | **Not covered by this workflow** — CI runners are non-interactive by nature. The numbered-list terminal picker and the Windows file-dialog picker still need a human at a real keyboard at least once. |

## What this session cannot do, and what's needed next

This repository has no git remote configured yet, and no `gh` CLI is available in this environment.
The workflow file is ready, but Phase 4 does not actually run until:

1. A GitHub remote exists for this repo (new repo, or an existing one you point it at).
2. This workflow — and this plan document — are actually committed (not left as uncommitted
   working-tree files, which is exactly how the original copies were lost).
3. This commit is pushed there.
4. The workflow is triggered once, by hand, from the Actions tab (`workflow_dispatch` — deliberately
   not automatic, per the point above).

None of those four steps happened in this session — creating a remote and pushing this codebase
externally is exactly the kind of action that should wait for your explicit go-ahead, not happen as
a side effect of "prepare for Phase 4." Say the word and I'll walk through it (or do it) when you're
ready; until then, Phase 4 stays honestly at "prepared," not "started."
