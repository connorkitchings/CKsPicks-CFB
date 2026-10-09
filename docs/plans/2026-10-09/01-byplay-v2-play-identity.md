# byplay_v2: provider-keyed play identity (impact-first)

- **Status:** In Progress (Tasks 1–3 and Task 4.1–4.4 delivered 2026-10-09; Task 4.5–4.7 next)
- **Created:** 2026-10-09
- **Planner:** Sol
- **Approval source:** User approved this plan in-session on 2026-10-09 (checkpoint → surgical docs pruning → impact-first `byplay_v2`), after two review rounds that corrected the ordering rule and the ID typing recorded below.
- **Parent contract:** [Repair-track certification and closure](../2026-10-08/02-repair-track-certification-and-closure.md) (milestone: duplicate plays / scoring / complete metrics). That contract keeps its text and completion matrix; this contract is linked from it by Amendment.
- **Implementation log:** `session_logs/2026-10-09/03-byplay-v2-implementation.md` (Tasks 1–2); `session_logs/2026-10-09/06-byplay-v2-tasks-3-4.md` (Task 3 onward)
- **Commit policy:** Separate user-run plan commit; implementation in later user-run commits. No automatic merge, deployment, cloud write or serving change.

## Goal

Stop the legacy `(game_id, drive_number, play_number)` key from silently removing distinct provider plays, without disturbing any measurement that is unaffected.

Success means all of the following:

- A play is identified by `(season, game_id, source_play_id)`. Displayed drive and play numbers are attributes and ordering inputs, never the uniqueness key.
- Only payload-identical repeats of one provider ID collapse. Divergent versions of one provider ID are quarantined and block the build.
- Every one of the 28 known collisions (1 in 2021, 27 in 2025) is retained and reported by key.
- For every game without a collision, every `*_v2` descendant equals its `*_v1` counterpart by key and value. Every difference in an affected game is a row in a discrepancy ledger with source evidence.
- `byplay_v1` and its descendants stay readable as superseded evidence; new corrected descendants must require v2.

## Current State

- The [pinned census](../2026-10-08/repair-track-evidence/play-identity-census.json) verified 168 Bronze captures (1,673,337 rows) across all 11 B2 seasons. Bronze and Silver contain the same 28 complete-sequence collisions with distinct provider IDs. 25 of the 27 2025 groups cross regulation and overtime periods. The legacy `keep="first"` dedup has 28 removal candidates, of which 19 carry non-null PPA and 3 are scoring plays.
- The census pairs negative IDs (for example `-22405`) with 18-digit IDs (`401762831104868701`) at one displayed position. **Provider IDs are not monotonic and must never be used for ordering.**
- `byplay_v1` identity is declared in `src/cks_picks_cfb/data/schema_contracts.py` (around line 354) and `src/cks_picks_cfb/data/silver/contracts.py` (around line 126). The provider ID is renamed `id` → `play_id` in Silver plays (`data/silver/builders.py`) and dropped before byplay is written.
- New `byplay_v1` builds already fail closed on distinct records at one sequence (`features/byplay/enrichment.py`, uncommitted before the Phase A checkpoint). That is a protective gate, not a correction.
- Ordering today is `(season, game_id, quarter, drive_number, play_number)` in `ratings/possession_measurements.py`, `ratings/possession_verification.py`, `metrics/ledger.py` and `ratings/score_envelope_r1.py`; `ratings/observations.py` sorts drive before quarter. The clock and the provider ID are not used for ordering anywhere.
- The draft [`byplay-play-identity.patch`](../2026-10-08/drafts/byplay-play-identity.patch) retains distinct IDs but does not version any contract. It stringifies IDs with `str(value)`, which is lossy for float input (see Task 2).

## Proposed Approach

Measure first, then change. Task 1 is read-only and is a **stop gate**: report its numbers to the user before Tasks 2–6 begin. The versioned contracts then follow, with proof of unchanged output for everything the collisions do not touch.

Ordering and typing decisions (settled in review; do not reopen without an Amendment):

- **Order by period, then the provider's own sequence:** `(period, drive_number, play_number)`, where period is the `quarter` column in v1 data. Period alone separates the 25 cross-period groups.
- **The game clock is diagnostic only, never an ordering key and never an exclusion rule in this contract.** Several plays legitimately share a clock second, and the clock can move backwards (replay-review time restoration, provider capture jitter).
- **Overtime has no game clock;** order there is sequence alone.
- **`source_play_id` is a string everywhere:** contracts, Parquet schemas, loaders and every derived ID. It is converted exactly once, at the Silver → byplay boundary, from the integer value. Float input is rejected, not converted, because it loses precision on 18-digit IDs. This preserves `"-22405"` and `"401762831104868701"` exactly across Python, Parquet and Postgres.
- **Unresolved ordering, in exactly two cases:** a play is marked unresolved, and excluded from order-sensitive measurements, scoring and ratings, only when (a) its period is missing, or (b) distinct provider IDs remain tied on `(period, drive_number, play_number)` after the period-first sort. Unresolved plays are explicit missingness, disclosed and reported by key. Nothing is sorted into a fabricated sequence.
- **Drives:** use the provider `drive_id` when present. Otherwise admit a derived drive only when its membership and order are unambiguous; a mixed-period or otherwise ambiguous derived drive stays unresolved (the existing `ambiguous_drive_identity_or_period` classification in `possession_measurements.py` is the model).

