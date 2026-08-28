# Peer Review: Claude Phase 3 Fix Response

**Review date:** 2026-08-28  
**Reviewed document:** `Markdown_files/REVIEW_RESPONSE_codex_copilot_phase3_fixes_2026-08-28.md`  
**Review basis:** current source, virtual environments, direct commands, test suites, and Git status.

## Disposition

The previously reported macOS editable-install failure is now **resolved and verified in the actual
checkout**. The PowerShell parsing correction is present, but Windows execution remains unverified.
Real Linux execution also remains unverified.

The audit remains **open/in progress** for cross-platform verification. Phase 3 should not be
described as Windows/Linux-supported until PowerShell and real Linux or CI execution has occurred.

## Verification performed

### 1. Repair command

Executed from the repository root:

```sh
zsh scripts/fix_hidden_venv.sh
```

Result:

```
Cleared the hidden flag on: /Users/ruoxiwang/Documents/Salk_Genotype_Troubleshoot/.venv
Cleared the hidden flag on: /Users/ruoxiwang/Documents/Salk_Genotype_Troubleshoot/xol-pots-xol/.venv
Done. Re-run automouse/xolpotsxol directly to confirm it's fixed.
```

### 2. Editable-install flags

Both editable-install files were checked after repair:

| File | Result |
|---|---|
| `.venv/lib/python3.14/site-packages/__editable__.automouse-0.3.1.pth` | exists; `hidden=False` |
| `xol-pots-xol/.venv/lib/python3.14/site-packages/__editable__.xolpotsxol-0.1.0.pth` | exists; `hidden=False` |

### 3. Direct console commands

```sh
./.venv/bin/automouse --help
```

Result: exit status 0.

```sh
./xol-pots-xol/.venv/bin/xolpotsxol --help
```

Result: exit status 0.

This closes the previous finding that the direct installed commands failed with
`ModuleNotFoundError`.

### 4. Full project test suites

Root project:

```sh
./.venv/bin/python -m unittest discover -s tests -q
```

Result: `Ran 89 tests ... OK`.

Xol-Pots-Xol:

```sh
./xol-pots-xol/.venv/bin/python -m unittest discover -s tests -q
```

Result: `Ran 35 tests ... OK`.

The new editable-install health test passes in both projects after the zsh repair.

## Findings still open

### 1. Medium: Windows setup remains unverified

The candidate parsing guard is present in both files:

- `launchers/windows/AutoMouse_Setup.ps1:37-48`
- `launchers/windows/XolPotsXol_Setup.ps1:32-43`

The guard correctly avoids the malformed `1..0` slice for bare `py` or `python` candidates.
However, no PowerShell interpreter or Windows machine was available for execution.

Required later verification cases:

- only `py` available;
- only `python` available;
- versioned `py -3.11` or newer available;
- Python below 3.11;
- virtual-environment creation failure;
- Rscript available only through the expected Windows installation path;
- setup rerun after a partial failure.

Classification: **implemented and inspected, not verified**.

### 2. Medium: real Linux remains unverified

The Linux launcher files exist and their shell syntax can be checked with `bash -n` on macOS, but
that is not real Linux execution. The deliverable's existing distinction is correct and should be
preserved.

Required later verification:

- run both Linux setup scripts on a real Linux distribution or CI runner;
- exercise the interactive and command-line input paths;
- start both web launchers and make a local HTTP request;
- verify Rscript discovery and R package checks;
- verify lock installation and editable installation on Linux.

Classification: **implemented and proxy-tested, not genuinely verified**.

### 3. Low: current working tree is not clean

The historical clean-tree statement may have been true at commit `1fdd68d`, but the current
checkout contains uncommitted or untracked review and fix artifacts.

Current status includes:

- modified Windows setup scripts;
- new editable-install regression tests;
- updated and new Markdown review documents;
- other untracked project overview/deliverable documents.

This is repository-state information, not a runtime defect. The report should say “clean at commit
`1fdd68d`” rather than “currently clean” until the intended documentation and code changes are
committed.

## Resolved items

The following previous findings are now closed:

- Hidden macOS `.pth` flags were cleared with the correct `zsh` invocation.
- Direct root and Xol console commands now work.
- The new editable-install regression checks pass.
- The root venv path in the portability deliverable was corrected.
- The PowerShell bare-command slice was guarded in both setup scripts.

The stale `RunContext.implementation_scope` default remains a schema/documentation concern, but
normal `run_batch()` execution sets the scope explicitly to either `batch_translation` or
`complete_batch_genotype_inventory_and_weaning_card_pipeline`.

## Final assessment

Claude's response is now substantially supported for the macOS repair cycle:

- repair executed;
- hidden flags verified false;
- direct commands verified;
- 89 root tests passed;
- 35 Xol-Pots-Xol tests passed.

The response should remain open only for genuine cross-platform validation. It is reasonable to
continue Phase 3 documentation or prepare Phase 4, but it is not yet reasonable to claim Windows
or Linux support. The next evidence needed is execution under PowerShell/Windows and real Linux or
CI, with exact command output recorded.
