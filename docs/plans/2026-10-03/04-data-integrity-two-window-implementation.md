# Data Integrity Repair in Two Windows

- **Status:** In Progress (Window 1 closed for implementation; Window 2 Step 5 closed 2026-10-04, 6A authorized but not started); Amendment 3 Approved 2026-10-04 (pre-6A execution contract approved; Preview R2 and Preview catalog writes permitted for 6A only; no serving or production writes)
- **Created:** 2026-10-03
- **Planner:** Sol
- **Approval source:** The user resolved the decision packet in this session and explicitly requested that the final plan be documented before implementation.
- **Amendment 1 approval:** User approved the recommended release-controller amendment with “Do it” in this chat on 2026-10-03, after explicitly authorizing implementation of the contract.
- **Implementation log:** `session_logs/2026-10-03/08-data-integrity-two-window-implementation.md` (existing partial Window 1 work; no release completion asserted).
- **Commit policy:** Make a separate documentation/plan commit on `dev`. Implementation commits are separate. Preview and production data writes remain user-run and require the exact release packet specified below.
- **Supersedes:** [01-unified-data-fix-and-matchup-rollout.md](01-unified-data-fix-and-matchup-rollout.md) as implementation authority. Its investigation is retained as evidence. This plan also absorbs the remaining Phase 2 scope in [team-stats-feeds-ratings](../2026-10-02/03-team-stats-feeds-ratings.md) and Phase B in [matchup-data-layer-v2](../2026-10-02/01-matchup-data-layer-v2.md).

## Goal

Repair the verified data-integrity defects without rewriting frozen prospective history or silently changing the meaning of an existing V5 result. Ship independent presentation and measurement fixes in **Window 1**, then ship a corrected scoring lineage, full historical rating rebuild with the unchanged forecast design, and corrected historical replay together in **Window 2** only after the scoring attribution evidence is sufficient.

Observable success is:

- every corrected source artifact and market selection has a new, immutable, versioned identity;
- Window 1 can serve independently while the present V5 rating lineage remains unchanged;
- Window 2 evaluates full R1 across the complete corpus and admits allocation changes only when independently corroborated, does not impute EPA, and preserves valid PPP when EPA is withheld;
- historical public performance shows the corrected reconstructed replay, while original frozen predictions, quotes, grades, and artifacts remain audit records;
- the public Performance page reports accuracy rather than financial return; and
- a failed Window 2 gate leaves the serving Window 1/V5 state intact.

## Current State and Constraints

The investigation reproduced the served V5 observations and ratings, so the current values are reproducible but contain known source and selection defects. The important distinctions are deliberate:

- The serving possession rating fits `ppp`; raw EPA is not a fitted V5 input. The 155 formerly zero-filled eligible null-`ppa` plays still corrupt EPA-derived measurements and display averages.
- R1 is the full monotone score-envelope rule capped by the certified final. It has a points-recovery channel and a separate attribution channel. Quarter totals corroborate recovery totals but cannot prove within-quarter attribution.
- Full R1 remains the complete-corpus candidate. Amendment 2 retains baseline allocations when evidence is insufficient, retains baseline quarantines, and certifies the complete admitted output. It does not authorize a V1 replacement or dropping difficult games to certify a subset.
- Frozen runs, selected quote records, original grades, and original artifacts are immutable audit evidence. A replacement replay must be a newly identified, explicitly reconstructed retrospective product.
- Tie behavior is **away** for spreads and **under** for totals everywhere: publisher, verifier, replay, display, and grading.
- No EPA imputation is authorized. Affected EPA measurements must be withheld with a reason; valid PPP and other independent measurements remain usable.
- User-run Preview and production actions remain outside this contract's code authorization. Extend the existing release controller under Amendment 1 to make corrected run selection and team-stat publication atomic; separate publisher commits do not satisfy this requirement.

## Scope

### Included

- Versioned market snapshots, deterministic best-line selection, frozen-side grading, and null-lean handling.
- Punt classification and missing-PPA masking for Silver/team-stat display measurements.
- Required venue capture and publication checks.
- Removing public profit, units, and ROI presentation while retaining accuracy, audit, and stored historical fields.
- Signed Gold `team_game_metrics` and scoring/possession ledgers as the shared source for season aggregation and V5 inputs; `team_game_stats` is the earlier logical name, not another dataset.
- Full R1 evidence and certification; corrected 2015–2019, 2021–2025 and eligible 2026 measurements; ratings, unchanged-design bridge refit, and replacement historical replay.
- Six pipeline admission gates and Preview/production rehearsal/rollback evidence.
- Matchup-data repinning and the 2025 historical backfill after the corrected Window 2 lineage is selected.

