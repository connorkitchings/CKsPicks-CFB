# Phase 2: Data Repair and Recertification

- **Status:** In Progress
- **Created:** 2026-09-05
- **Planner:** Sol
- **Approval source:** User approved the full data-first plan on 2026-09-05 and
  explicitly approved the full Phase 2 scope (split sub-phases, ingest 2015-2019,
  include FBS-FCS games) on 2026-09-05.
- **Implementation log:** `session_logs/2026-09-05/06-phase2-completion.md`
- **Sealed Phase 1 input:**
  `artifacts/research/data-first-football-v1/phase1/2026-09-05T1510Z-phase1-evidence-audit-v2/`
- **Commit policy:** Separate plan commit required

## Goal

Repair reproduced defects, recertify trustworthy research inputs, and begin
validated automated pregame capture without changing production behavior.

## Dependencies and Scope

Consume the Phase 1 inventory and issue register. Include deterministic repairs,
bounded recapture, rebuilt research descendants, eligibility, and capture.
Exclude speculative fixes, production changes, model selection, purchases, and
rewriting immutable source/history.

## Interfaces

Publish corrected dataset refs under the new research namespace, repair
dispositions, before/after impact reports, and an eligibility manifest naming
seasons, populations, timing class, null/fallback policy, parents, and checksums.

## Implementation Tasks

1. Reproduce and repair admitted identifier, join, duplicate, finite-value,
   count, or transformation defects. Give definition changes new versions.
2. Rebuild only affected research descendants under new identities; preserve
   original captures, reports, and historical timestamps.
3. Perform budgeted recapture from existing providers where recoverable, with
   call estimates and distinct retrieval observations. Quarantine unresolved
   conflicts; preserve unavailable values as null with reasons.
4. Recompute affected metrics and document conclusion changes. Keep invalidated
   artifacts readable as historical evidence but ineligible for selection.
5. Validate and establish automated capture of already available pregame
   information. Capture outputs cannot become eligible without timing/coverage
   checks and must stay isolated from production.
6. Publish the eligibility manifest and explicit Phase 3 input refs.

## Acceptance and Validation

No unresolved correctness or leakage defect remains in admitted inputs.
Applicable coverage and reconciliation gates pass without post-result weakening.
Every repair has a regression test, lineage verification, deterministic rerun,
before/after reconciliation, and proof that V4 outputs and production interfaces
remain unchanged. Missing FCS detail remains explicit.

## Failure Behavior and Done

Unresolved conflicts are quarantined and excluded; affected descendants do not
advance. Shared fixes that could alter V4 are isolated under research versions.
A production defect receives a separate contract. Complete reports, capture
runbook, eligibility manifest, validation, session log, and status update.

## Amendments

Production fixes, new paid sources, fabricated timing, gate changes, or new
measurement definitions require separate authorization or a revised plan.

### Amendment 1 - Detailed sub-phase execution plan (superseded)

This amendment is retained as planning history but is not implementation
authority. Direct verification found that its duplicate-key, missing-object,
API-call, and historical-result assumptions were incorrect. Amendment 2
replaces it in full.

**Reason:** The user approved full Phase 2 scope on 2026-09-05 (split
sub-phases, ingest 2015-2019, include FBS-FCS games) and directed
implementation.

#### Phase 1 findings driving Phase 2 scope

| Issue | Severity | Count | Phase 2 Sub-phase |
|---|---|---|---|
| postseason-capture-gap | critical | 1 | 2b |
| silver-fbs-fcs-exclusion | critical | 1 | 2c |
| preseason_team_inputs duplicate keys | high | 1 (434 rows) | 2a |
| catalog-missing lineage parents | high | 52 | 2a |
| downstream-game-outside-denominator | high | 2 (761 + 888 game_ids) | 2a (verify by-design) |
| 2015-2019 Silver ingestion gap | coverage | plays 50.6%, outcomes 50.6% | 2b/2c |
| All 5 research results `unsupported` | blocking | 5 | 2d |

#### Sub-phase 2a — Deterministic repairs

**Goal:** Fix defects that don't require new data capture. Low-risk, fast.

##### Tasks

1. **Investigate 52 catalog-missing lineage parents**
   - Query Neon `catalog.dataset_dependencies` to find which child datasets
     reference the missing parent version_ids.
   - Classify each as:
     - **Unavailable historical evidence:** parent dataset object no longer
       exists in the current immutable lake. Quarantine and exclude; affected
       research results remain unsupported.
     - **Missing registration:** parent version was never registered in the new
       catalog system but its R2 object exists. Register it from the existing
       R2 object (read manifest, call `register_dataset_version`).
   - Write a research script `scripts/research/repair_phase2_catalog.py` with
     `--dry-run` and `--apply` modes.
   - Add regression tests for the classification logic.