## Scope

### Included

- A read-only shadow impact diff and clock-reversal census.
- `byplay_v2`, `drives_v2`, v2 possession and scoring-ledger identities, and the v2 source-play-list, score-envelope, ledger, observation and independent-verifier versions that depend on them.
- Relaxing the equal-row-count assumption in `rebuild/silver.py` to a key-joined comparison.
- Regression tests and a discrepancy ledger for the affected games.

### Excluded

- Rebuilding or republishing any dataset in R2, the catalog, Neon or Production. This contract produces local, checksummed evidence and code; publishing successor artifacts is a later gated step in the parent contract.
- Any exclusion rule driven by the game clock. A rule for clock reversals requires a separate, explicit decision made on the Task 1 census.
- Quality-policy builder integration, scoring-defect repairs, the 95 database-only adjusted rows, Week 6 certification and the Preview rehearsal. They remain with the parent contract.
- Overwriting any existing artifact. Successors get new versions; B2, c2 and all `byplay_v1` artifacts stay as historical evidence.
- Model, rating-design and B2-recipe changes. Refits that follow corrected inputs are the parent contract's work.

## Affected Components and Contracts

- Schemas: `data/schema_contracts.py` (`byplay`, `drives`, Gold possessions, `football_scoring_ledger`), `data/silver/contracts.py`, `rebuild/silver.py` (`DERIVED` map and `PIN_SCHEMA`).
- Identity and ordering: `features/byplay/enrichment.py`, `features/byplay/corrections.py` (manual fixes are addressed by sequence tuples), `features/aggregations/drives.py`, `ratings/possession_measurements.py`, `ratings/possession_verification.py`, `ratings/observations.py`, `ratings/score_envelope_r1.py`, `metrics/ledger.py`, `metrics/contracts.py` (`possession_id_for`), `metrics/evidence.py`, `quality/silver.py`.
- Rebuild stages that read byplay: `rebuild/{silver_2026,measurements,gold,comparison,parity,baseline,attribution,recon_foundation,states_2026,published_comparison,legacy}.py`.
- Scripts that read byplay (full list from the investigation): `scripts/research/{run,verify}_data_first_possession_measurements.py`, `run_data_first_repair_v2.py`, `run_data_first_phase3*.py`, `audit_data_first_evidence.py`; `scripts/pipeline/{build_rating_measurements,build_successor_r1_foundation,pin_6a_silver_parents,promote_silver_versions,build_team_game_dataset,publish_team_stats,build_corrected_publication_payloads,verify_corrected_publication_payloads}.py`; `scripts/analysis/{build_admitted_ledger_5c,audit_score_stream,size_r1_*,corroborate_r1_with_cfbd,handcheck_team_stats}.py`.
- Tests: `tests/test_new_features.py`, `test_ledger_conversion.py`, `test_possession_measurements_ledger.py`, `test_schema_contracts.py`, `test_gold_contracts.py`, `test_quality_silver.py`, `test_silver_reconciliation.py`.
- Evidence: `docs/plans/2026-10-08/repair-track-evidence/` (new impact file and `checksums.json` entry).

## Implementation Tasks

### Task 1 — Shadow impact diff and clock-reversal census (read-only; stop gate)

**Files:**

- `scripts/analysis/audit_play_identity.py` (extend) or a sibling script; evidence `docs/plans/2026-10-08/repair-track-evidence/play-identity-impact.json`

**Changes:**

- Classify each of the 28 collision groups by key: cross-period or same-period, and which provider IDs, drives and periods are involved. Per the census, 2 of the 27 2025 groups and the 2021 group are not documented as cross-period; this task states each one's class instead of assuming it.
- Using the pinned parents from the census, build byplay, drives, possessions, scoring ledger and team-game measurements for the affected games two ways: (a) the historical `keep="first"` result and (b) all distinct provider IDs retained under the ordering rule above. Report every changed value by key, with original value, corrected value, source evidence and affected descendants.
- Clock-reversal census across all 11 seasons: count every place where the clock runs backwards between consecutive plays within a regulation period, by season and by size (≤10 s, 11–60 s, >60 s). Report only; apply no exclusion.
- Report the number of plays that would be marked unresolved under the two-case rule.

**Acceptance criteria:**

- The script performs no cloud or database write and reads only pinned, checksum-verified parents.
- The impact JSON is deterministic (two runs produce identical bytes) and is added to `checksums.json`.
- **Stop here and present the impact and census numbers to the user.** Proceed to Task 2 only after the user confirms. If the unresolved count exceeds the same-period collision count, or the diff touches any game outside the 28 collision keys, stop and amend before continuing.

**Validation:**

- Focused tests for the classification and the reversal counter on synthetic data (including same-second plays, a replay-review reset and an overtime sequence).
- `uv run pytest <new tests> -q -W error`; evidence manifest verification.

### Task 2 — Versioned identity contracts

**Files:**

- `src/cks_picks_cfb/data/schema_contracts.py`, `src/cks_picks_cfb/data/silver/contracts.py`, `src/cks_picks_cfb/data/silver/builders.py`, `src/cks_picks_cfb/features/byplay/enrichment.py`, `src/cks_picks_cfb/rebuild/silver.py`

