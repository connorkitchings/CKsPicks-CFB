# 2026 Historical Bootstrap and Week 0 Execution Plan

- **Status:** Approved for implementation
- **Decision date:** 2026-08-09
- **Execution environment:** Preview only until every promotion gate passes

**Source inventory:**
`artifacts/preview/history-inventory/4eaf0c1b394b43769fe5c2500b1782be.json`

## Objective

Build reproducible 2021-2025 training and evaluation data, refit the frozen
design on 2021-2025, and rehearse the 2026 opening slate without modifying the
production R2 history or making claims that the source data cannot support.

The published system must reproduce a prediction from immutable source lineage,
use increasing current-season evidence for the 0/1/2/3/4+ regimes, and display
every 2026 FBS-vs-FBS game. Bookmaker data remains excluded from model features.

## Inventory Baseline

The approved plan starts from the following observed source state:

- The production bucket contains 36,138 objects; 8,020 are recognized historical
  data objects and 7,156 are eligible for bootstrap.
- Eligible data covers 2019 and 2021-2026. No 2020 object was found.
- All eligible objects are transformed `legacy_cfbd_export` files, not native
  provider captures.
- Schedules, plays, team-season features, teams, venues, weather, and historical
  betting lines have useful coverage, with known season-specific gaps.
- Historical betting-line records do not contain authentic capture or quote
  timestamps.
- The 2026 schedule contains 761 FBS-vs-FBS games. CFBD assigns the August 29
  opening slate to provider Week 1 and exposes no provider Week 0 partition.
- The existing 2026 source does not yet contain current preseason/team-season or
  weather inputs.

## Approved Data Decisions

### Historical markets

Untimestamped betting-line exports will be preserved as a separate immutable
`legacy_market_references` Silver dataset. They will not be promoted to canonical
`market_quotes` or `market_snapshots`.

Each legacy row must retain its original value, provider label, source object,
source checksum, and missing-timestamp status. It must also carry:

```text
exact_replay_eligible = false
grading_eligible = false
lean_eligible = false
timestamp_status = missing_authentic_timestamp
```

These values may be used for migration comparison and descriptive research only.
They may not be used to reconstruct a freeze, grade a prediction, calculate ROI,
select a model, brand a prediction as high confidence, or enter a model feature.

Predictive model evaluation using outcomes and MAE/RMSE may proceed. Historical
market-dependent promotion gates remain blocked until an authentic point-in-time
quote dataset is available. New 2026 quotes captured by the hardened adapter are
eligible under the canonical market policy.

### Canonical Week 0

Silver schedules will preserve `provider_week` exactly. A separate versioned
canonical schedule policy will assign `canonical_week`.

For 2026, games in the opening August 29 slate will be assigned canonical Week 0
through an explicit, checksummed schedule-policy dataset. The policy will use
game IDs and kickoff timestamps, not silently decrement every provider week.
Later games retain their normal canonical week. Any schedule revision must
create a new policy version and invalidate affected downstream snapshots.

The site and operational commands use `canonical_week`; source lineage and
provider reconciliation retain `provider_week`.

### Historical scope

- 2019 is allowed only as prior-quality lineage for early 2021.
- 2020 is rejected from captures, datasets, features, training, evaluation, and
  lineage edges.
- Candidate selection uses temporal folds ending in 2024.
- 2025 remains inaccessible to selection and is opened once for locked testing
  only after the design SHA is frozen.
- The unchanged selected design is refit on labeled 2021-2025 data for 2026.

## Execution Plan

### Phase 1: Encode the adjudications — ✅ COMPLETE

1. ✅ Added the `legacy_market_references` contract, normalizer, and provider
   routing (`DATASET_PROVIDERS`). Legacy captures cannot enter canonical
   `market_quotes` or `market_snapshots`.
2. ✅ Authentic timestamps remain mandatory in canonical market contracts.
3. ✅ Added exact-market audit mode (`make audit-data MODE=exact-market`) and
   adjusted structural audits to report legacy market blockage as coverage
   rather than a structural-data failure.
4. ✅ Added the versioned canonical-week policy dataset, the
   `build_schedule_week_policy.py` builder, and the explicit 2026 Week 0
   game-ID assignments (`conf/policy/canonical_week_2026_v1.yaml`).
5. ✅ Added 17 contract tests proving legacy lines cannot produce leans,
   grades, ROI, or model features, and that the Week 0 policy is correct.

**Exit gate:** The historical import can preserve legacy lines without weakening
canonical markets, and all Week 0 tests pass while provider weeks remain intact.

### Phase 2: Run the resumable historical bootstrap

1. Run `make inventory-source` again only if the source has changed.
2. Run `make import-history` against read-only `cfb-model-data`, writing only to
   preview R2 and preview Neon.
