# Session: V5 Contract 10 Umbrella Planning (10a/10b)

## TL;DR
- **Worked On:** Refined Draft Contract 10 into an Approved umbrella with two execution contracts.
- **Outcome:** Umbrella `10-v5-historical-foundation-audit.md` rewritten; `10a-v5-audit-harness-and-lineage.md` and `10b-v5-full-corpus-audit-execution.md` created; plans index updated.
- **Plan Contract:** `docs/plans/2026-09-18/10-v5-historical-foundation-audit.md` (umbrella) + 10a/10b
- **Approval / Status:** User approved the revised plan with "go" on 2026-09-18; umbrella + 10a/10b are Approved.
- **Blockers:** None for planning. Execution needs a fresh Terra task with explicit authorization.
- **Next:** Terra implements 10a, then 10b, in order. No Contract 11 work until the 10 gate is evaluated.

## Context and Decisions
- Start-session routed to plan-session (Sol): data/model lineage, multi-subsystem audit.
- Branch `main`, clean tracked worktree (ahead of origin); preserved as-is.
- Planning confirmed `CFB_STORAGE_BACKEND=r2`; Terra must verify Preview + source credentials (bucket, account ID, access key, secret key each) without printing values before cloud I/O.
- User issued eight corrections, all applied: 55-test baseline wording, lowercase 10a/10b filenames, two verifier gaps as confirmed structural facts, 10a/10b publication boundary, Git-object-database code/config verification, compact JSON outputs, audit-verifier scope, determinism + runtime gates (preflight 3,600s; apply/verify 600s each).
- Key scoping answers: umbrella + 10a/10b layout; new `src/cks_picks_cfb/audit/` namespace; confirm-then-expand test baseline.

## Work Completed
- Rewrote umbrella Contract 10 with frozen parents, artifact root, four outputs, severities/dispositions, Contract 11 gate, execution sequence.
- Created 10a (spec, lineage inventory, read-only harness; ends with three byte-identical preflights; zero R2 writes).
- Created 10b (full-corpus execution, independent verification, findings report, publication sequence).
- Updated `docs/plans/index.md` historical-first sequence table.

## Files Modified
- `docs/plans/2026-09-18/10-v5-historical-foundation-audit.md` — umbrella rewrite.
- `docs/plans/2026-09-18/10a-v5-audit-harness-and-lineage.md` — new execution contract.
- `docs/plans/2026-09-18/10b-v5-full-corpus-audit-execution.md` — new execution contract.
- `docs/plans/index.md` — lifecycle rows for 10/10a/10b.
- `session_logs/2026-09-18/05-v5-contract-10-umbrella-planning.md` — this log.

## Validation
- [x] `git diff --check`
- [x] `uv run mkdocs build --quiet`

## Amendments and Blockers
- None. Material changes to boundary, parents, outputs, severities/dispositions, or gate conditions require a separately approved amendment.

## Handoff Notes
- **Resume at:** Fresh Terra task implementing 10a first:
  `docs/plans/2026-09-18/10a-v5-audit-harness-and-lineage.md` (requires explicit authorization naming the exact path).
- **Watch out for:** Do not duplicate Contract 11 reconstruction inside the audit; record forecast-output reconstruction as unresolved for 11. Never check out or modify the worktree during historical commit hashing.

**tags:** ["v5", "contract-10", "audit", "planning"]
