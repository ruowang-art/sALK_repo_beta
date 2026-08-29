# Claude Progress Report: Phase 4 CI — Real Windows/Linux Runs Now Green

**Date:** 2026-08-28
**Audience:** codex and copilot, to pick up review/context from here.
**Repo:** `github.com/ruowang-art/sALK_repo_beta` (public), workflow
`.github/workflows/phase4-portability.yml` (manual `workflow_dispatch` only).
**Commits this covers:** `509441b`, `c0b315a` (both on `main`, both pushed).

---

## System Debriefing

Phase 4's job was to verify, for the first time on real (not proxy-tested) Windows and Linux
machines, that both projects' setup/launcher scripts and test suites actually work — not just that
the logic looks portable. The workflow runs two jobs, each as a 2×2 or 2×1 matrix:

- `setup-and-tests`: `{ubuntu-latest, windows-latest} × {Python 3.11, Python 3.14}` — runs each
  project's setup script, its test suite, and a web-launcher smoke test (start the Flask app,
  poll it, kill it).
- `bare-command-selection`: `{ubuntu-latest, windows-latest}` — deliberately hides every Python
  binary except a bare `python3`/`python`/`py`, to catch the exact class of bug fixed in `012d454`.

The first real run failed all 6 jobs. Getting to green took two rounds of genuine diagnosis, both
done through the GitHub CLI (`gh`) reading real job logs directly — not through GitHub's web
Annotations panel (which only gives exit codes, not command output) and not through a bulk
log-archive upload (which arrived at Claude stripped of all real content by an intermediate
redaction step, leaving only file-size/line-count metadata for every failing step). `gh` was
installed locally (no `sudo`, portable binary in `~/.local/bin`) and authenticated interactively by
the user, then used for `gh run view <id> --log-failed` and `gh workflow run` to close the loop
without any further manual log-pasting.

### Round 1 — three genuine, first-time-exposed bugs

None of these are regressions from recent work; all three were invisible until code actually ran on
a real non-macOS machine for the first time.

1. **`tests/test_config.py` — `CrossPlatformRExecutableDiscoveryTests`.** Two tests asserted
   `.is_absolute()` on hardcoded POSIX candidate paths (e.g. `/usr/bin/Rscript`) returned by
   `_common_r_executable_locations()`. `pathlib.Path()` is host-OS-dependent — on a real Windows
   runner it constructs a `WindowsPath`, and `WindowsPath('/usr/bin/Rscript').is_absolute()` is
   `False` (no drive letter), regardless of the test's `patch("automouse.config.platform.system", ...)`
   mock, since that mock only changes which *branch* of `_common_r_executable_locations()` runs, not
   which concrete `pathlib` class `Path()` resolves to. Failed on all 3 Windows jobs.

2. **`xol-pots-xol/tests/test_webapp.py::test_consolidate_then_download`.** Deferred closing a
   downloaded file's response via `self.addCleanup(download_response.close)`, which runs *after* the
   test method returns — but the enclosing `tempfile.TemporaryDirectory()` tries to delete that same
   directory when its `with` block exits, which happens *before* the test method returns. POSIX
   allows deleting a directory with an open file handle inside it; Windows raises
   `PermissionError: [WinError 32]`. Fixed by closing the response inside a `try/finally` before the
   `with` block ends, instead of deferring it. Failed only on the Windows `bare-command-selection` job
   (the only job that runs this test *and* Windows).

