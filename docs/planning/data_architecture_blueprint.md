# Football Data Architecture Blueprint

**Status:** Approved strategic guidance with the requested amendments incorporated.  
**Approved:** 2026-10-22, by the owner in the architecture-review session.  
**Execution:** Deferred. This blueprint does not authorize implementation, migration, model changes, or publication.

## 1. Architectural assessment and principles

The current architecture has strong evidence preservation and release controls, but football measurements are assembled through overlapping model, matchup, and chart aggregation paths.

Preserve:

- Cloudflare R2 as the immutable evidence lake.
- Neon Postgres as derived serving state.
- Hash-pinned inputs, explicit lineage, verification, and atomic season releases.
- The accepted V5 Blitzkrieg model and its sealed eligibility rules.
- Separate football measurements, model forecasts, market comparisons, and grades.

Improve the shared measurement layer rather than replace the infrastructure. The existing Python pipeline and Postgres/Drizzle serving stack remain the baseline; this blueprint introduces no streaming platform, queue, warehouse, or new orchestration service.

Reusable numerators and denominators prevent incorrect averaging and preserve metric-specific missingness. They do not eliminate Simpson’s paradox; population definitions and comparisons still require explicit interpretation.

## 2. Canonical facts, measurements, and storage boundaries

The conceptual backbone is:

**Immutable captures → canonical football facts → reusable team-game measurements → windowed analytical products → verified serving projections.**

Play, drive, and possession measurements are parallel contributors to team-game products. Official outcomes, scoring events, schedules, and venue context remain independently sourced facts.

### Canonical facts and identity

Retain normalized plays, provider drives, analytical possessions, scoring events, official outcomes, schedules, venue context, and season-specific team membership.

- Preserve stable `game_id`, `play_id`, and `drive_id` identities, qualified by their required source/game scope.
- Preserve relationships between plays, provider drives, and analytical possessions; these entities are not interchangeable.
- Normalize provider team aliases at the Silver boundary using the shared canonical-name contracts.
- Retain canonical team-name keys and existing consumer compatibility. Introducing surrogate integer team IDs into Neon is outside this blueprint.
- Preserve provider identifiers and original names as provenance.
- Any future identity migration requires a separate contract and append-only migrations; historical migrations must never be rewritten.

Official finals remain the reconciliation authority. Unexplained score differences must not be assigned to the offense simply to balance totals.

### FBS/FCS classification

Canonical games carry `game_classification`; team-perspective facts also carry `is_fbs_opponent`, derived from season-specific membership.

- FBS-versus-FCS games may produce valid raw team-game box-score rows when source coverage supports them.
- Official outcomes remain available independently of efficiency-stat eligibility.
- Default efficiency and ranking products exclude FCS opponents under explicit population policies.
- Standings and résumé products declare whether they represent all games or FBS-only games; existing FBS W-L displays retain their meaning.
- Missing play coverage never becomes a fabricated zero or a reason to discard a valid official final.

Opponent classification and play eligibility are separate filters. `scrimmage_play_mask` determines eligible plays; it does not itself establish FBS membership.

### Measurement contracts

Establish a machine-readable catalog defining each metric’s:

- Meaning, units, grain, and eligible population.
- Numerator, denominator, exposure, and missingness rules.
- Aggregation method and adjustment policy.
- Semantic version and source lineage.

Retain both the sealed V5 eligibility policy and the corrected descriptive scrimmage policy. Shared infrastructure must not silently harmonize their outputs.

Store additive counts and sums with independent validity denominators. Keep raw measurements, opponent-adjusted measurements, ratings, predictions, and grades as distinct products.

### R2 versus Neon

| Layer | Responsibility |
|---|---|
| **R2** | Immutable captures and granular Parquet facts: plays, drives, possessions, scoring events, and detail needed for future distributions or situational analysis |
| **Batch pipeline** | Validated measurements, approved slices, window aggregation, adjustments, model computation, and deterministic projection preparation |
| **Neon** | Pre-aggregated release-scoped serving products: team-game measurements, season summaries, rolling windows, situational summaries, forecasts, results, and grades |
| **Web** | Read prepared projections and perform bounded presentation calculations |

Serving projections are materialized during `run_season.py prepare` and published through the existing verified release process. Web routes must never scan raw play tables or query granular R2 datasets per request.

## 3. Consumer profiles and future analytical capabilities

### Pregame matchup profile

