# Codex Deliverable — Portability Initiative, Phases 1–3

**Audience:** codex, as a reviewer/continuer of this work.
**Scope:** the cross-platform portability initiative only (Phases 1–3, all committed to `main`).
Not a restatement of the whole project — see `mouseley-kras-and-xol-pots-xol-overview.md` for that.
This document follows the same two-domain convention used throughout this session: a
System Debriefing section (intent, decisions, status — no code) followed by an Isolated Code
Artifacts section (the actual diffs, paths, commands, and test output).

Codex previously reviewed Phase 1 and Phase 2 in separate documents (`PHASE_1_PORTABILITY_FEEDBACK.md`,
`PHASE_2_PORTABILITY_FEEDBACK.md`, `PHASE_2_PORTABILITY_FEEDBACK_UPDATE.md`). This document
consolidates the cumulative state through the end of Phase 3 into one place, so codex does not have
to reconstruct it from three feedback threads plus a progress log.

---

## System Debriefing

### Why this initiative exists

Möuseley Kräs and Xol-Pots-Xol were both originally built and run on a single Mac. The user asked
for them to become runnable by other lab members, on other operating systems, without changing what
either tool does or loosening any of the existing safety guarantees (checksum-verified writes,
explicit two-portal boundary, no silent partial success). The user scoped this explicitly as a
staged initiative and approved each stage before it started:

- **Phase 1** — decide the goal is real portability (not just "runs on my Mac"), initialize git,
  scope Phase 1 narrowly.
- **Phase 2** — give each project its own virtual environment, lock dependencies with `pip-tools`,
  and *actually* test across Python 3.11–3.14 rather than just documenting intent.
- **Phase 3** — build Windows and Linux launchers equivalent to the existing macOS `.command` files,
  make the R-executable discovery logic platform-aware, and write cross-platform CLI documentation —
  while being explicit about what could and could not be verified from this session's environment.

### What changed and why, per phase

**Phase 1.** Git was initialized and an initial commit made of both projects' source, tests, and
docs. No code changes beyond that — this phase was scoping and version-control hygiene, not
implementation.

**Phase 2.** Each project got its own `.venv` (previously they shared one root environment, which
blurred the "standalone sibling" boundary Xol-Pots-Xol is supposed to have). Dependencies were
locked with `pip-tools`/`pip-compile` for both projects. This surfaced a real bug during setup: a
macOS `UF_HIDDEN` flag on `.venv` files interacts with a Python 3.14 `site.py` change that silently
skips hidden `.pth` files, which broke editable installs (`pip install -e .`) intermittently. That
was root-caused (not just patched around) and fixed with a `chflags -R nohidden` step folded into
the setup scripts, plus a standalone repair script (`scripts/fix_hidden_venv.sh`) for when it
recurs. Codex's Phase 2 review caught a second, more serious issue: the dependency lock files had
been generated using Python 3.14 as the resolving interpreter, which pinned a `numpy` version with
no wheel for Python 3.11 — meaning the "supports 3.11–3.14" claim was false for a fresh 3.11
install. This was verified independently (reproduced the failure) and fixed by regenerating both
lock files using Python 3.11 — the *oldest* supported version — as the resolver, then re-verified
installable across the full 3.11–3.14 matrix using Conda-managed test environments.

**Phase 3.** Windows (`.ps1`) and Linux (`.sh`) equivalents of the five existing macOS `.command`
launchers were written, and `config.py`'s R-executable discovery was made to branch on
`platform.system()` instead of assuming macOS Homebrew/CRAN install paths. Codex's and copilot's
combined Phase 3 scope instructions were followed exactly: preserve the macOS workflow unchanged,
keep `chflags`/`fix_hidden_venv.sh` macOS-only (there is no known equivalent bug on the other
platforms), do not broaden data access or touch the two-portal boundary, and — critically — do not
claim Windows or Linux are *supported* yet, only that launchers exist for them.

### Verification honesty — the most important thing for codex to know

This is the one point worth codex weighing most carefully, because it's easy to overstate from a
progress doc alone:

- **Linux launchers**: executed for real, but only via `bash` running on this macOS machine, which
  is a reasonable proxy for POSIX-shell correctness but is *not* a real Linux machine. Both setup
  scripts were run end-to-end with the actual test suites (88 + 34 tests passing), the run-launcher
  was exercised on its input-validation paths only (never against real lab data), and both web-app
  launchers were confirmed to start a real local Flask server (GET request returning 200, then
  killed within seconds).
- **Windows launchers**: written, but **never executed at all** — no `pwsh`/PowerShell interpreter
  was available in this session. They are explicitly labeled "IMPLEMENTED BUT NOT VERIFIED" in their
  own header comments and in the README.
