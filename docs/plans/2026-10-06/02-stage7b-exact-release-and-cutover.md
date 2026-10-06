# Stage 7B: Exact Release and Cutover

- **Status:** In Progress (2026-10-06; Amendment 1 approved; implementation of the Week 5 attestation route and remaining release gates pending)
- **Created:** 2026-10-06
- **Planner:** Sol planning workflow
- **Authority:** Contract 04 Amendments 2 and 4 and its normative Appendices A and B; Stage 6B and Stage 7A are Implemented with Preview-only evidence
- **Predecessor:** [Stage 7A Release Foundations](01-stage7a-release-foundations.md)
- **Commit policy:** Commit this plan separately before implementation; all Git operations are user-run
- **Implementation log:** `session_logs/2026-10-06/08-stage7b-exact-release-implementation.md`

## Goal

Prepare and execute the exact corrected-lineage release for 2026 using `v5_intended_update_batch_selection_v2`: select certified, stabilized replay replacements for Weeks `0..N-1`, select one eligible pending corrected run for `N`, publish the corrected team-stat and matchup lineage, freeze `N` under the existing policy, and prove exact rollback. Choose `N` only when the signed release packet is built from fresh state. This contract does not preselect Week 6.

The release is environment-bound and evidence-bound. Preview rehearsal and Production cutover have separate preflights, packets, authorizations, receipts, and operator decisions. This plan authorizes preparation and testing; it does not itself authorize Preview serving writes, Production serving writes, authorization/revocation inserts, or a freeze. Each such live operation requires the exact operator authorization defined below and in Contract 04.

Stage 7B does not perform the Stage 8 2025 matchup backfill and does not by itself close Window 2.

## Current evidence and unresolved prerequisite

The Stage 7A Preview read-only report found `current_week=(2026, 6)`, six active selections, and zero rows in `public.prospective_week_records`. The Stage 7B preflight later captured environment-specific snapshots: Preview remains through migration 0024 with no prospective row; Production is through 0022 with the new table absent. Treat all these observations as dated evidence and refresh state at implementation and packet time.

Historical prospective status must never be inferred from a reconstructed replay, current selection, grade, or database backfill. First search for an authentic original Week 5 receipt. If absent, use only the narrow retrospective `v5_legacy_freeze_attestation_v1` route approved by Contract 04 Amendment 4: actual attestation creation time, explicit missing-receipt disclosure, exact environment-specific database and immutable R2 facts, independent source re-derivation, and a distinct user-run registration decision. The attestation is canonical-content-checksummed under repository convention, not cryptographically signed. Never invent or backdate a freeze. If its bound evidence cannot establish the original selection and freeze before kickoff, stop before registration, packet authorization, or serving selection and return to Contract 04.

## Scope and boundaries

Included work:

- Fresh environment and schedule preflight; dynamic selection of `N`; exact signed Preview and Production packets and their rollback packets.
- Verification of the authentic original Week 5 prospective record and, only if evidence and an approved route permit, its narrowly scoped registration.
- Environment-specific prior authorization, revocation, lease, lock, and identity checks using the Stage 7A implementation.
- Preview rehearsal of the v2 batch, corrected Week `N` freeze, 2026 matchup repin, readback, and exact rollback.
- After successful Preview evidence and a separate Production decision, the Production-bound release, freeze, matchup repin, readback, rollback proof, and receipts required by Contract 04.
- Update `docs/status.md` only after real serving/week state changes, using freshly verified production evidence and keeping live run IDs only there.

Excluded work:

- Model, measurement, rating, cutoff, threshold, or market-policy changes; changing historical forecast cutoffs or source identities.
- Choosing `N` during planning, loosening the one-hour freeze or certified-finals-plus-24-hour stabilization requirements, or fabricating prospective evidence.
- Any unbound selection, freeze, authorization, revocation, or serving write; pipeline-created approvals or authorizations.
- Stage 8 2025 matchup backfill or unrelated weekly operations.

## Execution sequence

### 1. Fresh preflight and cutover-week decision

