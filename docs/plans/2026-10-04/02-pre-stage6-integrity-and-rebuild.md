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

## Amendment 1 (2026-10-04): Gold scope, write namespaces, evidence ids, orchestration design

**Approval source:** user answers and plan approval in the implementation chat of 2026-10-04 (Gold set "add to the four", chain design "new pinned DAG", code identity "user commits Task 1 first", scope "all of Task 3"). Task 1 was committed by the user as `2f9ec06` (docs) and `1e9e3bd` (code); the Task 2 harness pins `HEAD` and requires a clean tree.

- **Gold scope (adds to Task 3.4).** Six Gold outputs: `team_game_metrics_v1`, `football_possessions_v1`, `football_scoring_ledger_v1`, `scoring_attribution_evidence_v1` (the four contracted in Appendix A), plus `point_in_time_matchups` (existing modelling dataset), `season_level_features_v1` (terminal-week per-season aggregates of `team_game_metrics_v1`, website and V5 populations kept separate) and `forecast_feature_frame_v1` (the refit feature frame with admitted-ledger offsets). The two new datasets are additive and change no accepted model design.
- **Write namespaces (6A, Preview only).** `lake/silver/`, `lake/gold/`, `rebuild/6a/<run_id>/` and `quality/receipts/`. Serving, selection and authorization prefixes are rejected. Preview and production R2 variables resolve to a shared bucket, so the harness verifies the configured bucket and endpoint against the plan and uses create-once writes: identical bytes are a no-op, different bytes fail.
- **Evidence ids.** Contract text says `cfbd_drives:<sha256 of group id and bundle hash>`. The 5C script truncated the digest to 20 hex characters. The 5C decision CSV and report hashes are unaffected (they do not contain the id). The Gold evidence builder uses the full sha256 per contract; the ledger conversion and verifier are updated to match when the evidence table is built.
- **Orchestration design.** A new `src/cks_picks_cfb/rebuild/` package (preflight, build, verify, publish) calls the existing pure builders with explicitly pinned parents. Legacy runners and their hardcoded pins are unchanged and used only for baseline reproduction. Build runs one season at a time; catalog registration is one transaction after R2 readback; the 2026 cutoff is a single exact UTC `as_of` in `conf/rebuild/6a_v1.yaml`, and the run stops at preflight if recorded evidence does not pin it.
- **Scope unchanged.** No production or serving writes; 2015-2019 and 2021-2025; `ppp__rho_0_60__exposure`; alpha-10 Ridge recipe. Task 4 (deltas, signed 6A receipt, published-stat comparison) remains a later step.

## Amendment 2 (2026-10-04): Silver parents corrected; `point_in_time_matchups` deferred

**Approval source:** user answers in the implementation chat of 2026-10-04 ("Pin Phase 2c Silver" and "Defer").

