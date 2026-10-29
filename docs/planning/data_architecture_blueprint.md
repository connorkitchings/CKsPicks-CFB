# Football Data Architecture Blueprint

**Status:** Approved strategic guidance; roadmap revised and approved 2026-10-29 (supersedes the 2026-10-28 six-stage sequence).
**Approval:** Owner approved the original blueprint on 2026-10-22, the six-stage roadmap on 2026-10-28, and the amendments below (Stage 1 split, web performance track, merged facts contract, deferred stages) on 2026-10-29.
**Execution:** Through separately approved outcome-named contracts. This roadmap does not authorize provider captures, database migrations, historical repairs, or release activation.
**Next contracts:** [Stage 1a: operational safeguards](../plans/2026-10-28/01-data-architecture-operational-safeguards.md) (Draft) and, in parallel, [web read performance](../plans/2026-10-29/01-web-read-performance.md) (Draft).

## 1. Direction and current baseline

**Proportionality.** The site is display-only, with one owner, one season (2026) and a weekly cadence: 138 FBS teams, about 56 games a week, about 69.5k rows across 24 tables (46 MB normalized) per release, and about 80k plays so far (about 150k by season end). Data volume is not the constraint; everything fits in memory. The real costs are reproducibility, the cost of adding a metric, `prepare` run time, and process burden. Contracts are therefore few and outcome-named, each with one user-visible or operational payoff, rather than one per architectural layer.

Consolidate duplicated descriptive football calculations into versioned facts and shared measurement builders. Preserve Cloudflare R2 as immutable evidence, Neon as derived serving state, hash-pinned revisions, point-in-time preparation, independent verification, and atomic season releases. V5 Blitzkrieg (`possession_intended_update`) stays sealed; this migration does not replace its computation or change forecasts, ratings, market selections, or grades.

Start with **2026 and existing site products**. Use the existing Python/lake/schema/catalog machinery and Postgres/Drizzle serving stack. No new warehouse, queue, streaming platform, orchestration service, surrogate team-ID migration, or request-time play scans.

The three aggregation paths are not interchangeable:

- `data/team_stats.py` builds long-format season statistics using descriptive `scrimmage_play_mask` eligibility.
- Chart builders assemble wide team-game success/EPA and yardage products, also using descriptive eligibility.
- `data/matchup_data.py` assembles possession-derived measurements from sealed V5 observations; its legacy eligibility differs deliberately.

Incremental weekly rollover shipped under the [October 25 narrow amendment](../plans/2026-10-25/01-incremental-close-week-rollover.md). The [original ingestion draft](../plans/2026-10-20/02-incremental-weekly-ingestion.md) retains deferred request-scope, promotion, and repair requirements. Weekly automation now invokes revision building and preparation directly; it must be included in compatibility work. Consult [current status](../status.md) for live state and the [weekly runbook](../ops/weekly_runbook.md) for operations.

**Scope of the duplication.** The only true overlap is `data/team_stats.py` (`team_season_stats`) against `charts/team_game_stats.py` and `charts/team_game_yardage.py`: about 60–100 lines covering game selection, the scrimmage play mask, missing-PPA handling and the offense/defense group-by. `charts/reconciliation.py` already proves the two paths agree for 2 of the 11 metrics. `data/matchup_data.py` builds nothing from plays; it reshapes V5 possession observations into a table that is already a typed team-game measurement table, so it is adapted rather than merged. `features/aggregations/` (about 1.3k lines) is not on the serving path and is a retirement candidate, not a consolidation target. The main payoff of shared facts is that a new metric becomes cheap; turnover margin for the matchup "Key factors" card is the concrete example.

**Efficiency goal.** `prepare` recomputes every completed week on every run, and `_team_season_stats` calls `build_team_season_stats` once per as-of week (`projection_football.py:433`), each call rescanning the full play frame with a per-row Python filter. The V5 measurement cache is keyed on code commit and `through_week` (`inputs.py:280-289`), so it misses on every new week and commit. Computing team-game components once and deriving each window with cumulative sums removes that cost. No `prepare` duration has been recorded; Stage 1a records a baseline so the gain and the weekly automation's timeout headroom (2,400 s) can be shown.

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

Adopt and extend the existing registry, `src/cks_picks_cfb/metrics/registry.py` (`team_game_metrics_registry_v1`), rather than creating a new one. It already defines population, numerator, denominator, aggregation and rank direction for the 11 site metrics and the possession metrics, but only the Gold validators use it, and `team_stats.METRICS` keeps a second copy. Keep the web in sync with the `contracts/projection_sets.json` pattern (a Python copy plus a byte-identical web copy, checked in CI). The registry defines each current metric's meaning, units, grain, population, eligibility, additive components, exposure, missingness, aggregation, ranking direction, adjustment, semantic version, and lineage. Retain distinct legacy V5 and descriptive scrimmage policies. Shared infrastructure must not silently harmonize outputs.

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

**Read-shaped serving projections.** Preparation already holds every input for values the web currently rebuilds on cache misses: season W-L-P from raw grades, team records as of each kickoff, and lines and leans re-derived from snapshots, plus correlated per-row subqueries for grades and market selections. Prepare emits these directly (grade fields joined onto the prediction row, records as of each kickoff, season totals) as an additive projection set, so the web reads rows instead of recomputing them. See [web read performance](../plans/2026-10-29/01-web-read-performance.md) for the web-side track.