3. **Ubuntu `bare-command-selection` job's own self-check caught a real gap.** The job builds a PATH
   with a shim directory first (containing only `python3`/`python` symlinked to the real interpreter),
   followed by the standard system directories — but `ubuntu-latest`'s `noble` image ships its own
   `/usr/bin/python3.12` (the OS's system Python), so including `/usr/bin` on PATH re-exposed exactly
   the versioned sibling this job exists to hide. Fixed by symlinking every *other* entry from those
   system directories into the shim (excluding `python`/`python2*`/`python3.*` names) instead of
   adding the raw directories to PATH — coreutils stay reachable, no versioned Python does.

Committed as `509441b`. Re-running exposed two *more* things — one a mistake in this round's own fix,
one a second real bug that only became visible once the first failure's error message was legible.

### Round 2 — a self-correction and a second real bug

4. **The Round 1 fix for finding #1 was itself wrong.** `PurePosixPath(str(location)).is_absolute()`
   still failed on the real Windows runner: `str()` on a `WindowsPath` renders backslashes, and
   `PurePosixPath` treats backslash as an ordinary character, not a separator — so the whole string
   became a single relative path component. Fixed by calling `.as_posix()` first (which normalizes to
   forward slashes on every platform) before wrapping in `PurePosixPath`.

5. **The `setup-and-tests` web-launcher smoke test failed for an unrelated reason**, only visible
   because Round 1's earlier `curl`/`set -e` fix (from the session before this one) turned a bare
   `exit code 7` into an actual stderr message: `Möuseley Kräs error: Unable to read configuration
   .../config/pipeline_run.yaml: [Errno 2] No such file or directory`. Root cause: `automouse serve`
   always calls `load_config()` first, which requires `config/pipeline_run.yaml` and its
   `r.executable`/`r.translation_script`/`r.wrapper_script` to resolve to real files — but the real
   config and the real R translation script are both deliberately excluded from git (see
   `.gitignore` and `CLAUDE.md`'s data-safety rules), since they hold real local paths and, for the
   translation script, live outside this repo entirely. A fresh checkout — exactly what CI is — has
   neither. Fixed by adding a step that writes a throwaway `config/pipeline_run.yaml` before the
   smoke test, reusing the one R script this repo does ship
   (`scripts/transnetyx_cli_wrapper.R`) for both `r.translation_script` and `r.wrapper_script` (its
   content is irrelevant — the smoke test never triggers a real translation run). `inventory` and
   `cage_card` are left out of this throwaway config entirely: both are optional sections, and a
   `grep` of `src/automouse/web/*.py` plus a real local run against this exact config confirmed the
   web app's index route never touches either when they're `None`.

Committed as `c0b315a`. Re-running produced 6/6 green.

### Verification performed before each commit

- macOS baseline (`zsh scripts/fix_hidden_venv.sh`, both `.pth` files' `UF_HIDDEN` flags, both direct
  commands, both test suites) re-verified clean immediately before each commit — this Mac has a
  recurring, unrelated bug where the flag gets silently re-set mid-session.
- Round 2's `.as_posix()` fix and throwaway-config fix were both verified locally against the real
  `src/automouse/config.py`/`src/automouse/cli.py` code before pushing (a temp-file `load_config()`
  call, and an actual `automouse serve` + `curl` round-trip) rather than trusting the reasoning alone.
- Final state: `PYTHONPATH=src .venv/bin/python -m unittest discover -s tests` → 107/107 OK;
  same for `xol-pots-xol` → 35/35 OK; both on macOS. Real Windows/Linux confirmed via the CI run
  itself, not a proxy.

### Final result

Run [`33237052498`](https://github.com/ruowang-art/sALK_repo_beta/actions/runs/33237052498): all 6
jobs green —

| Job | Result |
|---|---|
| `ubuntu-latest` / Python 3.11 | ✓ |
| `ubuntu-latest` / Python 3.14 | ✓ |
| `windows-latest` / Python 3.11 | ✓ |
| `windows-latest` / Python 3.14 | ✓ |
| `ubuntu-latest` / bare `python3`/`python` only | ✓ |
| `windows-latest` / bare `python`/`py` only | ✓ |

### Scope and limitations (added after codex's review — see `20260828_codex_review_of_phase4_ci_completion_report.md`
and `20260828_claude_response_to_codex_phase4_review.md` for the full exchange)

Phase 4's CI run proves: both projects' setup scripts complete, both test suites pass, both Flask web
apps bind a port and answer a request, and the bare-`python`/`py` scenario passes — all on real
GitHub-hosted Windows and Linux runner *images*. It does **not** prove behavior on any specific lab
member's actual machine/OS build/security policy/filesystem, and it does **not** exercise the main
interactive data-processing launchers (`AutoMouse_Run.sh`/`.ps1`, `XolPotsXol_Run.sh`/`.ps1`) —
only the `serve` web-launcher path is smoke-tested, which proves the process starts and answers
`GET /`, not a full run through the browser UI. R is intentionally left floating
(`r-version: "release"`, R 4.6.1 as of this run, confirmed from the real job logs) rather than pinned
to the locally-verified 4.5.2/4.5.3 — this matches this project's already-documented stance
(`README.md`: `r_dependencies.lock.json` is "a verification record, not an installable/managed
environment") rather than a new decision made for this report.

Real Windows and real Linux CI (setup + web-launcher path) are now both verified — the gap `20260828_claude_phase4_readiness_response.md`
identified as still open ("Windows verified: Not yet verified", "Real Linux verified: Not yet
verified") is closed as of this run.

### Not touched by this work (still open, unrelated to Phase 4)

- A real end-to-end Sheets write-back test against the corrected spreadsheet.
- Whether/how to give the external R translation script its own version/commit identity.
- Phase 5 (helping other lab members run this on their own machines/credentials) — not started.

---

## Isolated Code Artifacts

```
$ gh run view 33237052498 --repo ruowang-art/sALK_repo_beta
✓ main Phase 4 — Windows/Linux portability verification · 33237052498
✓ ubuntu-latest / Python 3.11        in 2m31s
✓ ubuntu-latest / Python 3.14        in 2m44s
✓ ubuntu-latest / bare "python"/"py" only  in 2m55s
✓ windows-latest / Python 3.11       in 1m46s
✓ windows-latest / Python 3.14       in 1m46s
✓ windows-latest / bare "python"/"py" only in 1m34s
```

**Commit `509441b`** — `tests/test_config.py`, `xol-pots-xol/tests/test_webapp.py`,
`.github/workflows/phase4-portability.yml` (Ubuntu shim rewrite).

**Commit `c0b315a`** — `tests/test_config.py` (`.as_posix()` correction),
`.github/workflows/phase4-portability.yml` (throwaway-config prep steps, Linux + Windows).

Key diff shape, `tests/test_config.py`:
```python
# before (fails on a real Windows runner, both attempts):
self.assertTrue(location.is_absolute())
self.assertTrue(PurePosixPath(str(location)).is_absolute())  # Round 1 — still wrong

# after (Round 2 — correct on every host):
self.assertTrue(PurePosixPath(location.as_posix()).is_absolute())
```

Key addition, `.github/workflows/phase4-portability.yml` (Linux; Windows is the `pwsh`/here-string
equivalent):
```yaml
- name: Prepare a throwaway config for the web launcher smoke test (Linux)
  if: runner.os == 'Linux'
  run: |
    cat > config/pipeline_run.yaml <<'EOF'
    {
      "r": {
        "executable": "Rscript",
        "translation_script": "scripts/transnetyx_cli_wrapper.R",
        "wrapper_script": "scripts/transnetyx_cli_wrapper.R"
      }
    }
    EOF
```

```
$ git log --oneline -3
c0b315a Fix test_config.py's as_posix() bug and give the web-launcher smoke test a real config
509441b Fix Phase 4 CI failures: Windows path semantics, xol-pots-xol file lock, Ubuntu bare-python shim
d2eec46 Add Sheets write-back and Plate ID/Order Date to the litter-entry portal
```

**Local verification baseline (macOS), re-run immediately before `c0b315a`:**
```
$ zsh scripts/fix_hidden_venv.sh
Cleared the hidden flag on: .venv
Cleared the hidden flag on: xol-pots-xol/.venv

$ .venv/bin/automouse --help                                                   -> runs
$ xol-pots-xol/.venv/bin/xolpotsxol --help                                     -> runs
$ PYTHONPATH=src .venv/bin/python -m unittest discover -s tests                -> Ran 107 tests ... OK
$ PYTHONPATH=src xol-pots-xol/.venv/bin/python -m unittest discover -s tests   -> Ran 35 tests ... OK
```
