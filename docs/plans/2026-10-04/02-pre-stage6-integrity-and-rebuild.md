# Pre-Stage-6 Integrity and Corrected-Lineage Rebuild

- **Status:** In Progress
- **Created:** 2026-10-04
- **Planner:** Sol
- **Approval source:** User explicitly requested “PLEASE IMPLEMENT THIS PLAN” with the complete reviewed plan in the planning chat on 2026-10-04. The user separately selected “R2 + Preview catalog (Recommended)” for the 6A write boundary.
- **Governing authority:** [contract 04](../2026-10-03/04-data-integrity-two-window-implementation.md), Amendment 3; [Appendix A](../2026-10-03/window2/data-contracts-and-certification.md), Amendment 4. This is their bounded execution contract, not a competing release authority.
- **Planning log:** [09-pre-stage6-integrity-plan.md](../../../session_logs/2026-10-04/09-pre-stage6-integrity-plan.md)
- **Implementation log:** `session_logs/2026-10-04/10-pre-stage6-integrity-implementation.md`
- **Commit policy:** Separate documentation/plan commit on `dev`, then scoped implementation checkpoints. All git operations remain user-run.
- **Handoff:** The user subsequently explicitly invoked implement-plan on this exact path in this chat; implementation is authorized here. The preceding planning edits remain uncommitted and are preserved.

## Goal and current state

Close the pre-6A correctness and integration gaps, then rebuild a fully pinned corrected measurement/rating/forecast lineage in Preview under the unchanged model design. Step 5 is closed as recorded evidence; it did not finish consumer integration or publish the new Silver/Gold foundation. Production activation remains in Stages 7–8 after Stage 6B reconstruction.

The review baseline is clean `dev` at `3f238fb`. All 86 focused Step 5 tests passed. Additional in-memory probes reproduced: missing source rows becoming observed zeros; unknown scoring-opportunity flags becoming false; cross-season aggregation; and exclusion of explicitly reverted baseline points. Code inspection also found lost reversion labels during Gold conversion, existing runners loading old measurement/prior parents, and a bridge helper replacing rating columns while retaining offsets. These are pre-6A repair requirements, not evidence of a serving-state change. Cloud state was not reverified during this review.

## Scope and authority

Include shared contract repairs, regression tests, explicit runner integration, full historical rebuild, eligible 2026 states, unchanged-design refit, immutable Preview publication and independent certification. Preserve the original Step 5 receipts and decision hashes.

Authorized writes are new immutable artifacts using Preview R2 credentials and verified Preview Neon dataset/schema/lineage and associated reconciliation metadata. No serving-table, selection, authorization-record, production-R2 or production-Neon writes. R2 buckets may be shared: Preview credentials alone do not prove isolation; verify the target and permitted immutable namespaces, retain old objects, and never overwrite serving refs. Fail closed on an unexpected database identity.

Excluded: model redesign, neutral-site changes, EPA imputation, retrospective run selection, live freeze/cutover, matchup publication, production-boundary refactoring and broad deferred quality-library work. Stage 6B and Stages 7–8 retain their existing contracts and exact release gates.

## Ordered implementation tasks

### 1. Repair shared data semantics before rebuilding

- Preserve `baseline_unchanged`, `corroborated`, `reverted_unverified` and `reverted_contradicted` through admission and Gold conversion. In the admitted output, reverted rows are the retained baseline allocations and contribute valid points. Correct metric, offset and independent-verifier consumers together, including tests currently asserting exclusion. Candidate ledgers cannot enter this consumer path.
- Require explicit source coverage and reconciliation evidence before interpreting absent events as verified zero. Missing coverage produces unavailable dependent measurements with reasons, while independently complete metrics remain usable. Known empty populations remain distinguishable from missing inputs.
- Preserve unknown scoring-opportunity and field-position values. Withhold dependent full-population metrics rather than substituting false or shrinking denominators. Apply the registry's full-population semantics to every required input.
- Aggregate by season, team, role and metric; retain the season in output keys. Apply explicit website (regular-season FBS-vs-FBS) and accepted V5 population policies. Preserve weighted ratios, ranking direction, minimum-rank ties and unavailable-value handling.
- Validate duplicate identities, possession/conversion references, and ledger-to-evidence references. Populate R1 envelopes from pinned score streams in canonical order; retained baseline allocations keep truthful baseline provenance rather than fabricated R1 envelopes.
- Build evidence from retained CFBD bytes with hash verification, approved group-to-bundle identities and precise allocation/event locators. Use the recorded user-specified terms URI and rights basis; do not represent them as independently verified legal findings. Verify references independently of the producer.
- Add versioned observation interfaces allowing nullable numerators. Keep legacy readers/verifiers and signed-artifact reproduction unchanged.

**Exit gate:** regression cases pass; schema and semantic checks reject invalid inputs; old signed-artifact semantics remain reproducible. No full rebuild starts before this gate.

### 2. Implement manifest-driven orchestration

Provide separate preflight, build, verify and Preview-publication operations. Bind source refs and hashes, source capture times, population/cutoff policies, registry checksum, code/config identity, decisions and output identities in manifests. Use existing immutable lake helpers and canonical-content signing; this is not cryptographic signer authentication.