2. **Repair `preseason_team_inputs` duplicate keys**
   - Read the existing dataset (434 duplicate rows).
   - Identify the duplicate key pattern (`season`, `team`, `as_of`).
   - Deduplicate under a new schema version `preseason_inputs_v2`.
   - Register the repaired dataset in the catalog with:
     - New `version_id`
     - `parent_versions` pointing to the original
     - `data_corrections` entry explaining the repair
   - Write `scripts/research/repair_phase2_preseason_inputs.py`.

3. **Clarify downstream-game-outside-denominator**
   - Phase 1 found 761 game_ids in Silver games and 888 in outcomes that are
     outside the development denominator (2015-2019 + 2021-2025, 2020 rejected).
   - Investigate: are these 2026 production games (by-design outside dev scope)?
     Or are they 2020 games (forbidden)?
   - If 2026 production: document as by-design; no repair.
   - If 2020: quarantine and exclude.

##### Acceptance

- All 52 lineage edges classified and either quarantined or registered.
- `preseason_team_inputs` repaired under new identity; original preserved as
  historical evidence.
- Downstream-game-outside-denominator clarified in a disposition report.
- Re-run Phase 1 audit v3 (new run-id) against the repaired catalog; verify
  issue count drops for resolved items.
- Validation: ruff, focused tests, full pytest, diff-check.

##### Risks

- Catalog edge pruning requires write access to `catalog.dataset_dependencies`
  (append-only schema). Verify the migration permits `DELETE` on stale edges;
  if not, add a migration.
- `preseason_team_inputs` repair may reveal deeper lineage issues if the
  duplicates propagated to descendants.

##### Definition of Done

- [ ] 52 lineage edges classified and resolved or quarantined.
- [ ] `preseason_team_inputs` repaired under `preseason_inputs_v2`.
- [ ] Downstream-game-outside-denominator disposition published.
- [ ] Phase 1 audit v3 confirms repair.
- [ ] Session log written.

---

#### Sub-phase 2b — Bounded recapture

**Goal:** Capture missing source data for the full target population
(2015-2019 regular + postseason, 2021-2025 postseason).

##### Tasks

1. **Estimate API call budget**
   - CFBD `/games` endpoint: ~1000 games/season regular, ~50 postseason.
   - CFBD `/plays` endpoint: ~200 plays/game.
   - CFBD `/teams`, `/stats` endpoints: per-season calls.
   - Total estimate:
     - 2015-2019 regular: 5 seasons × (1000 games + 200k plays + teams + stats)
     - Postseason: 10 seasons × (50 games + 10k plays + teams + stats)
     - Rough total: ~1M API calls.
   - CFBD rate limit: 1000 req/hour (free) or 10000 req/hour ($4/mo).
   - At 10000 req/hour: ~100 hours = ~4 days of bounded ingestion.
   - Fit within $15/mo ceiling (existing $4 CFBD subscription).

2. **Write bounded recapture scripts**
   - `scripts/research/recapture_phase2_postseason.py`:
     - For each season in 2015-2019 + 2021-2025:
       - `GET /games?season_type=postseason&year={season}`
       - Register Bronze capture with authentic timestamp.
   - `scripts/research/recapture_phase2_historical.py`:
     - For each season in 2015-2019:
       - `GET /games?year={season}` (regular)
       - `GET /plays?year={season}` (regular)
       - `GET /teams?year={season}`
       - `GET /stats?year={season}`
       - Register Bronze captures.
   - Use existing `fetch-source` infrastructure where possible.
   - Add `--dry-run` mode to estimate call count before executing.
   - Add `--resume` mode to skip already-captured entities.

3. **Execute bounded recapture**
   - Run postseason recapture first (smaller, lower risk).
   - Run historical recapture (2015-2019) in parallel batches.
   - Monitor CFBD rate limits; pause if throttled.
   - Register all new Bronze captures in the catalog.

##### Acceptance

- All postseason games captured for 2015-2019 + 2021-2025.
- All 2015-2019 regular-season games/plays/teams/stats captured.
- All new Bronze captures registered in the catalog with authentic timestamps.
- No 2020 data captured (forbidden).
- API call count within budget; no rate-limit violations.
- Validation: catalog registry check, Bronze object checksums.

##### Risks