### Excluded

- EPA imputation, including same-play-type or turnover imputation.
- A V1 substitute or uncertified partial-corpus release; evidence-limited per-allocation baseline retention follows Appendix A.
- Neutral-site model changes (issue #9); these require a separate model contract. The measurement repair retains the accepted venue treatment.
- Any use of 2020 or 2026 outcomes in model fitting/tuning. Frozen audit objects are immutable; a new pre-kickoff freeze may supersede a public slate under Appendix B. Normal causal 2026 rating-state updates remain permitted.
- Structural production-boundary refactoring: exclusively the separate draft `2026-10-01/04-production-boundary-refactor.md`.
- Betting or staking decisions, public profit claims, and replacement of original audit records.

## Release Model

```text
Window 1: selection/display/data presentation fixes
    └─ independently verified → Preview → user production decision

Window 2: full R1 certification → corrected measurement/rating lineage
    → unchanged-design refit → all-certified-week reconstructed replay
    → atomic serving selection + team stats → user production decision
```

Window 1 is useful and releasable by itself. Window 2 is all-or-nothing: if any R1, data-lineage, refit, replay, or release gate fails, do not ship a subset. Preserve the serving Window 1 state and record the failed evidence.

Amendment 1 approved the original release-controller extension; Amendment 2 (approved 2026-10-04) revises its scope. It is not a prerequisite for Window 1. Window 1 implementation, validation, and its separately gated release may proceed while that extension is pending. Window 2 activation remains blocked until full R1 certification and the atomic release/rollback checks pass.

## Affected Components and Contracts

- Silver play enrichment, venue ingestion, team-stat aggregation, and their source-version manifests.
- Market canonicalization, database snapshot identities, selection publisher, grading/backfill scripts, and independent verifiers.
- Possession observations, intended-update measurement/rating runners, forecast offsets, historical/live forecast builders, and V5 release controls.
- `team_game_stats`, season aggregation, matchup publication, and V5 basic-stat consumers.
- The Performance dashboard, query layer, test fixtures, wording, and audit presentation.
- [known data issues](../../data/known_issues.md), [decision log](../../decisions/decision_log.md), [status](../../status.md), the weekly operator, and production runbook.

## Implementation Tasks

### Task 1 — Window 1 market selection, snapshot, and grading integrity

**Changes**

- Add a versioned snapshot identity that retains existing canonical spread/total fields and separately retains selected quote/point fields. Existing snapshots remain immutable.
- Reject conflicting writes for the same identity and accept byte-identical writes idempotently. A new run identifier alone must never mutate a prior snapshot.
- For an away spread, select the lowest home-signed line; then use price and quote ID as deterministic tie-breakers. Apply the equivalent deterministic rule to totals.
- Use away/under on exact ties in the publisher, independent verifier, replay, display helper, and grade calculation.
- Do not create a publisher default selection for a null lean. Preserve the frozen Week 5 legacy null-lean record without rewriting it.
- Grade using the frozen selected side and selected point, never a later canonical quote or a recomputed side from a different line.

**Acceptance criteria**

- Conflicting same-identity snapshots fail; identical retries are idempotent.
- The selected quote, displayed side, and grade share the same frozen decision record.
- Away-line counterfactual tests show lowest home-signed selection; exact ties choose away/under.

**Validation**

- Unit tests for sorting, ties, null leans, identity conflicts, and grade consistency.
- Independent verifier fixtures with disagreeing books and late quotes.
- Reproduce original stored grades before generating any replacement replay.

### Task 2 — Window 1 Silver, display, and venue repairs

**Changes**

- Record missing `ppa` before any legacy compatibility fill and carry an explicit missingness flag/reason through Silver.
- Preserve legacy stored PPA for current V5 compatibility in Window 1, but calculate displayed averages with missing PPA masked.
- Tag punt returns/special-teams rows consistently and exclude them from the appropriate team-stat measurements.
- Keep the existing points-per-scoring-opportunity rule until full R1 is certified. Candidate R1 code may exist but must not serve data or ratings.
- Build and promote a new pinned venue capture/version. Verify city availability for every published game; legitimate international city-only venues remain allowed.
- Document the interim divergence: Window 1 presentation/team statistics improve while the V5 rating lineage stays unchanged.

**Acceptance criteria**

- A null PPA is distinguishable from a numerical zero.
- Affected EPA display averages exclude missing entries, while valid PPP stays available.
- Punt filtering and venue coverage are proven from immutable input versions in both environments.

**Validation**

- Null-versus-zero, punt-return, and venue-missing fixtures.
- Preview dry run rejects a scheduled published game lacking required venue city information.
- Compare source-version manifests and output hashes across Preview and production rehearsal inputs.

### Task 3 — Window 1 Performance accuracy presentation

**Changes**

- Remove public profit, units, ROI, payout assumptions, and financial copy from cards, tables, summaries, and derived UI computations.
- Retain spread/total record, win rate, forecast MAE, interval coverage, and audit/provenance context.
- Replace "closing line" language with truthful captured-line wording. Preserve stored historic financial fields and make price provenance distinguish actual from defaulted values in audit views.

**Acceptance criteria**

- No public metric represents a default -110 price as an observed payout.
- MAE continues to compare forecasts with certified actual outcomes.

**Validation**

- UI/component tests plus lint, typecheck, build, and Playwright checks.
- Manual Preview review of mobile and desktop Performance pages.

### Task 4 — Window 1 release gate

**Changes**

- Create a Window 1 release receipt containing code SHA, input/output identities, verifier output, venue coverage, and the known V5-lineage limitation.
- Rehearse Preview serving and rollback. Ask for the production decision only after those receipts are reviewable.

**Acceptance criteria**

- Window 1 can be selected and rolled back without changing ratings, forecasts, or frozen prospective data.

## Window 2 — Ordered Work and Admission Gates

Read [Amendment 2](#amendment-2-window-2-measurement-repair-and-prospective-cutover-2026-10-04) and both appendices before starting any Window 2 task. The existing investigation is the baseline; there is no new inventory phase. Window 1 completes independently first. Each row is a bounded implementation session with a retained receipt and explicit exit gate.

| Task | Deliverable | Exit gate / dependency |
|---|---|---|
| **5A** Baseline and sizing | Reproduce baseline; size full R1 changes and CFBD-drive corroboration | At least 25% of historical changed allocation groups corroborated; otherwise stop and retain baseline |
| **5B** Shared data contracts | Registry, signed metrics/ledgers, rebuilt Silver PPA missingness, shared consumers | Schema, population, null propagation and served PPP-only tests pass; no structural refactor |
| **5C** Independent certification | Complete-corpus admitted output and delta report | Evidence-backed changes; insufficient evidence retains baseline; full-output identity/attribution verification passes |
| **6A** Historical rebuild | Full historical measurements, ratings, priors, offsets and unchanged-design Ridge refit | Pinned lineage and independent verification; no 2020 or 2026 fitting/tuning; no neutral-site design change |
| **6B** Completed-week replay | Newly identified reconstructed replay of every certified completed week | Original cutoffs/quotes, certified finals, immutable originals, truthful retrospective labels |
| **7A** Release foundations | Migrations, authorization/revocation controls, web selectors and state guards | Contracts/grants, unit/publication/browser tests and real Preview verification pass |
| **7B** Exact release and cutover | Fix N, build packet, prior user authorization, atomic selection/statistics, freeze and rollback | Complete receipts, fresh quotes for new freeze, race checks, Preview rehearsal, separate exact production decision |
| **8** Matchup completion | Corrected matchup repin and 2025 historical backfill last | Matchup/ratings/stat lineage agrees in Preview and production; issue register reconciled |

### Task 5 — Signed metrics and scoring certification

[Appendix A](window2/data-contracts-and-certification.md) defines exact schemas, keys, fields, storage locations, formulas, populations, evidence precedence and the 5A go/no-go. CFBD drives are primary evidence after consistency checks; retained official gamebooks resolve conflicts or failed drive checks. Full R1 is evaluated across the whole corpus. Missing evidence alone retains the baseline allocation; a failed integrity gate holds the complete release. No EPA imputation is permitted.

### Task 6 — Rebuild and reconstructed replay

Appendix A defines the full historical rebuild and consumers. Preserve the selected PPP rating design and accepted alpha-10 bridge recipe, including existing venue constants. Replace every certified completed week's public retrospective selection through new identities; preserve original prospective freezes and grades. No new neutral-site model term is included.

### Task 7 — Schema, web, authorization and release

[Appendix B](window2/release-schema-and-web.md) defines planned migrations 0022+, explicit role grants, prior user-run authorization, append-only revocations, atomic batch verification/selection, prospective records, Performance separation, matchup guard and tests. The pipeline never inserts approval or authorization rows. N is fixed only when the release packet is built after certification, not targeted at Week 6. Until then, weekly operation continues on the current lineage.

### Task 8 — Matchup and issue completion

Appendix B defines matchup repinning, bounded updating/unavailable states, rollback and the 2025 backfill as the final step. Issue #5 is closed by investigation evidence, not a Window 2 fix. Issue #9 remains open under separate model scope. Partial local Window 1 code is not proof of production repair.

## Prevention Gates

1. **Score and box reconciliation:** configured checks must run, record comparisons, and fail if columns are missing or a known conflict is unexplained.
2. **Market coverage:** record unmatched events and reconcile fresh spread/total coverage against the complete eligible FBS schedule.
3. **Venue coverage:** fail publication if a required published game lacks a valid venue/city record.
4. **Price provenance:** distinguish actual prices from defaulted values; lack of actual price is an audit fact, not a release blocker.
5. **Points identity:** record offense/non-offense/excluded/OT-final identities; unresolved identities are not usable as complete observations.
6. **Earlier-game refresh:** pin captures, versions, timestamps, and hashes for completed-game corrections before they can enter a new prospective measurement build.

## Testing Strategy

- Focused Python tests for canonicalization, snapshot conflicts, frozen grading, score envelopes, measurement missingness, signed team-game records, and replay cutoff rules.
- Independent verifiers for market selection, scoring attribution, measurement lineage, ratings, bridge/replay, and serving payloads; they must not duplicate the implementation's faulty assumptions.
- Scoped Ruff and contract checks; documentation build; web lint, typecheck, publication tests, production build, and Playwright.
- Real Preview database verification and a rollback rehearsal. Fixtures alone are insufficient for selection, provenance, and optional-table behavior.

## Risks and Edge Cases

- Quarter totals validate totals, not every drive's attribution. That is why Window 2 requires additional event/drive evidence and may remain held.
- Provider corrections are allowed only in a labeled reconstruction. They cannot silently alter frozen prospective evidence.
- Snapshot versioning must preserve legacy audit access while preventing `ON CONFLICT` behavior from overwriting a prior quote identity.
- The rating and forecast reports must not conflate raw PPP movement with opponent-adjusted rating movement or bridge output movement.
- International venues may have no state but must retain a valid city and provenance.
- Price data may remain unavailable; it changes public explanation and audit records, not the ability to show accuracy.

## Definition of Done

- [ ] Window 1 has a complete release receipt, verification, and rollback rehearsal.
- [ ] Window 1 production selection occurs only after the user approves its exact release packet.
- [ ] Full R1 sizing and independent complete-output certification either permit Window 2 or record a hold; per-allocation baseline retention follows Appendix A.
- [ ] If certified, Window 2 has corrected signed measurement/rating/forecast lineage, unchanged-design refit, and all-certified-week replay.
- [ ] Public history and Performance pages are truthful about reconstruction, line timing, accuracy, and price provenance.
- [ ] Preview and production release receipts verify atomic serving selection, matchup repin, and rollback.
- [ ] Required tests and documentation checks pass; status, decision log, known-issues register, and session log are updated.
- [ ] Status changes to `Implemented` only after both authorized windows and their required release decisions complete.

### Window 1 progress (2026-10-04)

The definition-of-done boxes above stay unchecked until the Window 1 release receipt is signed and, for the later items, Window 2 completes. Task status on `dev`:

- [x] Task 1 market selection, snapshot identity and grading: code and tests committed (`850ca38`); the independent verifier's line ordering and tie rule corrected. Real Preview rehearsal still open.
- [x] Task 2 Silver, display and venue repairs: `ppa_missing` before fill, punt filtering (earlier commit), venue city gate and pinned publisher (`562b2b2`); Preview venue write verified 271/271.
- [x] Task 3 accuracy-only Performance: committed with the original design preserved; Playwright 28/28.
- [x] Task 4 release receipt: filled; Preview venue write and the Week 1 Preview serving rehearsal verified (public state unchanged); Window 1 closed for implementation by user sign-off 2026-10-04. The production release and production venue publish are a separate user decision. Public select-and-restore is a Window 2 controller item, not rehearsed.

## Amendments

Any change to R1 scope, EPA treatment, replay cutoff policy, data identities, neutral refit design, or atomic-release behavior is material. Terra must stop, append an amendment for user review, and not implement that change under this contract.

### Amendment 1 — Atomic team-stat release control (approved 2026-10-03)

- **Expected:** Task 7 can atomically select corrected runs and publish corrected team statistics through existing release controls while preserving ongoing/future pointers.
- **Actual:** `scripts/pipeline/select_v5_intended_update_batch.py::run` commits `select_week_runs_batch`; that helper updates public run pointers and recomputes performance `system_stats`, but does not publish `team_season_stats`. `scripts/pipeline/publish_team_stats.py` upserts team statistics in a separate connection/transaction and commits independently. The selector's packet has no team-stat payload binding or rollback payload. `select_week_run` also updates `current_week.active_run_id` when its week is included, without an explicit completed-week-only guard in the batch packet.
- **Material conflict:** Separate commits cannot provide the required all-or-nothing corrected run/team-stat release or rollback. Operator ordering alone cannot satisfy the acceptance criterion. Extending the release packet and transaction boundary changes the release interface and atomic-release behavior, which this contract explicitly treats as material.
- **Approval:** User approved the recommended fix with “Do it” after reviewing the conflict and proposed requirements. This amendment authorizes the controller/packet extension below; it does not authorize executing Preview/production writes or waive full R1 certification.
- **Dependency:** Resume Window 1 Task 1 independently. Build and verify this extension before Window 2 activation; do not pause Window 1 merely because this Window 2 capability is incomplete.

#### Release packet and retained payloads

- Add `v5_intended_update_batch_selection_v2` to the existing controller. Keep the v1 path for existing operational callers; only v2 can satisfy this contract's Window 2 atomic-release gate.
- Retain `environment`, `season`, `expected_current_runs`, `replacement_runs`, and `decision_ref`. Add `certified_completed_weeks`, `protected_runs` (all existing ongoing/future public selections plus the current-week pointer), `team_stats_scope` (explicit season/as-of-week snapshots), and `team_stats_before`, `team_stats_after`, and `team_stats_verifier` references, each containing immutable `uri` and raw-byte `sha256`.
- Each signed `v5_team_stats_release_payload_v1` contains environment, season, snapshot scope, source/rating manifest identities, and deterministically ordered rows using the existing team-season-stat upsert columns. The signed independent verifier binds both payload checksums, corrected lineage, complete scope/key coverage, and verification result. Actual database state must match the prior payload; a declared checksum alone is not sufficient.
- Retain the prior payload, candidate payload, verifier, and release/rollback packets as new immutable R2 artifacts using existing artifact storage and signature conventions. Preparation emits reviewable files for user-run staging and does not write serving tables. Never overwrite these retained artifacts on retry.
- Candidate and prior payloads must cover the same complete row-key set for every scoped snapshot, with no duplicate keys. Compare stored business fields and provenance; exclude database-maintained timestamps from payload identity. Reject extra/missing keys rather than silently delete rows or widen grants. A required key-set/schema change needs a separate amendment.
- The release packet and decision reference bind the exact candidate objects; the rollback packet reverses expected/replacement runs and before/after payload references, uses a verifier for the reversed operation, and retains the same protected-run guards. Review both before release.

#### Transaction and protection rules

- Before mutation, verify immutable bytes, signatures, independent certification, source/rating bindings, and payload scope. Require replacements to cover every certified completed week at release and no other week; check certification against authoritative stored run/finals state, not only a packet declaration. Quote/replay cutoff checks remain unchanged.
- Preserve environment identity checks, active pipeline lease, and exact per-run authorization. Acquire write-conflicting table locks for public/current selections and team-season statistics in a fixed order, then compare expected selections, protected pointers, and the complete prior team-stat payload inside the transaction. Reject stale state before any write.
- Within that same connection/transaction, use the existing selection helpers for eligible completed-week pointers, upsert the candidate team-stat rows through a cursor-level helper, and recompute `system_stats` from the new selected runs. No helper may independently commit or open a second publication connection.
- Read back selected runs, complete scoped team-stat business rows, and protected pointers before the single final commit. Any validation, write, or readback failure rolls back all writes. Payload scope must exclude future snapshots; current-week team-stat snapshots may reflect corrected completed games only, with their cutoff/source evidence verified and the current forecast pointer unchanged.
- Rollback uses the same guarded transaction with the retained prior payload and selections, including performance recomputation and readback. It is separately user-run under the reviewed release packet; the code must never substitute best-effort sequential commits for atomic rollback.
- Validate failure injection, successful apply/rollback, stale state, wrong environment, invalid signatures/checksums, duplicate or incomplete keys, and protected-week rejection. Real Preview rehearsal and read-only evidence are required before any exact production decision.


### Amendment 2 — Window 2 measurement repair and prospective cutover (2026-10-04)

**Status: Approved 2026-10-04.** Approval source: the user selected “Approve it now (Recommended)” when asked in the planning chat whether to approve Amendment 2 and both appendices. This authorizes Window 2 implementation sessions 5A, 5B, 5C, 6A, 6B, 7A, 7B and 8, each started by an explicit instruction naming this contract, in the stated order and gates (5A's 25% go/no-go stops the rest). It is not an exact Preview/production release decision; every data, authorization and selection write stays user-run. Window 1 finishes first. Window 1's existing authorization and independent delivery remain intact.

**Reading order and precedence:** this contract → [Appendix A: data contracts and certification](window2/data-contracts-and-certification.md) → [Appendix B: release, schema and web](window2/release-schema-and-web.md). Both appendices are normative parts of Amendment 2, not competing contracts. Amendment 2 supersedes conflicting Window 2 text and the specified Amendment 1 restrictions. Amendment 1 above is preserved as the historical approved design: its completed-only/current-pointer protection expands to the exact pending N cutover, with the new prospective/revocation schema. Its same-key team-stat payload, retained rollback evidence and single-transaction guarantees continue to apply. Approval writes stay separate from selection.

| Decision | Documented resolution |
|---|---|
| D1 — scoring | Full R1 candidate; corroborated allocation changes only, otherwise baseline retained; full-output certification |
| D2 — EPA | Restore source missingness, never impute; explicitly withhold affected EPA while retaining independent PPP |
| D3 — storage | New immutable Silver and signed Gold datasets; R2 is canonical, Neon holds derived serving/operations records |
| D4 — rebuild | Complete historical corpus and eligible 2026 state/replay; unchanged rating/bridge design; neutral model change excluded |
| D5 — history | 2025 matchup backfill last; replacements are retrospective, original prospective records retained |
| D6 — site | Matchup pages remain live; mismatched lineage renders updating/unavailable and disables sharing |

**Review changelog:** replaces the monolithic phase proposal with Tasks 5A–8 under the approved two-window architecture; removes redundant discovery and production-boundary refactoring; supplies exact data/registry contracts and null-consumer tests; restores CFBD drives and adds the 25% sizing gate; separates user authorization and append-only revocation from pipeline selection; specifies migrations/grants/schema synchronization, selectors, freeze checks and web tests including real Preview; fixes N at packet creation; scopes prospective records to V5 Week 5 onward (V4 Weeks 0–4 remain audit/rollback); specifies new-freeze quote timing and possible pre-kickoff lean changes; reconciles issue #5 and requires proof that served ratings never select EPA candidates.

The original October 3 investigation and decision packet remain evidence, not current conflicting instructions. See the [planning persistence log](../../../session_logs/2026-10-04/01-window2-amendment-planning.md). No code, migration, data rebuild, database write or release is performed by saving these documents.

### Amendment 3 — Pre-6A integrity review and rebuild contract (2026-10-04)

**Approved:** the user explicitly requested implementation of the reviewed pre-Stage-6 plan and selected Preview R2 plus Preview catalog registration. Execute [the bounded contract](../2026-10-04/02-pre-stage6-integrity-and-rebuild.md) in a fresh Terra session after this documentation-only Sol persistence.

Step 5 remains closed as local evidence. The review found missing-source/null-opportunity handling, season isolation and reverted-allocation semantics that must be repaired before the full rebuild. Existing runners also require explicit corrected measurement/prior/offset integration. These prerequisites refine 6A; they do not invalidate the retained historical Step 5 receipts or certify new datasets.

**Precedence:** this amendment and Appendix A Amendment 4 supersede earlier blanket prohibitions on Preview writes solely for 6A immutable Preview R2 artifacts and verified Preview catalog/schema/lineage/reconciliation metadata. They authorize no serving, selection, approval, production or release writes. Pipeline authorization insertion remains prohibited. Stage 6B reconstruction and Stages 7–8 activation/freeze/rollback/matchup completion remain separately gated. Earlier dated authorization text is retained as history.

### Amendment 4 — Week 5 legacy freeze attestation (2026-10-06)

**Status: Approved for contract persistence and Stage 7B implementation planning.** Approval source: the user approved the reviewed Option 1 amendment plan with “proceed” after reviewing the original Week 5 freeze evidence and the limits of the repository's checksum convention. This amendment changes only how the already completed 2026 Week 5 live freeze may be designated in the prospective series when no contemporaneous signed freeze receipt was created. It authorizes no Preview or Production migration, R2 write, prospective-record insert, authorization, selection, freeze, matchup publication, or serving-state change. Each such operation remains separately user-run under the Stage 7B gates.

**Evidence basis:** The Stage 7B preflight recovered environment-specific original Week 5 live run records, public selection history, freeze activation history, successful pipeline/step records, pre-kickoff timestamps and original prediction artifacts. The historical freeze implementation did not emit an immutable signed freeze receipt, and the bounded R2 search found none. This is a historical implementation gap; no receipt may be represented as having existed at the September freeze time.

**Narrow exception:** If a further bounded search finds an authentic contemporaneous receipt for an environment, use and verify that receipt. Otherwise, Stage 7B may create one `v5_legacy_freeze_attestation_v1` for the original Week 5 prospective freeze in that environment, subject to the Appendix B requirements. Preview and Production require separate attestations from their own original records. The attestation's `attested_at` is its actual creation time; its `frozen_at` and selection/freeze event times are historical observations copied from authoritative records. The payload must explicitly state that no contemporaneous receipt exists and describe the limits of retrospective attestation.

The attestation uses the existing canonical-content checksum convention and a content-addressed immutable R2 object. That checksum detects byte changes; it does not cryptographically authenticate a human signer. Record the approved amendment/operation decision reference and the verified environment-specific registration execution identity separately. Do not describe this artifact as cryptographically signed or as the original freeze receipt. No signing-key system is introduced by this amendment.

The canonical payload fields are `schema_version`, `evidence_class`, `environment`, `season`, `week`, `run_id`, `attested_at`, `decision_ref`, `run_frozen_at`, `first_kickoff_utc`, `freeze_activation`, `pre_kickoff_selection_history`, `freeze_pipeline`, `historical_freeze_code_sha`, `original_prediction_manifest`, `original_prediction_artifact`, `contemporaneous_schedule_evidence`, `current_schedule_check`, `source_snapshot_refs`, `limitations`, and `manifest_sha256`. The creation time is generated by the guarded registration operation and cannot be supplied or backdated by its caller. `evidence_class` is `legacy_attested_prospective`; `limitations` explicitly states that no contemporaneous freeze receipt exists and the artifact was prepared after kickoff.

The attestation binds the exact environment, season/week/run, actual attestation creation time, run `frozen_at`, freeze activation ID/time/metadata, every relevant pre-kickoff selection-history row ordered by `selected_at, selection_id`, successful pipeline/step identity and return code, first kickoff, historical freeze code commit, original prediction manifest and CSV URIs and raw SHA-256 values, and retained source-query snapshot references and hashes. Verify the original cutoff against both contemporaneous retained schedule evidence and the current schedule; the selection and freeze events that establish prospective status must precede the earliest kickoff. Include later history when present to show the full timeline, but it cannot establish pre-kickoff status. Re-derive that the designated run was the last valid publicly selected and frozen V5 run before kickoff. Current selection alone is insufficient. An absent, conflicting, ambiguous or altered source fails closed.

For this single 2026 Week 5 exception, `freeze_receipt_uri` and `freeze_receipt_sha256` in `public.prospective_week_records` refer to the legacy attestation object and its raw-byte digest. The SQL schema, non-null constraints, and migrations 0023/0024 remain unchanged. The application verifier must recognize the explicit `v5_legacy_freeze_attestation_v1` schema only for Week 5, validate its raw hash and canonical checksum, compare all bound facts against fresh read-only database and R2 evidence, and reject it for every other week. The v2 packet preflight/apply path must verify the attestation, rather than trusting the prospective-record row or packet declaration. Performance and audit views must label this record as retrospectively attested; later weeks continue to require the ordinary contemporaneous `v5_prospective_freeze_receipt_v1`.

Implement the builder and independent verifier in `src/cks_picks_cfb/ops/prospective_records.py`, the user-run entrypoint at `scripts/pipeline/register_v5_legacy_freeze_attestation.py`, and the receipt branch in `src/cks_picks_cfb/ops/v5_batch_selection_v2.py`. Use a distinct immutable URI containing environment, season, week, run ID and `legacy-attestation-v1`; bind URI kind to payload schema and reject unknown kinds. Stage 7B and Performance provenance display this as a legacy attestation from the constrained URI kind and validated payload. Packet preparation and v2 preflight/apply perform storage hash, canonical checksum and source re-derivation.

Registration is a distinct, exact, user-run operation for each environment, with dry-run and apply modes and the existing environment/identity guards. It writes the immutable attestation first, inserts only the matching Week 5 prospective row, and reads back both; an exact retry is idempotent and a conflict fails. An orphaned immutable object after a database failure is reported and safely reusable only when its bytes match. No production or Preview serving, selection, grade, current-week, freeze or authorization state is changed by registration. This amendment does not choose cutover `N`; all later Stage 7B preflights and releases remain unchanged.

**Acceptance:** focused tests prove environment separation, exact source re-derivation, timestamps, last-valid-freeze selection, immutable writes, idempotent registration and v2 packet verification. Altered source bytes, recomputed-but-inconsistent attestation hashes, wrong run/environment, later or ambiguous selection, missing kickoff evidence, nonzero pipeline return, conflicting activation, invalid time ordering, duplicate/conflicting registration and use outside Week 5 all fail closed. Production schema/grant parity, fresh schedule/quote certification, dynamic `N`, authorizations, Preview rehearsal, Production decision, freeze, repin and rollback remain separate Stage 7B gates.

The [Stage 7B contract](../2026-10-06/02-stage7b-exact-release-and-cutover.md) records the implementation sequence. The prior preflight hold remains an accurate report of the evidence and policy at capture time; this amendment resolves its policy question but does not itself satisfy environment-specific registration or release gates.

### Amendment 5 — Preview staging environment legacy freeze pipeline ledger adjudication (2026-10-06)

**Status: Approved for contract persistence and Stage 7B execution.** Fresh read-only evidence verified that Production retains the matching successful `freeze-week` pipeline run (`816d7d02c2364547bb5ad569b3113f25`) and step, with matching freeze activation and pre-kickoff timeline. In Preview, the authentic freeze activation (`2026w5-v5repair-20260929-p2` at 2026-09-29 20:43:53Z with `freeze_coverage_complete=true`), matching `prediction_runs` row, and selection history are present, but the Preview staging environment executed `scripts/pipeline/freeze_week.py` directly without wrapping it in the `run_pipeline.py --command freeze-week` harness; therefore, no matching `ops.pipeline_runs` row exists in Preview.

**Adjudication:**
1. In `preview` only, when `ops.activation_history` contains the authentic freeze activation (`action='freeze'`, `freeze_coverage_complete=true`), matching `prediction_runs` state, and pre-kickoff selection history, `freeze_pipeline` may be `null` in the legacy attestation payload.
2. The Preview attestation `limitations` list must explicitly include: `"In Preview staging, the original Week 5 freeze was executed directly via freeze_week.py and recorded in ops.activation_history without an enclosing ops.pipeline_runs harness record."`
3. In `production`, `freeze_pipeline` strictly requires the matching successful `freeze-week` pipeline run and `freeze` step (verified present in Production).
4. No change is made to SQL migrations, prospective table schemas, or Production requirements.

### Amendment 6 — Team-stat provenance may change when the verifier binds it (2026-10-07)

**Status: Approved by the user in session (2026-10-07); implemented in `src/cks_picks_cfb/ops/v5_batch_selection_v2.py` with tests.** Material change to atomic-release validation, recorded here because this contract treats release-controller behavior as material.

**Finding.** The v2 controller rejected any packet whose team-stat `source_versions` differed between the before and after payloads ("team-stats provenance changed across the packet"). Corrected statistics are built from corrected Silver, so their `source_versions` necessarily differ, and Appendix B says to include the new versions there. As written, the controller would have rejected every legitimate corrected payload on every release path. Writing the old provenance into corrected rows to pass would falsify it and is not permitted.

**Decision.** Provenance may change if and only if the independent team-stats verifier receipt (already required to be `verified`, bound to both payload raw hashes and the decision reference) carries a `provenance_change` object with `keys_changed` equal to the number of keys whose `source_versions` differ, and `before_provenance_sha256` and `after_provenance_sha256` equal to `stats_provenance_digest` of the before and after rows (a canonical hash of every key and its `source_versions`). Changed provenance must be a nonempty mapping. Complete key sets, scope equality, payload hashes and the database before-state check are unchanged; an unchanged-provenance packet validates exactly as before. Rollback packets use the same rule for the reversed payloads.

**Tests.** Accepts bound changed provenance; rejects unbound changes, a tampered digest and an empty mapping; the digest is order independent and sensitive to every key. Five of the new tests fail on the previous controller.

### Track 1 Window 1 release preparation — 2026-10-07

The [Track 1 preparation receipt](../2026-10-07/track1-release-packet.md) records fresh pinned Production venue dry-run coverage, exact before/proposed payloads, effective web grants, independently verified prospective designations and unchanged serving fingerprints. Local validation passes, including the explicitly authorized web SQL-shape repair. This is a HOLD receipt: rating-source binding is now repaired under the approved lineage contract, while exact-SHA CI/real Preview verification remain open. No Production venue publication, branch promotion, Window 2 activation or completed Window 1 production receipt is asserted.