**Changes:**

- Add `byplay_v2` keyed `(season, game_id, source_play_id)` and `drives_v2`. Keep `byplay_v1` and `drives_v1` registered and readable; their fail-closed collision guard stays.
- `source_play_id` is `string`, converted once at the Silver → byplay boundary; float input raises. Collapse only byte-identical repeats; divergent versions of one `(season, game_id, source_play_id)` raise. Build on the draft patch, replacing its `str(value)` conversion with the strict integer-to-string rule.
- Add the `DERIVED` v2 entries in `rebuild/silver.py`; replace the equal-row-count assumption in the PPA summary and value-difference code with a key-joined diff that reports one-sided keys.

**Acceptance criteria:**

- A v2 schema test asserts the string dtype, round-trips `"-22405"` and `"401762831104868701"` exactly, and rejects float input.
- New corrected descendants refuse a `byplay_v1` parent; v1 remains loadable for evidence use.

**Validation:**

- `tests/test_schema_contracts.py`, `tests/test_new_features.py`, `tests/test_silver_reconciliation.py`, then the full suite.

### Task 3 — Ordering and unresolved missingness

**Files:**

- `ratings/possession_measurements.py`, `ratings/possession_verification.py`, `ratings/observations.py`, `ratings/score_envelope_r1.py`, `metrics/ledger.py`, `features/aggregations/drives.py`, `quality/silver.py`

**Changes:**

- Introduce one shared ordering helper implementing the rule above and use it in every consumer, replacing the divergent sorts (including drive-before-quarter in `observations.py`).
- Unresolved plays carry an explicit flag and reason, are excluded from order-sensitive measurements, scoring and ratings, and are counted and disclosed by key in the evidence output.

**Acceptance criteria:**

- Same-second consecutive plays are kept and ordered by `(period, drive_number, play_number)`.
- A clock reversal is kept and appears only in diagnostics.
- Only the two stated cases produce an unresolved flag.

**Validation:**

- Regression tests listed under Testing Strategy.

### Task 4 — Versioned downstream identities and verifiers

**Files:**

- `metrics/ledger.py` (`source_event_id`), `metrics/contracts.py` (`possession_id_for`), `ratings/possession_measurements.py` (`_source_id`), `data/data_first_possession_v1.py` and the Gold possession/ledger contracts, `ratings/possession_verification.py`, `rebuild/gold.py`

**Changes:**

- Version possessions and the scoring ledger to v2, with `source_play_ids` and event IDs derived from the provider play ID instead of `"season:game:drive:play"`. Version score-envelope rows, observations and the independent verifiers accordingly, so verification stays independent of the builder.
- Update the other consumers listed under Affected Components only as far as they must accept or refuse v2; do not rebuild their outputs in this contract.

**Acceptance criteria:**

- Duplicate-source-play checks (`ledger.py`, `possession_measurements.py`) key on the provider ID. Their error paths are covered by tests (today there is none for the `duplicate stable source play IDs` error).
- v1 identities and checks are unchanged when v1 data is processed.

**Validation:**

- `tests/test_ledger_conversion.py`, `test_possession_measurements_ledger.py`, `test_gold_contracts.py`, then the full suite.

### Task 5 — Invariance proof and discrepancy ledger

**Files:**

- evidence under `docs/plans/2026-10-08/repair-track-evidence/`; the comparison runs through `rebuild/published_diff.py`

**Changes:**

- For all 11 B2 seasons (2015–2019 and 2021–2026), derive v2 and v1 locally from the pinned parents and compare by key. Every game outside the collision keys must be equal in every metric, mirror, denominator and eligibility flag.
- For affected games, write a discrepancy-ledger row per changed value: original value, corrected value, source evidence, disposition, affected descendants, explanation. No unexplained difference may remain.

**Acceptance criteria:**

- Zero differences outside the collision keys, or the task stops and amends. The ledger is checksummed.
- The measurement and rating descendants that the changes reach are listed so the parent contract can recertify them. Rebuilding and publishing them is out of scope here.

**Validation:**

- Evidence manifest verification; the comparison run is repeatable byte-for-byte.

### Task 6 — Close-out

**Changes:**

- Update the parent contract's completion matrix row for duplicate plays by appending a dated Amendment with the receipts; leave its earlier text intact. Update `docs/status.md` Open work only if the state changed. Write the implementation session log. Propose a commit message.

## Testing Strategy

Regressions to add (each with a failing-before / passing-after check):

- a duplicate provider ID with an identical payload (collapses) and with a divergent payload (blocks);
- distinct provider IDs sharing one displayed sequence (both kept);
- a cross-period collision (kept, correctly ordered by period first);
- a same-period collision (both kept, marked unresolved, reported by key);
- same-second consecutive plays (kept, not unresolved);
- a clock reversal such as a replay-review reset (kept, flagged in diagnostics only);
- an overtime sequence with no clock (ordered by sequence);
- a missing period (unresolved);
- string typing: `"-22405"` and `"401762831104868701"` round-trip exactly; float input is rejected;
- v1 data still loads and v1 guards still fire; a corrected descendant refuses a v1 parent.

