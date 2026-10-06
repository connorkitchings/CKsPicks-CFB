# Session: Stage 6B implementation

## TL;DR
- **Worked On:** Stage 6B execution contract (`docs/plans/2026-10-05/01-stage6b-completed-week-reconstruction.md`), Task 0 (issue register), Task 1 (harness generalization), and Task 2 (reconstruction stages).
- **Outcome:** Contract, Amendment 1, Task 1, and Task 2 implemented. Added all 12 stages, 5 reconstruction schemas, pinned execution plan `conf/rebuild/6b_v1.yaml`, and comprehensive test suite. Full repo validation clean (1,968 passed, 9 skipped). Tasks 3-5 open.
- **Next:** Task 3, staged execution and persisted verification (`rebuild_6a.py preflight`, `build`, and `verify`).

## Task 2 (reconstruction stages)
- **Schemas:** Registered 5 week-partitioned Gold schemas in `src/cks_picks_cfb/data/schema_contracts.py` (`reconstruction_offsets_2026_v1`, `reconstruction_application_frames_v1`, `reconstruction_predictions_v1`, `reconstruction_market_selections_v1`, `reconstruction_grades_v1`).
- **Write boundary:** `GuardedStore` in `src/cks_picks_cfb/rebuild/targets.py` restricts writes under `rebuild/6b/` strictly to `rebuild/6b/<run_id>/` and `lake/gold/dataset=reconstruction_*`, rejecting Silver, unrelated Gold, quality-receipt, serving, and production writes.
- **Plan:** Pinned `conf/rebuild/6b_v1.yaml` for run `6b-replay-20261005-r1` with hash-checked pins for 6A main root (`741d262f...`), Task 4 root (`3431a5fc...`), signed receipt (`bcd5783d...`, checksum `efcedf3e...` asserted), source lock, bets config, Silver 2026 parents, and served release packet (`deb1fd34...`).
- **Namespace dispatch:** `src/cks_picks_cfb/rebuild/recon_stages.py` defines `SIX_B_STAGE_BUILDERS`; `src/cks_picks_cfb/rebuild/stages.py` dispatches by `plan.namespace` so 6B `receipt` uses its own builder while 6A remains unchanged.
- **Legacy helpers:** Copied `spread_result`, `total_result`, `_profit`, `_normalize_result`, and `score_bets` verbatim into `src/cks_picks_cfb/rebuild/legacy.py` with provenance so library code remains independent of `scripts.*`.
- **Stages:**
  1. `foundation`: Verifies 6A roots, receipt checksum, and `inputs_for_6b`; reconstructs 271 games (8/43/49/57/58/56) and validates `as_of` chronologies (`recon_foundation.py`).
  2. `scoring_events_2026`: Re-runs possession measurements on published 2026 Silver as `baseline_unchanged`; requires observations digest to match 6A (`recon_foundation.py`).
  3. `offsets_2026`: Rebuilds frozen offsets and gates on parity with kickoff-order offsets; reports unusable team-games (`recon_offsets.py`).
  4. `states_at_cutoff`: Evaluates `IntendedUpdate` engine at each original `as_of`; gates on exact match with 6A `pregame_teams` (`recon_states.py`).
  5. `application_frames`: Constructs weekly frames (`home_host=1.0`, `venue_unknown=True`) with exact schedule coverage (`recon_forecast.py`).
  6. `predictions`: Verifies bridge bundle compatibility (`apply_exported_bridge`) before generating predictions; enforces pre-2026 training and state cutoff limits (`recon_forecast.py`).
  7. `markets`: Evaluates `model_side_best_quote_v2` quote selection; lowest home-signed spread for away, exact ties break away/under, preserves Week 3 missing total (`recon_markets.py`).
  8. `finals`: Locked Weeks 0-4 outcomes and pinned Week 5 outcomes; read-only cross-check against Preview `game_results` (`recon_markets.py`).
  9. `old_grade_reproduction`: Recomputes stored grades for the 6 original runs against Preview DB; enforces 0 mismatches before permitting new grades (`recon_grades.py`).
  10. `retrospective_grades`: Grades corrected selections with finals provenance and `retrospective_reconstruction` evidence labels (`recon_grades.py`).
  11. `comparison`: Compares new against served per week and season-to-date; reports prediction deltas, lean flips, line changes, grade movements, retrospective records vs 52.4%, and multi-factor attribution (`recon_comparison.py`).
  12. `receipt`: Emits signed `rebuild_6b_receipt_v1`, per-week lineage, rollback targets, and served-format `predictions.csv`, `scored.csv`, and `manifest.json`; verified by re-derivation (`recon_receipt.py`).

## Task 1 (harness generalization)
- `RebuildPlan.namespace` (`rebuild/6a/` default, `rebuild/6b/` allowed). It enters the signed plan and the root manifest only when it is not the default, so published 6A plans and roots keep their exact hashes (6A plan shas `fc263834...` and `dff398aa...` are pinned in a test).
- `GuardedStore(run_namespace=...)`; the orchestrator's root key, the parity receipt keys and `PublishedRun`'s prefix follow the plan or root. Preflight refuses a guard that lacks the plan's namespace. The existing 6A stage modules keep their fixed `rebuild/6a/` prefixes, so a 6B plan cannot run one: the guard rejects the write.
- Served-chain tokens (run and serving paths, rating `e80ae347...`, bundle `30c4f1eb...`) are in `LEGACY_PARENT_TOKENS`; only `legacy_allowed` stages may read them.
- `scripts/pipeline/rebuild_6a.py` and `publish_6a.py` pass the plan's namespace to the guard; they keep their names.

