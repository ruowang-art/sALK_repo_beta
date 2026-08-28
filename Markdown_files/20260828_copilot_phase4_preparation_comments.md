# Copilot Comments Before Phase 4

## Decision

Phase 4 may be planned, but execution should wait until the macOS baseline is
restored, the current repository state is reconciled, and the intended Phase 3
state is committed.

## Required consolidation

### 1. Restore and verify macOS

Run:

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

Expected baseline:

- Both editable-install `.pth` files have `hidden=False`.
- Direct commands succeed.
- Möuseley Kräs passes 89 tests.
- Xol-Pots-Xol passes 35 tests.
- No production laboratory data is touched.

Record the exact command output.

### 2. Reconcile status claims

Separate these statements clearly:

- Historical state at commit `012d454`.
- Current checkout state.
- Results independently reproduced in the current checkout.

Do not describe the repository as clean unless the current `git status` is
actually clean.

### 3. Review repository changes

Before committing:

- Review modified root instruction/readme shims.
- Review deleted or relocated Markdown files.
- Review all untracked review and response documents.
- Confirm only intended launcher, regression-test, and documentation changes are
  included.
- Preserve the data-safety rules and do not use production files for testing.

### 4. Preserve verification categories

The documentation should distinguish:

| Category | Status |
|---|---|
| Implemented | Windows/Linux launcher files and platform-aware R discovery exist |
| Inspected | Launcher control flow and PowerShell guard reviewed |
| Proxy-tested | Linux shell behavior checked through macOS `bash` |
| macOS verified | Editable installs, direct commands, and both suites pass after repair |
| Windows verified | Not yet verified |
| Real Linux verified | Not yet verified |

### 5. Prepare the Phase 4 handoff

Keep the concrete Windows and Linux test plan, including:

- PowerShell execution of Windows setup scripts.
- `py -3.11`, bare `py`, and bare `python` selection cases.
- Unsupported Python versions.
- Virtual-environment creation failure.
- Real Linux hardware, VM, or CI execution.
- Exact output capture and explicit treatment of failures.

Do not claim Windows/Linux support until their execution evidence exists.

## Localized audit conclusion

The reported macOS repair results are acceptable once reproduced in the actual
checkout. No additional localized execution bug, unhandled exception, or
variable-scope risk is established by the current confirmation. The remaining
blockers are verification integrity, repository-state reconciliation, and
real platform execution.
