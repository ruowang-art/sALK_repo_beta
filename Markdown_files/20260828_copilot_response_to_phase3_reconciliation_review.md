# Copilot Response to Phase 3 Reconciliation Review

## Conclusion

Phase 3 should remain open. Phase 4 should remain prepared but not executed
until the current macOS baseline and repository state are trustworthy.

## Required next sequence

### 1. Restore the macOS baseline

Run the repair script with zsh:

```zsh
zsh scripts/fix_hidden_venv.sh
```

Then verify the editable-install flags, direct commands, and both installed
environment test suites in the same checkout. Record exact output and exit
codes. Do not rely on earlier `95/35` results as the current baseline.

Expected result:

- Root and Xol editable `.pth` files are unhidden.
- `.venv/bin/automouse --help` succeeds.
- `xol-pots-xol/.venv/bin/xolpotsxol --help` succeeds.
- Möuseley Kräs passes its current full suite.
- Xol-Pots-Xol passes its current full suite.
- No production laboratory data is touched.

### 2. Fix PowerShell native-command failure handling

In both Windows setup scripts, check `$LASTEXITCODE` after every required
external command, including:

- virtual-environment creation;
- dependency installation;
- editable installation;
- console-script checks;
- R checks;
- full test suites.

`$ErrorActionPreference = "Stop"` alone is not sufficient protection for
nonzero exit codes from native executables. Prefer one small, auditable helper
over incomplete scattered checks.

### 3. Expand bare-command CI coverage

The `bare-command-selection` scenario should exercise Xol-Pots-Xol as well as
Möuseley Kräs. If it is intentionally excluded, document and test the
equivalent path separately.

### 4. Reconcile progress documentation

Clearly separate:

- historical snapshots;
- current `HEAD`;
- current working-tree contents;
- committed versus uncommitted files;
- implemented, inspected, proxy-tested, and genuinely verified behavior.

Keep the unexplained Phase 4 file disappearance factual. Describe it as
unexplained unless evidence establishes causation.

### 5. Isolate Sheets-write work

Keep `sheets_overlay.write_new_litters` and
`sheets_litter_writer.py` separate from the portability checkpoint unless
explicitly approved. Keep the feature disabled by default until its:

- changed credential scope;
- concurrent-edit behavior;
- retry/idempotency policy;
- local/remote divergence recovery;
- and real-API verification

are intentionally accepted.

### 6. Validate and commit

Run the available shell, YAML, and static checks. Commit the reviewed Phase 3
and Phase 4 preparation changes separately from Sheets-write changes. Run Phase
4 CI only from the committed workflow and plan that were reviewed.

## Phase 4 boundary

After the gate passes, Phase 4 may begin. Continue to label results precisely:

| Category | Status |
|---|---|
| Implemented | Windows/Linux launchers and platform-aware R discovery exist |
| Inspected | Launcher control flow and PowerShell guards reviewed |
| Proxy-tested | Linux behavior checked through macOS `bash` |
| macOS verified | Current editable installs, commands, and suites pass after repair |
| Windows verified | Not established until PowerShell or Windows execution |
| Real Linux verified | Not established until Linux hardware, VM, or CI execution |

Green CI results should be reported as compatibility with the tested runners,
not as universal Windows/Linux device compatibility.

## Final recommendation

Treat the setback as a verification-integrity issue, not a reason to discard
the portability work. Repair the root editable installation first, close the
PowerShell false-success risk, correct CI coverage and documentation, isolate
Sheets-write changes, and then commit the trustworthy Phase 3 checkpoint before
executing Phase 4.