- CFBD API rate limits may extend ingestion time.
- CFBD data quality issues in older seasons (missing plays, incomplete stats).
- Budget overrun if call estimates are wrong.

##### Definition of Done

- [ ] Postseason captures registered for all 10 seasons.
- [ ] 2015-2019 regular-season captures registered for all entities.
- [ ] Catalog registry check passes.
- [ ] Session log written.

---

#### Sub-phase 2c — Silver rebuild

**Goal:** Build new Silver datasets that include the expanded population
(FBS-involved, 2015-2019 + 2021-2025, regular + postseason).

##### Tasks

1. **Add `fbs_involved_games` Silver contract**
   - New dataset name: `fbs_involved_games`
   - Schema version: `fbs_involved_games_v1`
   - Required columns: same as `games_v2` plus `population`
     (`fbs_fbs` / `fbs_fcs` / `unresolved`)
   - Key columns: (`season`, `game_id`)
   - Add to `src/cks_picks_cfb/data/silver/contracts.py`.
   - Add builder logic to `src/cks_picks_cfb/data/silver/builders.py`:
     - Load all games captures (regular + postseason, 2015-2019 + 2021-2025).
     - Classify each game's population using team classification lookup.
     - Filter to FBS-involved (`fbs_fbs` + `fbs_fcs` + `unresolved`).
     - Reject 2020.
   - Add tests for the builder.

2. **Build `fbs_involved_games`**
   - Use `make build-silver DATASET=fbs_involved_games CAPTURE_ID=... AS_OF=...`.
   - Register in catalog.

3. **Build expanded `game_outcomes_v2`, `plays_v2`, `team_game_stats_v2`**
   - Use the existing Silver contracts but with new version identities.
   - Build from the expanded Bronze captures (2015-2019 + postseason).
   - Filter to FBS-involved games only (join with `fbs_involved_games`).
   - Register in catalog.

4. **Build `reconciled_team_game_v2`**
   - Reconcile team-game stats with plays for the expanded population.
   - Register in catalog.

##### Acceptance

- `fbs_involved_games` contains all FBS-involved games (regular + postseason,
  2015-2019 + 2021-2025, 2020 rejected).
- `game_outcomes_v2`, `plays_v2`, `team_game_stats_v2`, `reconciled_team_game_v2`
  contain the expanded population.
- All new Silver datasets registered in the catalog with new version_ids.
- Row counts match Bronze source counts (after FBS-involved filter).
- No 2020 data in any Silver dataset.
- Validation: ruff, focused tests, full pytest, diff-check.

##### Risks

- FBS-FCS classification may be incomplete in older seasons (teams endpoint
  may not have historical classification data).
- Reconciliation logic may surface new blocking issues in 2015-2019 data.

##### Definition of Done

- [ ] `fbs_involved_games` built and registered.
- [ ] `game_outcomes_v2`, `plays_v2`, `team_game_stats_v2`, `reconciled_team_game_v2` built and registered.
- [ ] Catalog registry check passes.
- [ ] Session log written.

---

#### Sub-phase 2d — Recomputation and eligibility manifest

**Goal:** Rebuild research descendants, recompute metrics, publish eligibility
manifest, and verify Phase 2 success via Phase 1 audit v4.

##### Tasks

1. **Rebuild `preseason_team_inputs` on new Silver**
   - Use the repaired `preseason_inputs_v2` logic.
   - Build on the expanded Silver (2015-2019 + 2021-2025, FBS-involved).
   - Register in catalog.

2. **Rebuild measurements and states (if applicable)**
   - Check whether Phase 1 audit identified measurement/state defects that
     require rebuilding on the new Silver.
   - If yes, rebuild under new identities.
   - If no, mark as not-affected.

3. **Recompute metrics on new descendants**
   - Use the Phase 1 audit tooling (`recompute_prediction_metrics`) on the
     new prediction datasets.
   - Compare recomputed metrics to reported claims.
   - Document any discrepancies.

4. **Publish eligibility manifest**
   - Write
     `artifacts/research/data-first-football-v1/phase2/eligibility-manifest.json`:
     - Seasons: [2015, 2016, 2017, 2018, 2019, 2021, 2022, 2023, 2024, 2025]
     - Forbidden: [2020]
     - Populations: [fbs_fbs, fbs_fcs, unresolved]
     - Timing class: pregame / postgame / reconstructed
     - Null/fallback policy: explicit per dataset
     - Parent versions: list of all Phase 2 dataset version_ids
     - Checksums: SHA-256 of each dataset
   - This manifest becomes the input to Phase 3.

