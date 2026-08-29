# Sheets-Write Architecture Decision — `sheets_overlay.write_new_litters`

**Status:** implemented, explicitly approved by the project owner, enabled in the real (gitignored)
production config, and used for two real litter-entry runs against the real Google Sheets API.
Deliberately kept as its own change, separate from the portability/Phase-3/Phase-4 work, per
`20260828_codex_phase3_setback_review.md`'s and `20260828_copilot_next_steps_for_claude_before_phase4.md`'s
request not to bundle it silently into that checkpoint. Extended after the second reconciliation
round with an automatic stale-row-replacement capability (see risk 5 below) in response to a direct
project-owner request, and hardened per that round's codex/copilot review before being treated as
settled.

## Why this exists as a separate decision record

Both reviews correctly pointed out that adding an exception to `CLAUDE.md` documents a capability,
but doesn't by itself constitute the kind of deliberate architecture review a live-data write
capability deserves. This document is that review: it restates the four risk categories raised,
what was actually decided for each, and what — if anything — remains open.

The decision to build this feature at all, and its shape (write to both targets, conflict-check
immediately before writing, degrade to a warning on any Sheet-side failure rather than fail the
run), was made by the project owner directly in conversation, across several turns, including
explicit answers to three targeted questions before any code was written. That is the "explicit
approval" both reviews asked for; this document exists to make the resulting design decisions
legible on their own, not to re-litigate whether to build it.

## The five risks, addressed

### 1. Conflict-check-then-append is not atomic

The Sheet's identifier column is re-fetched and checked immediately before appending, but there is
a real window between that check and the append call itself during which another lab member could
add the same mouse ID by hand. This is a genuine, unresolved race condition.

**Decision: accepted, not engineered around.** Google Sheets' API has no compare-and-swap or
transactional multi-step primitive that would close this window without disproportionate
complexity (e.g., a separate locking document, or moving the whole inventory to a system with real
transactions — which is a far larger change than this feature warrants). The window is narrow (one
API round-trip), the population of people who can edit this sheet is small and known, and a
resulting collision is not silent: any human editing the Sheet directly would see the resulting
duplicate row and could raise it. This mirrors a limitation already accepted elsewhere in this
project — the local inventory itself has no multi-writer locking either, on the premise that it's
a single-operator-at-a-time desktop tool, not a concurrent multi-writer database.

### 2. No retry/idempotency after an uncertain remote response

If the append request reaches Google and is processed, but the response is lost to the client
(network drop, timeout) before confirmation arrives, the code currently treats this identically to
"nothing happened" — raising `SheetsLitterWriteError` and telling the user the write failed. If the
user then manually re-adds those rows to the Sheet, or re-runs the litter entry, duplicate rows are
a real possibility.

**Decision: acknowledged in the warning message, not solved with a durable receipt.** A true fix
(an idempotency key per append, checked before every retry) is a reasonable future improvement but
is more infrastructure than this feature's current scale justifies, and Google Sheets' API doesn't
offer a native idempotency-key mechanism to build it on cheaply. As a cheap, real mitigation made in
response to this exact review, the warning text now explicitly says the write may have partially
succeeded and tells the user to check the Sheet for the specific mouse IDs before adding them by
hand, rather than implying the write definitely failed (see `app.py`'s Sheet-write exception
handler). This does not eliminate the risk; it prevents the tool from actively encouraging a
duplicate-creating action in response to it.

### 3. Local success / remote failure divergence

A litter can be written successfully to the local inventory copy while the Sheet write fails
independently — the two targets are not transactionally coupled.

**Decision: accepted by explicit design, not a defect.** This was one of the three questions put to
the project owner directly before implementation: write to both targets, with the local write as
the one that must never be blocked by the Sheet's availability. The recovery procedure is the
warning message itself, which names the exact mouse IDs that need manual reconciliation — there is
currently no automated re-sync step, and none is planned unless divergence turns out to happen often
enough in practice to justify one.

### 4. Real API/credential/permission verification status

The original review noted "no real Google API write, credential, permission, or retry behavior has
been verified" — accurate at the time it was written, but superseded by events in this same
session, worth stating precisely rather than leaving the stale claim standing:

- **Real writes**: verified for real. Two real litter-entry runs went through the actual Google
  Sheets API with the actual service-account credential. The first appended 10 real rows
  successfully — to the wrong spreadsheet, because the configured `spreadsheet_id` was stale, not
  because the write path itself failed. That misdirected write is itself evidence the write path,
  credentials, and Editor permission all function for real.
- **Real reads (conflict-check path)**: verified for real, against the corrected spreadsheet — a
  read-only connectivity check confirmed the service account can reach it, read all 51 header
  columns and 9,072 existing identifiers, and correctly did not find the earlier misdirected mouse
  IDs there.
