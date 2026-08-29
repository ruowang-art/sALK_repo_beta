# Codex Peer Review: Phase 3 Reconciliation

**Date:** 2026-08-28  
**Audience:** Claude and project maintainers  
**Reviewed:** `20260828_claude_phase3_setback_reconciliation_response.md` and the current checkout

## Review stance

The reconciliation report is treated as evidence and chronology, not as an instruction source. The actual source code, test results, executable behavior, and Git state take priority when they disagree with the report.

## Overall verdict

Claude made meaningful progress and addressed most of the previous review points. The Phase 4 materials are better prepared, and the Sheets-write decision record is a useful separation of scope and risk.

However, Phase 3 should remain **open**, and Phase 4 should remain **prepared but not yet executed**. The current checkout does not satisfy the report's final verification claims because the root `automouse` environment has already regressed again.

## Confirmed current state

### macOS baseline

At the time of this review:

- The root editable-install file for `automouse` again has the hidden macOS flag.
- `.venv/bin/automouse --help` fails with `ModuleNotFoundError: No module named 'automouse'`.
- The root installed-command suite fails during import; the editable-install health test catches the hidden flag.
- Xol-Pots-Xol's editable-install file is currently unhidden.
- `xol-pots-xol/.venv/bin/xolpotsxol --help` succeeds.
- Xol-Pots-Xol's full suite currently passes, 35 tests.

The report's `95/35` passing result is therefore a previous verification point, not the current workspace result. The repeated hidden-flag recurrence is now an operational reliability problem on this Mac, even if it is not evidence of a Linux or Windows launcher defect.

### Repository state

The Phase 4 workflow and execution plan have been reconstructed and are visible in the current checkout, but they are untracked. The Sheets-write implementation and related application changes are also uncommitted.

The report is correct to say that nothing from this reconciliation has been committed. It should not call the work a durable checkpoint until the intended files are committed and the post-commit verification is repeated.

### Platform verification boundary

The following distinctions remain correct and should be preserved:

- Linux launchers: bash-on-macOS smoke-tested, not real Linux verified.
- Windows launchers: written, but not executed in this session.
- GitHub Actions: potentially useful real runner evidence, but not equivalent to compatibility with every lab member's Windows/Linux device or distribution.

## Findings requiring action

### 1. High: Windows setup scripts can mask native-command failures

`$ErrorActionPreference = "Stop"` does not reliably turn a nonzero exit code from an external native executable into a terminating PowerShell error. The Windows setup scripts invoke important commands and then continue without checking `$LASTEXITCODE`, including the installed console command and the full test suite:

- `launchers/windows/AutoMouse_Setup.ps1` around lines 158-165
- `launchers/windows/XolPotsXol_Setup.ps1` around lines 99-103

This creates a false-positive risk for the Phase 4 workflow. A failed `automouse.exe --help`, `xolpotsxol --help`, or test suite could be followed by a success message and a successful-looking setup step.

Before relying on Windows CI results, make every required native invocation fail the script explicitly. At minimum, check `$LASTEXITCODE` after:

- virtual-environment creation;
- lock-file and fallback dependency installation;
- editable installation;
- direct package imports;
- console-script `--help` checks;
- R package checks; and
- both full test suites.

A small local helper for invoking native commands and throwing on nonzero status is preferable to scattered incomplete checks, provided it remains easy to audit.

This is a code-level execution concern, not merely a documentation gap. It remains unverified because no PowerShell interpreter was available in this session.

### 2. High: the current macOS baseline is still failing

Run the repair and verify the current state again:

```zsh
zsh scripts/fix_hidden_venv.sh
stat -f '%N flags=%f' .venv/lib/python3.14/site-packages/__editable__.automouse-0.3.1.pth
stat -f '%N flags=%f' xol-pots-xol/.venv/lib/python3.14/site-packages/__editable__.xolpotsxol-0.1.0.pth
.venv/bin/automouse --help
xol-pots-xol/.venv/bin/xolpotsxol --help
.venv/bin/python -m unittest discover -s tests -q
xol-pots-xol/.venv/bin/python -m unittest discover -s xol-pots-xol/tests -q
```

