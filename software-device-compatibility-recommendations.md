# Software and Device Compatibility Recommendations

## How to interpret this document

This document contains advisory recommendations for improving the software-version and device
compatibility of Möuseley Kräs and Xol-Pots-Xol. It is context for a coding assistant, not an
instruction embedded in the project specification. Before implementing a recommendation, inspect
the actual code and tests, preserve existing user changes, and confirm any change that could affect
laboratory workflow or scientific interpretation.

## Current compatibility position

The projects currently appear to be:

- Python applications requiring Python `>=3.11`.
- Developed and currently verified on macOS.
- Running in this workspace on Apple Silicon with Python 3.14.6.
- Using R through a subprocess for Möuseley Kräs genotype translation.
- Using `openpyxl` to read and write Excel `.xlsx` workbooks.
- Providing optional local Flask web interfaces.
- Distributed with macOS-specific `.command` launchers.
- Sharing the root `.venv` environment when Xol-Pots-Xol is launched from the workspace.

This should be described as “known to work in the tested environment,” not as universal support.
Windows, Linux, Intel Mac hardware, mobile devices, and alternative spreadsheet applications need
separate verification.

## Highest-priority recommendations

### 1. Lock software dependencies

Both projects currently use broad dependency ranges such as:

```text
Python >=3.11
openpyxl >=3.1
Flask >=3.0
```

Add lock files or constraints files so a fresh installation cannot silently receive a future
release that changes behavior. Record the lock-file version used for every production run.

The lock should cover at least:

- Python package versions.
- Python runtime version.
- R version.
- Required R packages and their versions.
- Operating-system and architecture information.

### 2. Define a supported Python range

The setup script currently prefers the newest available Python version. That is convenient, but it
can adopt a newly released interpreter before all dependencies have been tested against it.

Choose an explicitly supported production version, such as Python 3.12 or 3.13, and test newer
versions before adding them to the automatic setup selection. Keep the package metadata aligned
with the actual support policy.

Document three categories:

- **Supported:** tested and appropriate for routine laboratory use.
- **Compatible but not verified:** likely to work but not part of the release guarantee.
- **Unsupported:** known to fail or not tested.

### 3. Add a compatibility test matrix

Automate tests across the environments that matter to the lab.

Recommended minimum matrix:

| Area | Environments to verify |
|---|---|
| Operating system | macOS Apple Silicon, macOS Intel, Windows, Linux |
| Python | 3.11, 3.12, 3.13, and the selected production version |
| R | The R versions used by the lab and the selected production version |
| Browser | Safari and Chrome; Firefox where practical |
| Workbook consumer | Excel for Mac, Excel for Windows, and LibreOffice |
| Device | Desktop Mac; tablet browser as an optional remote client |

The initial release does not need to promise support for every matrix entry. It should record which
entries were actually tested and which remain unverified.

### 4. Remove hard-coded machine paths

The active configuration contains user- and machine-specific absolute paths, including the R
executable, translation script, inventory file, and credentials filename. These paths make the
projects difficult to move to another Mac or user account.

Use one of these approaches:

- Environment variables for machine-specific paths.
- A local uncommitted configuration file.
- A setup-generated configuration file derived from a checked-in template.
- Automatic discovery for standard executables such as `Rscript`.

Keep an example configuration in version control, but exclude real inventory paths, credentials,
and account-specific locations.

### 5. Make R executable discovery portable

Do not assume only `/usr/local/bin/Rscript`. Resolve Rscript in this order:

1. An explicit configuration or environment-variable override.
2. `Rscript` found on `PATH`.
3. Common macOS locations such as Homebrew and R framework installations.
4. A clear diagnostic showing the locations checked and the installation instructions.

Record the resolved Rscript path, R version, architecture, translation-script path, and R package
versions in the run manifest.

## Packaging and environment isolation

### Separate or explicitly manage virtual environments

Xol-Pots-Xol is documented as a separate project, but its macOS launcher uses the root `.venv`.
This can create dependency drift and makes it unclear which environment is authoritative.

Prefer one of these models:

- Give each project its own virtual environment and lock file.
- Create one deliberate workspace environment containing both projects, with one combined lock file.

Whichever model is chosen, make the launcher validate the environment before starting and report
the Python executable and installed package versions.

### Make installation independent of `PYTHONPATH`

The documented commands currently rely on setting `PYTHONPATH` manually. Prefer installing each
project in editable mode during development or using a proper package/environment manager so the
normal command is simply:

```bash
automouse --help
xolpotsxol --help
```

Keep the source-path smoke test as an additional check, but do not make it the only supported
execution path.