- **Still not verified**: a real *write* against the now-corrected spreadsheet specifically. Every
  real write so far went to the previously-misconfigured sheet; only a read has been proven against
  the corrected one. A real end-to-end litter entry against the corrected sheet is the one concrete
  verification step still outstanding, and is expected to happen the next time the project owner
  enters a real litter.
- **Retry behavior**: not exercised for real in either direction (no real failure has occurred yet
  to observe how the warning path behaves in practice).

### 5. Automatic stale-row deletion (added after the second reconciliation round)

The project owner separately asked for mouse IDs deleted from the primary Google Sheet to become
re-enterable, rather than staying permanently blocked because the local inventory copy still
remembers them. Implementing that required the Sheet, once reachable, to become authoritative over
the local copy for conflict detection — and, when a submitted mouse ID turns out to be exactly this
case, to remove that mouse ID's stale local row and replace it with the freshly submitted one. This
is the first automatic row-deletion this codebase has ever had, and codex's and copilot's second-round
reviews correctly treated it as a distinct risk category from the four above, not ordinary conflict
handling. Four concerns were raised; each is addressed below.

**a. Is the Sheet actually authoritative and complete, or could a bad read cause wrongful deletion?**
A successful HTTP response is not proof the data in it is complete — a wrong tab, a misconfigured
range, or a masked partial failure could all return a technically-valid but drastically incomplete
identifier list, which would make every local mouse ID absent from it look "deleted from the Sheet."

**Decision: guarded, not merely assumed.** `append_litter_to_inventory` now compares the fetched
identifier count against the local inventory's own known identifier count immediately after a
successful fetch; if the Sheet reports fewer than half of what the local inventory already has, the
fetch is treated as unreliable for this run — the same as a fetch failure — and everything falls back
to the pre-existing local-only conflict behavior, with a warning naming the discrepancy. Half of the
local count is a conservative, non-arbitrary floor: it needs no separately configured "expected"
number, only that the Sheet's view isn't drastically smaller than what Möuseley Kräs already knows.
An ordinary single-litter deletion (one ID missing out of thousands) is nowhere near this floor and
proceeds normally; a broken or wrong-tab response almost certainly is.

**b. Is the removal auditable and recoverable, or just a silent mutation?** Every stale-row
replacement is logged, and every affected mouse ID's prior field values (strain, mother, father,
DOB, sex, Plate ID, Transnetyx Order Date) are captured before deletion and written into that pup's
audit-entry message, alongside an explicit pointer to the run's own pre-write inventory backup file
(the same checksum-verified backup this project already makes before every inventory write) as the
recovery path. Nothing about the removal is inferred after the fact from a diff — it's named exactly,
at the moment it happens.

**c. Is this scoped tightly, or could it reach rows it shouldn't?** It only ever considers mouse IDs
that are literally part of the litter being submitted right now — never a background scan of the
whole inventory — and only when this run's own Sheet fetch has both succeeded and passed the guard
in (a). A local row is never removed on its own; removal only ever happens paired, in the same
operation, with immediately writing a fresh row for that same mouse ID.

**d. Test coverage.** `tests/test_litter_entry_integration.py` covers: the ordinary freed-and-replaced
case (exactly one surviving row, correct new data, Sheet-append still happens); the dry-run preview
of the same case (no mutation, matching message); and, added in response to this review, the guard
itself — both a completely empty Sheet response and a suspiciously small one (1 of 4 known local
IDs) are shown to fall back to local-only conflict behavior rather than freeing anything.

**What this decision does not cover:** the guard's 50%-of-local floor is a judgment call, not a
value the project owner was asked to approve directly, unlike the four original risk decisions above,
which were each the subject of an explicit turn-by-turn conversation. It should be read as a
reasonable engineering default, not a separately ratified policy. A real end-to-end deletion-and-
replacement against the live Sheet (as opposed to the mocked test suite) has also not yet happened —
see "What remains open" below.

## What remains open

1. The corrected-spreadsheet real-write verification noted in item 4 above.
2. Whether the accepted risks in items 1–2 ever need a stronger mitigation (a durable append
   receipt, or a locking mechanism) — deferred until real-world experience shows they matter, not
   engineered pre-emptively.
3. A real end-to-end stale-row replacement (item 5) against the live Sheet — everything so far is
   covered by the unit test suite against mocked Sheet responses, not a real deletion-and-replacement
   round-trip against the actual spreadsheet.
4. The 50%-of-local sanity-guard threshold in item 5 is an engineering judgment call, not something
   the project owner has separately reviewed and approved the way the original four risks were.
