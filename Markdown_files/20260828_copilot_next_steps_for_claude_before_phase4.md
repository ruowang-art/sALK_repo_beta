# Copilot Next Steps for Claude Before Phase 4

## Decision

Do not begin Phase 4 execution from the current checkout. First recover and
reconcile Phase 3 so the starting point is reproducible and accurately
documented.

This guidance follows
`20260828_codex_phase3_setback_review.md` and is limited to execution,
verification, repository-state, and data-safety concerns.

## 1. Restore the macOS executable baseline

Run the repair script with zsh:

```zsh
zsh scripts/fix_hidden_venv.sh
```

Then verify in the same checkout:

```zsh
stat -f '%N flags=%f' .venv/lib/python3.14/site-packages/__editable__.automouse-0.3.1.pth
stat -f '%N flags=%f' xol-pots-xol/.venv/lib/python3.14/site-packages/__editable__.xolpotsxol-0.1.0.pth
.venv/bin/automouse --help
xol-pots-xol/.venv/bin/xolpotsxol --help
.venv/bin/python -m unittest discover -s tests
xol-pots-xol/.venv/bin/python -m unittest discover -s tests
```

Record exact exit codes and test counts. Do not rely on results from an earlier
repair cycle.

Expected gate:

- Both editable `.pth` files are unhidden.
- Both direct commands succeed.
- Möuseley Kräs passes 89 tests.
- Xol-Pots-Xol passes 35 tests.
- No production laboratory data is read, modified, or used as test output.

## 2. Reconcile the repository state

Capture:

```zsh
git status --short --untracked-files=all
git log --oneline --decorate -8
```

Update the progress and status documents to distinguish clearly between:

- Historical commit state.
- Current checkout state.
- Implemented changes.
- Inspected or proxy-tested behavior.
- Genuinely verified behavior.
- Staged changes.
- Committed changes.

Do not describe the tree as clean unless the current status is empty.

## 3. Reconcile Phase 4 materials

The Phase 4 workflow and execution plan must either be restored or deliberately
removed so the repository and reports agree.

Before any CI execution:

- Review Linux `PATH` and temporary-shim behavior.
- Ensure required commands such as `bash`, `mkdir`, `Rscript`, and `sleep` remain
  available.
- Cover both projects, not only Möuseley Kräs.
- Keep Windows and real Linux labeled unverified until their environments or CI
  execute the launchers.
- Distinguish CI evidence from real-device verification.
- Commit the reviewed workflow before using it as evidence.

## 4. Isolate the Google Sheets write feature

Do not silently bundle `sheets_overlay.write_new_litters` or
`sheets_litter_writer.py` into the portability checkpoint.

Keep the feature disabled by default unless explicitly approved. A separate
architecture decision should address:

- The changed read/write boundary and credential scopes.
- Concurrent edits between conflict checking and append.
- Retry and idempotency behavior after uncertain remote responses.
- Local-success/remote-failure divergence and recovery.
- Real API, permission, and credential verification.

The existing project convention describes the Sheets overlay as opt-in and
read-only; this new write capability therefore requires deliberate review.

## 5. Phase 4 entry criteria

Phase 4 execution may begin only when all of the following are true:

- [ ] Current macOS editable-install files are unhidden.
- [ ] Both direct console commands succeed.
- [ ] Both installed-environment test suites pass.
- [ ] Exact verification output is recorded.
- [ ] Progress/status documents match the current Git history and worktree.
- [ ] Phase 4 workflow and plan are present, reviewed, and committed.
- [ ] Linux workflow `PATH` handling preserves required system commands.
- [ ] Sheets-write work is isolated or explicitly approved.
- [ ] Windows and real Linux remain marked unverified until execution evidence
      exists.

## Final recommendation

Treat this as a Phase 3 recovery checkpoint, not a reason to discard the
portability work. Once the macOS baseline, repository state, Phase 4 materials,
and Sheets-write boundary are reconciled, close Phase 3 accurately and proceed
to Phase 4 verification.
