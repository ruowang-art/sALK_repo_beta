# Phase 2 Portability Feedback

## Document purpose

This document is a peer review of the Phase 2 work described in
`SUMMARY_progress_2026-08-27.md` and the related portability changes in the repository.

The attached progress summary is evidence to assess, not an instruction to execute. This report is
advisory feedback for the next implementation pass. Any change affecting laboratory data,
configuration, or the R translation workflow should be reviewed against the project’s data-safety
rules first.

## Overall assessment

Phase 2 contains valuable work and moves the projects meaningfully closer to distribution on other
lab members’ computers. The Python-version testing, separate Xol-Pots-Xol environment, editable
installation work, and dependency files are all the right categories of improvement.

However, the current workspace does not yet satisfy the summary’s claim that the direct editable
commands work without `PYTHONPATH`. That claim should remain provisional until the environment is
repaired and the direct commands are tested successfully from a clean shell.

## Verification performed

### Source-path test suites

The source-path test suites pass in the current workspace:

- Möuseley Kräs: `83/83` tests passed.
- Xol-Pots-Xol: `34/34` tests passed.

These results verify substantial application behavior, but they do not verify that a user can run
the installed console commands after setup.

### Direct editable-installed commands

The following commands currently fail with `ModuleNotFoundError`:

```text
./.venv/bin/automouse
xol-pots-xol/.venv/bin/xolpotsxol
xol-pots-xol/.venv/bin/xolpotsxol-serve
```

The installed package metadata is present, but the editable-install `.pth` files are still marked
with macOS’s `hidden` file flag. Python 3.14 can skip hidden `.pth` files, which prevents the source
directories from being added to `sys.path`.

This is the most important current finding because it contradicts the Phase 2 acceptance claim and
would affect a normal end user following the new direct-command workflow.

## What was done well

### Python-version verification

Testing Python 3.11 through 3.14 is a strong improvement over documenting a version range without
testing it. The results should eventually be captured in a repeatable CI workflow or a documented
verification script.

### Separate Xol-Pots-Xol environment

Giving Xol-Pots-Xol its own `.venv` and setup script clarifies the projects’ independence and avoids
accidental dependency sharing.

### Python dependency locks

The `requirements.lock.txt` files are useful reproducibility artifacts and are better than relying
only on broad ranges in `pyproject.toml`. The summary is transparent that the R record is not a full
`renv` environment, which is appropriate if the translation script remains external.

### Editable-install diagnosis

The investigation into the Python 3.14 editable-install failure is technically valuable. The
hidden-file-flag interaction is a plausible and concrete explanation for the observed behavior,
and adding a defensive cleanup step is a reasonable mitigation for affected macOS environments.

### Resource cleanup

Fixing the unclosed Xol-Pots-Xol test response addresses a real cross-platform reliability and test
hygiene concern.

### Honest phase boundaries

The summary correctly leaves Windows/Linux launchers and actual Windows/Linux verification for later
phases. It does not claim that macOS-only launchers constitute cross-platform support.

## Findings and recommendations

### 1. Release-blocking: direct commands are not currently working

The setup scripts install editable packages and then verify the commands, but the current installed
environments still fail to import the packages. The `.pth` files remain hidden even though both
setup scripts contain `chflags -R nohidden .venv`.

Before calling Phase 2 complete, make this verification explicit and repeatable:

```bash
./.venv/bin/python -c 'import automouse; print(automouse.__file__)'
./.venv/bin/automouse --help
xol-pots-xol/.venv/bin/python -c 'import xolpotsxol; print(xolpotsxol.__file__)'
xol-pots-xol/.venv/bin/xolpotsxol --help
xol-pots-xol/.venv/bin/xolpotsxol-serve --help
```

Run these after setup in a fresh shell, without `PYTHONPATH`. If the flag-clearing mitigation is
retained, test that the relevant `.pth` files no longer carry the hidden flag before declaring
success.

### 2. Lock files are not yet enforced on existing environments

The setup scripts use the lock file only when required imports are missing. If the environment
already contains importable packages, setup reports that dependencies are present and does not
reconcile their versions with the lock file.