Capture the implementation commit SHA, exact plan/code identity, environment identity, active lease state, migration ledger, selected runs, `current_week`, protected runs, authorization/revocation state, and all relevant immutable R2 roots/manifests. Verify the signed source bytes and raw SHA-256 values. Use the approved Preview and Production identity guards and record `session_user`/`current_user` plus effective grants without exposing credentials.

Reconcile the complete 2026 FBS schedule against fresh spread and total quote coverage. Record capture time, all missing game IDs, next refresh, each kickoff, final certification/stabilization, original freeze cutoff and current freeze deadline. Do not infer current quote availability from an old capture. Choose the concrete `N` only after this review:

- Require corrected replay replacements for every contiguous week `0..N-1`, each certified and stabilized under the authoritative finals evidence and 24-hour rule.
- Require exactly one eligible corrected pending run for an unstarted `N`, with enough time to satisfy the existing one-hour pre-kickoff freeze boundary.
- If kickoff or the freeze deadline has passed, do not create prospective evidence. Let the slate complete and stabilize, add it to the replay range, choose a later `N`, and rebuild/re-authorize the packet.
- If an old-lineage freeze exists before kickoff, preserve it and bind the corrected new freeze and its eligible quote set separately.

Stop on stale/incomplete schedule or quote coverage, missing certified finals, an unexpected migration/identity/grant state, changed protected runs, or any failed deadline. No packet silently widens scope.

### 2. Recover the original prospective Week 5 evidence

Locate the original Week 5 freeze, immutable run and manifest, any contemporaneous receipt, original pre-kickoff selection state, first kickoff evidence, and registration decision reference separately in Preview and Production. Verify their environment, timestamps, hashes and lineage. If an authentic receipt is absent, prepare the Amendment 4 legacy attestation from the complete retained records, prove it identifies the last valid publicly selected and frozen run before kickoff, and verify its actual creation time and source hashes independently.

Implement the payload builder and independent verifier in `src/cks_picks_cfb/ops/prospective_records.py`, the guarded user-run entrypoint at `scripts/pipeline/register_v5_legacy_freeze_attestation.py`, and the packet verification branch in `src/cks_picks_cfb/ops/v5_batch_selection_v2.py`. Use a distinct immutable URI containing environment, season, week, run ID, and `legacy-attestation-v1`; include the canonical payload checksum in the JSON and store the raw-byte SHA in the database row. The payload fields and source re-derivation requirements are normative in Contract 04 Amendment 4 / Appendix B. Do not accept an attestation creation timestamp from CLI input. Stage7B and Performance provenance must render this as a legacy attestation based on the explicit URI kind and validated payload; unknown receipt kinds fail closed.

Only after a separate exact user decision for that environment, use the guarded registration command to write the content-addressed attestation to R2 and insert the matching Week 5 row in `prospective_week_records`; retain before/after reads and the registration result. Exact retries must be idempotent. Do not change selected runs, current week, grades, freeze history, or original artifacts. Re-read the full prospective set and independently validate the attestation before packet preparation. If evidence is incomplete or conflicting, halt before registration, authorizations, and release packet execution.

### 3. Build and review exact release packets

After all source certifications and prospective evidence are complete, build separate environment-bound v2 release packets and rollback packets. Each packet binds:

- `schema_version`, `environment`, season, decision reference, and concrete cutover `N`;
- exact expected and replacement run maps, contiguous certified weeks, protected runs, expected/replacement `current_week`, and original cutoffs, quote sets, admitted inputs, and run identities;
- bundle approval and exact run-authorization IDs, canonical record hashes, immutable authorization receipt references, and current revocation state (verification inputs only);
- complete prospective records before and after, including authentic Week 5 evidence; `N` enters this series only through the verified freeze operation;
- signed team-stat before/after payloads with identical complete keys and provenance, null rows retained, verifier, source refs, and exact scope;
- corrected serving configuration and measurement/rating/bundle refs; exact matchup before/after payloads and verifier; all artifact URIs and raw-byte hashes.

