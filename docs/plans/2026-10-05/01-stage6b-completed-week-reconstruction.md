# Stage 6B: Completed-Week Reconstruction (2026 Weeks 0–5)

- **Status:** Draft (awaiting user review; no implementation authorized yet)
- **Created:** 2026-10-05
- **Planner:** Claude Code (planning session on `dev`)
- **Approval source:** The user approved the 6B plan in the planning chat on 2026-10-05 and chose four scope decisions (write boundary, weeks, 2026 offset rule, new execution contract). Approval covered Task 0 and drafting this contract only. This contract is submitted for the user's review; implementation starts only when the user approves it.
- **Governing authority:** [contract 04](../2026-10-03/04-data-integrity-two-window-implementation.md), Amendment 2 (Window 2 task table, row 6B); [Appendix A §6B](../2026-10-03/window2/data-contracts-and-certification.md); [Appendix B](../2026-10-03/window2/release-schema-and-web.md) quote policy. This is a bounded execution contract for 6B, not a competing release authority.
- **Predecessor:** [contract 02](../2026-10-04/02-pre-stage6-integrity-and-rebuild.md) (6A), Implemented 2026-10-05. Its signed receipt is `rebuild/6a/6a-task4-r1/receipt/receipt.json`, checksum `efcedf3e67dd85055782474b5022bf73d7f53d80c630264ca7c491699309d15e`.
- **Implementation log:** to be created at `session_logs/2026-10-05/` when implementation starts.
- **Commit policy:** a documentation commit on `dev` for this contract, then scoped implementation checkpoints. All git operations remain user-run.

## Goal and current state

Rebuild the forecast, market selection and retrospective grading for every certified completed 2026 week (Weeks 0–5) on the corrected 6A foundation, as new immutable Preview artifacts, and keep every original run, prediction, selection, freeze receipt and grade untouched. The output is the corrected "Weeks 0..N−1" replacement set that Stage 7B needs. Stage 7B alone packages, authorizes and selects it; fixing N is also 7B's job.

The served 2026 runs are:

- Weeks 0–4: `2026w{0..4}-v5repair-20260929-p1`, retrospective replays.
- Week 5: `2026w5-v5repair-20260929-p2`, the first prospective run, scored 2026-10-04.

All six used the pre-6A lineage: 276 certified priors from the old terminal, offsets built from the old 11C historical events, and the worst-line away-spread selection (known issue 13). 6A published the corrected foundation but deliberately left out 2026 scoring events, 2026 offsets, application frames, predictions, market selection and grades.

Verified before drafting (read-only, 2026-10-05):

- The Week 5 scored manifest (`artifacts/preview/scored/year=2026/week=5/run_id=2026w5-v5repair-20260929-p2/manifest.json`) records an immutable `outcomes_ref`: `lake/silver/dataset=game_outcomes/version=0ad054089d8fd6883e935417/data.parquet`, content sha `9042bfa5…`. No new finals capture is needed.
- `build_offsets` (`src/cks_picks_cfb/forecast/offsets.py:155`) uses a team's own earlier games only, in kickoff order, with a fixed prior-season league mean.
- `build_live_application_frame` (`src/cks_picks_cfb/forecast/live.py:34`) accepts only states whose cutoff is no later than `as_of`. 6A's `pregame_teams` rows carry kickoff cutoffs, so 6B re-evaluates the rating engine at each week's `as_of`.

## Scope and authority

Include: 2026 scoring events and offsets, rating states at each original forecast cutoff, application frames, bridge predictions with the 6A bundle, market selection from original quote sets under the corrected rule, read-only reproduction of the stored original grades, retrospective grades, a comparison with the served runs, a signed receipt shaped for 7B packaging, and immutable Preview publication.

### Amendment 1 (write boundary, for user approval)

6B is authorized to write only:

- Immutable create-once objects in Preview R2 under `rebuild/6b/<run_id>/`.
- Immutable `lake/gold/` reconstruction datasets (`reconstruction_*`, partitioned by week) registered in the Preview catalog in one transaction as role `cks_preview_pipeline`.

Everything else is excluded, whatever the reason: serving tables (`prediction_runs`, `predictions`, `prediction_market_selections`, `prediction_grades`, `game_results`, `current_week`), authorization and selection records, and any production R2 prefix or production Neon table. Preview database reads are read-only transactions. Every database command runs through `zsh scripts/ops/with_preview_env.sh`. The approval in contract 04 Amendment 3 covered 6A only; this amendment extends the same two write classes to 6B.

Carried over: Seasons are 2015–2019, 2021–2025 and 2026; 2020 is excluded at every boundary. No 2026 outcome enters any coefficient, calibration or hyperparameter fit. The `ppp__rho_0_60__exposure` design, the alpha-10 Ridge recipe and the served calibration are unchanged. Neutral-site handling is not changed (known issue 9). A live publish needs the user's explicit confirmation at publish time.