Reject implicit latest selection and unverified scratch caches. Preflight records the complete intended seasons, inputs, outputs and write scope. Resume only against identical verified inputs; conflicting immutable retries fail. Partial outputs must not acquire a consumable certified root manifest. Retain quality receipts beside immutable build evidence; this scoped requirement does not reopen the entire quality-library contract.

### 3. Rebuild in dependency order

1. Pin and reproduce the baseline with the original Step 5 sources and decision hashes. Use byte identity or full canonical-record identity under the original schema, not rounded ratings.
2. Rebuild Silver from pinned original captures with nullable PPA and stream-score reconciliation. Record source gaps and explained discrepancies; do not infer missingness from legacy zeros.
3. Compare rebuilt stable event identities, score inputs, eligibility and allocation groups with Step 5. Do not silently reuse decisions on materially changed groups. Retain a comparison receipt; renewed certification is required for material changes, with an amendment if the approved decision set or scope must change.
4. Build the four Gold datasets and signed manifests. Wire V5 observations and website-stat aggregation to the shared metrics with their distinct populations. Validate source/ledger/evidence relationships before downstream consumption.
5. Rebuild historical measurements, chronological and terminal states, dependent priors and ratings in causal order. Eliminate stale baseline parents throughout the corrected chain. Old parents remain only in explicit baseline comparisons.
6. Recompute admitted-ledger non-offense offsets and the historical feature frame before refitting the accepted alpha-10 Ridge/calibration recipe. Do not use rating-only replacement as the corrected feature build.
7. Build eligible 2026 states separately with pinned coverage, certified inputs and precise cutoffs. Keep scoring allocations at baseline wherever independent admission evidence is absent; Step 5 did not admit later-game corrections.
8. After independent verification, publish immutable Preview artifacts and catalog entries, read back hashes, and demonstrate an identical idempotent retry.

Preserve 2015–2019 and 2021–2025 historical scope; exclude 2020 at every boundary. Exclude 2026 outcomes from coefficient, calibration and hyperparameter fitting/tuning; allow accepted chronological rating-state updates. Preserve one source-game observation once, accepted exposure/adjustment and availability policy, `home_host = 1.0`, and `venue_unknown = True`. Keep operational finals-plus-24-hour stabilization distinct from rating availability.

### 4. Verify, report and hand off to 6B

Independently verify full-corpus lineage and admitted allocations. Compare the shared aggregates against published statistics read-only, explaining expected population, punt, missing-PPA and scoring differences. Do not silently redefine a population to obtain agreement.

Produce baseline, EPA-only, scoring-only, offset-only and combined comparisons for raw/adjusted measurements, priors, states/ranks, non-offense points, offsets, coefficients/calibration and forecasts. Hold other inputs fixed in each attribution comparison. Require identical rating record hashes and forecast outputs when only EPA changes and PPP, population, priors and scoring stay fixed. Report residual baseline errors and raw-versus-adjusted materiality separately.

Produce a signed 6A receipt with exact verified output refs, coverage, residuals, validation evidence and inputs for 6B. No receipt may imply that all source defects are repaired or that production activation occurred.

## Validation

- Regress absent source versus genuine zero, null opportunities/field position, mixed seasons, retained reverted points, and legacy compatibility.
- Test duplicate keys, tampered evidence, unresolved/missing references, changed source groups, conflicting immutable retries, and failed-prerequisite publication guards.
- Prove chronological evidence use and forbidden-season rejection in datasets, priors, rating updates, fitting and calibration.
- Run the focused Step 5 tests plus new regression/integration tests, the required full Python suite with CI flags, scoped Ruff checks, `contracts/validation.py`, quality registry verification and `make contracts-check` when shared contracts are affected.
- Run `git diff --check` and `uv run mkdocs build --quiet`. Do not broad-format the worktree.
- Verify Preview target identity, immutable readback, catalog linkage and idempotence in the authorized build session; fixtures alone do not establish data readiness.

## Risks and amendments

New Silver eligibility can change the Step 5 comparison boundary. Missing original captures, changed groups or incomplete lineage must be surfaced, not bypassed. CFBD corroboration is mostly attribution-only; unverified/contradicted allocations retain baseline errors. Passing tests alone does not certify the rebuilt corpus. Do not reinterpret a failed gate as permission to drop games, broaden writes or change model design.

Stop the affected step for any material conflict with approved population, scoring decisions, model recipe or write scope; retain evidence and amend this contract before proceeding. Continue independent authorized work where safe. Fix cutover N only under the later exact release packet, never assume Week 6.

## Definition of done

- [x] Shared-contract repairs and regression tests pass (Task 1 complete: 2026-10-04).
- [ ] Manifest-driven orchestration consumes corrected parents end to end.
- [ ] Full historical and eligible 2026 builds are independently verified.
- [ ] Required delta reports and signed 6A receipt are retained.
- [ ] Preview publication, catalog linkage, readback and retry pass without serving changes.
- [ ] Current docs, issue register and implementation log reflect measured results.
- [ ] Contract marked Implemented only after all above gates; Stage 6B remains a separate handoff.
