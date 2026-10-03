# Data Integrity Repair in Two Windows

- **Status:** Approved
- **Created:** 2026-10-03
- **Planner:** Sol
- **Approval source:** The user resolved the decision packet in this session and explicitly requested that the final plan be documented before implementation.
- **Implementation log:** `session_logs/2026-10-03/08-data-integrity-two-window-implementation.md` (Terra creates it when work begins).
- **Commit policy:** Make a separate documentation/plan commit on `dev`. Implementation commits are separate. Preview and production data writes remain user-run and require the exact release packet specified below.
- **Supersedes:** [01-unified-data-fix-and-matchup-rollout.md](01-unified-data-fix-and-matchup-rollout.md) as implementation authority. Its investigation is retained as evidence. This plan also absorbs the remaining Phase 2 scope in [team-stats-feeds-ratings](../2026-10-02/03-team-stats-feeds-ratings.md) and Phase B in [matchup-data-layer-v2](../2026-10-02/01-matchup-data-layer-v2.md).

## Goal

Repair the verified data-integrity defects without rewriting frozen prospective history or silently changing the meaning of an existing V5 result. Ship independent presentation and measurement fixes in **Window 1**, then ship a corrected scoring lineage, full R1 rating rebuild, neutral-venue refit, and corrected historical replay together in **Window 2** only after the scoring attribution evidence is sufficient.

Observable success is:

- every corrected source artifact and market selection has a new, immutable, versioned identity;
- Window 1 can serve independently while the present V5 rating lineage remains unchanged;
- Window 2 uses full R1 only when attribution is independently validated, does not impute EPA, and preserves valid PPP when EPA is withheld;
- historical public performance shows the corrected reconstructed replay, while original frozen predictions, quotes, grades, and artifacts remain audit records;
- the public Performance page reports accuracy rather than financial return; and
- a failed Window 2 gate leaves the serving Window 1/V5 state intact.

## Current State and Constraints

The investigation reproduced the served V5 observations and ratings, so the current values are reproducible but contain known source and selection defects. The important distinctions are deliberate:

- The serving possession rating fits `ppp`; raw EPA is not a fitted V5 input. The 155 formerly zero-filled eligible null-`ppa` plays still corrupt EPA-derived measurements and display averages.
- R1 is the full monotone score-envelope rule capped by the certified final. It has a points-recovery channel and a separate attribution channel. Quarter totals corroborate recovery totals but cannot prove within-quarter attribution.
- The user selected full R1 as the Window 2 candidate, not the narrower V1 subset. Window 2 therefore requires additional scoring-attribution evidence; no narrower fallback and no partial certified subset are authorized.
- Frozen runs, selected quote records, original grades, and original artifacts are immutable audit evidence. A replacement replay must be a newly identified, explicitly reconstructed retrospective product.
- Tie behavior is **away** for spreads and **under** for totals everywhere: publisher, verifier, replay, display, and grading.
- No EPA imputation is authorized. Affected EPA measurements must be withheld with a reason; valid PPP and other independent measurements remain usable.
- User-run Preview and production actions remain outside this contract's code authorization. Production selection and team-stat publication are atomic only through the existing operational controls.

## Scope

### Included

- Versioned market snapshots, deterministic best-line selection, frozen-side grading, and null-lean handling.
- Punt classification and missing-PPA masking for Silver/team-stat display measurements.
- Required venue capture and publication checks.
- Removing public profit, units, and ROI presentation while retaining accuracy, audit, and stored historical fields.
- Signed `team_game_stats` as the basic-stat source for season aggregation and V5 inputs.
- Full R1 evidence, certification, corrected 2025/2026 measurements, ratings, bridge refit, neutral-venue treatment, and replacement historical replay.
- Six pipeline admission gates and Preview/production rehearsal/rollback evidence.
- Matchup-data repinning and the 2025 historical backfill after the corrected Window 2 lineage is selected.

### Excluded

- EPA imputation, including same-play-type or turnover imputation.
- A V1 or other narrower fallback release if full R1 cannot be certified.
- A separate neutral-site offset release before Window 2.
- Any use of 2020, any 2026 outcome in model fitting or tuning, and any change to an ongoing or future frozen slate.
- Betting or staking decisions, public profit claims, and replacement of original audit records.

## Release Model

```text
Window 1: selection/display/data presentation fixes
    └─ independently verified → Preview → user production decision

Window 2: full R1 certification → corrected measurement/rating lineage
    → neutral-aware refit → all-certified-week reconstructed replay
    → atomic serving selection + team stats → user production decision
```

Window 1 is useful and releasable by itself. Window 2 is all-or-nothing: if any R1, data-lineage, refit, replay, or release gate fails, do not ship a subset. Preserve the serving Window 1 state and record the failed evidence.

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

## Window 2 Admission Gate — Full R1 Scoring Certification

Do not begin the Window 2 serving/replay sequence until all conditions below are met.