## Decisions
- Write boundary (Amendment 1): Preview R2 `rebuild/6b/<run_id>/` plus `lake/gold/reconstruction_*` with catalog registration; no serving, selection, grade, authorization or production writes (user choice).
- Replay Weeks 0-5; Week 5 uses the p2 run's original cutoff and quote set (user choice).
- 2026 offsets use 6A semantics (unresolved team-games unusable); the run stops if frozen-at-cutoff offsets differ from kickoff-order offsets (user-approved gate).
- The run stops, before predictions, if the 6A bundle needs an adapter (user-approved gate).
- Contract is a new execution contract; production claims about the Week 5 quote set are excluded.
- The 6A stage modules keep fixed `rebuild/6a/` prefixes rather than being rewritten; the guard rejects them under a 6B plan.
- Stage builders dispatched by `plan.namespace` so 6B `receipt` uses `recon_receipt` while 6A `receipt` stays unchanged.

## Files changed
- Docs: `docs/plans/2026-10-05/01-stage6b-completed-week-reconstruction.md` (In Progress), this log.
- Config: `conf/rebuild/6b_v1.yaml` (new).
- Code:
  - `src/cks_picks_cfb/data/schema_contracts.py` (5 reconstruction Gold schemas)
  - `src/cks_picks_cfb/rebuild/targets.py` (6B GuardedStore namespaces)
  - `src/cks_picks_cfb/rebuild/stages.py` (namespace dispatch)
  - `src/cks_picks_cfb/rebuild/legacy.py` (copied grading & scoring helpers)
  - `src/cks_picks_cfb/rebuild/recon_common.py` (shared lake/data helpers)
  - `src/cks_picks_cfb/rebuild/recon_foundation.py` (stages 1 & 2)
  - `src/cks_picks_cfb/rebuild/recon_offsets.py` (stage 3)
  - `src/cks_picks_cfb/rebuild/recon_states.py` (stage 4)
  - `src/cks_picks_cfb/rebuild/recon_forecast.py` (stages 5 & 6)
  - `src/cks_picks_cfb/rebuild/recon_markets.py` (stages 7 & 8)
  - `src/cks_picks_cfb/rebuild/recon_grades.py` (stages 9 & 10)
  - `src/cks_picks_cfb/rebuild/recon_comparison.py` (stage 11)
  - `src/cks_picks_cfb/rebuild/recon_receipt.py` (stage 12)
  - `src/cks_picks_cfb/rebuild/recon_stages.py` (stage builders registry)
- Tests: `tests/test_rebuild_namespace.py` (10 tests), `tests/test_rebuild_6b.py` (12 tests).

## Validation
- `tests/test_rebuild_6b.py` (12 passed).
- `tests/test_rebuild_namespace.py` (10 passed).
- `tests/test_schema_contracts.py` (8 passed).
- Full Python suite: 1,968 passed, 9 skipped.
- `ruff check .` clean (0 errors).
- `make contracts-check` clean.
- `mkdocs build --quiet` clean.
- `git diff --check` clean (0 whitespace/newline issues).
- Preflight pin and remote storage validation simulation: passed (SHA `744f2975...`).
- Zero writes to Preview R2, database, serving, or production during this task.

## Blockers
- None.

## Contract status
`docs/plans/2026-10-05/01-stage6b-completed-week-reconstruction.md` stays **In Progress**: Definition-of-done items 2-8 remain open for Tasks 3-5.

## Next
Task 3: Execute staged build and verification using `scripts/pipeline/rebuild_6a.py` with `conf/rebuild/6b_v1.yaml` (preflight, build stages 1-12, stage-level verify, and full persisted verify). All git operations and live publishes remain user-run.

**tags:** ["stage6b", "reconstruction", "stages", "receipt", "comparison", "contract"]

## Task 2 quality review follow-up (2026-10-05)

Task 2 was audited under [quality review contract](../../docs/plans/2026-10-05/02-stage6b-task2-quality-review.md) after commit `7b93608`. Four confirmed defects were repaired: signed receipt verification now consumes the original payload after checksum validation; scoring events declare the source lock; required summaries and gates reject missing evidence; and receipt verification compares canonical serialized content. Additional fixes cover source pins, cutoff checks, complete Preview finals, full-key Preview/served grade reproduction, market input normalization, typed Gold lineage, direct-parent reads, and deterministic persisted re-derivation. The detailed contract-to-evidence table is in the quality review session log.

The full six-week, 271-game fixture pipeline passed through the real orchestrator. A fresh orchestrator verified all persisted stages, and an identical retry preserved all bytes. No Preview, serving, authorization, or production writes occurred. This fixture result does not establish live Preview parity; Task 3 must capture the new committed HEAD and run fresh preflight, then build and verify stages sequentially, stopping at the first failure.

**Updated review status:** Stage 6B contract remains **In Progress**. After user commit `4f09aef`, Task 3 preflight passed, and `foundation` through `predictions` built and verified. `markets` stopped with zero selections instead of 541 because Preview snapshots provide `spread_line`/`total_line`; the committed builder looked up `spread`/`total`. A local follow-up now maps those actual columns, and the 27-test fixture flow passes with Preview-shaped market inputs. This follow-up needs a user commit and a fresh preflight before Task 3 resumes; no later stage ran. Strict MkDocs also remains blocked by existing relative-link warnings. No Preview R2, database, serving, or production writes were made. Git staging and commits remain user-run.
