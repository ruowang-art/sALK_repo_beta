# Phase 1 Portability Feedback

## Document purpose

This document is a peer review of the Phase 1 portability work recorded in
`PROGRESS_phase1_portability_IN_PROGRESS.md`. It evaluates changes made by another coding
assistant, Claude, against the current repository state.

This is advisory review feedback, not an instruction embedded in the project specification. Any
implementation decision should be checked against the actual code, tests, laboratory workflow,
and data-safety rules before work begins.

## Overall assessment

Phase 1 is a solid foundation. The work is appropriately staged and several changes are meaningful,
verified improvements rather than cosmetic portability changes.

The projects are not cross-platform yet, but the current status is honestly documented: Phase 1
prepares the codebase for portability, while later phases are responsible for packaging,
cross-platform launchers, and actual Windows/Linux verification.

## Verification performed

The test suites were run from the current workspace:

- Möuseley Kräs: `83/83` tests passed.
- Xol-Pots-Xol: `34/34` tests passed.

The Xol-Pots-Xol suite passes when invoked from its project directory with the workspace virtual
environment:

```bash
PYTHONPATH=src ../.venv/bin/python -m unittest discover -s tests -q
```

The passing tests provide confidence in the current changes, but they do not substitute for testing
on Windows, Linux, Intel Macs, or additional browsers and spreadsheet applications.

## What was done well

### Version reporting

The stale hard-coded setup-script version was removed. This prevents the installer from presenting
an older version than the package actually contains.

### Configuration hygiene

A scrubbed `config/pipeline_run.example.yaml` was added, while the real machine-specific
configuration is excluded from Git. This is an important improvement because the active
configuration contains local inventory paths, a Google Sheet reference, and credentials-related
settings.

### R executable discovery

Möuseley Kräs now preserves an explicitly valid configured R executable, then falls back to `PATH`
and common macOS locations. The failure message is also more actionable when R cannot be found.

### Run-environment metadata

Run manifests now record operating system, operating-system version, and machine architecture in
addition to application and runtime information. This will make future data differences easier to
distinguish from software or device differences.

### Version-control and data protection

Initializing Git and adding a carefully reviewed `.gitignore` is a strong operational improvement.
The real inventory, raw laboratory exports, credentials, generated output, and local environments
are excluded from tracking.

### Appropriate deferral

The progress log correctly defers dependency locks, packaging, cross-platform launchers, and
Windows/Linux verification instead of implying that those goals are already complete.

## Remaining findings

### 1. The projects are not cross-platform yet

The setup and launchers still depend on macOS, zsh, AppleScript, and `.command` files. This is
acceptable for Phase 1, but the project should continue to describe Windows and Linux as
unsupported until Phase 4 testing is complete.

### 2. The translation script remains machine-specific

R executable discovery is portable within reason, but the configured `translation_script` is still
an absolute path to an external file. A new lab member will need a documented way to obtain and
configure the correct translation script, including its expected version and R package
dependencies.

### 3. Dependencies are still unpinned

Both projects use broad requirements such as:

```text
Python >=3.11
openpyxl >=3.1
Flask >=3.0
```

Future releases could change behavior without source-code changes. Phase 2 should add Python lock
files or constraints and an R `renv.lock` or equivalent package record.

### 4. The shared virtual environment needs an explicit policy

Xol-Pots-Xol currently uses the root `.venv` and a source-path override even though it is a
standalone sibling project. This works locally but leaves ownership unclear.

Choose and document one model:

- Separate virtual environments and lock files for each project.
- One deliberate workspace environment containing both projects, with one managed lock.

The launchers should report the Python executable and package versions they actually use.

### 5. The default configuration path depends on the working directory

The CLI default is `config/pipeline_run.yaml`. An installed command invoked outside the project
root may not find that file. A future packaging pass should define whether configuration is:

- Explicitly required from a command-line argument.
- Located relative to the project installation.
- Located through an environment variable.
- Generated per user during setup.

The behavior should be consistent across macOS, Windows, and Linux.

### 6. The repository needs a committed baseline

Git has been initialized, but there is no initial commit yet. Before substantial Phase 2 work,
review the dry-run file list, confirm that no real laboratory data or credentials would be tracked,
and commit a clean baseline. This will make later portability changes easier to review and recover.

### 7. Test resource cleanup should be tightened

The Xol-Pots-Xol test run passed but emitted a Python `ResourceWarning` for an unclosed workbook
file. This is not currently a test failure, but it should be fixed so resource leaks do not remain
hidden when tests run with stricter warning settings or on another operating system.

## Recommended Phase 2 entry criteria

Begin Phase 2 when:

- The initial Git baseline has been reviewed and committed.
- The R translation script distribution and version are documented.
- The lab chooses separate environments or a deliberately managed shared environment.
- A supported production Python version is selected.
- The configuration-loading behavior from outside the project root is defined.

## Recommended Phase 2 work

1. Make `pip install -e .` or the chosen package-manager workflow the normal installation path.
2. Remove routine reliance on `PYTHONPATH`.
3. Add Python dependency locks or constraints for both projects.
4. Add an R package lock or reproducible R environment.
5. Select and document the supported Python version range.
6. Make configuration paths portable and user-specific settings explicit.
7. Add a runtime diagnostic command showing Python, R, package, OS, and architecture details.
8. Fix the workbook resource warning and run tests with warnings treated as errors where practical.
9. Add a clean-install smoke test that starts both command-line interfaces from outside the project
   root.

## Bottom line

Claude’s Phase 1 work is credible and useful. It fixed real portability hazards, improved the
repository’s safety posture, and accurately identified what still requires design decisions or
other operating systems. The project is ready to move into packaging and environment management,
provided the Git baseline and the remaining machine-specific assumptions are addressed first.