- **Phase 4** (real Windows/Linux hardware or CI verification) has not started. Nothing in Phases
  1–3 should be read as claiming Windows or Linux work — only that the code exists and is believed
  correct by inspection and proxy-testing.

### Open decisions codex should weigh in on

1. The external R translation script (`Transnetyx_genotyping.R`) still has no version or Git-commit
   identity of its own — every run now records its SHA-256 checksum automatically in the run
   manifest, which detects *drift* but does not give the script a human-readable version number.
   Worth a recommendation either way.
2. When/whether to start Phase 4. This session's environment cannot execute PowerShell or run on
   real Linux hardware, so Phase 4 requires either a different environment or a different reviewer
   in the loop.

### Current status

All three phases are implemented, tested to the extent this environment allows, documented, and
committed to `main` (see commit list below). Working tree is clean. No lab data was read, modified,
or exposed at any point during this work — all pipeline-touching tests ran against fixtures or
scratch directories, never `runtime/` or `outputs/`.

---

## Isolated Code Artifacts

### Commits (chronological, `main`)

```
bb5b398 Initial commit: Möuseley Kräs and Xol-Pots-Xol source, tests, and docs      (Phase 1)
5864ec6 Phase 2 of portability initiative: separate venvs, dependency locks, fixed editable installs
3824991 Correct progress docs to reflect Phase 2 is now committed
1fdd68d Phase 3: cross-platform launchers implemented, NOT yet verified (Windows/Linux)
```

### Phase 2 — key files

```
.venv/                                 (root project-local, gitignored — NOT src/automouse/.venv/)
xol-pots-xol/.venv/                   (project-local, gitignored)
requirements.lock.txt                 (root; regenerated with Python 3.11 as resolver)
xol-pots-xol/requirements.lock.txt    (regenerated with Python 3.11 as resolver)
r_dependencies.lock.json              (R 4.5.2 / dplyr 1.2.1 / purrr 1.1.0 — verification record, not a full lock)
scripts/fix_hidden_venv.sh            (macOS-only: chflags -R nohidden on both .venv trees)
AutoMouse_Setup.command               (adds lock reconciliation + editable install + chflags step)
XolPotsXol_Setup.command              (new; mirrors AutoMouse_Setup.command for its own venv)
XolPotsXol_WebApp.command             (rewritten to call xol-pots-xol/.venv/bin/xolpotsxol-serve directly)
pyproject.toml                        (root; added pip-tools>=7.0 to dev extra)
```

### Phase 3 — key files

```
src/automouse/config.py
  _common_r_executable_locations() -> tuple[Path, ...]   # branches on platform.system()
  _resolve_r_executable(value, project_root) -> Path      # explicit config path always wins
  validate_config(...)                                    # platform-aware "R not found" message

launchers/linux/AutoMouse_Setup.sh
launchers/linux/AutoMouse_Run.sh
launchers/linux/AutoMouse_WebApp.sh
launchers/linux/XolPotsXol_Setup.sh
launchers/linux/XolPotsXol_WebApp.sh
  # ported from the .command originals; AppleScript file picker replaced with a
  # dependency-free numbered-list terminal picker; no chflags; bash-3.2-compatible
  # (tr '[:upper:]' '[:lower:]' instead of ${var,,})

launchers/windows/AutoMouse_Setup.ps1
launchers/windows/AutoMouse_Run.ps1
launchers/windows/AutoMouse_WebApp.ps1
launchers/windows/XolPotsXol_Setup.ps1
launchers/windows/XolPotsXol_WebApp.ps1
  # same logic in PowerShell; System.Windows.Forms.OpenFileDialog for multi-select;
  # header comment on every file: "IMPLEMENTED BUT NOT VERIFIED ... no PowerShell
  # interpreter was available to test it from this session."

src/automouse/app.py / models.py
  environment["translation_script_path"]   = str(config.r.translation_script)
  environment["translation_script_sha256"] = calculate_sha256(config.r.translation_script)
  # threaded into RunContext.to_summary()

tests/test_config.py
  class CrossPlatformRExecutableDiscoveryTests:
    test_macos_locations_are_absolute_and_named_rscript
    test_linux_locations_are_absolute_and_named_rscript
    test_windows_locations_end_in_rscript_exe
    test_resolve_r_executable_prefers_an_already_correct_configured_path
    test_resolve_r_executable_falls_back_to_path_on_every_platform
```

### Verification commands and results actually run this session

