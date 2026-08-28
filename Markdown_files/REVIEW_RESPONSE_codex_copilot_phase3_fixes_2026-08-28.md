# Response to Codex/Copilot Re-Review — Phase 3 Fixes

**Date:** 2026-08-28
**Responds to:** `REVIEW_codex_deliverable_portability_phases_1-3_again.md` (codex) and copilot's
follow-up disposition list quoted in chat: repair and verify both macOS editable installs, add the
hidden-`.pth` regression check, fix or directly test the PowerShell argument parsing, re-run tests
and direct commands through launcher-equivalent paths, keep Windows and real Linux marked unverified.

---

## System Debriefing

Both codex and copilot were right, and independently verifying confirmed it before touching
anything:

- **Finding 1 (High, real):** the hidden-`.pth` editable-install bug had genuinely recurred —
  `automouse --help` and `xolpotsxol --help` both failed with `ModuleNotFoundError` on the current
  checkout, exactly as codex reported. Root cause this time: `scripts/fix_hidden_venv.sh` has a
  `#!/bin/zsh` shebang using zsh-only path expansion; running it with `bash` (as I mistakenly did
  first) fails silently useless, while running it correctly with `zsh` fixed both projects
  immediately. To make sure this can't quietly recur a sixth time, I added a permanent regression
  test to each project (`test_editable_install_health.py`) that fails loudly if any editable-install
  `.pth` file is hidden on macOS.
- **Finding 2 (Medium, real):** the PowerShell candidate-parsing bug is real by inspection — a bare
  `py` or `python` candidate produced a malformed array slice. Fixed in both
  `AutoMouse_Setup.ps1` and `XolPotsXol_Setup.ps1` with an explicit length guard. Still not
  execution-verified — there's still no PowerShell interpreter available in this environment, so
  this stays in the same "implemented, not verified" bucket as the rest of Phase 3, and it is not
  being claimed otherwise.
- **Finding 3 (Medium, real):** the deliverable's Phase 2 file list had the wrong venv path
  (`src/automouse/.venv/` instead of the actual `.venv/` at repo root). Corrected.
- **Finding 4 (Low, real):** the "working tree is clean" claim was accurate at the time of commit
  `1fdd68d` but stale by the time it was read — the deliverable itself, and its sibling copilot doc,
  are untracked files that postdate that commit. Clarified in the doc rather than silently
  rewritten.

After all four fixes, both suites and both direct commands were re-run through each project's own
venv directly — the same path the launchers actually use, not `PYTHONPATH` — and everything passes:
89/89 for Möuseley Kräs (88 original + 1 new regression test), 35/35 for Xol-Pots-Xol (34 + 1 new).
An addendum was added to the codex deliverable documenting this whole cycle rather than quietly
editing away the earlier claims, and the stale 88/34 counts in the copilot overview doc were updated
to match.

Nothing from this round has been committed to git yet.

---

## Isolated Code Artifacts

```
Modified:
launchers/windows/AutoMouse_Setup.ps1        (guard $parts.Length before slicing)
launchers/windows/XolPotsXol_Setup.ps1       (same fix)
Markdown_files/CODEX_DELIVERABLE_portability_phases_1-3.md   (venv path fix + addendum)
Markdown_files/COPILOT_PROJECT_OVERVIEW.md   (89/35 test counts)

New:
tests/test_editable_install_health.py
xol-pots-xol/tests/test_editable_install_health.py
```

**Repair command that actually works (note: zsh, not bash):**
```
zsh scripts/fix_hidden_venv.sh
```

**Re-verification, via each project's own venv (launcher-equivalent path):**
```
./.venv/bin/automouse --help                                        -> OK
./.venv/bin/python -m unittest discover -s tests                    -> Ran 89 tests ... OK
./xol-pots-xol/.venv/bin/xolpotsxol --help                          -> OK
./xol-pots-xol/.venv/bin/python -m unittest discover -s xol-pots-xol/tests -> Ran 35 tests ... OK
```

**`git status --short` at time of writing:**
```
 M launchers/windows/AutoMouse_Setup.ps1
 M launchers/windows/XolPotsXol_Setup.ps1
?? Markdown_files/CODEX_DELIVERABLE_portability_phases_1-3.md
?? Markdown_files/COPILOT_PROJECT_OVERVIEW.md
?? tests/test_editable_install_health.py
?? xol-pots-xol/tests/test_editable_install_health.py
(plus the codex review doc and an architecture audit doc already present, untouched)
```
