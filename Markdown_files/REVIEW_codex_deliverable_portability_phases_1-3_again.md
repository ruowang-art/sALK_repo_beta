# Review: Codex Deliverable Portability Phases 1-3

**Review date:** 2026-08-28  
**Reviewed document:** `Markdown_files/CODEX_DELIVERABLE_portability_phases_1-3.md`  
**Review basis:** current Git state, source code, launchers, virtual environments, and test execution.

## Findings

### 1. High: the current editable installs are broken again on macOS

The deliverable says the hidden-`.pth` problem was fixed and that direct commands work without
`PYTHONPATH`. In the current checkout:

- `.venv/bin/python` starts, but `./.venv/bin/automouse --help` fails with
  `ModuleNotFoundError: No module named 'automouse'`.
- `xol-pots-xol/.venv/bin/xolpotsxol` has the same failure for `xolpotsxol`.
- Both editable-install files are currently marked with the macOS `hidden` flag:
  `.venv/lib/python3.14/site-packages/__editable__.automouse-0.3.1.pth` and
  `.venv/lib/python3.14/site-packages/__editable__.xolpotsxol-0.1.0.pth`.
- With `PYTHONPATH=src`, the root suite passes 88 tests and the Xol suite passes 34 tests, so
  the source code itself is importable and the failure is specifically in the installed-entry
  point path.

This means the deliverable's direct-command verification is not currently reproducible from the
checked-out environments. The Phase 2 repair step either was not applied to these environments,
was applied before the flags returned, or was not validated after setup completed.

**Evidence:** `.venv/lib/python3.14/site-packages/*.pth`; `AutoMouse_Setup.command:130-166`;
`XolPotsXol_Setup.command:85-98`; `scripts/fix_hidden_venv.sh`.

**Required follow-up:** rerun the setup/repair path, verify the flags are cleared, then prove
`./.venv/bin/automouse --help` and `xol-pots-xol/.venv/bin/xolpotsxol --help` in fresh shells. Add a
regression check that fails when an editable `.pth` file is hidden on macOS.

### 2. Medium: the Windows setup scripts have an unverified argument-parsing edge case

Both Windows setup scripts parse candidate commands like `py -3.14`, `py`, and `python` using:

```powershell
$parts = $candidate -split " "
$exeArgs = $parts[1..($parts.Length - 1)]
```

When `$candidate` contains only `py` or `python`, the range is `1..0`, rather than an empty
argument list. Depending on PowerShell's array coercion, this can pass an unintended argument to
the interpreter and cause a valid unversioned `py` or `python` installation to be rejected.

**Evidence:** `launchers/windows/AutoMouse_Setup.ps1:37-48` and
`launchers/windows/XolPotsXol_Setup.ps1:32-43`.

**Required follow-up:** represent each candidate as an executable plus an explicit argument array,
or branch on array length before slicing. Then run both setup scripts under Windows PowerShell or
PowerShell Core with each of these cases: `py -3.11`, `py`, and `python` only.

This is a static finding, not a claim that the bug has been reproduced on Windows. The deliverable
is correct to say that the Windows launchers have not been executed; that limitation makes this
edge case a Phase 4 prerequisite rather than a confirmed Windows runtime defect.

### 3. Medium: the deliverable's virtual-environment path is wrong

The Phase 2 key-file list says:

```text
src/automouse/.venv/
```

The actual root project environment is `.venv/`; only Xol-Pots-Xol has its environment under
`xol-pots-xol/.venv/`. The launcher scripts also use the root `.venv/` path.

**Evidence:** `Markdown_files/CODEX_DELIVERABLE_portability_phases_1-3.md:114-115`;
`launchers/linux/AutoMouse_Setup.sh:98`; `AutoMouse_Setup.command:82`.

**Required follow-up:** correct the path in the deliverable and any companion documentation. This
is documentation drift, not a source-code defect, but it can cause a future maintainer to repair
the wrong environment.

### 4. Low: the working-tree status claim is stale in the current checkout

The document states “Working tree is clean” and records a clean `git status --short`. The current
working tree has untracked Markdown files, including the deliverable under review and prior audit
artifacts. This does not indicate a code change or data exposure, but the statement is no longer a
true description of the checkout.

**Evidence:** current `git status --short` reports untracked files including
`Markdown_files/CODEX_DELIVERABLE_portability_phases_1-3.md`,
`Markdown_files/COPILOT_PROJECT_OVERVIEW.md`, and the architecture audit.

**Required follow-up:** describe the status as “clean at commit `1fdd68d`” if that was the intended
historical claim, or update the status after the documentation files are deliberately committed.

## Confirmed claims

The following parts of the deliverable were supported by the current inspection or rerun:

- `main` points to the documented Phase 3 commit `1fdd68d`.
- The five Linux launcher files and five Windows PowerShell launcher files exist.
- Linux launcher syntax passes `bash -n` on this macOS machine.
- Windows launcher files explicitly state that they have not been executed.
- `config.py` branches R executable candidates on `platform.system()` and the tests cover the
  candidate-selection logic for macOS, Linux, and Windows-shaped paths.
- `run_batch()` assigns `implementation_scope` explicitly at runtime. The default field value in
  `RunContext` is still `phase_1_and_phase_2`, but normal batch runs replace it with
  `batch_translation` or `complete_batch_genotype_inventory_and_weaning_card_pipeline`. Therefore,
  this is a documentation/schema concern, not currently a demonstrated runtime mislabel for the
  normal batch path.
- The run manifest records the translation script path and SHA-256 content hash.
- With explicit source paths and the available Python 3.14 environment, the root test suite passes
  88 tests and Xol-Pots-Xol passes 34 tests.

## Verification boundary

The deliverable is appropriately cautious about platform support. This review preserves the same
distinctions:

| Claim type | Current conclusion |
|---|---|
| Implemented | Linux and Windows launcher files exist; platform-aware R discovery exists. |
| Inspected | Launcher control flow and path handling were read directly. |
| Proxy-tested | Linux shell syntax and source-path test execution can be checked on macOS. |
| Genuinely verified | Current macOS source-path tests pass; Windows and real Linux remain unverified here. |

The additional current finding is that the installed-entry-point path is not passing on this Mac,
so a fresh setup/repair validation is needed even before interpreting the Linux proxy result as
meaningful. The existing report's historical test claims may still accurately describe the
environment in which they were run; they are simply not sufficient evidence for the current
checkout state.

## Recommended disposition

Do not treat this review as a reason to discard Phase 3. Treat it as a stop-the-line portability
check before claiming the phase is operationally complete:

1. Repair and regression-test the hidden editable-install files.
2. Correct the `.venv` path in the deliverable.
3. Fix or explicitly test the Windows candidate-command parsing.
4. Rerun direct command checks and both suites through the same paths the launchers use.
5. Keep Windows and real Linux in the “not verified” category until PowerShell and a real Linux
   environment or CI job execute the launchers.

## Bottom line

The deliverable's overall honesty about Windows/Linux verification is good, and the core Phase 3
changes are present. The most important issue is not the report's high-level reasoning; it is that
the current macOS editable installs reproduce the exact hidden-`.pth` failure that Phase 2 claimed
to have resolved. That should be fixed and proven first. After that, the unexecuted Windows setup
path deserves focused validation, especially its Python interpreter selection logic.