```
$ python -m unittest discover tests            # Möuseley Kräs
Ran 88 tests ... OK

$ python -m unittest discover xol-pots-xol/tests  # Xol-Pots-Xol
Ran 34 tests ... OK

$ bash -n launchers/linux/*.sh                 # syntax check, all 5 files
(clean)

$ bash launchers/linux/AutoMouse_Setup.sh      # full run, real dependency install + tests
... Ran 88 tests ... OK

$ bash launchers/linux/XolPotsXol_Setup.sh
... Ran 34 tests ... OK

$ bash launchers/linux/AutoMouse_WebApp.sh &   # background, curl localhost, then kill
HTTP/1.1 200 OK
$ kill %1

$ bash launchers/linux/XolPotsXol_WebApp.sh &  # same pattern
HTTP/1.1 200 OK
$ kill %1

# Windows scripts: NOT executed — no pwsh available in this session.

$ git status --short
(clean)

$ git log --oneline
1fdd68d 3824991 5864ec6 bb5b398
```

### Not touched, by design

```
scripts/fix_hidden_venv.sh    — remains macOS-only (chflags has no Linux/Windows equivalent bug)
Two-portal web/CLI boundary    — unchanged
config/*.yaml schema           — unchanged (only resolution logic in config.py changed)
runtime/, outputs/             — never read or written by any Phase 1-3 test or launcher run
```

---

## Addendum — response to the 2026-08-28 codex/copilot re-review

Codex's `REVIEW_codex_deliverable_portability_phases_1-3_again.md` and copilot's follow-up both
correctly flagged that this deliverable's "fixed and verified" language was stale relative to the
actual checked-out state at review time. Investigated and resolved the same day:

1. **Hidden-`.pth` regression reproduced and re-fixed (High).** Both `.venv/lib/python3.14/site-packages/__editable__.automouse-0.3.1.pth`
   and the xolpotsxol equivalents were re-hidden (UF_HIDDEN) at review time, exactly as codex found
   — `./.venv/bin/automouse --help` and `./xol-pots-xol/.venv/bin/xolpotsxol --help` both failed
   with `ModuleNotFoundError` before the fix. Root cause of *this* recurrence: `scripts/fix_hidden_venv.sh`
   has a `#!/bin/zsh` shebang using zsh-only parameter expansion (`${0:A:h:h}`); invoking it with
   `bash scripts/fix_hidden_venv.sh` instead of `zsh scripts/fix_hidden_venv.sh` (or executing it
   directly as `./scripts/fix_hidden_venv.sh`) fails with `A: unbound variable` and silently does
   nothing useful. Re-run correctly, it cleared both flags immediately; both direct commands then
   passed. A permanent regression test was added so this can never again go unnoticed silently:
   `tests/test_editable_install_health.py` and `xol-pots-xol/tests/test_editable_install_health.py`,
   each skipped on non-macOS and asserting no `__editable__.*.pth` file has `UF_HIDDEN` set.
2. **Windows candidate-parsing bug (Medium) — fixed by inspection, still not execution-verified.**
   `launchers/windows/AutoMouse_Setup.ps1` and `XolPotsXol_Setup.ps1` both guarded the `$parts[1..($parts.Length - 1)]`
   slice with a length check (`if ($parts.Length -gt 1) { ... } else { $exeArgs = @() }`), so a bare
   `py` or `python` candidate no longer produces a malformed range. No PowerShell interpreter has
   been available in any session so far to execute this fix — it remains implemented-and-inspected,
   not run.
3. **`.venv` path corrected (Medium).** The Phase 2 file list above previously said
   `src/automouse/.venv/`; the root project's environment is actually at `.venv/` (repo root). Fixed
   above.
4. **Working-tree claim (Low).** The original "working tree is clean" statement described the
   checkout immediately after commit `1fdd68d`, before this deliverable and its sibling
   `COPILOT_PROJECT_OVERVIEW.md` existed as untracked files. It was not describing the state at
   review time. Read it as "clean at commit `1fdd68d`," not as a live claim.

Re-verified after all fixes, via each project's own venv directly (the same paths the launchers use,
not `PYTHONPATH`):

```
./.venv/bin/automouse --help                          -> OK
./.venv/bin/python -m unittest discover -s tests       -> Ran 89 tests ... OK   (88 + 1 new regression test)
./xol-pots-xol/.venv/bin/xolpotsxol --help             -> OK
./xol-pots-xol/.venv/bin/python -m unittest discover -s xol-pots-xol/tests -> Ran 35 tests ... OK (34 + 1 new)
```

Phase 3's overall status is unchanged by this review: Linux remains proxy-tested via bash-on-macOS,
Windows remains implemented-but-unexecuted, and Phase 4 has not started. What changed is that the
macOS editable-install path — which every phase's verification claims quietly depend on — is now
re-confirmed working today, not just historically, and has a regression test so this doesn't have
to be re-discovered by hand a sixth time.
