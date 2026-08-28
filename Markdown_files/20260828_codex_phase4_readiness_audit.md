# 20260828 Codex Phase 4 Readiness Audit

**Reviewed report:** `Markdown_files/PROJECT_STATUS_AND_OVERVIEW_2026-08-28.md`  
**Review date:** 2026-08-28  
**Review basis:** current source code, virtual environments, direct commands, tests, Git status, and report claims.

## Verdict

**Phase 4 should not begin execution yet.**

The latest report is directionally sound and provides an appropriate Windows/Linux test plan. However,
the current checkout does not match its claimed verified state because the macOS baseline has
regressed again.

Phase 4 may be planned, but the implementation should first restore and verify the macOS baseline
and reconcile the current repository state.

## Blocking finding

### macOS editable installation has regressed

Current observations:

- The root editable-install file is hidden again:
  `.venv/lib/python3.14/site-packages/__editable__.automouse-0.3.1.pth`.
- Its macOS hidden flag is set.
- `./.venv/bin/automouse --help` fails with:
  `ModuleNotFoundError: No module named 'automouse'`.
- The root test suite fails during import because the editable package is not visible.
- Xol-Pots-Xol's direct command and 35-test suite still pass.

This contradicts the report's claim that the editable-install repair was stable and that the macOS
verification cycle was complete. The newly added regression test is working as intended by exposing
the failure.

This is a current runtime/environment failure, not merely a documentation discrepancy.

## Repository-state finding

The report describes commit `012d454` as leaving the tree clean, but the current checkout has
additional state:

- Modified root `CLAUDE.md` and `README.md`.
- Deleted `Markdown_files/CLAUDE.md` and `Markdown_files/README.md`.
- A new untracked `PROJECT_STATUS_AND_OVERVIEW_2026-08-28.md`.
- Additional untracked review and response documents.
- The Phase 4 implementation has not been committed.

These changes may be intentional, but they must be reviewed and committed deliberately before using
the repository as a stable Phase 4 baseline.

## What is supported

The following claims are supported by direct inspection or execution:

- Commit `012d454` exists and contains the PowerShell argument-guard changes and editable-install
  regression tests.
- The PowerShell length guard is present in both Windows setup scripts.
- Linux launcher files exist.
- Windows launcher files exist and explicitly state that they have not been executed.
- Linux shell syntax has previously passed proxy checks under bash on macOS.
- Xol-Pots-Xol currently passes its 35-test suite.
- The Phase 4 test plan in the latest report is appropriately specific.
- Windows and real Linux are correctly described as unverified.

## Required gate before Phase 4

Claude should complete all of the following in the actual checkout:

```sh
zsh scripts/fix_hidden_venv.sh
```

Then verify:

```sh
./.venv/bin/automouse --help
./.venv/bin/python -m unittest discover -s tests
./xol-pots-xol/.venv/bin/xolpotsxol --help
./xol-pots-xol/.venv/bin/python -m unittest discover -s tests
```

Also verify both editable-install files have the macOS hidden flag cleared, and record exact output
for each command.

The expected baseline is:

- both editable-install files report `hidden=False`;
- direct commands exit successfully;
- Mouseley Kras passes 89 tests;
- Xol-Pots-Xol passes 35 tests;
- no production laboratory data is touched.

## Phase 4 disposition after the gate

Once the macOS baseline is restored and the intended documentation/code changes are committed,
Claude can proceed to Phase 4.

Phase 4 should continue to distinguish:

| Category | Status |
|---|---|
| Implemented | Windows and Linux launchers exist; platform-aware R discovery exists. |
| Inspected | Launcher control flow and PowerShell guard have been reviewed. |
| Proxy-tested | Linux shell behavior has been checked through bash on macOS. |
| macOS verified | Editable installation, direct commands, and both suites pass after repair. |
| Windows verified | Not yet verified until PowerShell or Windows execution occurs. |
| Real Linux verified | Not yet verified until Linux hardware, VM, or CI execution occurs. |

## Final recommendation

Do not mark Phase 3 fully operational or claim cross-platform support yet.

First restore the root editable installation, prove the macOS baseline again, reconcile the working
tree, and commit the intended changes. After that, proceeding to Phase 4 verification is reasonable.