New facts/measurements are **computed during preparation**, not independently selected from the catalog or added as loosely resolved revision inputs. The shared-facts contract keeps the established candidate output contract and `resume_v1` schema unchanged. If deferred Stage 4B is ever re-opened, it would persist them as hash-verified `output_refs` under a new workflow version, with code, metric-policy configuration, revision and historical-publication input references binding identity.

## 3. Point-in-time history and corrections

> **Deferred (2026-10-29).** Everything in this section beyond the current corrected-pregame behavior describes deferred Stage 4B. The matchup page already reads `team_season_stats` at `as_of_week` equal to the game week, which is the corrected pregame profile named below as the default. An "as originally published" view cannot be shown for most of the season, because Weeks 0–6 lack authentic publication evidence. Re-open only if the owner wants a visible "as originally published" comparison on matchup pages. The text below is retained as the design for that case.

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

Each row is a separate implementation contract, with exact files, interfaces, commands, tests, approval and amendment rules agreed before implementation. The [Stage 1a draft](../plans/2026-10-28/01-data-architecture-operational-safeguards.md) and the [web read performance draft](../plans/2026-10-29/01-web-read-performance.md) are the next review artifacts; later contracts are not yet authorized.

| Order | Contract and gate |
| --- | --- |
| 1. Stage 1a: operational safeguards (urgent) | Immutable revision-specific score-exception files wired through the season builder, market builder and weekly automation; provider-free prepare/release/rollback test; rollover request-scope tests; full-history path refuses to fetch; recorded `prepare` timing baseline. Target: before or alongside enabling weekly automation. |
| 2. Web read performance (parallel track) | Measure Vercel TTFB first; release-cache `getMatchupData` and stop fetching the whole slate for one game; fix or accept-off ISR on pages reading `searchParams`; consider a deployment-independent cache key; watch the `/model` cache entry size. |
| 3. Shared descriptive facts (merges former Stages 2, 3 and 4A) | Team-game components for `team_season_stats` and the chart tables built once from the existing `metrics/registry.py`; windows derived by cumulative sums; schema unchanged under `resume_v1`; `charts/reconciliation.py` parity extended from 2 to all 11 metrics; turnover margin delivered as the first new metric; retire `features/aggregations/` and the legacy `publish_team_stats` and `publish_matchup_data` Make targets if confirmed unused. Canonical payload bytes identical under identical supplied identity; across commits normalize documented code/run provenance only and require float parity. Rehearse and activate separately. |
| 4. Read-shaped projections | Prepare emits the derived serving values listed under "Build and storage boundary" as an additive projection set; planned with item 3 or right after. |

**Deferred; re-open only on a concrete need:**

| Deferred item | Re-open trigger |
| --- | --- |
| Stage 1b: budgeted observation-repair CLI | A concrete historical repair is scheduled. Stage 1a already makes the full-history path refuse, so nothing is exposed meanwhile. Design retained in the Stage 1 contract appendix. |
| Stage 4B: persisted measurements and temporal profiles (`measurements_v1`, R2 publication index, dual-provenance gate, matchup profile UI) | Owner wants a visible "as originally published" comparison on matchup pages. |
| Stage 5: controlled cutover and retirement of older projection sets | Needed beyond the retirements already in item 3. |
| Historical expansion (2015–2019, 2021–2025) | Owner requests it; see Section 5. |

Stage 1a writes `score_reconciliation_exceptions_w<N>_v<K>.json` for new football revisions, carrying earlier entries from the previous manifest's verified reference. Sunday automation commits the exact new file. Monday market-only refresh inherits its source reference unchanged. Changed existing bytes are refused; identical-byte resume is allowed. No rewriting of historical manifests is authorized. The w7 and w8 manifests pin exception hashes that no longer match the single mutable file; this is preserved honestly as a historical checksum failure, not repaired.

Item 3 must preserve legacy-compatible arithmetic when necessary for byte parity; otherwise stop for an amendment. Weekly automation stays on established builders/workflow until an explicit cutover is accepted; the installed automatic activation policy for ordinary weekly releases remains unchanged.

## 5. Verification, recovery, and deferred expansion

Every applicable contract demonstrates:

- Hand-calculated independent denominators, unequal samples, zero exposure, invalid offense, mirrored defense, missingness and overlapping slices.
- Alias/membership/FBS-FCS behavior; exact key/population parity for matchup and `/stats` dual consumers.
- Later games cannot affect historical pregame comparisons; late corrections change revised comparisons without changing retained originals, sealed V5 outputs or forecast provenance.
- Real Preview queries expose no duplicate profiles or missing-relation CTE errors; for any re-opened Stage 4B, no lineage bypass, and unlinked associations and changed hashes fail closed.
- Normal rollover request scope, restart safety, immutable exception references, and zero provider requests during preparation/promotion. Durable repair budgets apply when deferred Stage 1b is built.
- Deterministic candidates, complete staging/readback, explicit migration acceptance, owner-controlled rollback and compatible retained release readers.
- Focused checks followed by `make contracts-check`, `make check` and `make web-e2e` before a web release, with independent shadow and Preview evidence.

Historical expansion is deferred (see Section 4) and would be a later contract for 2015–2019 and 2021–2025, excluding 2020. It starts with coverage auditing and explicit repair budgets. New rolling windows, venue splits, distributions, finishing, turnovers and special-teams products require separate feature contracts and coverage evidence; plays per drive is not clock tempo. Player analytics, live ingestion, model development and betting changes remain outside this migration.

The existing scoring, EPA replacement, quality and backfill obligations in [current status](../status.md#deferred-backlog) survive this roadmap. Installing guardrails does not certify their repair. Update operational documentation and status only when the corresponding implementation or live state actually changes.
