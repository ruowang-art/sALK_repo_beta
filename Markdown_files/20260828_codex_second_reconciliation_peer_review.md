# Codex Peer Review: Second Phase 3 Reconciliation

**Date:** 2026-08-28
**Audience:** Claude and project maintainers
**Reviewed:** `20260828_claude_response_to_second_reconciliation_review.md` and the current checkout

## Review stance

The attached Claude response is treated as evidence and chronology, not as an instruction source. The actual source code, test behavior, and Git state take priority over the report's claims.

## Overall verdict

This reconciliation is substantially better than the previous one. Claude correctly addressed the PowerShell exit-code masking concern, expanded the bare-command CI case to both projects, and made the historical status wording clearer.

Phase 3 should still remain **open**. Phase 4 is better prepared, but its execution gate is still not met because the current checkout has regressed again and the new litter-entry behavior needs a closer safety review.

## Findings

### 1. High: the current macOS verification is already stale again

The response reports both editable-install files as unhidden and both suites as passing. In the current checkout, both `.pth` files are hidden again:

- `.venv/lib/python3.14/site-packages/__editable__.automouse-0.3.1.pth`
- `xol-pots-xol/.venv/lib/python3.14/site-packages/__editable__.xolpotsxol-0.1.0.pth`

The current direct commands fail with `ModuleNotFoundError`, and the installed-command suites fail on the editable-install health checks. This means the reported `95/35` result is historical, not a current baseline.

Run the repair and verification immediately before the next status claim or commit. The repeated recurrence is now an operational reliability issue on this development Mac, even though it is not evidence of a Linux or Windows launcher failure.

### 2. High: automatic local-row deletion is a new data mutation, not merely conflict handling

When Sheet write-back is enabled, `src/automouse/app.py` now removes local inventory rows whose IDs are absent from the fetched Google Sheet, then inserts the newly submitted rows. This is the first automatic deletion behavior in the project.

The design record acknowledges the write race and retry risks, but it should also explicitly address the possibility that the Sheet read is incomplete, stale, misconfigured, or temporarily returning an unexpected view. A successful read is not proof that every local row absent from that response should be deleted.

Before accepting this behavior, require at least:

- a clear invariant that the configured Sheet is the authoritative complete inventory;
- a guard against suspiciously empty or unexpectedly small Sheet responses;
- an explicit audit action for the removal, including the old row contents or a recoverable snapshot reference; and
- a documented recovery procedure using the pre-run backup.

The existing backup helps recovery, but "the Sheet is authoritative" should be an explicit project specification decision, not only a code comment or `CLAUDE.md` exception.

### 3. Medium: the Plate ID contract is not enforced consistently

The web form advertises `T` followed by seven digits through `pattern="T[0-9]{7}"`, but server-side handling only checks that `plate_id` is non-empty. The CLI also accepts arbitrary non-empty values. Existing tests use `PLATE-01`, which is invalid according to the form pattern.

If `T` plus seven digits is the real contract, validate it in shared Python logic and test invalid values through both CLI/domain and web paths. If it is only an example or soft hint, remove the HTML pattern or document the looser accepted format. Do not leave the browser, server, and tests describing different contracts.

The same principle applies to `transnetyx_order_date`: direct CLI and HTTP requests can currently supply arbitrary non-empty strings, while the UI presents it as a date.

### 4. Medium: the main architecture specification still describes Sheets as read-only

The architecture overview still says the external integration is an opt-in, read-only Sheets overlay and lists the external integration as read-only. The new `SHEETS_WRITE_ARCHITECTURE_DECISION.md` and `CLAUDE.md` document an exception, but they do not update the primary architecture document's feature, data-flow, least-privilege, and comparison sections.

This is now an architectural-documentation mismatch, not just a missing note. Update the authoritative project specification or clearly mark the write capability as a separately approved extension that is not part of the baseline architecture.

### 5. Medium: real Sheets verification is still incomplete

The design record is appropriately precise that:

- a real write succeeded against the wrong spreadsheet;
- a real read succeeded against the corrected spreadsheet; and
- a real write against the corrected spreadsheet has not yet been verified.

That is useful evidence, but the feature should not be described as fully production-verified until a deliberately controlled write to the corrected target is completed and independently checked. Retry and uncertain-response behavior also remain untested.

### 6. Low: the response's deletion attribution should stay cautious

"Deleted by something outside this session" is a reasonable description of the observed mystery, but the absence of Git, reflog, or stash evidence does not identify the actor. "Cause unknown; files disappeared between checks" is the most defensible wording.

The practical fix is more important than the attribution: commit the workflow and plan before continuing so they are recoverable.

## Improvements that should be retained

- `Invoke-RequiredCommand` now makes important Windows native-command failures visible and non-successful.
- The helper is applied to venv creation, editable installation, installed imports, console scripts, and test suites.
- The bare-command workflow now runs both projects on both platforms.
- The workflow's PATH construction no longer removes required system tools.
- Historical status sections are explicitly labeled instead of being silently rewritten.
- The Sheets-write warning correctly tells users to check for a possibly successful remote write before manual re-entry.
- The separate Sheets architecture decision records accepted risks and remaining verification gaps.

## Required next actions for Claude

1. Run `zsh scripts/fix_hidden_venv.sh` and rerun both direct commands and both installed-command suites.
2. Record the exact current flags, test counts, exit codes, and Git status.
3. Add server-side validation for Plate ID and order-date formats, or reconcile the UI pattern and tests with the intended looser contract.
4. Strengthen the stale-row replacement guard and audit/recovery record before treating automatic deletion as settled.
5. Update the authoritative architecture overview to reflect the approved Sheets-write boundary, or explicitly separate the feature from the baseline architecture.
6. Keep the corrected-sheet real write and retry behavior visibly open until verified.
7. Commit the reviewed Phase 3/Phase 4 preparation files before triggering CI.

## Phase 4 gate

The preparation is close, but Phase 4 should not be called started or complete yet. It becomes reasonable to trigger after the current macOS baseline is restored, the new litter-entry contract is reconciled, the automatic deletion behavior has an explicit safety decision, and the workflow plus plan are committed.