Prebuild and verify the matchup candidate and exact previous payload before changing serving selections. Check normalized week keys for duplicates, contiguous coverage, signatures, hashes, before-state equality, protected-run state, stat-key completeness, authorization identity, and rollback reversibility. Require packet reviewers to inspect the before/after diff and retained rollback payloads. Dry runs are read-only.

### 4. Prior authorization and Preview rehearsal

Register exact Preview bundle/run authorizations using the user-run Stage 7A tooling under the verified Preview authorizer identity. The pipeline role verifies them and their receipts; it never inserts or revokes them. Keep receipts and decision references. An authorization or revocation change invalidates and requires rebuilding the packet if any bound identity or state changes.

After a separate explicit user instruction naming the Preview packet and apply operation, execute the Preview batch with the v2 controller. In one connection and transaction, recheck identity, lease, shared authorization locks, revocations, expected selections/current week/protected runs, complete prospective mappings, and full team-stat before-state; select `0..N-1` plus pending `N`, move `current_week`, preserve/register eligible completed-week prospective mappings, upsert the exact team-stat after payload, recompute selected-public `system_stats`, read back all scoped business and provenance rows, then commit once.

Freeze corrected `N` only through the existing guarded V5 freeze route, after a fresh quote capture at the new cutoff and while the existing deadline holds. A selected pending run is not prospective evidence until its signed freeze receipt is verified and its designated record is persisted. Keep the pipeline lease and authorization locks through the protected work.

Immediately repin and verify 2026 matchup data against the corrected selected manifest, targeting publication and cache invalidation within the existing five-minute cache window. During a mismatch, the web lineage guard must show updating/unavailable and hide incompatible model-derived fields. Verify recovery to ready with actual Preview reads and the separate Performance evidence classes.

Prove exact Preview readback for selections, `current_week`, team stats, system stats, prospective records, authorization evidence, freeze receipt, matchup provenance, and web query results. Perform the reviewed rollback rehearsal: restore the prior matchup payload first under its exact guard, then restore batch selections/team stats/current week in one guarded transaction, recompute statistics, invalidate caches, and verify exact restoration. Do not erase prospective history or approvals. Reject rollback if state has advanced, `N` has started, or any dependency makes the retained packet unsafe.

If any apply, freeze, repin, readback, or rollback guard fails, stop at the first failure, preserve all receipts, and do not proceed to Production.

### 5. Production decision and exact release

Only after the complete Preview rehearsal and rollback receipts are reviewable, present the exact Production-bound packet, rollback packet, code SHA, source roots, authorization receipts, selected `N`, before/after payloads, Preview evidence, risks, and any residuals for a separate explicit Production decision. The user must authorize the exact Production apply; this plan and prior Preview authorization do not grant it.

After that authorization, repeat fresh Production preflight and verify target identity, migration ledger, effective role privileges, live schedule/quotes/deadlines, exact packet hashes, authorization/revocation state, lease, and all before-state snapshots. Any drift invalidates the packet and requires fresh certification, packet creation, and authorization. Execute the same atomic selection/stat/current-week transaction, guarded corrected `N` freeze, immediate matchup repin/verification, and exact readback under Production identities. Retain complete evidence. If required gates fail, stop and use only the exact reviewed guarded rollback packet; rollback is never best-effort or sequential.

After successful state changes, update `docs/status.md` with separately sourced retrospective reconstructed and prospective V5 scoreboards, replaced-week coverage and cutover week. Put live run IDs only in that status authority. Do not edit status during planning or before the verified change.

## Required validation