Pregame projections for cutoff week `W` use eligible games through `W-1`, subject to the exact cutoff and declared provenance policy.

Freeze the input references, metric policies, opponent adjustments, and resulting matchup projection together. A later correction must not silently change an already published pregame record.

An explicitly requested historical reconstruction creates a new traceable revision and remains distinguishable from the originally published record. It does not acquire prospective provenance.

### Descriptive season profile

`/stats` uses corrected history admitted by the active release and its declared analysis window.

Corrections may trigger league-wide recomputation of opponent adjustments because those calculations depend on the schedule network. Publish the recomputed descriptive products in a new atomic release while preserving historical pregame and forecast artifacts.

Represent separately:

1. Football event time.
2. Source capture or correction time.
3. Computation and input-version identity.
4. Freeze and release publication time.

A presumed postgame availability time is not evidence of an authentic historical capture.

### Situational aggregation

Use **approved situational summary products**, rather than adding every possible split to a single wide team-game row.

- Define versioned situation policies, such as passing/rushing, down-and-distance, field position, regulation/overtime, and garbage-time inclusion.
- Build typed team-game situational summaries from granular R2 facts.
- Materialize the specific windows and slices required by approved site features during preparation.
- Retain independent numerators, denominators, and coverage for each slice.
- Declare overlapping slices so consumers cannot incorrectly sum them as mutually exclusive categories.

A fixed all-game aggregate cannot reconstruct an unrecorded split. New slices require batch recomputation from retained facts, not web-time play scans.

### Supported future direction

The architecture should enable richer matchup comparisons, rolling trends, venue splits, drive distributions, finishing, explosiveness, turnovers, special-teams context, and multi-season comparisons.

Retain lower-grain observations for percentiles, distributions, and sequence-based questions. Do not precompute every hypothetical metric.

Each proposed feature must establish source coverage and measurement validity. For example, tempo requires suitable clock information; plays per drive is not a substitute.

Player analytics and live ingestion remain outside scope.

## 4. Operational boundaries and contract sequence

Keep distinct operations for scoped ingestion, retained-input rebuilding, explicit historical repair, and release promotion.

Routine ingestion should reuse certified history. Corrections identify affected facts and downstream dependencies. Incremental retrieval does not require incremental mathematics everywhere: deterministic full-season recomputation may remain appropriate.

When scheduled, use sequential Sol → Terra contracts:

| Contract | Required outcome |
|---|---|
| **1. Ingestion and boundary decoupling** | Adopt and reconcile the existing incremental-ingestion draft; separate normal rollover, historical repair, and provider-free promotion |
| **2. Metric catalog and typed team-game facts** | Establish R2 fact contracts, canonical identities, FBS/FCS classification, dual eligibility policies, coverage, and approved situational summaries |
| **3. Shadow consumer verification** | Run shared builders alongside existing aggregations using identical pinned inputs; explain every difference |
| **4. Matchup and chart migration** | Move projection builders to shared facts while enforcing frozen pregame versus corrected descriptive profiles |
| **5. Deprecation and legacy cleanup** | Retire duplicated paths only after parity, provenance, release compatibility, and recovery requirements are accepted |

The existing [incremental weekly ingestion contract](../plans/2026-10-20/02-incremental-weekly-ingestion.md) remains the starting point for Contract 1. This blueprint neither supersedes its detailed gates nor authorizes its execution.

## 5. Acceptance standards and deferred status

Future contracts must demonstrate:

- Identical-policy parity with existing matchup, chart, and accepted V5 outputs.
- Correct aggregation from summed numerators and valid exposures.
- Explicit distinction between zero, missing, excluded, and quarantined evidence.
- Valid raw FCS-opponent facts without unintended inclusion in default efficiency or ranking products.
- Correct situational membership and no double-counting of overlapping slices.
- Frozen pregame adjustments despite later historical corrections.
- Traceable new descriptive revisions with preserved original publications.
- Canonical team-name compatibility across Python, TypeScript, and serving projections.
- No raw-play scans from web routes.
- Authorized request scope for rollover and zero provider requests for promotion.
- Deterministic preparation, internally consistent releases, and verified recovery.

This is a strategic standard for future planning, not an implementation-ready migration specification. Exact schemas, approved initial slices, backfill scope, and migration mechanics belong in the individual contracts when work is scheduled.

Persistence is limited to this blueprint, documentation-index updates, and a planning session log. Repository policy leaves staging and committing to the user.
