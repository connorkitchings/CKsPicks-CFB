# Football Data Architecture Blueprint

**Status:** Approved strategic guidance; revised migration roadmap approved 2026-10-28.
**Approval:** Owner approved the original blueprint on 2026-10-22 and requested implementation of the revised roadmap in chat on 2026-10-28.
**Execution:** Through separately approved stage contracts. This roadmap does not authorize provider captures, database migrations, historical repairs, or release activation.
**Next contract:** [Stage 1: operational safeguards and baseline](../plans/2026-10-28/01-data-architecture-operational-safeguards.md) (Draft; detailed execution decisions need review).

## 1. Direction and current baseline

Consolidate duplicated descriptive football calculations into versioned facts and shared measurement builders. Preserve Cloudflare R2 as immutable evidence, Neon as derived serving state, hash-pinned revisions, point-in-time preparation, independent verification, and atomic season releases. V5 Blitzkrieg (`possession_intended_update`) stays sealed; this migration does not replace its computation or change forecasts, ratings, market selections, or grades.

Start with **2026 and existing site products**. Use the existing Python/lake/schema/catalog machinery and Postgres/Drizzle serving stack. No new warehouse, queue, streaming platform, orchestration service, surrogate team-ID migration, or request-time play scans.

The three aggregation paths are not interchangeable:

- `data/team_stats.py` builds long-format season statistics using descriptive `scrimmage_play_mask` eligibility.
- Chart builders assemble wide team-game success/EPA and yardage products, also using descriptive eligibility.
- `data/matchup_data.py` assembles possession-derived measurements from sealed V5 observations; its legacy eligibility differs deliberately.

Incremental weekly rollover shipped under the [October 25 narrow amendment](../plans/2026-10-25/01-incremental-close-week-rollover.md). The [original ingestion draft](../plans/2026-10-20/02-incremental-weekly-ingestion.md) retains deferred request-scope, promotion, and repair requirements. Weekly automation now invokes revision building and preparation directly; it must be included in compatibility work. Consult [current status](../status.md) for live state and the [weekly runbook](../ops/weekly_runbook.md) for operations.

Recent chart fixes reinforce the need for independent metric denominators and explicit missingness. Additive components prevent incorrect averaging; they do not eliminate Simpson's paradox or replace population interpretation.

## 2. Facts, names, and measurement contracts

The target backbone is:

**Immutable captures → canonical football facts → reusable team-game measurements → windowed analytical products → verified serving projections.**

Play, provider-drive, analytical-possession, scoring-event, official-outcome, schedule, venue, and season-membership facts remain distinct, with explicit relationships and source/game-qualified identities. Official finals are reconciliation authority. Never assign unexplained final-score residuals to offensive scoring.

### Names and compatibility

| Namespace | Contract |
| --- | --- |
| `provider_team` | Name recorded in the pinned CFBD schedule |
| `rating_team` | Provider name normalized through the shared `TEAM_LOGO_MAP`, used by V5 artifacts |
| Fact `team` | Shared contract-normalized name using that same mapping |

Python already loads `TEAM_LOGO_MAP` from `contracts/teams.py`; TypeScript uses the synchronized contract. Introduce no competing map. Preserve original names and identifiers. Resolve provider serving names through a season-specific pinned schedule/membership crosswalk; never reverse a many-to-one alias dictionary. Missing or ambiguous crosswalks fail validation.

Compatibility adapters retain provider names in descriptive projections and rating names in V5 projections. Identity reconciliation stays part of release verification. New facts do not require rewriting existing Silver datasets or sealed V5 artifacts.

### Populations, coverage, and metric registry

Canonical games carry `game_classification`; team-perspective facts carry `is_fbs_opponent` from season membership. Supported FBS/FCS games may yield raw facts, but default efficiency/ranking products remain FBS-versus-FBS. Standings and résumé products retain their declared populations. Missing play coverage does not erase valid finals or fabricate zero measurements.

