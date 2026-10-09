# byplay_v2: provider-keyed play identity (impact-first)

- **Status:** In Progress (Task 1 delivered 2026-10-09; stop gate: Task 2 waits for the user to confirm the Task 1 numbers)
- **Created:** 2026-10-09
- **Planner:** Sol
- **Approval source:** User approved this plan in-session on 2026-10-09 (checkpoint → surgical docs pruning → impact-first `byplay_v2`), after two review rounds that corrected the ordering rule and the ID typing recorded below.
- **Parent contract:** [Repair-track certification and closure](../2026-10-08/02-repair-track-certification-and-closure.md) (milestone: duplicate plays / scoring / complete metrics). That contract keeps its text and completion matrix; this contract is linked from it by Amendment.
- **Implementation log:** `session_logs/2026-10-09/03-byplay-v2-implementation.md`
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
- The shadow historical build reproduces the pinned legacy by-play and drives for these games exactly, apart from `field_position_bin` (later code change) and `ppa` zero-fill versus null (41 and 115 rows, all legacy-zero/new-null).
- The historical dedup removed 28 plays: 19 with non-null PPA, 3 scoring, 25 in regulation, 3 in overtime. This matches the census.
- Retaining them adds 1 + 24 by-play rows, 0 + 9 net drive/possession rows, and changes scoring events (2025: 1 historical-only, 2 retained-only). No cell of any other by-play row changes. 92 team-game measurement cells change in 3 games (2021 Week 1; 2025 Weeks 6 and 8), reaching 6 team-games. The overtime-only game changes no regulation measurement. Excluding the 6 unresolved plays instead leaves the same observation changes (16 and 76 cells).
- Drive-number reuse across provider drive IDs occurs only in the 3 collision games of 2025; no game outside the collision games has it.
- Clock census over 1,538,279 compared pairs (no exclusion applied): 3,688 reversals, of which 12 involve impossible clock values (39 regulation rows in 2021 with `clock_minutes` above 15, up to 58) and 3,676 have valid clocks. Of the valid ones, 310 land on a fresh 15:00 clock (the period label looks wrong for those plays) and 1,702 exceed 60 seconds without being a period reset; they are far commoner in 2021–2026 than in 2015–2019 and are not explained by replay review.

**Open decisions for the user (not taken by this contract):** keep the two-case unresolved rule as written; whether the clock and period-label anomalies get their own read-only investigation; proceed to Task 2.