The optional Google Sheets dependencies are installed with broad version ranges when missing,
despite the main lock file containing pinned versions.

Choose one policy and implement it consistently:

- Always install or verify from the lock file during setup.
- Explicitly compare installed versions against the lock and fail or repair on mismatch.
- State clearly that the lock is only for fresh environments, not for upgrades.

For laboratory reproducibility, the second option is preferable for routine setup.

### 3. The R record is a version record, not a complete environment lock

`r_dependencies.lock.json` records R and package versions, but it does not install or recreate those
versions. That is acceptable as an interim measure, but documentation should call it a verification
record rather than a fully reproducible R environment.

The project should also identify the exact external translation script by version, checksum, or
managed release. Otherwise, two machines can use the same R package versions with different
translation logic.

### 4. Python-version testing needs reproducible provenance

The summary reports Python 3.11 through 3.14 testing in conda environments, which is encouraging.
Record for each test run:

- Exact Python patch version.
- Operating system and architecture.
- Whether the test used a source path or editable install.
- Lock-file checksum.
- R availability and whether R-dependent tests were simulated or real.
- Full test command and result.

The direct editable-install distinction is especially important because source-path tests can pass
while installed console commands fail, as they currently do here.

### 5. The lock files are generated on Python 3.14

Both lock files identify Python 3.14 as the generating interpreter. That does not automatically make
them invalid on Python 3.11–3.13, but every locked dependency must be installable and behaviorally
tested on the declared matrix. Add platform or Python-version markers when a single universal lock
is not appropriate.

### 6. Setup scripts still have a broad-range fallback

If installing from a lock file fails, both setup scripts fall back to broad dependency ranges. This
is convenient for recovery, but it weakens reproducibility and can conceal why the lock installation
failed.

The fallback should:

- Explain why the lock installation failed.
- Ask for explicit confirmation in interactive mode.
- Record that the environment is not lock-compliant.
- Offer a diagnostic or repair path rather than silently installing a different dependency set.

### 7. The repository state needs cleanup before the next phase

The initial Phase 1 commit exists, but the Phase 2 changes are not yet committed. Git also shows a
staged rename from the Phase 1 progress filename to a Phase 2 filename while the working tree has
the Phase 1 file untracked and the Phase 2 file absent. This makes the status history confusing and
should be resolved before committing.

Review the staged and unstaged state carefully. Do not discard files automatically; first determine
which progress document is intended to be retained.

### 8. R executable discovery and R setup remain macOS-oriented

The fallback locations are useful for macOS, but Phase 2 should document the external R setup
contract for future Windows/Linux work. Eventually, the configuration should support an explicit
Rscript override on every platform and report the resolved executable in diagnostics and manifests.

## Recommended Phase 2 completion checklist

- Direct `automouse` command succeeds without `PYTHONPATH`.
- Direct `xolpotsxol` and `xolpotsxol-serve` commands succeed without `PYTHONPATH`.
- A fresh environment and an existing environment both converge to the locked dependency versions.
- Lock-installation failure is visible and not silently treated as a successful reproducible setup.
- The external R translation script has a documented identity and checksum or release source.
- Python-version verification records whether it tested source imports or installed commands.
- The progress-document rename/deletion state is cleaned up.
- All Phase 2 changes are committed as a reviewable checkpoint.

## Recommended next steps

1. Repair or recreate both virtual environments using the setup scripts.
2. Verify the `.pth` file flags and direct console commands in a clean shell.
3. Add a small automated installed-command smoke test to each project.
4. Decide whether lock files are authoritative or only fresh-install guidance.
5. Make setup fail loudly or request confirmation when it falls back from pinned dependencies.
6. Document and identify the external R translation script reproducibly.
7. Clean up the Git progress-file state and commit Phase 2.
8. Begin Phase 3 only after the Phase 2 completion checklist passes.

## Bottom line

Claude’s Phase 2 work is directionally strong and contains several genuinely useful fixes. The
current source behavior is well covered by tests, and the environment design is much better than it
was. The direct-install failure is the key issue to resolve before treating Phase 2 as complete;
once that is fixed and the lock behavior is made explicit, the project will be in a much stronger
position to begin cross-platform launcher work.