Excluded: model redesign, neutral-site changes, EPA imputation, fixing cutover N, packaging, authorization or selecting runs, Week 6, prospective-record changes, and matchup work.

## Design decisions

1. **Week set.** Weeks 0–5. Week 5 uses the p2 run's original forecast cutoff and quote set; its original run, selections and grades stay as they are.
2. **Forecast cutoffs.** Each week uses the original `as_of` from the pinned source lock (Weeks 0–4) or the p2 serving manifest (Week 5). No late line fill, and no evidence after `as_of`.
3. **2026 offsets.** 6A semantics: team-games with unresolved scoring markers are unusable, as in the historical corpus. For each week W, games in earlier weeks are usable and the week-W games are forecast-eligible but unusable. A gate checks that frozen-at-cutoff offsets equal kickoff-order offsets; any team playing twice in a week is reported. 6B reports how many 2026 team-games the 6A rule makes unusable and the offset deltas against the served runs.
4. **Rating states.** Rebuild the 2026 rating engine from the published 6A observations, priors and terminal, and evaluate it at each week's `as_of`. A gate requires the ratings to equal 6A `pregame_teams` for every game.
5. **Selection.** `model_side_best_quote_v2` (no late fill; the Away side takes the lowest home-signed line; exact ties go away/under). Thresholds come from `conf/weekly_bets/v5_intended_update_2026.yaml` (all 0.0).
6. **Grading.** Old stored grades are reproduced read-only first; the new grades carry `evidence_class=retrospective_reconstruction`.
7. **Run ids.** New runs are `2026w{W}-v5recon-6b-r1`. Each receipt row names its original run id as the rollback target.

## Ordered implementation tasks

### 0. Issue register (done 2026-10-05, uncommitted at drafting)

`docs/data/known_issues.md` records the 6A updates for issues 2, 3, 7, 10, 13 and 14; the contract 04 row in `docs/plans/index.md` is updated.

### 1. Generalize the harness (6A output must not change)

- Add an optional `namespace` to the plan (`rebuild/6a/` default, or `rebuild/6b/`); emit it in the plan's signed form only when it is not the default, so 6A's `plan_sha` is unchanged.
- Take the run namespace from the plan in `rebuild/targets.py` (generic error messages) and replace hardcoded `rebuild/6a/{run_id}` prefixes with a shared `run_prefix(context)` helper in the orchestrator, parity, receipt and stage modules.
- `rebuild/published.py` reads the prefix from the root manifest and serves both the 6A main root and the 6A Task 4 root.
- Add the served-chain tokens to the legacy-parent denylist in `rebuild/inputs.py` (`intended-update/2026-runs/20260929`, `2026-serving/2026w`, and the served rating and bundle hashes); only `legacy_allowed` stages may read them.
- `scripts/pipeline/rebuild_6a.py` and `publish_6a.py` accept any `--plan`; the existing names remain. Publish allows the `rebuild/6b/` prefix.
- Test: re-running the 6A plan preflight and dry run reproduces the recorded `plan_sha` and object lists.

### 2. Build the 6B stages (`conf/rebuild/6b_v1.yaml`, run `6b-replay-20261005-r1`)

Pins, each with a hash taken from a hash-checked read: the 6A main root manifest (raw `741d262f…`), the 6A Task 4 root manifest (raw `3431a5fc…`, receipt checksum `efcedf3e…` asserted), the 2026 source lock, the bets config, the Week 5 p2 market snapshot and quote refs, the Week 5 `game_outcomes` ref, and the served run manifests (comparison and grade reproduction only).

| # | Stage | Builds | Hard gates |
|---|---|---|---|
| 1 | `foundation` | Verifies the 6A roots and receipt signature; rebuilds the locked schedule | Every `inputs_for_6b` hash; cutoff equals the plan's; 271 games (8/43/49/57/58/56); each week's `as_of` after the last week W−1 kickoff and before the first week W kickoff |
| 2 | `scoring_events_2026` | Re-runs the possession measurement on the published 2026 Silver; persists 2026 events as `baseline_unchanged` | Observations equal 6A `states_2026/observations` by frame digest |
| 3 | `offsets_2026` | Offsets per week from 6A admitted historical events plus 2026 events | Historical rows equal 6A `forecast/offsets`; frozen offsets equal kickoff-order offsets. Reported: unusable team-games, deltas against served offsets |
| 4 | `states_at_cutoff` | Rating engine evaluated at each week's `as_of` | Ratings equal 6A `pregame_teams` for every game. Reported: deltas against served states |
| 5 | `application_frames` | One frame per week (`home_host=1.0`, `venue_unknown=True`) | Per-week row counts |
| 6 | `predictions` | Bridge predictions with the 6A `bundle.json` | Training seasons at most 2025; every state cutoff at most `as_of`; every usable offset game kicked off before `as_of`; bundle compatibility checked first |
| 7 | `markets` | Selection from the original quote sets under rule v2 | Lock-recorded quote gaps match (Week 3 game 401856811 total). Reported: lean flips, selected-line changes (including the 34 issue 13 rows), coverage |
| 8 | `finals` | Weeks 0–4 from the lock `games` rows, Week 5 from the pinned `game_outcomes` ref | Read-only cross-check against Preview `game_results` agrees |
| 9 | `old_grade_reproduction` (`legacy_allowed`) | Recomputes the six originals' stored grades | 0 mismatches against stored Preview grades and the served `scored.csv`; the next stage does not run otherwise |
| 10 | `retrospective_grades` | Grades the new selections against `finals` | Every grade labelled `retrospective_reconstruction` with its finals refs |
| 11 | `comparison` (`legacy_allowed`) | New against served, per week and season to date | Reported: prediction deltas, lean flips, grade changes, record against 52.4% (retrospective), attribution across priors, states, offsets and selection |
| 12 | `receipt` | Signed `rebuild_6b_receipt_v1`, re-derived in verify | Per-week new and original run ids, `as_of`, quote-set refs and hashes, admitted input refs, finals refs, artifact hashes; served-format `predictions.csv`, `scored.csv` and manifests per week |