- Existing v1 batch path remains behaviorally compatible; v2 unit, packet, signature/hash, cursor/transaction, authorization, lease, revocation, role, deadline, and lock-race tests pass.
- Isolated-database integration covers contiguous moving `N`; completed/stabilized vs pending/unstarted evidence; quote-at-original-cutoff vs quote-at-new-freeze-cutoff; authentic historical prospective registration; complete team-stat keys and null retention; system-stat recomputation; exact retry; and rollback.
- Failure injection after selection, current-week movement, team-stat upsert, recomputation, and readback proves a single transaction leaves no partial state. Stale state, gaps, duplicates, missing finals, altered refs, revoked/mismatched auth, incomplete stats, late `N`, and protected runs all fail closed.
- Concurrency tests show revocation serializes with selection and both weekly-cycle and direct freeze routes without a lock-order deadlock.
- Matchup tests cover prior payload retention, mismatched lineage and disabled sharing, repin recovery, timeout handling, and correct compensation order.
- Run the full Python suite and Ruff; `make contracts-check`; web lint, typecheck, publication tests, build, and Performance/matchup Playwright; MkDocs and `git diff --check`.
- After separately authorized Preview rehearsal and Production release, retain real-identity migration/grant/readback receipts and actual web query readback. Fixtures do not establish live parity.

## Stop conditions

Stop before the dependent operation and retain evidence if any of the following occurs: original Week 5 freeze provenance cannot be authenticated or safely designated; a Preview/Production identity or effective privilege is unexpected; the migration ledger drifts; schedule, quote, finals, or cutoff evidence is stale or incomplete; no eligible `N` remains; packet bytes or signatures differ; before-state, protected runs, authorization, or revocation state changes; team-stat keys are incomplete; matchup repin misses its bounded window; or exact rollback is unsafe. A material change to lineage, model identity, cutoff, table or role identities, cutover semantics, or write scope returns to Contract 04 for amendment.

## Definition of Done

- [ ] Fresh evidence selects and justifies `N`; all replay, finals, quote, cutoff, and stabilization gates pass.
- [ ] Authentic Week 5 prospective provenance is verified and represented without inference or backdating.
- [ ] Preview packet, prior authorizations, apply, corrected freeze, matchup repin, readback, and exact rollback all pass under Preview identities and separately authorized operations.
- [ ] Production exact packet and authorizations are reviewed, the user separately authorizes the exact Production apply, and Production freeze, repin, readback, and rollback evidence pass.
- [ ] Full tests and validation above pass; receipts include code SHA, packet hashes, identity, inputs, before/after state, freeze, matchup, and rollback evidence.
- [ ] `docs/status.md` reflects the verified resulting live state, with IDs only in that file.
- [ ] Stage 7B exit receipt is complete. Stage 8 2025 backfill remains separately gated; Window 2 is not declared complete until its own Stage 8 requirements pass.

## Amendments

### Amendment 1 — Week 5 legacy freeze attestation (2026-10-06)

Approved by the user in this planning task. Implements the narrow exception in Contract 04 Amendment 4 and Appendix B: when no authentic contemporaneous Week 5 receipt exists, verify environment-specific original records and register an explicit, current-time `v5_legacy_freeze_attestation_v1`. Preserve the non-null schema and identify this provenance as retrospective attestation. No migration, serving change, selection, authorization, freeze or release is authorized by this amendment. All other Stage 7B gates, including Production schema parity and fresh dynamic `N`, remain.

Any further scope or policy conflict is returned to Contract 04 before implementation.

## Execution record — 2026-10-06

Fresh read-only Preview and Production snapshots verified exact restricted pipeline identities and applied migration checksums. Preview is through 0024 with zero prospective/revocation rows; Production is through 0022 with those tables absent, as anticipated by Stage 7A. Both have six selections and Week 6 with no active run. These observations do not select cutover `N` or update the serving-state authority.

The original Week 5 selection/freeze ledger and kickoff are retained, but the checked immutable prefixes contain no contemporaneous receipt; the historical implementation did not persist one. The current receipt-generating helper cannot recover absent original bytes. The initial preflight hold stopped packet preparation and all writes. Contract 04 Amendment 4 and this plan's Amendment 1 now permit a narrowly scoped, clearly retrospective attestation after implementation, independent verification and a separate user-run registration decision. The preflight hold report remains the evidence snapshot and is not edited to imply that policy existed at capture time. No live registration or release operation has yet been authorized or performed. Production schema parity, full live preflight, dynamic `N`, and all Preview/Production release gates remain open.
