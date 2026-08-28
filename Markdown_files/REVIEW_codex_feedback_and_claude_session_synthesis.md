# Codex Feedback and Claude Session Synthesis

## Purpose and scope

This is an independent review for Claude and Codex to consume. It synthesizes
`REVIEW_full_session_report_feedback.md` and
`REPORT_full_session_progress_and_methodology.md`; it is not a replacement for
either source and does not direct unrelated implementation work.

The review covers release evidence, reproducibility, portability boundaries,
data safety, and documentation quality for Möuseley Kräs and Xol-Pots-Xol.

**Verified facts** below are claims supported by the source documents.
**Recommendations** are proposed follow-up work. **Open decisions** require an
explicit product or release choice.

## Executive assessment

**Verified fact:** The session produced a credible, safety-conscious macOS
baseline. Both projects have separate environments and dependency lock files;
83/83 Möuseley Kräs tests and 34/34 Xol-Pots-Xol tests reportedly pass on
Python 3.11, 3.12, 3.13, and 3.14. The report also says real
editable-installed commands were smoke-tested, not only source-path tests.

**Assessment:** The work is close to a macOS-focused release candidate, but the
historical report should become more operational before serving as the primary
handoff document. The largest technical reproducibility gap is the identity of
the external R translation script. The largest scope risk is confusing the
verified macOS/Apple Silicon boundary with broad portability.

## Agreements and strengths

- The two-portal boundary is explicit: Cage Card Production remains a combined
  translate/match/update/generate flow, while Mouse Inventory Update registers
  new litters.
- Verification was empirical: source tests, installed-command smoke tests,
  lock-file installation, and root-cause reproduction were distinguished.
- The editable-install failure was correctly traced to macOS `UF_HIDDEN` flags
  interacting with Python 3.14 `.pth` handling, rather than treated as a
  fundamental packaging defect.
- Data-safety protections are unusually clear: production inventory, raw
  Transnetyx exports, templates, credentials, and runtime outputs are
  protected; inventory writes use backup-verified copy-on-write; conflicts and
  unknown values remain explicit exceptions.
- The session records failed claims and regressions instead of presenting only
  successful outcomes.
- Deferred work was named rather than silently implemented, including the
  inventory propose/approve/promote workflow, new CLI subcommands, schema
  versioning, property-based testing, and portability phases.

## Prioritized risks and gaps

1. **External R script identity — highest priority.** The script is outside the
   repository and is not identified by version, Git commit, release, or
   checksum. Matching R and package versions alone cannot prove identical
   translation behavior.
2. **Release provenance is incomplete.** Python 3.11–3.14 testing is valuable,
   but a release record should include exact patch versions, OS/CPU, lock-file
   checksum, commands, import mode, and whether the real R translator ran.
   Source tests and installed-command verification must remain separate claims.
3. **The R lock record is easy to overstate.** `r_dependencies.lock.json` is a
   verified version record, not a full, installable, environment-recreating
   lock such as a managed `renv` environment.
4. **Platform reproducibility is unproven.** Version-pinned Python locks may
   still resolve differently across OS, architecture, and Python versions.
   Wheel hashes, markers, platform-specific locks, and a supported-platform
   policy remain unresolved.
5. **Support-boundary visibility.** The currently verified boundary is macOS,
   Apple Silicon in the verified environment, Python 3.11–3.14 for the tested
   workflows, and local CLI/browser use. Windows, Linux, Intel Macs, mobile
   devices, and alternative spreadsheet applications are unverified.
6. **macOS-specific repair can be misread.** `scripts/fix_hidden_venv.sh` and
   `chflags` address the observed macOS hidden-file condition; they are not a
   Windows/Linux portability mechanism.
7. **Deferred scope can be mistaken for missing implementation.** The report
   should distinguish intentionally deferred phases and design decisions from
   release blockers.

## Concrete recommendations

### Immediate

- Add a prominent “Current support boundary” notice near the beginning of the
  report.
- Add a release-readiness table and a short evidence/provenance checklist.
- Preserve the wording that `r_dependencies.lock.json` is a verification
  record, not a full lock.
- Record the external R script’s source and exact identity in every translation
  run manifest, using a SHA-256, Git/versioned release, or another documented
  exact identifier.