Create a machine-readable registry defining each current metric's meaning, units, grain, population, eligibility, additive components, exposure, missingness, aggregation, ranking direction, adjustment, semantic version, and lineage. Retain distinct legacy V5 and descriptive scrimmage policies. Shared infrastructure must not silently harmonize outputs.

Typed team-game summaries supply **all** current `team_season_stats` metrics: EPA/play, passing/rushing EPA, early-down EPA, success, explosiveness, conversions, scoring-opportunity rate, points per scoring opportunity, starting field position, and turnover rate. Existing chart rows are compatibility projections of those components; their current narrow schema cannot reconstruct every metric.

Store independent numerators and denominators. Derive each window from summed components, not averages of game averages; preserve existing game counts, ranks, and cohorts. Keep valid zero, missing, excluded, and quarantined evidence distinct.

For points per scoring opportunity, preserve whole-team-game offensive invalidity from score-stream validation. Exclude that offense's scoring-opportunity points and valid-opportunity exposure together, mirror the exclusion into the opposing defense's allowed metric, and retain valid opportunities from other games. Do not invalidate unrelated metrics or erase official finals.

Situation policies are versioned and declare overlap. Build existing pass/rush, down, drive, and yardage summaries from retained granular evidence; do not add every hypothetical split to a wide row. Lower-grain evidence remains available for later distributions, percentiles, or sequence analysis.

### Build and storage boundary

| Layer | Responsibility |
| --- | --- |
| R2 | Immutable captures, granular facts, measurement artifacts, retained publication evidence and receipts |
| Preparation | Deterministic facts and measurements from explicit revision-pinned inputs; windows, adjustments, forecasts, grades and projections |
| Neon | Release-scoped prepared aggregates and provenance; no raw-play serving dependency |
| Web | Read prepared projections and perform bounded presentation calculations |

New facts/measurements are **computed during preparation**, not independently selected from the catalog or added as loosely resolved revision inputs. Stage 4B persists them as hash-verified `output_refs` under a new workflow version. The code, metric-policy configuration, revision and historical-publication input references bind identity. Shadow work and Stage 4A do not change the established candidate output contract.

## 3. Point-in-time history and corrections

| Profile | Evidence and behavior |
| --- | --- |
| Originally published | Retained inputs, policies, adjustments and statistics proven to support the selected forecast's pre-kickoff publication |
| Corrected pregame | Corrected evidence for games eligible before the original matchup cutoff; adjustments use only that historical population |
| Current descriptive | Corrected history admitted by the active release and selected analysis window |

Historical matchup pages default to corrected pregame statistics, label revisions, and offer retained originals when available. Later corrections may enter corrected comparisons; later games may not. Forecasts and rendered V5 ratings keep their original provenance. Revised descriptive comparisons never imply revised forecasts or acquire prospective status.

Represent event time, capture/correction time, computation/input identity, and freeze/publication time separately. A presumed postgame availability timestamp does not prove authentic capture or publication.

Preparation never reads Neon. A separate evidence-export operation verifies retained release payloads and publication evidence and copies required artifacts into R2. A hash-pinned R2 publication index becomes an explicit preparation input in Stage 4B. Select the latest qualifying pre-kickoff publication associated with the selected forecast. Weeks 0–6 replay evidence remains reconstruction unless independent evidence proves authentic publication; later weeks also require inspection. Missing originals remain unavailable.

Preserve existing table keys, columns, and `CORE_RELEASE_TABLES`. Existing `team_season_stats` remains a single descriptive profile for `/stats` and compatibility consumers. Add separate release-scoped matchup snapshot, metric, and provenance projections, read directly by active release, game and profile, following `team_resume`'s optional-relation pattern. Old projection sets never query these relations.

Introduce `measurements_v1` after `resume_v1` without changing released sets. Validate forecast/rating consistency, descriptive-snapshot integrity and cutoff population, and the explicit forecast/snapshot association independently. Corrected measurement hashes may differ from original hashes; new association records authenticate that relationship rather than bypassing or faking the existing lineage gate. Missing or tampered evidence fails closed.

## 4. Ordered contracts and acceptance gates