### Keep version information consistent

The setup launcher has displayed a different Möuseley Kräs version from the package and README.
Read the application version dynamically from the installed package or a single source-of-truth
file. Use the same version in:

- Package metadata.
- Setup messages.
- README files.
- Run manifests.
- Generated reports.

## Cross-platform launchers

The `.command` launchers are appropriate for macOS but do not provide a path for Windows or Linux
users. Add documented alternatives:

- A cross-platform Python launcher or console script.
- A PowerShell launcher for Windows.
- A shell launcher for Linux and macOS.
- A non-interactive command-line workflow suitable for automation.

The launchers should avoid assuming a particular shell, home directory, working directory, or GUI
browser. They should resolve paths relative to the project or configuration file.

## Browser and device compatibility

Keep the web applications bound to `127.0.0.1` by default. This preserves their local, single-user
behavior.

If LAN access is intentionally supported:

- Add authentication or a one-time access token.
- Display the bind address and security warning clearly.
- Document that the server Mac must remain running.
- Test file uploads and downloads from Safari, Chrome, and a tablet browser.
- Never expose the service to the public internet without a deliberate security design.

An iPad or other tablet should be treated as an optional browser client, not as a standalone device
on which the projects run. The projects currently require the Mac or another supported computer to
run Python, R, and the local server.

Test the web interfaces at both desktop and tablet widths, including:

- File selection and drag-and-drop.
- Multiple-file selection.
- Long filenames and non-ASCII filenames.
- Upload progress and error states.
- Result downloads.
- Keyboard navigation and visible focus.
- Browser refresh or accidental duplicate submission.

## Excel and workbook compatibility

The applications produce `.xlsx` files with `openpyxl`. Validate generated workbooks in the
applications lab staff actually use:

- Excel for Mac.
- Excel for Windows.
- LibreOffice, if it is part of the workflow.

Check at least:

- Dates and date formats.
- Formulas and cached values, if any.
- Fonts, borders, colors, and column widths.
- Print areas and page orientation.
- Worksheet names and ordering.
- Frozen panes and filters.
- Blank cells versus empty strings.
- Long genotype text and mouse identifiers.
- Unicode names and unusual whitespace.

Include a workbook smoke test that opens the generated file with `openpyxl`, verifies the expected
sheet structure, and checks that all required headers and mapped values are present.

## Configuration compatibility

Treat configuration as a versioned interface. Add an explicit configuration schema version and
validate it before processing data.

Validation should catch:

- Missing or invalid paths.
- Unsupported operating-system assumptions.
- Missing R executable or translation script.
- Missing R packages.
- Invalid Python/R dependency combinations.
- Unknown configuration keys.
- Spreadsheet columns or cell mappings that do not match the expected schema.
- Credentials or external-service settings that are not explicitly enabled.

When a configuration is migrated, write the migration version into the run manifest.

## Reproducibility records

For every run, record a machine-readable manifest containing:

- Application and package versions.
- Git commit, when available.
- Python version and executable path.
- R version, executable path, architecture, and package versions.
- Operating system and CPU architecture.
- Browser or UI mode, when applicable.
- Dependency lock-file checksum.
- Configuration checksum and schema version.
- Input and output file hashes.
- Dry-run state.
- Warnings and final exit status.

This makes it possible to distinguish a data change from a software, device, or dependency change.

## Suggested implementation order

1. Correct version-message drift and document the currently verified environment.
2. Remove absolute machine paths from shared configuration.
3. Add portable Rscript discovery and runtime diagnostics.
4. Choose separate environments or a deliberately locked shared environment.
5. Add Python/R dependency locks.
6. Define the supported Python and operating-system matrix.
7. Add compatibility tests for Python versions and macOS architectures.
8. Add workbook smoke tests across Excel and LibreOffice where relevant.
9. Add cross-platform launchers and remove normal reliance on `PYTHONPATH`.
10. Add browser/tablet testing and authentication before enabling LAN access.

## Acceptance criteria

Compatibility work is ready for routine use when:

- A new user can install the correct environment without editing source code.
- The application reports exactly which Python, R, and dependency versions it is using.
- A fresh installation is reproducible from a lock file.
- The setup process does not assume one user account, home directory, or R installation path.
- Supported and unverified operating systems and devices are clearly documented.
- Both applications pass their test suites on the declared production environment.
- Generated workbooks open correctly in the spreadsheet applications used by the lab.
- Web workflows work in the declared browsers and do not expose the local server unintentionally.
- Every production run records enough environment information to reproduce or explain its behavior.