Then focused tests per task, the full Python suite with `-W error`, `ruff format --check`, `ruff check`, shared-contract validation, the quality registry check and a strict docs build.

## Risks and Edge Cases

- The collisions may reach more descendants than the 28 plays suggest (drive membership, possession boundaries, scoring attribution). Task 1's gate exists to measure this before any contract changes.
- Negative provider IDs are synthetic; their meaning is not documented. They are treated as opaque strings and never compared numerically.
- Rows with incomplete sequence keys (75,032 in Bronze) are a separate population. Normalized Silver has none; this contract does not change how Bronze rows are normalized.
- Relaxing the row-count assumption must not hide real divergence; the key-joined diff reports one-sided keys explicitly.
- Changed measurements will change fitted B2-recipe bundle bytes downstream. That is expected and belongs to the parent contract's recertification.
- Manual corrections in `corrections.py` address plays by sequence tuples; affected games must be checked for correction misapplication.

## Definition of Done

- [ ] Task 1 evidence delivered and confirmed by the user before Task 2 began.
- [ ] All implementation tasks and acceptance criteria are complete.
- [ ] Invariance proven outside the collision keys; every affected-game difference is explained in the ledger.
- [ ] Full suite with `-W error`, ruff, shared contracts and registry checks, and the strict docs build pass.
- [ ] The parent contract carries the Amendment with receipts; the session log is written.
- [ ] Plan status is updated to `Implemented`.

## Amendments

### Amendment 1 (2026-10-09): Task 1 receipt and mechanical findings

**Reason:** Record the Task 1 deliverables and two mechanical findings. The approach, interfaces, scope and acceptance criteria are unchanged.

**Delivered:** `scripts/analysis/play_identity_impact.py` and `play_identity_shadow.py` (read-only; pinned parents only), `tests/test_play_identity_impact.py` (19 tests, `-W error`), and the checksummed report `docs/plans/2026-10-08/repair-track-evidence/play-identity-impact.json` (two runs byte-identical; registered in `checksums.json`).

**Results (all verified from the report):**

- The 28 collisions are 25 cross-period and 3 same-period. All 25 cross-period collisions pair an overtime play (provider drive IDs negative, overtime drive numbers restarted) with a regulation play of another team. All 28 sit in 4 games (one 2021, three 2025).
- Unresolved plays under the two-case rule: 6 across all 11 seasons, which are exactly the 3 same-period groups (2 plays each). No missing periods. The 2021 pair shares one provider drive and its clocks (3:41, 3:10) agree with file order; the two 2025 groups are overtime plays on different provider drives and offenses, all at clock 0:00.
- The shadow historical build reproduces the pinned legacy by-play and drives for these games exactly, apart from `field_position_bin` and `ppa` zero-fill versus null (41 and 115 rows, all legacy-zero/new-null). *Correction (Task 2 session): the `field_position_bin` difference on every row is not a code change. The current build yields a real missing value where the pinned legacy file stores the string `'nan'`; the rebuild stage's `value_differences` already normalizes that, so Task 1's fidelity check should have too.*
- The historical dedup removed 28 plays: 19 with non-null PPA, 3 scoring, 25 in regulation, 3 in overtime. This matches the census.
- Retaining them adds 1 + 24 by-play rows, 0 + 9 net drive/possession rows, and changes scoring events (2025: 1 historical-only, 2 retained-only). No cell of any other by-play row changes. 92 team-game measurement cells change in 3 games (2021 Week 1; 2025 Weeks 6 and 8), reaching 6 team-games. The overtime-only game changes no regulation measurement. Excluding the 6 unresolved plays instead leaves the same observation changes (16 and 76 cells).
- Drive-number reuse across provider drive IDs occurs only in the 3 collision games of 2025; no game outside the collision games has it.
- Clock census over 1,538,279 compared pairs (no exclusion applied): 3,688 reversals, of which 12 involve impossible clock values (39 regulation rows in 2021 with `clock_minutes` above 15, up to 58) and 3,676 have valid clocks. Of the valid ones, 310 land on a fresh 15:00 clock (the period label looks wrong for those plays) and 1,702 exceed 60 seconds without being a period reset; they are far commoner in 2021–2026 than in 2015–2019 and are not explained by replay review.

**Open decisions for the user (not taken by this contract):** keep the two-case unresolved rule as written; whether the clock and period-label anomalies get their own read-only investigation; proceed to Task 2.

### Amendment 2 (2026-10-09): Task 2 receipt, decisions and mechanical findings

**Reason:** Record the Task 2 deliverables and the user's decisions on the Task 1 findings. The approach, interfaces, scope and acceptance criteria are unchanged.

**User decisions on Task 1 (2026-10-09):** keep the two-case unresolved rule as written (the clock does not order the 2021 pair); run a targeted read-only diagnostic of the 310 period-reset plays *before the Task 3 ordering helper is finalized*; proceed with Task 2 meanwhile. The two exclusion variants gave identical observation changes (16 and 76 cells); the team-game feature cells differ slightly (45 vs 39 and 315 vs 302), so the effect is small, not zero.

**Delivered:**

