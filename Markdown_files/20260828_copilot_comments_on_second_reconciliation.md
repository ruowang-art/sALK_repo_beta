# Copilot Comments on the Second Reconciliation

## Overall assessment

Claude addressed several prior concerns correctly:

- Windows native-command failure handling now uses an explicit helper.
- The bare-command CI scenario covers both projects.
- Historical progress sections are labeled more clearly.
- Sheets-write risks remain separately documented.

However, Phase 3 should remain open and Phase 4 should remain prepared but not
executed. The current checkout does not yet provide a stable entry baseline.

## Highest-priority next steps

### 1. Reproduce the macOS baseline immediately before any status claim

Run:

```zsh
zsh scripts/fix_hidden_venv.sh
```

Then verify both editable-install files, both direct commands, and both
installed-environment test suites in the same checkout. Record exact flags,
exit codes, and test counts. Earlier `95/35` results are historical unless
reproduced after the final repair.

The repeated hidden-`.pth` recurrence is now an operational reliability issue
on this Mac. It is not evidence of a Windows or Linux defect, but it prevents
the macOS baseline from being treated as stable.

### 2. Treat automatic stale-row deletion as a separate safety gate

The Sheets-write path now removes local inventory rows that are absent from the
fetched Sheet before adding replacement litter rows. This is a real data
mutation, not ordinary conflict handling.

Before accepting it, require:

- an explicit decision that the configured Sheet is authoritative and complete;
- a guard against empty, partial, stale, or unexpectedly small Sheet responses;
- an audit action containing the removed row or a recoverable snapshot reference;
- a documented recovery procedure using the pre-run backup;
- tests for incomplete fetches and deletion failure paths.

Keep the feature disabled by default until this decision and safety behavior are
accepted.

### 3. Reconcile Plate ID and order-date contracts

The browser pattern for Plate ID and the server/CLI validation must describe the
same accepted format. The same applies to `transnetyx_order_date`: a calendar
date in the UI should not become an arbitrary non-empty string through direct
CLI or HTTP input.

Choose one contract, enforce it in shared Python logic, and test both domain/CLI
and web paths. Do not leave the form, server, and tests inconsistent.

### 4. Keep architecture documentation truthful

The primary architecture document still describes Sheets integration as
read-only. Either:

- update the authoritative architecture to include the approved write
  extension; or
- explicitly state that Sheets-write is a separate, non-baseline feature.

Do not rely only on a supplemental decision record or instruction-file
exception.

### 5. Preserve cautious verification wording

Continue distinguishing:

- implemented;
- inspected;
- proxy-tested;
- macOS verified in the current checkout;
- Windows unverified;
- real Linux unverified;
- CI runner evidence versus universal device compatibility.

Describe the unexplained file disappearance as "cause unknown; files
disappeared between checks" unless stronger evidence exists.

## Commit and Phase 4 gate

Before committing:

- restore and verify the macOS baseline;
- resolve the stale-row deletion decision and safeguards;
- reconcile Plate ID and order-date validation;
- review the Phase 4 workflow and plan;
- run shell, YAML, and relevant static checks;
- keep Sheets-write changes separate unless explicitly approved.

Phase 4 execution should begin only after the reviewed workflow and plan are
committed, the current macOS checks pass, and the new litter-entry safety
contracts are explicit.

## Localized audit conclusion

The Windows `$LASTEXITCODE` issue and bare-command coverage were correctly
addressed by inspection. The remaining high-confidence concerns are the
recurrent root editable-install failure and the newly introduced automatic
local-row deletion path. The latter requires a stronger invariant and recovery
design before it can be treated as safe.
