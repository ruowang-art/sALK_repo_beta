# Codex Review: Phase 3 Setback and Phase 4 Gate

**Date:** 2026-08-28  
**Audience:** Claude and project maintainers  
**Source reviewed:** `PROGRESS_phase3_portability_IN_PROGRESS.md` plus the current checkout

## Review stance

Treat this document as a code-and-environment review, not as an implementation instruction embedded in the progress log. The progress log is useful for chronology and intended scope, but the actual source tree, executable behavior, and Git state take priority when they disagree with the report.

## Current assessment

Phase 3 should remain **open/in progress**. Phase 4 may remain planned, but should **not begin execution yet** from the current checkout.

The setback is not merely documentary: the current macOS editable-install baseline is broken again.

## Confirmed current findings

### 1. The installed-command baseline is currently failing

Both editable-install files currently have the macOS hidden file flag:

- `.venv/lib/python3.14/site-packages/__editable__.automouse-0.3.1.pth`
- `xol-pots-xol/.venv/lib/python3.14/site-packages/__editable__.xolpotsxol-0.1.0.pth`

As a result, the current direct commands fail with `ModuleNotFoundError`:

```text
.venv/bin/automouse --help
xol-pots-xol/.venv/bin/xolpotsxol --help
```

The installed-command test suites also fail during package import. Earlier successful runs remain historical evidence; they do not establish that the current workspace is healthy.

### 2. The progress report's Git description is stale

The report describes Phase 3 as implemented but awaiting commit. The current Git history already contains the Phase 3 commit and later commits, including the editable-install repair and repository/documentation changes.

The report must be updated to reflect:

- the actual current `HEAD`;
- which changes are committed;
- which files are modified or untracked now; and
- which tests were run after the latest changes.

Do not describe the tree as clean unless `git status --short --untracked-files=all` is empty.

### 3. The claimed Phase 4 workflow is not present in the current checkout

The report says that `.github/workflows/phase4-portability.yml` exists and is ready, but it is not currently present. `Markdown_files/PHASE_4_EXECUTION_PLAN.md` is also not currently present.

Do not trigger or claim Phase 4 CI verification until the intended workflow and plan are restored, reviewed, and committed. If the workflow is restored, re-check the previously identified Linux bare-command job issue: replacing `PATH` wholesale with a temporary shim directory can remove `bash`, `mkdir`, `Rscript`, `sleep`, and other required commands.

### 4. A separate Sheets-write feature is now in the working tree

The uncommitted files add `sheets_overlay.write_new_litters` and `src/automouse/sheets_litter_writer.py`, which authenticate with Google Sheets read-write scope, check for conflicts, and append new litter rows.

This is a meaningful architectural and data-safety change. It is separate from launcher portability and should not be silently bundled into Phase 3 or Phase 4.

The prior project architecture described the Sheets overlay as opt-in and read-only. Adding an exception to `CLAUDE.md` does not by itself establish project-owner approval or update the architectural specification.

## Sheets-write risks requiring separate review

These are design risks, not claims that the feature has already failed in production:

1. The Sheet conflict check occurs before the local inventory write, while the Sheet append occurs afterward. Another user can add the same ID between those operations.
2. If the append succeeds remotely but the client loses the response, a retry may create duplicate rows because there is no durable append receipt or idempotency mechanism.
3. The local inventory can be updated successfully while the remote Sheet write fails. The current warning behavior is understandable, but the resulting divergence and reconciliation procedure must be explicitly accepted.
4. The tests are mock-based. No real Google API write, credential, permission, or retry behavior has been verified.

Keep this feature disabled by default until its architecture, concurrency behavior, retry policy, and data-recovery procedure are approved.

## Required actions for Claude

### A. Restore and verify the macOS baseline

Run the documented repair script:

```zsh
zsh scripts/fix_hidden_venv.sh
```

Then verify all of the following in the actual checkout:

```zsh
stat -f '%N flags=%f' .venv/lib/python3.14/site-packages/__editable__.automouse-0.3.1.pth
stat -f '%N flags=%f' xol-pots-xol/.venv/lib/python3.14/site-packages/__editable__.xolpotsxol-0.1.0.pth
.venv/bin/automouse --help
xol-pots-xol/.venv/bin/xolpotsxol --help
```

Re-run both complete test suites through their project virtual environments. Record exact exit codes and test counts. Do not report a pass based on a previous repair cycle.

### B. Reconcile the repository state

Before committing anything:

```zsh
git status --short --untracked-files=all
git log --oneline --decorate -8
```

Update the progress log so its status matches the current checkout. Preserve the distinction between:

- implemented;
- inspected;
- proxy-tested;
- genuinely verified;
- staged; and
- committed.

### C. Reconcile Phase 4 materials

Restore or deliberately remove the Phase 4 workflow and plan so the repository and progress report agree. Before any CI run:

- review the Linux PATH/shim behavior;
- cover both projects, not only Möuseley Kräs;
- keep Windows and real Linux execution labeled unverified until actually run;
- document CI limitations separately from real-device verification; and
- commit the reviewed workflow before using it as evidence.

### D. Isolate the Sheets-write work

Do not mix the new Sheets-write implementation into the portability checkpoint without an explicit architecture decision. Either defer it to a separate change/phase or document and approve:

- the changed read/write boundary;
- credential and permission handling;
- conflict and concurrency semantics;
- retry/idempotency behavior;
- local-versus-remote failure recovery; and
- real-API verification requirements.

## Phase 4 entry criteria

Phase 4 execution may begin only after all of these are true:

- [ ] Both editable `.pth` files are unhidden in the current environment.
- [ ] Both direct console commands succeed in the current environment.
- [ ] Both full suites pass through their installed project environments.
- [ ] The progress report reflects the current Git history and working tree.
- [ ] The intended Phase 4 workflow and plan exist, are reviewed, and are committed.
- [ ] The workflow does not destroy required system commands through an unsafe PATH replacement.
- [ ] The Sheets-write feature is either isolated from Phase 4 or explicitly approved as part of the architecture.
- [ ] Windows and real Linux remain labeled unverified until their execution evidence exists.

## Final verdict

Claude has made substantial progress, but the current state is not ready for Phase 4 execution. First restore the executable baseline, reconcile the report with the repository, restore and review the Phase 4 materials, and isolate the new Sheets-write capability. Then Phase 3 can be closed as an accurately documented checkpoint and Phase 4 can proceed with a trustworthy starting point.