- `src/cks_picks_cfb/data/play_identity.py` (new): exact-string provider IDs (floats, booleans, non-integer text and missing values rejected; integral floats below 2**53 admitted only for drive IDs), `deduplicate_source_plays`, provider/derived drive IDs with an ambiguity rule, the lineage rule, and `require_v2_byplay` for consumers.
- `data/schema_contracts.py`: `byplay_v2` and `drives_v2` registered beside v1 (`_DERIVED_SILVER_SCHEMA_REVISIONS`); new `identifier_columns` field, emitted into a schema's hash only when set, so all 83 pre-existing schema hashes were verified unchanged (and the two v1 hashes are pinned by a test); `validate_frame` rejects non-string or non-integer-text identifiers. `data/silver/contracts.py`: `SILVER_CONTRACT_REVISIONS` and `silver_contract()`.
- `features/byplay/enrichment.py`: `allplays_to_byplay(play_identity="byplay_v2")`; `aggregations/drives.py`: `aggregate_drives(schema_version="drives_v2")`; `features/pipeline.py`: option passed only for v2, so the v1 call is textually unchanged. The v1 collision guard is untouched.
- `data/lake.py`: `build_dataset_version` refuses any v2 play-identity build with a `byplay_v1`/`drives_v1` parent.
- `rebuild/silver.py`: `DERIVED_V2`, `PIPELINE_CONFIG_V2`, plan policy `play_identity` (default `byplay_v1`, so existing plans are unchanged), a comparison keyed on `(game_id, source_play_id)` that reports one-sided keys instead of requiring equal length, and a v2-aware `verify`.
- Tests: `tests/test_play_identity_v2.py` (28), eight additions to `tests/test_rebuild_silver.py`, and one updated assertion in `tests/test_schema_contracts.py` (it asserted that `byplay_v2` was invalid; it now asserts an unknown version).

**Decisions inside the approach:**

1. **`drives_v2` is keyed `(season, game_id, drive_id, offense, defense)`.** A provider drive holds the kickoff (kicking team on offense) and then the receiving team's plays, and the team-game drive counts count those v1 rows. A first version keyed on `drive_id` alone would have merged 8,959 kickoff rows in 2021 and shifted drive counts everywhere; the real-data smoke test caught it (`drives_rows_equal` false) and it was corrected before this receipt. This still honors "provider drive identity when available"; it stops v1 from merging distinct provider drives that share a number.
2. **Derived drives** (no provider `drive_id`) are admitted when they hold at most two offense/defense orientations within at most two adjacent periods; otherwise `drive_ambiguous` is true. No derived drive appeared in the 2021, 2022 or 2025 runs.
3. **Added columns:** `byplay_v2` carries `source_play_id`, string `drive_id`, `drive_id_source` and `drive_ambiguous`.
4. **`data/silver/builders.py` is unchanged.** The integer-to-string conversion happens once at the by-play build (the Silver → by-play boundary); normalized Silver plays keep their integer `play_id`.
5. **Left for Task 3/4:** `calculate_st_analytics_agg` finds the next drive by `(game_id, drive_number)` with `.first()`, so a reused drive number still collapses two provider drives for net punt yards. Sequence-addressed manual corrections already fail closed in v2, because `apply_data_corrections` raises when a correction matches more than one row.

**Real-data check** (read-only; the unmodified stage code, a throwaway local lake; evidence for Task 5, not the Task 5 proof):

| Season | By-play rows (v2 / legacy) | Drives (v2 / legacy) | One-sided keys | Value differences on matched rows |
| --- | --- | --- | --- | --- |
| 2022 (no collisions) | 152,083 / 152,083; v1 and v2 builds identical | 30,758 / 30,758 | none | `ppa` 31,162 (the existing nullable-PPA change) |
| 2021 | 150,828 / 150,827 | 30,558 / 30,558 | 1 new (`-218`), 0 legacy-only | `ppa` 31,177 only |
| 2025 | 154,656 / 154,632 | 31,456 / 31,447 | 24 new (the exact IDs Task 1 listed), 0 legacy-only | `ppa` 30,789; `st`/`st_punt` 739 (the documented punt-return fix) |

Reconciliation classes had zero mismatches and zero blocking rows in all three. v1 on 2021 refuses the real collision. The stage's `verify`, run against the real v2 output, reported only the single-season harness limitation; every manifest, config, parent, row-count and `validate_frame` check on the 150k-row `byplay_v2`/`drives_v2` passed.

**Open:** the period-label diagnostic (above) gates Task 3. Task 4 must move the possession, scoring-ledger and observation versions into `REQUIRES_V2_PLAY_IDENTITY`.

### Amendment 3 (2026-10-09): period-label diagnostic, Task 3/4 boundary and Task 4 scope

**Reason:** Record the diagnostic that gated Task 3, the user's decisions on the plan for Tasks 3 and 4, and one boundary change between the two tasks. The ordering rule, the two-case unresolved rule and the acceptance criteria are unchanged.

**Diagnostic** ([`period-label-diagnostic.json`](../2026-10-08/repair-track-evidence/period-label-diagnostic.json), `scripts/analysis/play_order_diagnostic.py`; deterministic, read-only, registered in `checksums.json`): 310 plays land on a fresh 15:00 clock under an older period label; 289 start a new drive, 263 are in games that also have the next period label, one is in a game missing a regulation period. In 245 of 8,759 games provider `drive_number` goes backwards across periods; period-first against drive-first ordering, measured against the period label and the clock, is better in 75 of those games, worse in 75 and equal in 95 (3,676 vs 3,615 violations overall). **Conclusion:** `(period, drive_number, play_number)` stays the ordering; the stale label does not change relative order within a game. Recorded as known issue 17.