5. **Re-run Phase 1 audit v4**
   - Execute the full Phase 1 audit pipeline against the Phase 2 outputs.
   - Verify:
     - All resolved issues no longer block.
     - All 5 research results now `reproducible` or `requires-correction`
       (not `unsupported`).
     - Coverage rates: plays/outcomes/reconciled > 95% for FBS-FBS regular season.
     - FBS-FCS coverage: > 90% for FBS-FCS regular season.
   - Write the v4 audit report to R2.

##### Acceptance

- Eligibility manifest published with all required fields.
- Phase 1 audit v4 confirms all blockers resolved.
- All 5 research results have a disposition other than `unsupported`.
- Coverage rates meet the thresholds above.
- Validation: ruff, focused tests, full pytest, diff-check.

##### Risks

- Phase 1 audit v4 may surface new issues in the expanded data.
- Metric recomputation may reveal discrepancies that require further repair.

##### Definition of Done

- [ ] Eligibility manifest published.
- [ ] Phase 1 audit v4 confirms success.
- [ ] All 5 research results disposed.
- [ ] Session log written.
- [ ] Phase 2 plan status updated to `Implemented`.

---

#### Mapping to original implementation tasks

| Original Task | Sub-phase |
|---|---|
| 1. Reproduce and repair admitted defects | 2a |
| 2. Rebuild affected research descendants | 2c, 2d |
| 3. Budgeted recapture | 2b |
| 4. Recompute metrics and document conclusion changes | 2d |
| 5. Validate and establish automated capture | 2b (bounded), 2d (automated) |
| 6. Publish eligibility manifest and Phase 3 input refs | 2d |

#### Handoff

After this amendment is committed, open a fresh Terra task to implement
Sub-phase 2a (deterministic repairs). Sub-phases 2b, 2c, and 2d each require
their own fresh task after the preceding sub-phase is accepted.

### Amendment 2 - Correct Phase 1 before Phase 2 execution

**Approval source:** The user explicitly approved and directed implementation
of this replacement plan on 2026-09-05.

**Verified corrections:** All 52 catalog-missing dataset objects exist at their
exact R2 URIs; `preseason_team_inputs` has zero duplicates on its declared
`(season, team, as_of)` key; the R1 derived ref set contains 100 refs, 90 of
which Phase 1 did not inventory; and the previous API estimate counted returned
rows instead of provider requests.

#### Prerequisite - Phase 0 closure and corrected Phase 1

1. Correct current-authority documentation while preserving V4 production and
   historical interfaces.
2. Traverse declared JSON links, dataset refs, catalog parents, and capture
   dependencies recursively. Validate exact objects even when registration is
   absent; classify registration, object, manifest, and checksum failures
   separately.
3. Require schema-declared keys, retain root-to-descendant attribution, and
   propagate defects and timing restrictions through lineage.
4. Report coverage by dataset version, season type, season, and population;
   preserve exclusions and incomplete opponent-experience evidence.
5. Recompute reported metrics only after matching result, design/model, target,
   fold, population, and immutable labels. Exercise actual unique-game and
   bootstrap semantics.
6. Seal a new audit and an issue crosswalk under a fresh immutable identity.

#### Phase 2a - Deterministic repair

1. Validate the 52 existing objects and their manifests. Reuse valid evidence;
   register only entries supported by complete immutable metadata.
2. Preserve distinct preseason `as_of` observations. Collapse only byte- or
   value-identical rows with the same declared key; quarantine conflicts.
3. Repair only defects reproduced by the corrected audit under research-only
   identities. Publish before/after counts, descendants, and dispositions.

#### Phase 2b - Bounded capture

1. Reuse valid captures and calculate remaining requests by endpoint, season,
   season type, and week. The plays endpoint receives both year and week.
2. Extend the existing resumable, isolated capture system with dry-run request
   counts, quota checks, bounded retries, checkpoints, and explicit partial or
   empty-response dispositions.
3. Cover regular and postseason 2015-2019 and 2021-2025, including FBS-FCS;
   reject 2020. Do not purchase or upgrade a source.

#### Phase 2c - Research rebuild

1. Add `fbs_involved_games_v1` without changing production `games` behavior.
2. Build versioned outcomes, plays, team-game statistics, and reconciled inputs
   from explicit capture refs. Keep the full schedule denominator when FCS
   detail is unavailable and preserve null/exclusion reasons.
3. Rebuild only affected descendants required for reconciliation; defer new
   measurements and model selection.

#### Phase 2d - Recertification and capture automation

