# Stage 7B: Exact Release and Cutover

- **Status:** Approved (2026-10-06; approved by the user in this planning task)
- **Created:** 2026-10-06
- **Planner:** Sol planning workflow
- **Authority:** Contract 04 Amendment 2 and its normative Appendices A and B; Stage 6B and Stage 7A are Implemented with Preview-only evidence
- **Predecessor:** [Stage 7A Release Foundations](01-stage7a-release-foundations.md)
- **Commit policy:** Commit this plan separately before implementation; all Git operations are user-run
- **Implementation log:** To be created by the fresh Stage 7B implementation task

## Goal

Prepare and execute the exact corrected-lineage release for 2026 using `v5_intended_update_batch_selection_v2`: select certified, stabilized replay replacements for Weeks `0..N-1`, select one eligible pending corrected run for `N`, publish the corrected team-stat and matchup lineage, freeze `N` under the existing policy, and prove exact rollback. Choose `N` only when the signed release packet is built from fresh state. This contract does not preselect Week 6.

The release is environment-bound and evidence-bound. Preview rehearsal and Production cutover have separate preflights, packets, authorizations, receipts, and operator decisions. This plan authorizes preparation and testing; it does not itself authorize Preview serving writes, Production serving writes, authorization/revocation inserts, or a freeze. Each such live operation requires the exact operator authorization defined below and in Contract 04.

Stage 7B does not perform the Stage 8 2025 matchup backfill and does not by itself close Window 2.

## Current evidence and unresolved prerequisite

The Stage 7A Preview read-only report found `current_week=(2026, 6)`, six active selections, and zero rows in `public.prospective_week_records`. Treat those as dated evidence only; refresh all state at implementation and packet time. The empty prospective table means the original Week 5 V5 freeze designation must be recovered from its authentic original run, signed freeze receipt, receipt timestamp, earliest kickoff, and original selection/freeze history before packet preparation.

Historical prospective status must never be inferred from a reconstructed replay, current selection, grade, or database backfill. Use an existing contract-conformant registration route only if it validates the original immutable receipt and pre-kickoff evidence. If a narrowly scoped operator route is needed, it must verify those same exact source bytes, signatures, run identity, cutoff, and schedule evidence and retain a registration receipt. If the evidence or a valid route cannot be established, stop before authorization or serving selection and return for a Contract 04 amendment or further evidence. Never invent or backdate a freeze.

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

Locate the original Week 5 production freeze, immutable run and manifest, signed receipt bytes, original pre-kickoff selection state, first kickoff evidence, and registration decision reference. Verify their hashes, signatures, environment, timestamps, and lineage against the actual Week 5 freeze. Determine whether a Stage 7A-supported route can register that historical freeze while satisfying `prospective_week_records` constraints.

If registration is permitted, use a distinct user-run operation bound to the exact Week 5 run and receipt, retaining before/after reads and a signed audit receipt. Do not change the selected run, current week, grades, freeze, or original artifacts. Re-read the complete prospective record set afterward. If evidence or schema-compatible registration is not available, halt Stage 7B before authorizations and release packet execution.

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

No amendments at approval. Any scope or policy conflict is returned to Contract 04 before implementation.
