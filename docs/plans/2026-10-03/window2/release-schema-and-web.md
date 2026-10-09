# Amendment 2 Appendix B — Release, Schema and Web

- **Authority:** [contract 04, Amendment 2](../04-data-integrity-two-window-implementation.md#amendment-2-window-2-measurement-repair-and-prospective-cutover-2026-10-04).
- **Status:** Approved 2026-10-04 as a normative part of Amendment 2. Not a Preview/production release decision.
- **Date:** 2026-10-04. Part of the same contract, not a new contract.
- **Prerequisite:** [Appendix A: data contracts and certification](data-contracts-and-certification.md).

## 7A — Controller and authorization separation

Retain `model_id = v5-intended-update-2026-v1`; the unchanged-recipe refit has a **new inference-bundle SHA** and new immutable runs. Do not bypass `require_intended_update_release_record` or existing bundle approval checks.

Authorization is a prior **user-run** operation under its own decision reference and verified authorization identity. The pipeline only verifies authorization inside its release transaction. Migration 0018 deliberately grants `cks_pipeline` SELECT only on both approval tables; do not weaken that separation.

Extend authorization tooling to consume exact packet-bound IDs and cutover N, replacing the historical week range 0–5 and fixed first-live Week 5. Preserve `authorize_v5_intended_update_preview.py`'s Preview-only environment guard and exact identity checks; add an explicitly Production-guarded authorization path using the existing Production authorization identity. Shared validation helpers may be extracted without the broader production-boundary refactor.

The prior operation registers:

- Exact bundle approval for `(model_id, new SHA)`, `first_live_season = 2026`, `first_live_week = N`.
- Exact intended-update authorization for each replay week and N's pending run, binding all existing AUTH_COLUMNS and manifest/checksum relationships.
- Authorization receipt with code SHA, record hashes and its separate decision reference.

These writes do not activate anything. Identical writes are idempotent; conflicting records fail. If batch selection fails, approvals remain unused and are recorded, not deleted or claimed rolled back. If release is abandoned, a separately user-run authorization operation revokes them.

### Revocations

Authorization identities append revocations; selectors and **all V5 freeze paths** check both bundle and run-authorization revocations. Pipeline/web identities cannot mutate revocations. No UPDATE/DELETE grants to the authorization-only role.

Use transaction-scoped advisory locks shared by selection/freeze readers and exclusive for authorization/revocation writers, with deterministic sorted keys derived from approval and authorization IDs. Hold checks through the protected operation to avoid revocation races without pipeline write grants on authorization tables. Include the controller and lower-level freeze-week path so alternate entrypoints cannot bypass the check.

After a completed cutover, rollback serving state first. Revoke abandoned approvals separately only after checking that no active run depends on them. Keep every authorization/revocation receipt. Reject a stale rollback/revocation request if later active releases depend on the approval.

## Migrations and exact new serving contracts

Reserve `0022_prospective_week_records.sql` and `0023_v5_release_revocations.sql`; if another migration consumes these numbers before implementation, use the next consecutive numbers and record that mechanical renumbering. Never modify an applied migration.

### public.prospective_week_records

| Column | SQL type / constraint |
| --- | --- |
| season, week | INTEGER NOT NULL; primary key (season, week); week >= 0 |
| run_id | TEXT NOT NULL REFERENCES prediction_runs(run_id) ON DELETE RESTRICT; UNIQUE |
| freeze_receipt_uri | TEXT NOT NULL, nonempty |
| freeze_receipt_sha256 | TEXT NOT NULL, 64-character SHA-256 |
| frozen_at, first_kickoff_utc | TIMESTAMPTZ NOT NULL; frozen_at < first_kickoff_utc |
| decision_ref | TEXT NOT NULL, nonempty |

Scope: **2026 V5 Week 5 onward** (check season = 2026 and week >= 5 for this schema version). V4 Weeks 0–4 stay audit/rollback records, not this prospective series.

A validation trigger checks the run belongs to the same season/week, V5 family, and has valid prospective freeze metadata; the application verifies the immutable receipt. No DELETE. UPDATE is allowed only before the stored first kickoff and only to a verified replacement freeze for the same slate. A pre-kickoff time correction must not permit reopening a slate that already started: validate against the earliest kickoff in both expected and current schedule evidence. Post-kickoff reassignment is forbidden. Historical INSERT must bind an original authentic pre-kickoff freeze; it cannot backdate a newly generated run.

The designated run is the last valid publicly selected freeze before first kickoff. Record older freezes in retained artifacts and selection history. Register N's final prospective record as part of successful freeze, not merely when its pending run is selected. Batch backfill of completed-week records must reproduce authentic historical selection/freeze evidence.

### Amendment 4 — Week 5 legacy freeze attestation

For the original 2026 Week 5 V5 freeze only, an environment may lack a contemporaneous signed freeze receipt because the historical freeze implementation did not create one. If a bounded search does not find an authentic original receipt, Stage 7B may designate the original run using a `v5_legacy_freeze_attestation_v1` artifact under Contract 04 Amendment 4. The artifact records its real creation time and explicitly states that it is a retrospective attestation, not an original receipt. Preview and Production evidence must be verified and attested separately.

The canonical payload has `schema_version`, `evidence_class`, `environment`, `season`, `week`, `run_id`, `attested_at`, `decision_ref`, `run_frozen_at`, `first_kickoff_utc`, `freeze_activation`, `pre_kickoff_selection_history`, `freeze_pipeline`, `historical_freeze_code_sha`, `original_prediction_manifest`, `original_prediction_artifact`, `contemporaneous_schedule_evidence`, `current_schedule_check`, `source_snapshot_refs`, `limitations`, and `manifest_sha256`. The creation time is generated by the guarded registration operation and cannot be supplied or backdated by its caller. `evidence_class` is `legacy_attested_prospective`; `limitations` explicitly states that no contemporaneous freeze receipt exists and the artifact was prepared after kickoff.

The payload binds the exact environment and run; `prediction_runs.frozen_at`; freeze activation ID, time and metadata; the complete relevant pre-kickoff selection history ordered by `selected_at, selection_id`; successful freeze pipeline/step identity and return code; earliest kickoff from contemporaneous retained schedule evidence, cross-checked against current schedule; historical freeze code commit; original R2 manifest and prediction CSV URIs and raw SHA-256 digests; retained source-query snapshots and hashes; and the approved decision reference. The selection and freeze events establishing prospective status must precede kickoff. Include later history when present to show the full timeline, but do not treat it as evidence of pre-kickoff status. An independent verifier re-reads the source records and immutable bytes and proves that the designated run was the last valid publicly selected and frozen V5 run before kickoff. Missing, conflicting, ambiguous or changed evidence stops registration.

The artifact uses the repository's canonical-content checksum convention. This is a content-integrity check, not cryptographic signer authentication; the payload and documentation must not claim otherwise. For Week 5 alone, the existing non-null `freeze_receipt_uri`/`freeze_receipt_sha256` fields point to the immutable attestation object and raw digest. No database migration or nullable receipt is introduced. The application verifier accepts the legacy schema only for Week 5 and verifies its contents against live read-only source evidence before packet preparation and v2 apply. Performance and audit views identify Week 5 as retrospectively attested. Weeks 6 onward require the normal contemporaneous `v5_prospective_freeze_receipt_v1` created by the guarded freeze flow.

Implement the builder and independent verifier in `src/cks_picks_cfb/ops/prospective_records.py`, the user-run entrypoint in `scripts/pipeline/register_v5_legacy_freeze_attestation.py`, and receipt verification in `src/cks_picks_cfb/ops/v5_batch_selection_v2.py`. Use a URI with environment, season, week, run ID, and the explicit `legacy-attestation-v1` kind; bind both URI kind and payload schema, and reject unknown kinds. The web read path can label the evidence kind from that constrained URI convention and must fail closed on an unknown Week 5 ref; it does not claim to cryptographically verify the content. Packet preparation and v2 preflight/apply perform the full storage hash, canonical checksum and live source re-derivation.

Registration is a separately authorized user-run operation in each environment with dry-run/apply, exact identity guards, immutable R2 write, same-environment database insert and readback. Exact retries are idempotent; conflicts fail. It does not modify serving selections or authorize a migration, cutover, freeze, or Production release. All remaining 7B preflight, dynamic `N`, authorization, rehearsal, release and rollback gates continue unchanged.

### ops.v5_release_revocations

| Column | SQL type / constraint |
| --- | --- |
| record_type | TEXT NOT NULL; bundle_approval / intended_update_authorization |
| record_id | TEXT NOT NULL, nonempty |
| decision_ref | TEXT NOT NULL, nonempty |
| revoked_at | TIMESTAMPTZ NOT NULL DEFAULT NOW() |

Primary key: `(record_type, record_id)`. Validate referenced ID against the corresponding registry with a trigger (polymorphic reference); reject nonexistent IDs. Append-only privileges and trigger reject UPDATE/DELETE. Same-ID identical retries are no-ops, not rewritten audit records.

### Roles, synchronization and tests

| Object | cks_web | cks_pipeline | Authorization identity |
| --- | --- | --- | --- |
| prospective_week_records | SELECT | SELECT, INSERT, UPDATE constrained by trigger | Existing administrative access |
| ops.v5_release_revocations | None | SELECT (and schema USAGE) | SELECT, INSERT only |
| Existing approval/authorization tables | Unchanged | SELECT only | Existing authorized writes |

Create an authorization-only NOLOGIN group `cks_release_authorizer` for revocation grants. Only the existing verified authorization login identities receive membership through environment-verified provisioning; never grant membership to pipeline/web identities. Preserve exact current_user/session_user checks (Preview currently uses `cks_preview_migrator`). Check actual inherited privileges in each environment, including production-specific login roles; table grants to base roles alone do not prove isolation. Do not expose revocations via web credentials.

Update `contracts/schema.sql`, `contracts/schema.ts`, and synced `web/src/lib/schema.ts`; run `make contracts-check`. Apply migrations only in separately authorized operator sessions. Test fresh schema and upgrade from 0021, constraints, foreign references, role-denied writes, pre-kickoff update, post-kickoff rejection, historical freeze registration, concurrent revocation and real Preview identity grants.

## 7B — Packet preparation, explicit cutover and release

Choose concrete **N when this release packet is built**, after rebuild/certification, not Week 6 in advance. Until then weeks open/freeze normally on the current lineage and join the replacement set as they complete. A packet must name the exact week and cannot say merely "next week".

Use `v5_intended_update_batch_selection_v2`, preserving v1 compatibility. v2 requires contiguous replay replacements **Weeks 0..N−1**, all certified/stabilized, plus a corrected **pending** run for unstarted N with enough time for the existing freeze deadline. Do not loosen the one-hour freeze boundary or certified-finals plus 24-hour stabilization.

### Packet / payload shape

Retain Amendment 1 fields:

- `schema_version`, `environment`, `season`, `decision_ref`.
- `expected_current_runs`, `replacement_runs` (integer week keys represented canonically in JSON; duplicate normalized keys rejected).
- `certified_completed_weeks`, `protected_runs`.
- `team_stats_scope`, `team_stats_before`, `team_stats_after`, `team_stats_verifier`.

Add cutover bindings:

- `cutover_week`, `expected_current_week`, `replacement_current_week` (season/week/run ID).
- `bundle_approval` and `run_authorizations`: exact prior registered records plus their canonical hashes and authorization receipt refs; these are verification inputs, **not inserts**.
- `prospective_records_before`, `prospective_records_after`: complete scoped historical mappings and freeze evidence; N is registered at freeze if not yet frozen.
- `serving_config` and corrected measurement/rating/bundle refs used by the weekly cycle.
- `matchup_before`, `matchup_after`, `matchup_verifier`: retained payload refs for the separately executed repin/rollback.

Every artifact ref has immutable URI and raw-byte SHA-256. The signed `v5_team_stats_release_payload_v1` includes environment, season/snapshot scope, source/measurement/rating manifest refs and ordered existing team-stat business columns: season, as_of_week, team, role, metric, value, n, games, rank, cohort_size, source_versions. Exclude DB-maintained timestamps from identity. Include new metric/ledger versions in source_versions; complete refs/coverage live in payload parents.

Before/after stat key sets must be identical and complete; keep newly unavailable rows as null-valued rows. Bootstrap N's keys through the normal week-opening path before taking the before snapshot. Extra/missing keys halt packet preparation for explicit scope resolution—never delete rows or broaden permissions to make the packet pass. Preparation/dry runs do not change serving rows.

Bind exact original run IDs, forecast cutoffs, quote sets, admitted input refs and rollback targets. Prospective record insertions preserve old observations; rollback never removes historical prospective evidence.

### Quote and race policy

- Historical replays use original forecast cutoffs and original eligible quotes, never late backfills.
- Pre-kickoff supersession uses quotes eligible at its **new freeze cutoff**, before kickoff and under existing market policy. Retain both freezes and quote sets; public lines and leans may change before kickoff.
- `run_v5_weekly_cycle.py` consumes packet-bound corrected manifest/config hashes before N's freeze. Freeze verifies lineage and unrevoked approval/authorization.
- If an old-lineage week freezes before release but remains before its freeze deadline/kickoff, retain the old freeze and produce/select/freeze a new corrected run.
- If kickoff or the required freeze deadline has passed, do not invent prospective evidence. Let that week finish/stabilize, include it among reconstructed weeks, choose later N and rebuild/re-authorize the packet as needed.
- Stale packet state fails; never silently expand scope. Hold the pipeline lease through final cutover/freeze coordination. A missed freeze deadline is a failed cutover, not permission to relax it.

### Atomic batch

1. Verify R2 bytes/signatures, independent receipts, target database identity, active lease, complete scope and prior authorization records.
2. Take shared authorization advisory locks and fixed-order write-conflicting locks for site selections, current_week, prospective records, team_season_stats and system_stats; use existing per-week advisory locks in ascending week order. Authorization writers must not acquire these serving locks in reverse order.
3. Compare expected selections, current-week state, complete scoped stat payload and unchanged protected records under locks. Recheck completion/cutoff and revocations.
4. Verify—not insert—bundle approval and exact intended-update authorizations. Select corrected replay 0..N−1 and corrected pending N; move current_week to N as an explicit amendment to Amendment 1's blanket current-pointer protection.
5. Preserve/register completed-week prospective mappings, upsert team stats and recompute selected-public system_stats using the same cursor/connection.
6. Read back all scoped business/provenance rows, pointers and audit identities; commit once. No helper independently commits or opens a second publication connection.

Keep all original run data unchanged. Freeze N separately through the existing guarded freeze operation with exact corrected lineage; a newly selected pending run is not yet prospective evidence. Do not declare the cutover complete until its freeze receipt passes. Failure rolls back transaction writes, **not pre-existing approvals**. Retain unused approvals in receipts and revoke if abandoned.

Rollback uses exact expected after-state and before payload through the same guards. Do not delete valid historical prospective mappings, approvals or original runs. If N has started, rollback cannot select a newly produced forecast for it or overwrite its designated freeze; it needs an exact reviewed safe serving decision. Never use a stale rollback packet against later activity.

### Matchup interval and rollback order

Prebuild/check matchup candidate and previous payload before batch selection. After corrected selection, the existing publisher can satisfy its selected-manifest gate. Immediately repin/verify 2026 data; target publication plus invalidation within five minutes (the existing cache TTL). During mismatch, affected model-derived sections display updating/unavailable; do not silently combine old possession data and corrected basic stats. If repin/verification misses the window, begin rollback.

Rollback order: restore matchup payload first under an exact rollback-only current/target-manifest guard; incompatible content stays unavailable. Then restore the batch run/stat/current state, recompute stats, invalidate caches and verify. Authorization-side revocations follow separately. Retain both payloads and audit receipts. This is compensating recovery across the matchup step, **not** a claim that matchup publication is part of the batch transaction. Test its intermediate states.

## Performance and web scope

`system_stats` continues to represent selected public runs. It is never labeled prospective. Add explicit read queries/helpers (no new aggregate table) for:

- Retrospective reconstruction: selected replay runs only.
- Prospective V5: runs designated in prospective_week_records (2026 Week 5 onward), independently of public replacement selection.

Prevent duplicates within each class; no latest-run fallback. Show separate spread/total W-L-P and win rate, with pushes excluded from win-rate denominator, and distinct empty/ungraded states. Preserve Window 1 accuracy-only presentation. Provide original-run/grade provenance in Performance so prospective evidence stays accessible without changing public run selection. Do not report a combined total as prospective.

Implementation files and tests:

| Area | Files / behavior |
| --- | --- |
| Queries | `web/src/lib/queries.ts`: selected replay vs designated original records; matching manifest/provenance fetches |
| Accuracy | `web/src/lib/performance-accuracy.ts`: class-separated aggregation, duplicates and empty states; preserve existing uncommitted work |
| Performance | `web/src/app/performance/page.tsx`, `web/src/components/PerformanceDashboard.tsx`: separate labels, records and original-run audit access |
| Matchup loading | `web/src/lib/matchup.ts`, new `web/src/lib/matchup-lineage.ts`: ready/updating/unavailable based on selected forecast/rating, publication and stat provenance |
| Matchup UI/share | `web/src/app/matchup/[gameId]/page.tsx` and ShareButton: block incompatible model-derived sections and export during mismatch; retain safe schedule/venue content |

Missing tables/provenance do not imply compatibility. Unit-test pure aggregation and lineage helpers, including incorrect manifest, absent table, no prospective record, superseded pre-kickoff freezes and recovery after repin. Add tests to `web/package.json`'s `test:publication`. Extend `web/e2e/matchup.spec.ts` for states and disabled sharing; add `web/e2e/performance.spec.ts` for class labels, distinct totals and audit access. Run lint, typecheck, test:publication, build and Playwright.

One real Preview database check is mandatory: selected reconstructed week with its original prospective record and a deliberately mismatched publication, then repin recovery. Verify class-separated totals, permissions, updating state and actual read queries. Fixtures alone do not satisfy this requirement. Preview test writes require the separately authorized operator session and retained before payload.

At actual release, update docs/status.md with separately sourced reconstructed public and original prospective V5 scoreboards, replaced-week coverage and cutover week. Live run IDs remain only in that status authority. No scoreboard or week-state values change during planning persistence.

## Task 8 — Matchup completion and issue ownership

Matchup pages are already public; CFB_MATCHUP_ENABLED=0 is only an emergency opt-out. Window 1 owns production display repairs and verifies them independently; do not delay it behind this work. After 2026 repin and release checks, complete 2025 matchup backfill last, labeled historical_replay, with its own receipt.

| Issue | Owner / disposition |
| --- | --- |
| #1 score stream | Window 2 admitted corrections; name baseline residuals instead of claiming total resolution |
| #2 returned punts | Window 1 display/enrichment; Window 2 rebuilt V5 companions |
| #3 null PPA | Window 1 masking; Window 2 original-source Silver and coverage/delta evidence |
| #4 venue city/state | Window 1; close only after both environment coverage receipts |
| #5 overtime-drive hypothesis | Closed as not a defect by October 3 investigation; no new fix |
| #7 reconciliation score comparison skipped | Window 2, step 5B (user-confirmed 2026-10-04): the new Silver team-game contract carries an explicit `points` column and the reconciliation compares it with certified finals. Until then it is detected, not fixed, by `silver.reconciliation_compares_scores` (warn); `exact_match` proves team identity and rows only |
| #9 neutral-site model | Separate challenger/promotion contract; not Window 2 |

Issue #5 evidence is `session_logs/2026-10-03/04-data-integrity-investigation.md`: 0/76 overtime plays and 0/20 OT drives entered eligible metrics; independent hand-check matched 24/24 values. This was investigation evidence, not a claimed Window 1 deployment. Reconcile the pushed register with that dated record while retaining the original hypothesis and independence limit.

## Session checkpoints and acceptance

Each 5A, 5B, 5C, 6A, 6B, 7A, 7B and 8 is its own Terra session with a scoped commit checkpoint and exit receipt. Do not launch them from this planning session. 7A controller engineering may run in parallel with 5C/6 under coordinated file ownership; it cannot activate uncertified data.

Required release tests include baseline hashes; source-null recovery; allocation-group reversion; every named null consumer; EPA-only/scoring-only/offset/combined deltas; PPP invariance; exact auth rejection; role-denied inserts; revocation vs selection/freeze races; contiguous scope; moving cutover; fresh-vs-historical quote policies; original prospective records; complete-key stat payloads; failure after selection/stat write/recompute/readback; idempotent retries; separate matchup compensation and actual Preview/Production readback.

Window 2 is not Implemented until both environment receipts, successful N freeze, 2026 repin, 2025 backfill and rollback rehearsal are complete. Individual unverified scoring changes revert; broader integrity failures hold the release. Every residual is explicit in the issue register. All data/authorization/selection operations remain user-run under exact decisions.

## Pre-6A authority update (2026-10-04)

Contract 04 Amendment 3 and the [pre-Stage-6 execution contract](../../2026-10-04/02-pre-stage6-integrity-and-rebuild.md) authorize immutable Preview R2 and verified Preview catalog/schema/lineage/reconciliation metadata writes for 6A. Earlier blanket “all data operations remain user-run” language in this appendix is superseded only for that scope. No serving or authorization writes are included. The exact 7A/7B release gates, dynamic cutover N, prospective records, freeze and rollback rules above remain authoritative. Issue 7's code exists; persisted reconciliation is not repaired until the verified Silver rebuild.
