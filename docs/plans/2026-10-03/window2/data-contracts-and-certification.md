# Amendment 2 Appendix A — Data Contracts and Certification

- **Authority:** [contract 04, Amendment 2](../04-data-integrity-two-window-implementation.md#amendment-2-window-2-measurement-repair-and-prospective-cutover-2026-10-04).
- **Status:** Approved 2026-10-04 as a normative part of Amendment 2. Not a Preview/production release decision.
- **Date:** 2026-10-04. This appendix is part of the existing contract, not a new contract.
- **Next:** [Appendix B: release, schema and web](release-schema-and-web.md).

## 5A — Baseline reproduction, sizing and go/no-go

Use the existing investigation and decision packet; do not repeat the source-to-screen inventory. Verify required R2 credentials/backend and database identity before data I/O. No repository-root data directory or local fallback is permitted.

Reproduce the signed served V5 measurement and rating artifacts before reporting deltas. Require byte-identical artifacts where serialization is deterministic; otherwise require identical canonical record hashes under the original schema/canonicalization. Compare complete records, missingness, quality flags and provenance, not rounded ratings. Explain serialization-only differences. Numerical tolerance alone is insufficient.

Run the baseline and full R1 candidate across 2015–2019 and 2021–2025, with a separate eligible-2026 report. Exclude 2020 in every boundary. Report changed allocation groups and team-games by season and cause: dip/restore, restoration above eight points, final cap, conversion reassignment, possession/category reassignment, incomplete stream and other. Separate recovered points from attribution-only changes. Freeze linked allocation grouping before looking at evidence, to prevent denominator manipulation.

CFBD drives are the **primary** corroborating source, only when the relevant game passes all checks:

1. Drive scoring reconciles with certified quarter and final totals, explicitly accounting for non-drive scores.
2. Drive boundaries and team identities match the possession ledger.
3. Touchdowns/conversions have consistent associations.
4. No unexplained regression, excess points, duplicate allocation or timing conflict remains.

A final-total match alone does not validate attribution. Retain exact CFBD responses, capture timestamps and checksums. Document each check's result and evidence independence limits.

**Go/no-go:** clean drives must corroborate at least **25% of changed historical allocation groups**. Count a linked group once. Also report by season/cause and points recovered, rather than presenting the percentage alone. If there are no changed groups, report that outcome and stop for review. Below 25%, retain baseline and stop after the sizing receipt; do not automatically build a gamebook pipeline. Report expected benefit and remaining evidence burden. This feasibility threshold never admits an unverified change.

Official institutional final gamebooks/scoring summaries are secondary adjudication sources for failed drive checks or conflicts. Capture permitted bytes, publisher URL, UTC retrieval time, SHA-256, page/event locator and applicable terms/permission. Example source: [Duke Athletics final Army gamebook](https://goduke.com/documents/2025/11/12/Duke_vs._Army_West_Point_Final_Game_Book.PDF). No blanket open license is assumed. [NCAA terms](https://www.ncaa.org/terms-of-service/) do not establish blanket permission for a retained pipeline corpus. Record `terms_uri` and `rights_basis`; where retention/use permission cannot be established, evidence is insufficient and the allocation reverts. Do not build an unrestricted scraper or publicly redistribute gamebooks.

The receipt also sizes original null-PPA exposure by season, metric and team-game. Historical sizing and withholding counts are **not yet measured**; 2026 investigation counts are not substitutes.

## Source restoration and storage

Choose a **new Silver build from pinned original captures**, not inference from old Silver zeros:

```text
original captured provider records → corrected Silver → Gold scoring/possession ledger
→ team_game_metrics → V5 observations / weekly statistics → ratings / forecast
```

Preserve nullable provider PPA; remove `fillna(0)` for this field in the new build and derive `ppa_missing` before compatibility conversion. Preserve true numerical zeros. Missing captures are source gaps, never permission to guess. Rebuild dependent Silver outputs with new identities and retain old versions for original-run verification.

Silver `team_game_stats` remains provider box scores. The calculated source is Gold `team_game_metrics`. Store the four datasets below as immutable, season-partitioned lake datasets using existing DatasetRef/PartitionedDatasetRef helpers and `lake/gold/dataset=<name>/version=<version_id>/…`; register schema/version/parents/quality in Neon `catalog`. Do not add Neon copies of foundational lake data.

A signed manifest binds schema versions, code identity, metric-registry checksum, source DatasetRefs, source capture times, row counts, canonical record hashes, population/timing policy and certification refs. `source_versions` maps names to IDs resolved through those manifest parents. Use existing canonical-content checksum signing; do not claim cryptographic signer authentication. Baseline, candidate and admitted outputs have separate immutable identities.

## Exact lake schemas

Fields are required except where explicitly nullable. Dates are timezone-aware UTC timestamps; numeric measurements are finite float64, never NaN/Infinity on serialization. Lists have deterministic ordering. Foreign references are validated by lake contract validators.

### team_game_metrics_v1

Primary key: `(season, game_id, team, role, metric)` within a version.

| Fields | Type / constraint |
| --- | --- |
| season, week | Integer, canonical season/week |
| game_id | Int64 |
| team, opponent, season_type | Canonical strings |
| role | offense / defense |
| side | home / away |
| opponent_fbs | Boolean |
| kickoff_utc | UTC timestamp |
| metric, definition_version, population_id | Registry-bound strings |
| numerator, denominator, value | Nullable float64 |
| eligible_count, observed_count | Nullable nonnegative int64 |
| coverage_unit | plays / possessions / drives / events / games |
| coverage_status | observed / missing |
| missing_reason | Nullable string; required if missing |
| quality_flags | Sorted string list |
| timing_class | Existing live/reconstructed classification |
| source_versions | String-to-string version map |

Observed values satisfy their formula; count/sum metrics use denominator 1. Undefined ratios/incomplete numerators remain null. Preserve a known denominator when the numerator is missing. Unknown counts are null; a verified zero-event population is zero. Defense rows mirror the opponent's offensive measurement/provenance. Counts satisfy `0 <= observed_count <= eligible_count` when both known.

### football_possessions_v1

Primary key: `(season, game_id, drive_number, offense)`.

- Integer: `season`, `week`, `drive_number`, `eligible_play_count`, `ineligible_play_count`; int64 `game_id`.
- String: `possession_id`, `offense`, `period_class`, `timing_class`; nullable string `defense`, `quality_reason`.
- Boolean: `mixed_eligibility`, `possession_eligible`; nullable Boolean `scoring_opportunity`.
- Nullable float64: `start_yards_to_goal`.
- String list: `source_play_ids`; version map: `source_versions`.

`possession_id` is deterministic from the composite identity. Ambiguous identity/period is recorded and cannot be admitted by arbitrarily choosing a defense/period. Preserve the existing possession eligibility rules except the explicitly corrected kicking-play filter.

### football_scoring_ledger_v1

Primary key: `(season, game_id, source_event_id, team)`.

- Integer: `season`, `drive_number`, `quarter`, `play_number`; int64 `game_id`.
- String: `source_event_id`, `team`, `period_class`, `scoring_category`, `unit_category`, `timing_class`, `rule_version`, `allocation_group_id`, `admission`.
- Nullable integer: `score_increment`, `envelope_before`, `envelope_after`, `certified_final`.
- Nullable float64: `raw_score_before`, `raw_score_after`.
- Nullable string: `associated_possession_id`, `conversion_for_event_id`, `quality_reason`.
- Sorted string list: `evidence_ids`; version map: `source_versions`.

Scoring categories: `eligible_regulation_offense`, `excluded_regulation_offense`, `regulation_non_offense`, `overtime`, `unresolved`. Unit categories: offense / non_offense / unknown. Admission: `baseline_unchanged`, `corroborated`, `reverted_unverified`, `reverted_contradicted`. Candidate versions use baseline/candidate identity in the manifest; final admission labels apply to the admitted ledger.

Keep score events and anomaly markers. Unresolved markers have null increments, not fictitious zero-point events. Resolved increments are nonnegative integral points and preserve the existing eight-point limit. Original streams remain pinned source evidence. Possession IDs reference actual ledger possessions; conversions reference events within the same game/team. Zero scoring is established from complete coverage/reconciliation, not absent events.

### scoring_attribution_evidence_v1

Primary key: `evidence_id`.

- String: `evidence_id`, `allocation_group_id`, `team`, `source_event_id`, `source_kind`, `source_uri`, `source_sha256`, `source_locator`, `terms_uri`, `rights_basis`, `verdict`, `reason`, `verifier_version`, `unit_category`.
- Integer: `season`, `quarter`, `points`; int64 `game_id`; UTC timestamp `captured_at`.
- Nullable string: `possession_id`, `conversion_for_event_id`.
- Verdict: supports / contradicts / insufficient. Evidence source includes validated CFBD drives or an authorized official gamebook. A citation without retained evidence bytes and a locator cannot certify allocation.

## Versioned metric registry

Each registry entry fixes numerator rule, denominator rule, eligible population, coverage dependencies, unit, aggregation and rank direction. Required missing input fields fail contract validation; no alternate formula silently replaces them.

- **P:** corrected eligible regulation scrimmage plays: existing eligibility plus explicit kicking exclusion; no penalties, conversions, dead plays or garbage time.
- **D:** unambiguous regulation possessions with at least one eligible play.
- **O:** eligible drives with the existing scoring-opportunity flag: a first-down play with `yards_to_goal < 40`.
- **Q:** admitted points assigned to eligible regulation offense.
- **E:** provider PPA sum over the required eligible population, with complete coverage.
- **N:** admitted regulation non-offense points.

Do not recompute garbage-time eligibility using R1 envelopes: that is a separate model/population change. Preserve normalized success/conversion flags and existing dropback/rush classification.

| Metric | Formula |
| --- | --- |
| eligible_possessions | count D |
| offensive_possession_points | Q |
| ppp | Q / count D |
| eligible_epa | E |
| epa_per_possession | E / count D |
| eligible_scrimmage_plays | count P |
| plays_per_possession | count P / count D |
| non_offense_points | N |
| ppa_per_play; epa_per_play alias | E / count P |
| epa_pass | PPA sum / count on eligible dropbacks |
| epa_rush | PPA sum / count on eligible rush attempts excluding dropbacks |
| early_down_epa | PPA sum / count on eligible downs 1–2 |
| success_rate | successful plays / eligible plays |
| explosive_rate | eligible gains of at least 20 yards / eligible plays |
| conv_rate_3rd_4th | conversions / eligible third/fourth-down attempts |
| turnover_rate | turnovers / eligible plays |
| scoring_opp_rate | count O / eligible drives |
| pts_per_scoring_opp | admitted offensive points on O / count O |
| avg_start_field_pos | sum(100 − start_yards_to_goal) / eligible drives |
| possessions_per_game | eligible possessions / included games |
| non_offense_points_per_game | regulation non-offense points / included games |

Weekly ratios aggregate numerators/denominators, not game averages. Sums/counts aggregate by sum. Website basic stats retain regular-season FBS-vs-FBS scope; V5 retains accepted repair-population rules. Sharing calculation does not silently unify populations. Preserve current role-specific ranking direction, minimum-rank ties and one-game ranking minimum. No rank for unavailable values; possessions/game remains unranked pace. Offense turnover rate is lower-is-better; defense turnover rate is higher-is-better.

## 5B — Shared builders, missingness and consumers

Implement pure ledger/metric builders and adapters to existing observation/team-stat interfaces. Only move shared helpers needed for basic-stat ownership. Timing, opponent adjustment, priors and state updates remain rating-layer responsibilities. Preserve legacy schemas/verifiers for old immutable artifacts.

Incomplete PPA withholds the affected game EPA metric and dependent full-population aggregate; preserve coverage/reason. Missing pass PPA does not invalidate independently complete rush PPA. No imputation and no placeholder numerator zero. Independent PPP remains usable. Window 1 masking remains as deployed until Window 2 replacement.

Report withheld counts by season/metric plus EPA-only, scoring-only and combined deltas for aggregates, ratings/ranks, offsets and forecasts. No numeric tolerance automatically waives a delta; the signed report is required before exact release review.

Served-path proof: `ratings/possession_intended_update.py` fixes `MEASUREMENT_ID = "ppp"` and filters observations before updates; `build_v5_intended_update_2026.py` imports it; the intended-update bundle builder consumes repaired rating states. EPA candidates in `possession_rating_tournament.py` do not establish a served dependency. Trace selected manifests to the intended-update path. Remove/perturb EPA observations while holding PPP, population, priors and scoring fixed; require identical rating record hashes and forecast outputs. Keep this test distinct from correcting scores/offsets.

| Ledger consumer | Required null behavior |
| --- | --- |
| forecast/offsets.py | Select valid admitted regulation non-offense events; incomplete ledger never becomes zero |
| forecast/forecast_verification.py | Independently verify offset parents, admitted events and missingness |
| audit/corpus.py | Known totals and unresolved counts separately; all-null sum is not zero |
| audit/foundation_blocker_diagnosis.py | Preserve incomplete identities; no arithmetic/comparison on null increments |
| ratings/possession_verification.py | Independently reproduce admission/usability; no null-to-zero conversion |

Test true scoreless games, mixed resolved/unresolved, all-null groups, invalid nonnumeric events and legacy verification. Adapt existing observation schema validation to allow missing numerators under a new version; never reinterpret old signed artifacts.

## 5C — R1 candidate and independent admission

Baseline handling rolls back earlier points on score regression. R1 instead computes `e_t = min(F, max(s_u for u <= t))` in `(season, game_id, quarter, drive_number, play_number)` order. It preserves earlier envelope attribution and does not roll it back. Capping clips/suppresses later increments, which is precisely why final-total agreement is not independent attribution proof.

Test dip/restore (including restoration above eight points), final overshoots, conversions and category changes. These are mechanisms to test, not assumed diagnoses for Kent State/Air Force/Army. Keep the existing eight-point increment limit, conversion and category rules. A short terminal envelope, missing/negative/nonintegral score or unresolved attribution stays explicitly unresolved.

1. Reproduce baseline; run the full corpus.
2. Diff allocations including removed/reassigned baseline events. Separate recovery from attribution-only effects.
3. Admit independently corroborated changes.
4. Revert unverified/contradicted changes exactly to baseline, list allocation IDs, and retain baseline quarantine or baseline attribution. Never introduce exclusion because evidence is unavailable.
5. Linked point transfers and conversions form one allocation group. If coherent admission requires an unverified dependency, revert the linked group. Do not synthesize balancing points.
6. Verify final admitted identities and coverage. Report corroborated, reverted-unverified and reverted-contradicted groups by season/cause and recovered points.
7. Compute materiality on admitted output only: greater than 0.05 raw PPP or more than five rank positions. Report raw versus adjusted/state deltas separately.

The independent verifier may share parsing/schema helpers but cannot call the candidate builder to establish correctness. Failed baseline reproduction, invalid admitted identities or lineage failure holds release. Individual insufficient evidence reverts, not a global hold. Below-threshold 5A feasibility still stops further work for review.

## 6A — Historical foundation and unchanged-recipe refit

Rebuild historical measurements, chronological states, terminal states and dependent priors for 2015–2019 and 2021–2025, then eligible 2026 states. Preserve the intended-update design: one source game observation once, accepted exposure/adjustment parameters, and existing availability policy. Separate rating availability from certified-finals plus 24-hour stabilization required by weekly operations.

Refit **unchanged alpha-10 Ridge and calibration on corrected measurements**. Retain `home_host = 1.0` and `venue_unknown = True` in historical and live paths. No neutral-aware fit or neutral-effect reporting requirement in this window; that requires its own challenger/promotion contract. Exclude 2026 outcomes from coefficients, calibration and hyperparameter fitting/tuning; permit their accepted chronological rating-state updates.

Report raw/adjusted measurements, priors, states/ranks, non-offense points, `offset_margin`, `offset_total`, bridge coefficients/calibration and prediction deltas. Non-offense repairs can change offsets without changing the model recipe. Use admitted ledger-derived offsets when rebuilding the historical feature frame; do not accidentally preserve stale offsets merely because an existing helper only replaces rating columns. Preserve all other feature/population policies.

## 6B — All-completed-week reconstruction

New immutable runs replace public selection for **all certified completed weeks at release**, including prospectively frozen Week 5 and later weeks. Original runs, predictions, selections, freeze receipts and existing grades remain unchanged/queryable. An ungraded original may receive its first grades through the approved scoring path; never overwrite existing grades. Reproduce old stored grades before comparing replacements.

Historical replay uses original forecast cutoffs and quote sets; no late line fill and no target/future outcome leakage. Later provider corrections are explicitly reconstructed evidence, never backdated captures. New public grades are retrospective reconstruction. The independent prospective V5 record and pre-kickoff supersession policy are specified in Appendix B.

## Amendment 1 (Step 5B, 2026-10-04): decisions made while implementing the contracts

Made under the user's 5B authorization ("nullable PPA, the `team_game_metrics` schema with team scores resolving Issue 7, the admitted ledger contract, and the metric registry"). None changes the 5A gate, the formulas or the populations above.

- **`points_scored` metric added to `team_game_metrics_v1`** (population `G`, unit `games`, a sum metric): the certified final points. Its defense row is points allowed. It gives the reconciliation and every consumer an explicit team-points value. It is in the registry; the formulas table above is otherwise unchanged. `possessions_per_game` and `non_offense_points_per_game` stay aggregation-time per-game ratios, not game rows.
- **Lists and maps are stored as canonical JSON text** (`quality_flags`, `source_versions`, `evidence_ids`, `source_play_ids`) because the shared frame validator rejects nested values. Nullable numbers and cross-field rules are checked by `cks_picks_cfb.metrics.contracts`, which also enforces the null semantics listed in that module (missing is null, never zero; a zero denominator gives a null ratio; a missing coverage status needs a reason and a null value; count and sum metrics use denominator 1; defense rows mirror the opponent).
- **Existing ledger conversion.** The baseline ledger's `associated_possession_id` is the source *play* id (`season:game:drive:play`), not a possession id, and its unresolved markers carry a zero increment. `metrics/ledger.py` converts both to the v1 contracts without changing any allocation: possession references become the deterministic possession id of the play's offense and drive; unresolved increments become null; the baseline ledger is `admission = baseline_unchanged`, `rule_version = baseline_v1`, with null envelope fields (R1 fills them).
- **Issue 7 resolution.** The reconciliation's score comparison looked for a `points`, `team_points` or `score` column the team-game data never had. It now also compares each team's stream-derived score (`stream_points`, the highest running score in the play stream) with the certified final, records the count compared and any mismatches in each game's `details`, and **never blocks** (known streams with gaps are handled per allocation). The persisted `reconciliation_v1` schema is unchanged. The legacy `points` comparison still blocks, as before.
- **Null-aware consumers activate only for v1 data** (an `admission` column, or null increments), so every legacy artifact, verifier and sealed audit behaves exactly as before: `forecast/offsets.py` and the independent `forecast/forecast_verification.py` count only admitted allocations, treat a team-game with an unresolved marker as unusable, and reject a null non-offense increment; `audit/corpus.py` keeps all-null groups null, counts unresolved markers separately and reports unresolved team-games apart from shortfalls; `audit/foundation_blocker_diagnosis.py` leaves null increments out of its arithmetic.
- **Not in 5B, moved to 5C:** a v1 mode for `ratings/possession_verification.py`. It reconstructs the *baseline* legacy ledger; reproducing *admitted* allocations needs the 5C admission decisions and the candidate. It cannot convert a null to zero today because v1 frames do not pass its legacy schema.
- **Nullable PPA** is an opt-in (`allplays_to_byplay(nullable_ppa=True)`, `build_preaggregation_pipeline(nullable_ppa=True)`, `build_team_game_dataset.py --nullable-ppa`). The default reproduces every existing Silver version and the served lineage. `ppa_missing` is always derived from the provider value before any conversion. The `byplay_v1` schema already allows a null `ppa`, so no schema version changes. Legacy features derived from `ppa` (for example `epa_pp`) average the non-null plays in this mode; the EPA withhold semantics live in `team_game_metrics`.

## Amendment 2 (Step 5C, 2026-10-04): admission decisions

Made under the user's 5C directives (admit the 1,416 corroborated groups, fail closed, v1 mode for `possession_verification.py`, no R2/Neon writes).

- **Decision mapping.** `corroborated` is the only admitting status. Usable games whose drives support the baseline or match neither are `reverted_contradicted`; everything else (unusable game, indistinguishable at drive level) is `reverted_unverified`. Reverted groups keep exactly the baseline events, including baseline quarantine markers; nothing is excluded for lack of evidence.
- **Scope.** Historical 2015-2019 and 2021-2025 only. The 132 groups of 2026 weeks 0-4 had no CFBD evidence and remain baseline (fail closed); 2026 admission needs its own evidence.
- **Verifier independence.** `verify_admitted_ledger` in `possession_verification.py` reconstructs the baseline with its own ledger code, applies its own copy of the envelope, reconstructs the candidate, and checks that the supplied baseline equals its reproduction, that every changed event belongs to exactly one decided group (and no decided event is unchanged), that linked conversions never cross groups, that the admitted ledger equals the ledger derived from the decisions alone, and that labels and counts agree. It imports neither `admission` nor `score_envelope_r1`. It does not re-evaluate the CFBD corroboration; the decisions are the 5A gate result, pinned by file hash in the receipt.
- **Evidence ids.** Each admitted group gets one deterministic id (`cfbd_drives:<sha256 of group id and bundle hash>`) tied to the retained bundle hash. The `scoring_attribution_evidence_v1` table (terms URI and rights basis) is **not built**: the rights basis for CFBD data is a decision for the user, not an assumption.
- **Envelope fields** (`envelope_before/after`) stay null in the converted admitted ledger; the admitted events are the R1 allocation, and populating the fields is part of the 6A Gold build.

## Amendment 3 (Step 5 closure and 6A guardrails, 2026-10-04)

- **Amendment 2 above is approved by the user (2026-10-04).** Steps 5A, 5B and 5C are closed (`f7c3a47`, `e33d63d`, `ea53c07`). Step 5 changes no serving, rating, selection or production data.
- **Evidence rights (user-specified):** `terms_uri = https://collegefootballdata.com/key`, `rights_basis = cfbd_api_user_agreement`. Evidence ids stay `cfbd_drives:<sha256>`, tied to the retained bundle hashes.
- **Step 6A is authorized but not started.** The user authorized Preview-lake R2 writes (`CFB_STORAGE_BACKEND=r2`, `CFB_R2_PREVIEW_*` credentials) and then asked for Step 5 to be finalized first. Guardrails the user set for 6A, recorded so the next session starts from them:
  - 2020 is excluded from every dataset, prior, rating and model; 2026 outcomes are excluded from Ridge coefficients, calibration and hyperparameter tuning (only chronological rating-state updates use eligible 2026 games).
  - The accepted alpha-10 Ridge bridge and calibration recipe stay unchanged; `home_host = 1.0` and `venue_unknown = True` stay in the historical and live paths (no neutral-site change in Window 2).
  - The rebuilt historical feature frame uses the admitted-ledger offsets (`offset_margin`, `offset_total`), not the stale baseline ones.
  - Writes are new immutable runs on Preview R2 only; no production R2 credentials and no production Neon.
  - Report deltas for raw and adjusted measurements, priors, states and ranks, non-offense points, offsets, Ridge coefficients and calibration, and predictions.
- **Open items carried into 6A:** Silver must be rebuilt with `--nullable-ppa` for `ppa_missing` and the stream-score reconciliation to take effect (the persisted Preview reconciliation is unchanged); the Gold datasets (team game metrics, possessions, admitted ledger, evidence) and their signed manifests do not exist yet; `envelope_before/after` are null in the converted admitted ledger; 2026 weeks 0-4 have no admitted R1 groups; adjusted and rating-level materiality is not yet measured; the rights basis above is the user's statement, not independently checked.

## Amendment 4 — Pre-6A integrity and integration prerequisites (2026-10-04)

**Approved** by the user's explicit implementation request for the [pre-Stage-6 plan](../../2026-10-04/02-pre-stage6-integrity-and-rebuild.md). That execution contract supplies the ordered tasks, acceptance tests and 6A receipt requirements under contract 04 Amendment 3.

- Reverted rows in the admitted ledger are retained baseline allocations, not rejected candidate events. Preserve their exact dispositions and include valid retained points in metrics, offsets and independent verification. This supersedes Amendment 1's two-label consumer filter.
- Require explicit coverage/reconciliation before asserting zero from absent events; preserve missing opportunities/field position and separate seasons in aggregation. Keep website and V5 populations explicit.
- Reconcile rebuilt Silver event identities, scores, eligibility and allocation groups against pinned Step 5 decisions before reuse. Material differences require renewed certification; never silently transfer admission.
- Version nullable observation interfaces, validate evidence references/bytes, and integrate corrected measurements, terminal states, priors and offsets through the refit. Legacy reproduction remains available.
- Writes now include verified Preview Neon catalog/schema/lineage and associated reconciliation metadata alongside immutable Preview R2 artifacts. No serving, selection, authorization or production writes. This resolves the catalog requirement versus the narrower earlier R2 authorization.
- Step 5 is closed; integration and the full rebuild are not complete. 6A must retain independent full-corpus verification, attributed deltas, readback/retry and a signed exit receipt before 6B.