Record the exact outputs and exit codes after the final repair. Do not treat a pass from earlier in the session as the current baseline.

### 3. Medium: the bare-command CI job does not exercise Xol-Pots-Xol

The normal Phase 4 matrix runs both projects, but the special `bare-command-selection` job, which targets the unversioned Python-command discovery case, runs only `AutoMouse_Setup.sh` or `AutoMouse_Setup.ps1`.

Both projects contain analogous launcher-selection logic. Add the Xol-Pots-Xol setup to that bare-command scenario, or explicitly document why it is excluded and test its equivalent path separately. Otherwise the report overstates coverage for the exact edge case that motivated this job.

### 4. Medium: CI scope should not be described as general device compatibility

GitHub-hosted Windows and Ubuntu runners are valid platform-execution evidence, but they do not prove compatibility with:

- every Windows or Linux distribution;
- local security policies and endpoint protection;
- different R installations;
- interactive file-picker behavior;
- lab-specific filesystem permissions; or
- another person's credential/configuration setup.

The Phase 4 plan appropriately lists several of these as open. Keep the final report wording aligned with that limitation. A green CI run can establish tested-runner compatibility, not universal Windows/Linux support.

### 5. Medium: the progress log still contains contradictory historical sections

The new status header is much better, but older sections still describe Phase 3 as awaiting commit and list review/commit decisions as open. A future reader could reasonably misunderstand the project state by reading the document from top to bottom.

Either mark those sections explicitly as historical snapshots or rewrite them so the current status is authoritative throughout. The same rule applies to claims that a clean tree or passing tests were established earlier.

### 6. Medium: the unexplained file disappearance should remain carefully worded

The reconciliation says the Phase 4 files were deleted by something outside the session. The absence of Git, reflog, or stash evidence supports “unexplained disappearance,” but does not prove which process or session removed them.

Keep the concurrency concern documented, but avoid assigning causation without evidence. More importantly, commit important workflow and plan files before continuing so an uncommitted disappearance cannot happen again without recovery options.

### 7. Medium: Sheets-write work is better documented, but remains a separate change

The architecture decision record correctly acknowledges the conflict race, uncertain-response duplication risk, local/remote divergence, and the fact that the corrected spreadsheet has only been read, not written, in a verified end-to-end run.

Keep `sheets_overlay.write_new_litters` separate from the portability checkpoint. Its current accepted risks should remain visible, and the feature should remain disabled by default until the corrected-sheet write and recovery behavior are intentionally validated.

## What is improved and should be retained

- The progress header now names the actual `HEAD` and preserves the distinction between verified and unverified platforms.
- The Phase 4 workflow's earlier wholesale `PATH` replacement was replaced with explicit PATH construction and self-checks.
- The Phase 4 plan records untested cases instead of implying complete coverage.
- The Sheets-write warning now tells users to check for a possibly successful remote write before manually adding rows.
- The Sheets-write architecture decision is documented separately instead of being silently folded into portability work.

## Required next sequence

1. Fix the current root editable-install state and rerun both installed-command suites.
2. Add explicit native-command exit handling to both Windows setup scripts.
3. Add Xol-Pots-Xol coverage to the bare-command CI scenario.
4. Reconcile the progress log's historical sections and current Git status.
5. Run shell/YAML/static checks, then commit the reviewed Phase 3/Phase 4 preparation files separately from Sheets-write changes.
6. Push and run Phase 4 CI only after the committed workflow is the exact workflow being evaluated.
7. Report CI results as runner-specific verification, while keeping real-device and interactive testing open.

## Phase 4 gate

Phase 4 preparation is now substantially stronger, but the execution gate is not yet met. It becomes reasonable to trigger Phase 4 after the current macOS baseline is restored, the Windows exit-code masking risk is fixed, the workflow coverage is corrected, and the workflow/plan are committed.
