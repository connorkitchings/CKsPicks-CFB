# Investigate the 95 database-only adjusted rows

- **Status:** Implemented
- **Created:** 2026-10-10
- **Planner:** Sol
- **Approval source:** User explicitly requested implementation in this chat.
- **Implementation log:** `session_logs/2026-10-10/11-adjusted-row-investigation.md`
- **Commit policy:** Commit with implementation; user controls Git.

## Goal and acceptance

Explain every recoverable historical database-only row by exact `(season, as_of_week, team, role, measurement_id)` key, determine current Preview and Production disposition, and recommend evidence-backed actions. Counts and bucket labels are insufficient. Every current difference requires evidence and a disposition. Week 6 finals are unnecessary.

## Baseline and constraints

Work on `dev` at `d22efb1a`, preserving five uncommitted preparation-document files. Investigation only: restricted environment-specific credentials, repeatable-read read-only transactions, immutable Preview R2 reads and new local evidence. No deletion, publication, schema/model/serving change, release approval or Git operations. Never create root `data/`. Anchor history to the pinned Week-5 Task 4 configuration and saved metadata; analyze later as-of-6 state separately. Verify storage and database identity without exposing secrets.

## Ordered changes

1. Locate original comparison report, complete key lists or snapshots, manifests and candidate metadata. Verify hashes, cutoffs, week sets and mappings. Recover exact historical keys; missing retained identity remains a blocker, without inventing a convenient 95-row result.
2. Capture all scoped adjusted rows, publication records and referenced lineage from Preview and Production. Bind capture time, identity, scopes, counts and canonical hashes. Compare complete keys and fields; report later weeks separately.
3. Rebuild the pinned candidate in memory with existing artifact readers and pure builders, never publishing stages. Compute both anti-joins and shared-field differences. Separate original extras, current disposition and subsequent population/value/provenance drift. Reject duplicates and ambiguous aliases.
4. Trace every extra to source games, eligibility, availability/cutoff, observed status, numerator, denominator, missingness and adjustment population. Test restored PPA missingness independently. Record source game IDs and hashes. Classify supported retention, supported exclusion/replacement recommendation, explained later-state change or unresolved. Candidate omission alone never makes deletion safe.
5. Add a read-only CLI requiring explicit environment, pinned comparison plan and fresh output directory. Produce snapshots, complete key-level CSV findings, source explanations and checksummed receipt binding code, inputs and outputs. Exit nonzero for unresolved findings, unavailable history, duplicates or unexplained drift; preserve partial evidence. Update repair matrix and session log with actual findings and a separately scoped remediation recommendation.

## Validation

Test exact-key anti-joins (equal counts/different keys), duplicate/alias conflicts, null versus zero, missing-PPA exclusion, cutoff violations, provenance-only differences and environment drift. Use existing numeric tolerance `1e-9` while retaining exact values/deltas; compare nulls, identifiers and UTC timestamps explicitly. Verify read-only setup and overwrite refusal. Run focused Python tests, scoped Ruff, unchanged documentation-authority tests, strict MkDocs and `git diff --check`; inspect affected links and evidence.

## Handoff/amendments

Explicit same-chat implementation authorization is recorded as an exception to the usual fresh Terra handoff. Persist before code edits. Completion requires individual evidence and disposition for all recoverable historical keys and current differences. Missing historical evidence or unexplained findings keep this contract In Progress. Database remediation needs a separate reviewed scope. No physical archival or architecture refactoring is included.


**Implementation outcome (2026-10-10):** all 95 historical keys recovered from checksum-matching snapshots, explained independently and confirmed unchanged in Preview/Production. Final receipts pass with zero unresolved findings; the full current 2,611-key population agrees on all business fields. All-field review retains 2,611 environment-specific write timestamp differences as operational metadata. See [decision report](adjusted-row-investigation/decision-report.md). This completes only the authorized investigation. Remediation, descendant certification, repair closure and release approval remain separate.

**Mechanical clarification:** the saved local comparison and immutable Task 4 report have different envelopes; their adjusted-table comparison sections are equal. Validation compares that exact section while preserving both reports and the initial failed run. This does not change historical identity, scope or acceptance.