**Boundary change.** The possession ledger and its independent verifier key events on drive and play number and cannot process tied `byplay_v2` plays until Task 4 moves event and possession identities to `source_play_id`. Task 3 therefore delivers: the shared helper `data/play_order.py`; persisted `play_order_unresolved` / `play_order_reason` columns on the (still unpublished) `byplay_v2` schema; boundary-tie handling in `drives_v2`; period-first order in the score-stream quality check for v2 input only; loud refusals of v2 input by v1-only consumers; and a golden regression proving v1 outputs and schema hashes are unchanged. The scoring exclusion logic lands in Task 4.

**Scoring rule (user decision): neutrality check.** A tie group is harmless if every member shows the same teams and score as the running state just before it; no order can then change any points. Otherwise scoring attribution is unresolved and disclosed: events at or rolled back by the group's members become `scoring_category='unresolved'` with `quality_reason='unresolved_play_order'` (the increment is kept so game totals reconcile), and the team-game's scoring measurements become missing through the existing path. A non-neutral overtime group is flagged but stays category `overtime`, so regulation measurements are untouched. Real data: the 2021 pair is neutral (both show 3–0 for New Mexico State); the two 2025 groups are overtime plays whose scores disagree. Rows are never dropped from the score stream, because dropping one moves its score change onto the next play.

**Task 4 scope (user decision):** includes the v2 score envelope, independent envelope, scoring-attribution evidence and Gold stage wiring. The pinned 5C admission decisions embed legacy ids, but the CFBD corroboration compares points per `(team, drive_number)` against hash-pinned drive bundles and never looks at play ids, so the decisions are **re-keyed by a deterministic mapping, not re-admitted**: no fresh CFBD run. Groups created only by retained plays in a collision game fail closed to `reverted_unverified` unless the offline classifier reproduces a status. v1 pins, hashes and schemas are added beside, never edited.

**Other decisions:** `ratings/observations.py` and the v1-pinned rebuild modules stay v1-only and refuse v2 input (re-sorting them would change served lineage). Net punt yards: v2 pairs by provider drive and matches v1 wherever no drive number is reused; known issue 16 records the collapse (corrected in Amendment 6: it occurs only in the collision games).

### Amendment 4 (2026-10-09): Task 3 receipt

**Reason:** Record the Task 3 deliverables and results. The approach, interfaces, scope and acceptance criteria are unchanged.

**Delivered:**

- **v1 frozen first.** `tests/test_v1_play_order_invariance.py` pins the output digests of the v1 producer, the independent verifier (which must agree), `aggregate_drives`, net punt yards, the Gold converters and the score-stream check, plus the eight v1 schema hashes, recorded from the unmodified Task 2 code. It still passes after every Task 3 change.
- `src/cks_picks_cfb/data/play_order.py`: `order_plays` (the exact v1 sort, stable, no conversion, no clock, no provider ID), `flag_unresolved_plays`, `tie_groups`, `unresolved_play_keys`. A missing period is null or `< 1` (byplay stores a missing quarter as 0) and takes precedence over a tie; v1 frames, which have no `source_play_id`, can only be unresolved for a missing period and a duplicated v1 sequence raises.
- `byplay_v2` now carries `play_order_unresolved` (non-null boolean) and `play_order_reason` (`missing_period` / `tied_sequence` / null), computed last in the v2 path, after every row filter. The v2 schema is unpublished, so its hash changed freely and both v2 hashes are now pinned in `tests/test_play_identity_v2.py`.
- `drives_v2`: a drive's start (end) yard line is left null only when plays tied at its first (last) position disagree on `yards_to_goal`. No schema change; the columns were already nullable.
- `possession_measurements.py` and `metrics/ledger.py` use `order_plays` (same keys, same stable sort, so v1 output is byte-identical, which the golden test confirms). The independent verifier keeps its own sort. `quality/silver.py` `score_stream_regressions` is period-first for v2 frames only.
- `require_v1_byplay` refuses provider-keyed frames in `ratings/observations.build_measurement_observations`, `score_envelope_r1.apply_r1` and `restoration_jumps`. The v1-pinned rebuild modules read lake datasets rather than frames, so their refusal lands with the plan-policy guard in Task 4.6, not here.
- Tests: `tests/test_play_order.py` (10), additions to `tests/test_play_identity_v2.py` (now 41), the golden file (15), `tests/test_play_order_diagnostic.py` (5).

**Real-data results** (read-only, pinned parents, unmodified stage code; rebuilt `byplay_v2` in memory):

| Season | By-play rows | Drives | Unresolved plays | Drive edges nulled | Score-stream regressions |
| --- | --- | --- | --- | --- | --- |
| 2021 | 150,828 | 30,558 | 2 (`-217`, `-218`, game 401310699, drive 5 play 6) | 0 | 530 (v2 order) |
| 2022 | 152,083 | 30,758 | 0 | 0 | 501 (v2 order) vs 504 (v1 order on the same data) |
| 2025 | 154,656 | 31,456 | 4 (game 401756916, overtime drives 23 and 24) | 0 | 591 (v2 order) |