3. Import 2019 prior inputs and all eligible 2021-2026 objects; reject 2020.
4. Verify each preview Bronze object against source SHA-256 and source metadata.
5. Resume the same pipeline run after recoverable failures rather than creating
   duplicate observations or versions.

**Exit gate:** Every eligible object is imported or explicitly classified, all
checksums match, no production write is possible, and no 2020 lineage exists.

### Phase 3: Build and reconcile canonical Silver

1. Build season-scoped teams, aliases, venues, schedule revisions, games, plays,
   outcomes, weather, preseason inputs, and legacy market references.
2. Pull missing team-game statistics and other required sources through the
   hardened CFBD adapter as native timestamped captures when the provider offers
   them.
3. Reconcile completed 2021-2025 games across schedules, plays, box scores, and
   outcomes. Resolve conflicts only through a versioned policy or correction.
4. Produce explicit combined 2021-2025 training references.
5. Report missing 2026 future results and plays as expected rather than errors.

**Exit gate:** Zero unexplained blocking reconciliation conflicts, complete
eligible game keys and targets, and explicit coverage/missingness for every
required source.

### Phase 4: Build structural and model-ready Gold

1. Build kickoff-ordered team-side features with independent completed-game
   counts and separate prior/current blocks.
2. Build deterministic game-wide views for the five routing regimes.
3. Run the structural audit before any baseline model is required.
4. Generate strictly temporal OOF baseline predictions for 2022-2024.
5. Join explicit baselines into model-ready Gold without joining legacy market
   references.
6. Persist adjacent-regime transition diagnostics and feature lineage.

**Exit gate:** Structural and model-ready audits pass, 2019 appears only in the
approved early-2021 prior lineage, and every 2022-2024 row has eligible OOF
baselines.

### Phase 5: Select, lock, test, and refit models

1. Run Ridge, CatBoost, and blend candidates independently for spread and total
   in regimes 0, 1, 2, 3, and 4+.
2. Select weights and candidates using only the 2022-2024 OOF artifacts.
3. Freeze features, candidates, thresholds, blend search, routing, and code SHA.
4. Open 2025 once for locked anti-regression evaluation.
5. Mark market-dependent gates as unavailable—not passed—where authentic quotes
   do not exist. Such routes remain display-only and not high-confidence eligible.
6. Refit the unchanged design on 2021-2025 and create one checksummed ten-route
   `model_bundle_v2` for 2026.

**Exit gate:** All ten routes exist, predictive gates and locked-test reporting
are reproducible, failures are encoded as display fallbacks, and no result from
2025 influenced design selection.

### Phase 6: Capture and rehearse live 2026 Week 0

1. Refresh the 2026 schedule and capture one immutable preseason snapshot before
   the first kickoff.
2. Capture live market quotes with authentic timestamps through the canonical
   adapter; missing lines remain visible but cannot create leans.
3. Run Week 0 readiness in preview using explicit dataset and bundle versions.
4. Publish progressively, rerun as lines arrive, and freeze only the validated
   active run.
5. Replay 2025 for predictive/site equivalence, noting that exact historical
   market grading remains blocked.
6. Verify the Vercel preview, health endpoint, canonical Week 0 navigation,
   mobile/desktop rendering, and failure non-activation behavior.

**Exit gate:** Every opening-slate FBS-vs-FBS game appears; the run is reproducible
from its ID; current quotes are authentic; failed steps activate nothing; and the
site clearly distinguishes preview, published, and frozen state.

## Required Quality Gates

- Ruff format and check.
- Full pytest suite.
- SQL contract and migration validation from empty and legacy schemas.
- Source checksum and lineage audit.
- Structural and model-ready data audits.
- Reconciliation report with zero unexplained blocking conflicts.
- Web lint, typecheck, production build, and preview browser smoke tests.
- Reproducibility check from prediction run ID through capture, dataset, bundle,
  frozen quote, prediction, and grade.

## Stop Conditions

Stop rather than infer or silently degrade if:

- A source attempts to introduce 2020 data or lineage.
- A historical market value lacks a timestamp but is routed toward canonical
  markets, grading, ROI, leans, or confidence.
- A completed eligible game has an unresolved blocking reconciliation conflict.
- Source and destination bucket identities match.
- A failed or partial pipeline step would activate a dataset or prediction run.
- The locked 2025 command is invoked without a frozen-design SHA.

## Next Session Resume Point

Begin with Phase 2. Run `make import-history` in preview. No additional user
credential setup is currently required; read-only source R2, preview R2, and
preview Neon connectivity have been verified. Phase 1 contracts and the
canonical Week 0 policy are implemented and tested.