1. Define a full R1 envelope: monotone running-score reconstruction capped by certified final score, with a complete record of unresolved jumps and attribution changes.
2. Separate and report the points-recovery channel from the attribution-only channel.
3. Validate attribution using quarter totals **and** corroborating event/drive evidence capable of addressing attribution. A capped final-score identity alone is insufficient evidence.
4. Produce an independent measurement/rating delta report. The materiality criterion remains movement greater than 0.05 raw PPP or more than five ranks, but it counts only independently corroborated movement.
5. Reconcile every unresolved observation explicitly. No missing score or PPA is converted to zero to make a gate pass.

If this gate fails, mark Window 2 held. Do not replace R1 with V1, ship a certified subset, or release neutral treatment independently.

### Task 5 — Window 2 signed team-game-stat contract and corrected measurements

**Changes**

- Define signed `team_game_stats` records keyed by game, team, role, metric, numerator, denominator, coverage, and provenance.
- Make season aggregation and V5 consume these records for basic statistics rather than duplicate aggregation logic. Timing and opponent adjustment retain their existing rating-layer ownership.
- Build corrected 2025 terminal measurements and 2026 measurements from pinned source versions. Rebuild 2026 priors from corrected historical parents when required by the lineage.
- Withhold EPA only for measurements affected by missing PPA, recording the reason and coverage. Do not impute. Keep PPP and other independent measures usable.
- Obtain verified neutral/non-neutral venue context for both historical and live workflows.

**Acceptance criteria**

- Every downstream basic statistic has a traceable signed parent.
- Missing PPA produces explicit withheld EPA, never artificial zero or imputed EPA.
- Non-offense offsets derive from their regulated event ledger, never from missing data treated as zero.

**Validation**

- Schema/contract checks, coverage reconciliation, and lineage signature verification.
- Tests proving independent PPP remains usable when EPA is withheld.
- Baseline reproduction before applying deltas; separate reports for raw PPP, adjusted ratings, priors, offsets, and forecast bridge.

### Task 6 — Window 2 ratings, neutral-aware refit, and corrected replay

**Changes**

- Run the certified full R1 measurement/rating rebuild and retain the old lineage unchanged.
- Refit the existing Ridge recipe and calibration using 2015–2019 and 2021–2025, excluding 2020 and all 2026 outcomes from fitting/tuning. The accepted alpha 10 design remains unchanged except for verified venue context.
- Ship neutral-venue treatment only as part of this certified Window 2 refit. Report historical neutral/non-neutral baselines; use the existing 2025 diagnostic as context rather than a new untouched holdout claim.
- Generate a new historical replay for **all certified completed weeks at release**, with the manifest enumerating game IDs, original forecast cutoffs, original quote sets, corrected input references, and rollback targets.
- Use only quotes at or before the original forecast cutoff and before kickoff. A missing historical line remains unlined; later quotes may not fill it.
- Treat later provider corrections to earlier completed games as corrected reconstruction and label the output retrospective. Do not present it as prospective evidence.

**Acceptance criteria**

- Original frozen runs and grades remain readable as stored audit records.
- Replacement predictions, grades, market snapshots, measurements, and ratings have new immutable identities.
- Corrected public history is labeled reconstructed retrospective and covers all certified completed weeks available at release.

**Validation**

- Reject late quotes and target/future outcomes in replay fixtures.
- Verify replacement grades against certified actuals and the newly frozen selected quote.
- Verify old-as-stored grades reproduce exactly before replacement results are published.

### Task 7 — Window 2 release, serving, and matchup completion

**Changes**

- Stage the full corrected lineage on Preview, verify all components, and rehearse rollback to the existing selected lineage.
- Atomically select the corrected serving run and corrected team statistics using existing release controls. Preserve current ongoing/future pointers.
- Repin matchup data to the corrected rating manifest and complete the 2025 matchup historical backfill last, labeled `historical_replay`.
- Permit future prospective activation only for a slate that has not begun and meets fresh line/coverage/freeze gates.

**Acceptance criteria**

- A full Window 2 failure leaves the current Window 1/V5 serving state intact.
- The release packet identifies every selected object, user-run authorization, verification result, rollback action, and public labeling change.

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
- [ ] Full R1 admission evidence either certifies Window 2 or records a hold; no fallback release occurs.
- [ ] If certified, Window 2 has corrected signed measurement/rating/forecast lineage, neutral-aware refit, and all-certified-week replay.
- [ ] Public history and Performance pages are truthful about reconstruction, line timing, accuracy, and price provenance.
- [ ] Preview and production release receipts verify atomic serving selection, matchup repin, and rollback.
- [ ] Required tests and documentation checks pass; status, decision log, known-issues register, and session log are updated.
- [ ] Status changes to `Implemented` only after both authorized windows and their required release decisions complete.

## Amendments

Any change to R1 scope, EPA treatment, replay cutoff policy, data identities, neutral refit design, or atomic-release behavior is material. Terra must stop, append an amendment for user review, and not implement that change under this contract.