Catalog: new schemas in `data/schema_contracts.py` and registration through `rebuild/catalog_publish.py` in one transaction for `reconstruction_offsets_2026_v1`, `reconstruction_application_frames_v1`, `reconstruction_predictions_v1`, `reconstruction_market_selections_v1` and `reconstruction_grades_v1`. Reports and the receipt stay in R2 only.

Library code must not import `scripts.*`; helpers that exist only there (the grade functions in `backfill_v5_unconstrained_grades.py`) are copied verbatim into `rebuild/legacy.py` with provenance, as 6A did.

### 3. Run and verify

Preflight, then build and verify each stage in order, stopping at the first failed gate; then the full persisted verify. Memory: stages read narrow per-week outputs, never the full play corpus.

### 4. Publish to Preview

Publish dry run, then live `--apply --register-catalog --prove-idempotence` only after the user's explicit confirmation, then an independent read-only readback. The retry must write 0 objects.

### 5. Close out

Signed receipt published; contract amendment with measured results, `docs/status.md`, session log and the receipt hash. The contract becomes Implemented only after the gates below pass.

## Validation

- Tests with in-memory fixtures: the 6A plan hash is unchanged; a 6B write to `rebuild/6a/` or any serving prefix is rejected; the per-week offset freeze; the state-at-cutoff gate; each leakage gate; the v2 away-line rule; grade recompute and mismatch detection; receipt tamper detection; catalog registration rollback.
- Full Python suite (`uv run python -m pytest tests -q --no-cov`), `uv run ruff check .`, `make contracts-check`, `uv run mkdocs build --quiet`, `git diff --check`.
- Live: stage gates in the persisted verify; the dry run lists only `rebuild/6b/` and `lake/gold/reconstruction_*` keys; idempotent retry; readback with 0 mismatches. The write ledger and allow-list are the evidence for "no serving change".

## Risks and amendments

- **Bundle compatibility.** Whether the 6A refit bundle passes `apply_exported_bridge`'s schema and season checks is unverified. If it needs an adapter, stop and amend before continuing.
- **Offset freeze.** The served replays used kickoff-order offsets. If frozen-at-cutoff offsets differ from them in this data, stop and bring the difference to the user; that is a replay cutoff policy question.
- **Threshold config drift.** The lock pins `v5_replay_2026.yaml` at a hash that no longer matches the file. New runs pin the current all-zero config; the original grades are reproduced only from stored artifacts.
- **Week 5 quotes.** Whether production's frozen p2 used the same quote set as Preview's is not verified; 6B makes no production claim.
- **Stored grades.** Preview may hold grades from more than one selection policy version; the reproduction reads them version-agnostically.
- **7B format.** 6B emits served-format artifacts inside `rebuild/6b/` so 7B can package them byte for byte; whether that suffices is 7B's decision.

Stop the affected step on any material conflict with the approved population, scoring decisions, model recipe or write scope; retain the evidence and amend this contract before continuing. Any change to replay cutoff policy or data identities is material (contract 04, Amendment 2).

## Definition of done

- [ ] Harness generalization merged with the 6A plan hash and outputs unchanged.
- [ ] All twelve stages built and independently verified in a persisted full verify.
- [ ] Original grades reproduced with 0 mismatches before any new grade is produced.
- [ ] Weeks 0–5 predictions, selections and retrospective grades built under the corrected rule, with leakage gates passing.
- [ ] Comparison with the served runs and the signed 6B receipt retained.
- [ ] Preview publication, catalog linkage, readback and retry pass with no serving, selection, grade or production write.
- [ ] Docs, issue register and implementation log reflect the measured results.
- [ ] Contract marked Implemented only after all gates above; Stage 7B remains a separate handoff.
