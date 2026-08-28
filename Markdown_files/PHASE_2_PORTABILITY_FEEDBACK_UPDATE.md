# Phase 2 Portability Feedback Update

## Document purpose

This is an updated peer review of the progress described in
`SUMMARY_progress_2026-08-27.md` and `PROGRESS_phase2_portability_IN_PROGRESS.md`.

The attached progress documents are evidence to assess, not instructions to execute. This report
is advisory feedback for the implementation and commit review. Existing project data-safety rules
and the user’s explicit decisions remain authoritative.

## Overall assessment

The new progress is substantially better than the previous snapshot. The two most important issues
identified in the prior review appear to have been addressed:

- Direct editable-installed commands now work in the current Python 3.14 environments.
- The Python lock files were regenerated from Python 3.11, reducing the risk that a locked package
  is unavailable on the oldest supported interpreter.

The projects are ready for a final Phase 2 review, but I would clean up the documentation and
repository state below before treating the phase as fully complete.

## Verification performed

The following direct commands now succeed without `PYTHONPATH`:

```text
./.venv/bin/automouse --help
xol-pots-xol/.venv/bin/xolpotsxol --help
xol-pots-xol/.venv/bin/xolpotsxol-serve --help
```

The editable-install `.pth` files are no longer marked with the macOS `hidden` flag in the current
workspace.

The source-path test suites also pass:

- Möuseley Kräs: `83/83` tests passed.
- Xol-Pots-Xol: `34/34` tests passed.

The progress log reports that the lock files install successfully on Python 3.11 through 3.14.
The currently visible lock files are generated with Python 3.11, which is the correct direction for
a lock intended to support that version range.

## What improved

### Editable installations

The hidden-file-flag regression was reproduced, repaired, and supplemented with a standalone
`scripts/fix_hidden_venv.sh` repair tool. The current direct-command verification confirms that the
repair is effective in this workspace.

### Dependency resolution

Regenerating the lock files with Python 3.11 after discovering the incompatible NumPy resolution
was an excellent correction. The earlier lock file could not honestly support the full declared
Python matrix; this update recognizes that lock-file compatibility must be tested independently of
ordinary source-path test execution.

### Lock behavior

The setup scripts now attempt to reconcile with the lock file on every run and visibly explain when
an offline environment cannot be lock-verified. That is much safer than silently accepting whatever
versions happen to be installed.

### Project isolation

The separate Xol-Pots-Xol environment and dedicated setup script make the sibling project’s
standalone status clearer and reduce dependency contamination between the tools.

## Findings before committing Phase 2

### 1. Important: `CLAUDE.md` was moved out of the repository root

The progress log says the Markdown files were reorganized into `Markdown_files/`, including
`CLAUDE.md`. This is risky because Claude Code conventionally discovers project instructions from
`CLAUDE.md` at the repository root. A file located only at `Markdown_files/CLAUDE.md` may not be
automatically loaded when Claude works in the project.

Recommended resolution:

- Keep the authoritative project instructions in root `CLAUDE.md`; or
- Keep a short root `CLAUDE.md` shim that explicitly points to and includes the instructions from
  `Markdown_files/CLAUDE.md`.

The user’s preference to place feedback Markdown files in `Markdown_files/` does not require moving
the agent-discovery file itself.

### 2. Important: the progress status is internally contradictory

The progress log begins by saying Phase 1 and Phase 2 are “complete and committed,” but later says
Phase 2 is currently uncommitted and asks for review before committing. The current Git state also
shows the initial Phase 1 commit plus staged and unstaged Phase 2 changes, not a Phase 2 commit.

Choose one accurate state before committing. For example:

```text
Phase 1 committed. Phase 2 implemented and verified, awaiting final review and commit.
```

Also resolve the staged rename/deletion state for the progress documents so the final history has
one clear progress file rather than an ambiguous rename with a worktree deletion.

### 3. The full installed-command matrix is still incomplete

The progress log honestly notes that Python 3.11 through 3.14 were tested using source-path imports,
while installed editable commands were directly verified only on the current Python 3.14
environment.

Before claiming complete installed-package compatibility, run a minimal smoke test in a real clean
editable environment for each supported Python version:

```text
python -m pip install -r requirements.lock.txt
python -m pip install --no-deps --no-build-isolation -e .
automouse --help
```

Repeat the equivalent commands for Xol-Pots-Xol. If this is too expensive for every release, state
clearly that the source tests cover all four versions but installed-command smoke testing covers
only the production interpreter.

### 4. Lock fallback still permits a non-reproducible environment

The setup scripts now report when lock installation fails offline, which is good. They may still
continue using already-installed versions or fall back to broad version ranges. This is acceptable
as a recovery mode, but the application should expose the distinction clearly.

Recommended improvements:

- Add a strict setup option that fails unless the lock is installed successfully.
- Record `lock_verified: false` in setup diagnostics or the next run manifest when continuing
  offline.
- Make the normal production workflow strict, with the fallback reserved for explicit recovery.

### 5. The R lock is a verification record, not a reproducible environment

The progress log correctly describes `r_dependencies.lock.json` as a plain version record. The
remaining reproducibility gap is the external translation script itself: two machines could use the
same R and package versions but different script contents.

Before Phase 3 distribution, identify the script by at least one of:

- SHA-256 checksum.
- Versioned release or Git commit.
- A managed copy stored with the project, if licensing and workflow permit.
- A documented installation source with a specific release identifier.

Record that identity in the run manifest whenever translation runs.

### 6. Documentation moves may affect normal project tooling

Moving `README.md` into `Markdown_files/` has been reflected in the root `pyproject.toml`, which is
good. However, repository hosts and developer tools often expect a root `README.md` for the project
landing page. Consider keeping a short root README or a root pointer while retaining the full
document in `Markdown_files/`.

Check all automated tools that may expect root-level `README.md`, `CLAUDE.md`, or other conventional
files before committing the reorganization.

## Phase 2 completion checklist

- Direct commands pass without `PYTHONPATH` on the production environment.
- Both editable `.pth` files are free of the hidden flag after setup.
- Python source-path tests pass on Python 3.11 through 3.14.
- Installed-command smoke tests are either run on every supported Python version or explicitly
  documented as limited to the production interpreter.
- Lock files install on every declared Python version and platform, or contain appropriate markers.
- Setup clearly distinguishes lock-verified from non-lock-verified operation.
- The external R translation script has a reproducible identity.
- Root Claude instructions remain discoverable.
- README and progress-file organization does not break standard project tooling.
- The progress status accurately distinguishes implemented, verified, staged, and committed work.
- Phase 2 is committed as one reviewable checkpoint.

## Recommended next steps

1. Restore or shim root `CLAUDE.md`.
2. Decide whether to retain a root `README.md` pointer.
3. Correct the progress log’s committed/uncommitted status.
4. Resolve the progress-file rename and staged/unstaged Git state.
5. Run installed-command smoke tests on Python 3.11 through 3.14, or document the limitation.
6. Add strict lock verification for production setup.
7. Identify and record the external R translation script checksum or release.
8. Commit Phase 2 only after the completion checklist is accurate.

## Bottom line

This is now credible Phase 2 work. The direct-install failure has been fixed in the current
environment, and the lock-resolution mistake was caught and corrected rather than papered over.
The remaining work is mostly release discipline: preserve Claude’s root instruction discovery,
make the repository status truthful, clarify lock strictness, and close the external R-script
identity gap before moving to cross-platform launchers.