- Keep the macOS hidden-flag repair explicitly labeled macOS-only.
- Reconfirm that documentation and verification never use or overwrite
  protected laboratory data.

### Pre-release

- Re-run the source test suites and installed-command smoke tests from clean
  environments, reporting them as separate evidence.
- Record exact Python patch versions, OS and architecture, dependency lock-file
  checksums, installation/test commands, and whether real R-dependent behavior
  was exercised.
- Verify the lock files on every claimed Python version and document the
  Python-3.11 resolution choice and its limits.
- Decide whether the release policy is macOS-only or whether another platform
  must be supported before release.
- Confirm that setup failures surface clearly and do not silently fall back;
  retain the data-safety and artifact-preservation guarantees.

### Later portability work

- Execute the deferred Phase 3 launcher/setup work for Windows and Linux.
- Execute Phase 4 cross-platform verification, preferably with CI, including
  supported OS/architecture/Python combinations.
- Evaluate platform-specific lock files, Python-version markers, wheel hashes,
  and a documented supported-platform installation policy.
- Revisit portability-sensitive assumptions only after the support matrix is
  chosen; do not generalize the macOS repair script.

## Release-readiness table

| Area | Status | Evidence or limitation | Release implication |
|---|---|---|---|
| Core workflows | Implemented | Two portals and safety boundaries documented | Suitable for scoped review |
| Python source tests | Independently verified | 83/83 and 34/34 on Python 3.11–3.14, per report | Record exact provenance |
| Installed commands | Independently verified | Real editable-installed command smoke tests reported | Keep distinct from source tests |
| Python dependencies | Implemented/verified for current scope | Python-3.11-resolved `requirements.lock.txt` files; cross-platform coverage unknown | Accept only with stated boundary |
| R dependencies | Version-recorded | `r_dependencies.lock.json` is not a full lock | Do not claim environment recreation |
| R translation script | Known gap | External script has no version/checksum identity | Required before reproducible release |
| macOS setup | Independently verified | Apple Silicon environment; hidden-flag repair addressed | Keep repair macOS-specific |
| Data safety | Implemented/verified by report | Protected inputs, backups, copy-on-write, explicit conflicts | Preserve as release gate |
| Windows/Linux | Deferred | Phase 3 not started | Not supported unless separately verified |
| Cross-platform CI | Deferred | Phase 4 not started | Do not promise portability yet |

## Suggested report edits

In `REPORT_full_session_progress_and_methodology.md`:

1. Add the support-boundary notice before the chronological narrative.
2. Add a compact table based on the readiness table above.
3. Replace any wording that could call `r_dependencies.lock.json` a full lock.
4. Add exact test/install commands, patch versions, OS/architecture, lock
   checksums, source-vs-installed mode, and real-translator status.
5. Add an explicit external R script identity field to the release checklist.
6. Keep Phase 3/4, Windows/Linux support, and other deferred decisions visible
   in the opening summary and final status.

These edits should improve handoff value without rewriting the accurate
historical narrative. `REVIEW_full_session_report_feedback.md` already
contains a closely aligned table and checklist that can be used as a
cross-reference.

## Final decision-oriented checklist

- [ ] **Verified:** Is the release explicitly bounded to macOS and the verified
  Apple Silicon environment, with Python 3.11–3.14 stated?
- [ ] **Verified:** Are source-path tests and installed-command verification
  reported separately, with exact commands and provenance?
- [ ] **Decision:** Is the external R translation script identified by an exact,
  recorded version or checksum before release?
- [ ] **Verified:** Is `r_dependencies.lock.json` described as a version record,
  not a full lock?
- [ ] **Decision:** Which OS/architecture/Python combinations are actually
  supported, and which remain deferred to Phases 3–4?
- [ ] **Verified:** Are platform-specific lock limitations and the macOS-only
  hidden-flag repair clearly documented?
- [ ] **Verified:** Are production inputs, credentials, templates, and prior
  artifacts protected by the stated data-safety rules?
- [ ] **Decision:** Are the intentionally deferred inventory workflow,
  subcommands, schema versioning, and property-based testing release blockers
  or later work?