- **Correction (retraction kept visible).** The first `silver` build used the R1 derived ref set as its normalized parents on the basis that it traced to the same inputs as Step 5. That was **not verified and was wrong**: the R1 derived set covers 8,521 games, while the Step 5 population is 8,936 FBS-involved games (2024: 874 versus 920 games; byplay rows 125,027 versus 152,221). Its results (1,260,062 byplay rows, 245,671 nulled `ppa`) are **superseded** and must not be cited as the corrected Silver. The baseline reproduction (stage 1) is unaffected.
- **Decision.** `silver` takes its normalized parents from `conf/rebuild/phase2c_silver_parents_v1.json`, generated read-only by `scripts/pipeline/pin_6a_silver_parents.py` from the parent versions of each season's Step 5 byplay (`plays`, `fbs_involved_games`, `teams`, `team_game_stats`, `data_corrections`), with the legacy derived datasets kept only for like-for-like comparison. The file is a tracked input pin; these are normalized Silver datasets, not measurement or rating artifacts.
- **Evidence (smoke, local temp output, 10 seasons).** Games sum to 8,936. Byplay, drives, team-game and reconciliation row counts equal the Step 5 chain's in every season; per-game reconciliation classes have 0 mismatches; the only byplay value change is `ppa` (nulled count equals the legacy zero-`ppa` count in every season). Only 2025 shows a second change: 739 `Punt Return` plays move `st`/`st_punt` from 0 to 1 (the documented punt fix), which `verify` accepts only in that exact form. Earlier 626-row finding was against the wrong parent and is superseded.
- **Deferred.** `point_in_time_matchups` is removed from the 6A Gold scope: it needs wide matchup features from the older modelling pipeline and the V5 ratings and forecast do not use it. Deferral changes no V5 input. 6A Gold outputs are the four contracted datasets plus `season_level_features_v1` and, later, `forecast_feature_frame_v1`.
- **Stages 3-4 evidence (in-memory orchestrator smoke on live Preview, 2026-10-04; not yet a committed harness run).** `eligibility`: 8,936 games, 8,935 forecast-eligible, 8,903 measurement-usable (the legacy counts), 33 provider-declared omissions. `step5_comparison`: recomputed allocation groups equal the pinned Step 5 groups; the recomputed decision file is byte-identical to the pinned file; baseline 86,937, candidate 82,416 and admitted 85,457 events; the admitted ledger equals the stage-1 admitted ledger record for record; population parity with the legacy population; independent verifier ok. One check failed as first written and is now defined precisely: the 2025 punt-return flag change (739 plays) leaves possession keys, `possession_eligible`, `quality_reason`, `period_class` and every scoring event unchanged (eligible possessions 20,204 in both) and only moves 699 plays from eligible to ineligible across 698 possessions, with totals conserved on every possession (`mixed_eligibility` flips on 530). The gate now requires exactly that bounded form and fails on anything else. The first form of the check sorted on changed columns and so reported spurious differences in unrelated columns; superseded.

## Amendment 3 (2026-10-04): Gold stage findings on real data

Found by building and independently verifying the Gold datasets against the staged, zero-drift comparison outputs (development run; the committed harness run of `gold` is still to come). The 5B contract was written and tested on fixtures; real data exposed these.

- **`possession_eligible` means measurement-eligible in Gold (converter fix).** 33 possessions (of 316,257) carry the legacy eligible flag but an `unknown` period and the quality reason `ambiguous_drive_identity_or_period`, which violates the Gold invariant that an eligible possession is regulation and carries no quality reason. `possessions_to_v1` now sets `possession_eligible` only for regulation possessions without a quality reason; the legacy detail stays in the play counts and `quality_reason`. The metric builder already required all three conditions, so no metric or point total changes. This narrows the meaning of a field Task 1 and 5B defined only as "Boolean"; it is recorded here so it can be reversed before publication.
- **Impossible field position becomes unknown.** Three possessions in one 2016 game (400869725, Montana State/Idaho) have `start_yards_to_goal = 127`. They were already ineligible, so no measurement is affected; the converter sets values outside 0-100 to null (never clipped), and the Silver drive keeps the provider value.
- **Evidence design (decision recorded).** One evidence row per admitted group (1,416). The id is the full `cfbd_drives:<sha256 of group id and bundle hash>` the contract names (the 5C script truncated it to 20 hex characters; 5C decision hashes are unaffected). The locator is JSON naming the retained bundle and every event the group allocates; the source hash and bytes are checked against the pinned CFBD manifest. Terms and rights basis are the user-specified values from Amendment 3 of Appendix A, not an independent legal finding.
- **Partition digest round trip.** The writer digests the frame it is given and the reader digests what it reads back, so frames are normalized through the lake's own parquet round trip first; without this the ledger partitions failed lake-level verification.
- **Harness hardening.** A stage that fails before writing its manifest has its partial staged files discarded on retry (they collided with a rebuilt manifest's fresh timestamp); transient R2 read failures are retried a few times (reads only).
