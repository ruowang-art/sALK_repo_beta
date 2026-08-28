# Phase 3 Readiness Suggestions

## Overall conclusion

Claude and Codex are good to proceed with the **macOS Phase 3 repair and
re-verification**. They are not yet good to declare full cross-platform
support.

## Confirmed position

- Hidden macOS flags were cleared during the repair cycle.
- Both direct commands passed after repair.
- Möuseley Kräs passed 89/89 tests.
- Xol-Pots-Xol passed 35/35 tests.
- Windows/PowerShell and real Linux execution remain unverified.
- The clean-tree statement should be understood as historical at commit
  `1fdd68d`; the current worktree contains uncommitted or untracked review,
  response, test, and launcher changes.
- No new localized execution bug, unhandled exception, or variable-scope risk
  was reported by the confirmation audit.

## Corrections to preserve

- Describe the macOS result as **repair and re-verification of existing
  environments**, not a completely fresh environment rebuild.
- Correct the document count: the listed worktree contains **seven Markdown
  documents**, not six.

## Before committing

1. Review the complete staged file list.
2. Confirm that only intended launcher, regression-test, and documentation
   changes are included.
3. Preserve the distinction between historical clean status and current Git
   status.
4. Preserve the distinction between:
   - source-path tests,
   - installed-command verification,
   - macOS verification,
   - Linux proxy testing,
   - and unexecuted Windows testing.
5. Do not claim Windows or Linux support until PowerShell and real Linux or CI
   execution has completed.

## Phase 4 handoff

The remaining work is genuine platform execution:

- Run Windows setup scripts under PowerShell or PowerShell Core.
- Exercise `py -3.11`, unversioned `py`, and unversioned `python`.
- Test unsupported Python versions and virtual-environment creation failures.
- Run Linux launchers on real Linux or CI, not only through macOS `bash`.
- Record exact outputs and retain failures as part of the verification record.

## Decision

Proceed with the intentional commit after the final staged-file review.
Continue Phase 4 separately, with Windows and Linux explicitly marked
unverified until their execution evidence exists.