1. Publish an eligibility manifest with exact refs, checksums, parents, timing
   classes, permitted uses, null policies, exclusions, seasons, and populations.
2. Require zero unresolved correctness or leakage defects for admitted inputs.
   Report regular/postseason and season/population gates separately. Historical
   results may remain unsupported when excluded with an exact reason.
3. Add Preview-only GitHub Actions capture at 12:00 UTC daily plus manual
   dispatch for schedules, returning production, recruiting, and coaching.
   Enable scheduling only after a successful manual rehearsal and timing proof.
4. Close with the full Python/coverage, documentation, contract, V4
   compatibility, and diff validation required by this contract.

**Amendment rule:** Production changes, purchases, relaxed gates, or new
measurement definitions require another amendment. Each failed gate remains
visible and blocks only the affected inputs; it is never weakened after seeing
results.

### Amendment 3 - Complete postseason capture and enforce Preview routing

**Approval source:** The user explicitly approved and directed implementation
of the Phase 2 completion plan on 2026-09-05.

The first Phase 2b execution captured the ten missing postseason schedule
requests, but the sealed v3 denominator contains regular-season rows only. The
historical planner therefore could not derive postseason weekly plays and
game-stat requests from that unchanged denominator. Phase 2b remains partial
until those endpoints are captured.

The historical capture CLI accepts explicit registered postseason schedule
capture IDs, validates their CFBD provenance and permitted seasons, and merges
their game/week observations with the sealed denominator without hiding
identity conflicts. The Silver and team-game ops wrappers must also propagate
their explicit environment; `build_silver.py` resolves both storage and catalog
targets from that value instead of an ambient database URL. These repairs do
not alter the Phase 2 architecture, acceptance gates, V4, or production.

### Execution record

- **Corrected Phase 1 audit v3 (prerequisite) — complete 2026-09-06.** Sealed
  at `artifacts/research/data-first-football-v1/phase1/2026-09-06T0055Z-phase1-evidence-audit-v3/`
  (code SHA `f77dd213…`): `complete_with_blockers`, 70 issues, 5 result
  dispositions with exact reasons, 12 sealed outputs. Two unresolved-lineage
  blockers remain visible (research parquet objects at non-canonical URIs that
  cannot hold dataset manifests).
- **Phase 2a deterministic repair — complete 2026-09-06.** Root cause found
  and fixed (commit `052486c`): 43 of 53 gaps were sealed under schema
  versions the executable registry never learned (lake writes tolerate
  unknown versions with `schema_sha: null`). The registry now carries the 12
  historical (dataset, version) combos and `register_dataset_version`
  tolerates null-sha historical manifests while preserving recorded-sha drift
  checks. Repair report sealed at
  `artifacts/research/data-first-football-v1/phase2/catalog-repair/2026-09-06T0055Z-catalog-repair/repair-report.json`:
  53 registered, 0 quarantined, confirmed in Preview Neon. All 53 objects
  pass `validate_frame` under the registered schemas.
- **Phase 2b bounded capture — partial 2026-09-06.**
  - Pregame rehearsal (7 requests): 7/7 captured, all first-attempt, Preview
    Neon registration confirmed, authentic pregame timestamps.
  - Historical postseason capture (10 requests): 10/10 postseason `/games`
    requests captured across 10 seasons (2015–2019 + 2021–2025), ~415 games,
    all first-attempt, registered in Preview Neon under entity
    `data_first_games`.
  - Amendment 3 dry-run with those ten explicit captures discovers 20 missing
    requests: one postseason `/plays` and one postseason `/game/team/stats`
    request for each permitted season. Phase 2b completes only after these are
    captured and registered in Preview.
  - CFBD quota: Tier 2, ~29,360/30,000 remaining this month.
  - GHA daily cron (`CFB_DATA_FIRST_CAPTURE_SCHEDULE_ENABLED=true`) ready for
    enablement per Amendment 2 (manual rehearsal + timing proof satisfied).
- **Phase 2c Silver rebuild — blocked on Phase 2b completion.** Root cause fixed (commit
  `64879e2`): mixed camelCase/snake_case column conventions in concatenated
  Bronze captures (`_rename_common` now coalesces camelCase aliases into
  snake_case twins). `fbs_involved_games` builder ready; regular-season Bronze
  captures exist for all 10 target years; postseason captures are the 10 new
  `data_first_games` captures. Next: loop all 10 seasons for
  `fbs_involved_games`, then expanded `game_outcomes`, `plays`,
  `team_game_stats`, `reconciled_team_game` per year.