Row and drive counts equal the Task 2 smoke run exactly. Unresolved plays total 6, all `tied_sequence`, none `missing_period`, matching Task 1. The period-first score-stream order removes 3 false regressions in 2022 (restart-game artifacts); 2021 and 2025 have no v1 baseline because v1 refuses their collisions.

**Validation:** full suite with `-W error` 2,344 passed and 15 skipped (the one added skip is the other session's disposable-PostgreSQL test in `test_matchup_6a_bridge.py`; none of this work's tests skip); `ruff format --check .` (747 files) and `ruff check .` clean; `git diff --check`, `make contracts-check` and `mkdocs build --strict` pass.

**Next:** Task 4. The ledger, verifier and Gold converters still key on the legacy sequence and raise on tied v2 plays until Task 4 moves identities to `source_play_id`.

### Amendment 5 (2026-10-09): Task 4.1–4.4 receipt (first Task 4 stop gate)

**Reason:** Record the identity, builder, independent verifier and Gold-converter deliverables and their results. The approach, interfaces, scope and acceptance criteria are unchanged; two mechanical decisions are noted below.

**Delivered:**

- `data/data_first_possession_v2.py` (new; v1 untouched): `POSSESSION_COLUMNS_V2` (+`drive_id`), `SCORING_EVENT_COLUMNS_V2` (+`source_play_id`, `drive_id`), `POSSESSION_DATASETS_V2` (ledger, scoring-event and observation `_v2`; population, snapshots, history, terminal and coverage stay v1, so the forecast materializer refuses v2 references by design), and `source_event_id_v2 = season:game_id:source_play_id`.
- `data/schema_contracts.py`: v2 revisions for the possession ledger, scoring event, observation, `football_possessions`, `football_scoring_ledger` and `scoring_attribution_evidence`, each derived from its v1 entry with only the identity changed; the possession and Gold ledgers are keyed on `drive_id`, identifiers are validated as exact strings. No v1 entry was edited, which the golden hash test enforces.
- `data/play_identity.py`: `REQUIRES_V2_PLAY_IDENTITY` now lists all eight v2 versions and a `SUPERSEDED_PLAY_IDENTITY` set of eight `(dataset, version)` pairs replaces the old two-name check, so an observation v2 cannot descend from a possession ledger v1.
- `ratings/possession_measurements.py`: `play_identity` on `build_possession_ledger` and `build_measurements`. v2 groups possessions on `(season, game_id, drive_id, offense)`, ids events from the provider play, validates an injected ledger on the provider drive, and applies the **tie-neutrality rule**: for each group of live plays tied at a sequence, snapshot the teams' running scores; the group is harmless if every member shows those scores. Otherwise events created by its members are `unresolved` (`unresolved_play_order`, increment kept so totals reconcile; overtime keeps category `overtime`), and if members also disagree with each other the next event for those teams is marked too.
- `ratings/possession_verification.py`: an independent v2 path with its own event key, duplicate check, grouping and neutrality predicate. It **recomputes the tie flags from raw columns and raises if the persisted `play_order_*` flags disagree**. It imports neither `data.play_order` nor `data.play_identity`; the import-boundary test now bans both.
- `metrics/ledger.py`, `metrics/contracts.py`: `possessions_to_v2`, `scoring_events_to_v2` (a raw score is not asserted across a tied play and an envelope stops at one), `possession_id_for_v2`, `possessions_v2_problems`, `scoring_ledger_v2_problems`. Both v1 converters refuse v2 frames.
- Tests: `tests/test_possession_v2.py` (19; every scenario is run through the builder *and* the verifier, which must agree frame for frame), `tests/test_gold_v2.py` (17), `tests/test_possession_v2_comparison.py` (4).

**Decisions inside the approach:**

1. **Rollbacks triggered at a tied play are not rewritten.** A score regression is a property of the score stream, not of the order of the tied plays: in the 2025 overtime game the 0–0 provider rows regress the score whichever twin comes first. Rewriting the rolled-back regulation events would have blanked regulation measurements because of an overtime-only tie, contrary to the intent that an overtime tie never touches regulation.
2. **Neutrality is judged over the *live* tied members.** A dead play (timeout, end of game) never scores, so a pair of one live and one dead play is not a reorderable pair for scoring. The persisted flag still marks all tied plays for disclosure.
3. A logic bug found by the tests and fixed in **both** implementations: the "next event" marker was consumed by an event inside the tie group instead of the first event after it. Builder-versus-verifier agreement could not have found it, because both had it; a scenario test did.