Each row is a separate implementation contract, with exact files, interfaces, commands, tests, approval and amendment rules agreed before implementation. The [Stage 1 draft](../plans/2026-10-28/01-data-architecture-operational-safeguards.md) is the next review artifact; later contracts are not yet authorized.

| Stage | Required outcome and gate |
| --- | --- |
| 1. Operational safeguards and baseline | Reproduce the latest configured test baseline; complete request-scope/restart/provider-free promotion tests and budgeted repair controls; make new score exceptions revision-specific across rollover, refresher, market builder and automation. Preserve historical checksum failures honestly. |
| 2. Shared facts and builders in isolation | Define registry and typed facts; deterministic builders from pinned frames; use unchanged V5 observations for possession products; isolated shadow materialization and receipts with no provider calls or serving writes. |
| 3. Independent shadow verification | Standalone verification and artifact namespace; compare every current consumer on identical inputs. Never append shadow data to live `output_refs`, payloads, reports or identity. Exact keys/counts/populations/exclusions/ranks; floats within `1e-9`; only enumerated provenance differences. |
| 4A. Backend replacement under `resume_v1` | Shared in-memory descriptive summaries with unchanged schema, UI, temporal behavior, output names and V5-derived matchup policies. Identical canonical payload bytes under identical supplied identity; across commits normalize documented code/run provenance only and require float parity. Rehearse and activate separately. |
| 4B. Persisted measurements and temporal profiles | New workflow/output references, additive migrations and `measurements_v1`; pinned R2 publication evidence; separate profile tables and dual-provenance checks; matchup profile UI, labels, exports and cache keys. |
| 5. Controlled cutover and retirement | Real Preview query/migration/readback checks; correction/original access; recovery to `resume_v1` and supported older sets. Explicit migration activation before automation adoption; then retire only replaced descriptive paths. |

Stage 1 writes `score_reconciliation_exceptions_w<N>_v<K>.json` for new football revisions, carrying earlier entries from the previous manifest's verified reference. Sunday automation commits the exact new file. Monday market-only refresh inherits its source reference unchanged. Changed existing bytes are refused; identical-byte resume is allowed. No rewriting of historical manifests is authorized.

Stage 4A must preserve legacy-compatible arithmetic when necessary for byte parity; otherwise stop for an amendment. Stage 4B must not be bundled into that refactor. Weekly automation stays on established builders/workflow until the relevant explicit cutover is accepted; the installed automatic activation policy for ordinary weekly releases remains unchanged.

## 5. Verification, recovery, and deferred expansion

Every applicable contract demonstrates:

- Hand-calculated independent denominators, unequal samples, zero exposure, invalid offense, mirrored defense, missingness and overlapping slices.
- Alias/membership/FBS-FCS behavior; exact key/population parity for matchup and `/stats` dual consumers.
- Later games cannot affect historical pregame comparisons; late corrections change revised comparisons without changing retained originals, sealed V5 outputs or forecast provenance.
- Real Preview queries expose no duplicate profiles, missing-relation CTE errors or lineage bypass; unlinked associations and changed hashes fail closed.
- Normal rollover request scope, durable repair budgets, restart safety, immutable exception references, and zero provider requests during preparation/promotion.
- Deterministic candidates, complete staging/readback, explicit migration acceptance, owner-controlled rollback and compatible retained release readers.
- Focused checks followed by `make contracts-check`, `make check` and `make web-e2e` before a web release, with independent shadow and Preview evidence.

Historical expansion is a later contract for 2015–2019 and 2021–2025, excluding 2020. It starts with coverage auditing and explicit repair budgets. New rolling windows, venue splits, distributions, finishing, turnovers and special-teams products require separate feature contracts and coverage evidence; plays per drive is not clock tempo. Player analytics, live ingestion, model development and betting changes remain outside this migration.

The existing scoring, EPA replacement, quality and backfill obligations in [current status](../status.md#deferred-backlog) survive this roadmap. Installing guardrails does not certify their repair. Update operational documentation and status only when the corresponding implementation or live state actually changes.