**Real-data results** (`repair-track-evidence/possession-v2-comparison.json`; read-only, two runs byte-identical). Population: games with plays whose baseline ledger reconciles to the certified finals, plus the four collision games, identical for v1, v2 and the verifier (the unadmitted baseline otherwise trips the builder's 94% season guard on a fraction of real games, which is a known pre-existing issue).

| Season | Games used | Producer = verifier | Possessions v1 / v2 | Events v1 / v2 | Shared events differing | Observation cells changed | One-sided events (v1 / v2) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2022 (no collisions) | 671 of 896 | all four frames | 23,434 / 23,434 | 6,675 / 6,675 | 0 | 0 | 0 / 0 |
| 2021 | 656 of 887 | all four frames | 22,744 / 22,744 | 6,494 / 6,494 | 0 | 16, all game 401310699 | 0 / 0 |
| 2025 | 702 of 934 | all four frames | 23,486 / 23,495 (+9) | 6,900 / 6,901 | 0 | 76 (401761632: 46, 401762831: 30); 401756916: 0 | 3 / 6, games 401756916 and 401761632, **0 points** |

Zero `unresolved_play_order` events appear in real data: the 2021 pair is score-neutral, and the 2025 overtime streams were already quarantined by the existing malformed-score path, which takes precedence. All one-sided events are zero-point quarantine or rollback markers that land on a different twin in v2. The 16 and 76 observation cells equal the counts Task 1 predicted.

**Validation:** full suite with `-W error` 2,384 passed and 15 skipped; `ruff format --check .` (752 files) and `ruff check .` clean; `git diff --check` and `make contracts-check` pass.

**Next:** 4.5 (admission re-key and the v2 score envelope, evidence and verifier block), 4.6 (rebuild wiring) and 4.7 (net punt yards), then the final Task 4 stop gate.


### Amendment 6 (2026-10-09): Task 4.5–4.7 receipt (final Task 4 stop gate)

**Admission re-key (4.5).** `scripts/analysis/rekey_admission_v2.py` maps each pinned legacy event id to the provider id of the play the legacy build kept (Silver file order), re-derives `group_id` from the v2 first event (recovered by hashing the members), and reconciles the result against groups recomputed from `byplay_v2` ledgers. No CFBD call; evidence is the same hash-pinned bundles. Outputs (evidence `admission-v2/`, in `checksums.json`; two assemble runs byte-identical): `admission_decisions_v2.csv`, `corroboration_group_status_v2.csv`, `rekey_report.json` and ten per-season summaries.

| Check | Result |
| --- | --- |
| Decisions admitted / contradicted | 1,416 / 28, equal to the pins |
| Decisions unverified | 1,747 against 1,749 pinned: the two pinned groups of game 401756916 have no v2 counterpart (the overtime tied streams are skipped by the v2 envelope) and are dropped, not admitted |
| Groups matched | 3,191 of 3,193 pinned groups recomputed from v2 (one of them differs on members: game 401761632, already `reverted_unverified`); 2 pinned-only (game 401756916); 0 new v2-only groups |
| Anchors (v1 groups and decisions rebuilt equal the pins) | true in all ten seasons |
| v1-mapped admitted ledger equals v2 outside the four collision games | row-equal in all ten seasons (2025: 9,145 rows; 9,187 v1 against 9,188 v2 events overall) |
| `verify_admitted_ledger` v2 | ok in all ten seasons; Gold v2 dry run 0 problems, evidence rows = admitted counts (1,416) |

No admitted or contradicted group touches a collision game, as the Task 4 plan predicted, so the re-key changes no served decision.

**Wiring (4.6).** `play_identity` plan policy (default `byplay_v1`) is honoured by `rebuild/comparison.py` (a v2 build/verify beside the untouched v1 bodies), `rebuild/gold.py` (`settings_for(identity)`) and `rebuild/measurements.py`; `common.silver_summary` raises if staged Silver was built with a different identity than the plan; eight stages (`V1_PINNED_STAGES`) refuse a v2 plan and name themselves. A v2 plan needs inputs `corroboration_group_status_v2` and `admission_rekey_report`, and the pin `admission_decisions_v2_csv`. **Honesty note:** the v2 comparison and Gold stage paths are covered by unit tests and a faked-context run of the comparison stage, not by an orchestrated Preview rebuild; that remains the parent contract's milestone.

**Deviations from the Task 4 plan:** the re-key is a new script and library (`ratings/admission_rekey.py`) rather than a v2 mode in `build_admitted_ledger_5c.py`; `score_envelope_r1.restoration_jumps` and `apply_r1` now accept v2 frames (tied-stream teams are skipped and reported as unresolved); `admission.py` and `metrics/evidence.py` needed no change; the possession duplicate-key check in `metrics/builders.py` uses `drive_id` when present.

**Net punt yards (4.7) and a correction.** `calculate_st_analytics_agg` runs the unchanged v1 algorithm on every game without a play-sequence collision and pairs provider drives chronologically only in collided games, ordering by `(is_overtime, drive_number, drive_start_period, first_play_number, drive_id)` and returning NaN when drives cannot be ordered. Real data (`net-punt-yards-comparison.json`, ten seasons): 17,755 team-games compared, 3 differ, all in collision games (401761632 Texas State; 401762831 Buffalo and Eastern Michigan), 0 outside. **Correction:** Amendment 3 and the first known issue 16 said the collapse also affects the 245 games whose drive numbers go backwards across periods. No game outside the collision games shares a drive number between two provider drives, so that part was wrong; known issue 16 now says so, and issue 17 (backward numbering) stays separate.

**Validation:** full suite with `-W error` 2,418 passed, 15 skipped; `ruff format --check .` (759 files) and `ruff check .` clean; `git diff --check`, `make contracts-check` and `mkdocs build --strict` pass.

**Next:** Task 5 (invariance proof) after the user's review of this gate.
