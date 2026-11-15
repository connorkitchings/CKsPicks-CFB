# V5 baseline audit and model analysis framework

- **Status:** Draft
- **Created:** 2026-11-14
- **Planner:** Sol
- **Approval source:** The owner approved writing this Draft and running the local read-only inventory on 2026-11-14, after two rounds of review. Approval to execute any step of the work order is the next gate and is given per step.
- **Implementation log:** `session_logs/2026-11-14/02-baseline-audit-contract-and-inventory.md` (this Draft and the inventory), `session_logs/2026-11-14/03-baseline-input-retrieval.md` (the approved retrieval)
- **Commit policy:** Commit on local `dev` with the documentation. No push.

## Goal and acceptance

Before any V6 candidate is designed, establish which model is being studied, whether its inputs are reproducible, and where its error comes from. The first deliverable is a baseline audit; analysis tables follow it.

Acceptance for this Draft: the three baselines are named; the local inventory classifies every required artifact as present and hash-verified, referenced but unavailable locally, or missing/unknown; the next executable scope is stated exactly; the protocol amendments are proposed, not applied.

**Scope limit.** The six-step work order below is a research roadmap. No model execution, new diagnostic scoring, source retrieval requiring credentials, candidate experiment, or protocol amendment is authorized by this documentation-and-inventory task. The existing adoption thresholds in the [research protocol](../2026-11-12/02-offseason-research-protocol.md) stay as approved until their amendments are separately decided.

## Baselines

| Name | What it is | Role |
|---|---|---|
| Historical V5 | The 2026-09-21 frozen model pinned by the ratings-lab corpus | Reproducibility reference only |
| Operational V5 | A historical replay of the intended-update model that serves the site (`model_id` `v5-intended-update-2026-v1`) | The benchmark a candidate must beat |
| Closed V6 | The `kalman_exposure_v1` multi-factor tournament, `RETAINED_AS_BENCHMARK` on 2026-09-30 | Historical comparator |

The [prediction-error diagnostics](../../modeling/prediction_error_diagnostics_2021_2025.md) describe Historical V5 and have not yet been established for Operational V5. The report remains valid for its stated baseline.

The retained repair experiment (`docs/archive/research/2026-09-28-v5-intended-update-repair-experiment.md`) reports, for 2022 to 2025 on 3,659 games per target: current-season evidence in 1,926 of 35,740 historical states (5.4%) against 29,376 (82.2%) in the repaired arms; margin MAE 14.320 against 13.744; total MAE 13.662 against 13.507. The repaired arm is worse at completed-game stages 0 to 3 and better at 4+. These are documented results; nothing was rerun for this contract.

## Inventory (2026-11-14, local and repository only)

This section is the state before the retrieval. The [retrieval section](#retrieval-2026-11-14-owner-approved) below supersedes the rows it names.

Method: every child listed in each ratings-lab stage manifest under `~/cfb_ratings_lab_v6/output` was read and its SHA-256 compared with the manifest. Repository files were hashed directly. Nothing was read from R2 or any database.

### Present and hash-verified

| Artifact | Baseline | Evidence |
|---|---|---|
| Corpus stage `fb0baf90841f51d42958665c` (seven tables: population 8,936, outcomes 8,936, observations 285,952, scoring events 86,937, terminal 8,794, V5 features 8,935, V5 predictions 7,318) | Historical V5 | 64 of 64 children match |
| Closed V6 measurements, 5 stages (four `v6_4factor_game_v1`, one `v6_5factor_game_v1`) | Closed V6 | 50 of 50 children match |
| Closed V6 ratings, 5 stages | Closed V6 | 50 of 50 children match |
| Closed V6 features, 5 stages | Closed V6 | 50 of 50 children match |
| Closed V6 predictions, 10 stages (`alpha10_direct18` x4, `alpha10_differentials` x5, `alpha10_direct22` x1; 7,318 rows each, 2022 to 2025) | Closed V6 | 40 of 40 children match |
| Closed V6 comparisons, 4 stages | Closed V6 | 4 of 4 children match |
| Repair experiment summary `docs/archive/research/2026-09-28-v5-intended-update-results.json` (SHA-256 `b7b345b1982812b1879f294ea9eca222fdbb8d8f08f49ac96e788d3005cc625b`) | Historical V5 and repaired arms | In git. Its five parent hashes equal the corpus parents, so the experiment ran on the Historical V5 inputs |
| Serving model manifest `conf/season/2026/model_manifest_v1.json` | Operational V5 | In git; names the pins listed below |

The Closed V6 stages carry five distinct code hashes, consistent with the five scoring runs recorded in its log.

### Referenced but unavailable locally

| Artifact | Needed for | Reference |
|---|---|---|
| Repair experiment row-level outputs: 12 parquet files (states, predictions, early predictions for four arms) | Step 2 historical reproduction | Named with SHA-256 in the results JSON (for example `predictions_v5_game_adjusted_at_cutoff_v1.parquet`, `2c3ec6c2…`); not found on this machine |
| Historical V5 control inputs: measurement snapshots, priors, certified rating states | `replay_v5_control`, the repair-arm runner | Read from the pinned measurement and rating parents in Preview R2; the local `source` directory is empty |
| Lower-level datasets: `byplay`, `drives`, `plays`, `fbs_involved_games`, `game_outcomes`, `reconciled_team_game`, `team_game_stats` | Any new measurement or accounting from plays | Referenced by URI and content hash in the corpus manifest |
| Serving bridge bundle `…/intended-update/runs/v5-intended-update-corrected-w5-r1/bundle.json` (`a507d0c7…`) | Operational equivalence | `model_manifest_v1.json` |
| Serving priors, terminal table, historical population and events under `rebuild/6a/6a-rebuild-w6-20261012-r2` | Operational equivalence | `model_manifest_v1.json` |

### Present, not verified against a pin

| Artifact | Note |
|---|---|
| `score-attribution/` cache: `byplay` and `fbs_involved_games` for 2021 to 2025 | The `byplay` files for 2021 and 2025 do not hash to the corpus's `content_sha` for those seasons. They may be re-serialized or a different version; unknown. Not usable as verified inputs |
| `score-attribution/` 2026 files (plays, schedule, finals) | 2026 data on disk. Research code must not read them |
| `ratings-lab/v1/diagnostics/…/game_site_context.parquet` | Cached from Preview on 2026-11-12 for the diagnostics report; no manifest |

### Missing or unknown

- **No historical replay of Operational V5 was found locally** (superseded in part by the retrieval: historical states for the operational recipe exist in Preview storage). The repair experiment used the 2026-09-21 parents. The serving model takes its priors, terminal table, historical population and events from the 2026-10-12 rebuild (`6a-rebuild-w6-20261012-r2`) and applies a pinned bridge bundle. The experiment therefore differs from serving in input lineage as well as in bridge fitting.
- **How the serving bridge bundle was fitted** (seasons, rating lineage, penalty) is not established from the repository. It needs the bridge manifest.
- Whether a local-verified cache from the repair run (`--verified-cache`) survives anywhere.
- Historical market lines for 2021 to 2024 (only the 2025 diagnostic is known).
- The original prepared artifacts the [ratings audit](../../modeling/v5_offense_defense_ratings_audit_2026.md) could not recover.

### Capability table

| Capability | Code | Runs offline today |
|---|---|---|
| Historical V5 bridge-level scoring and slicing | `ratings_lab/evaluation.py`, `error_slices.py`, `total_bias.py` | Yes, from the corpus (last demonstrated by the 2026-11-12 diagnostics run; not rerun today) |
| Closed V6 scorecards | `evaluation.scorecard` on the verified prediction stages | Yes |
| Historical V5 rating-state replay | `ratings_lab/v5_control.py` | Yes: ran offline on 2026-11-14 inside the repair-script rerun and passed its fidelity gate |
| Repair-arm replay | `scripts/research/v5_intended_update_review.py` | Yes: ran offline on 2026-11-14 from a cache built out of the mirror, reproducing the retained results |
| New measurements from plays | `Corpus.read_byplay`, `ratings_lab/measurements.py` | No: needs lower-level datasets |
| Operational V5 historical scoring | Serving states plus the rebuild feature frame through `common_bridge_predictions` | Yes: ran offline on 2026-11-14; predictions and scorecard are local. The states come from the serving bridge run; rebuilding them from plays is still not possible offline |
| Paired comparison per protocol | `evaluation.paired_comparison` returns 90% season/week intervals | Gap against the written protocol |

`replay_v5_control` reproduces downstream rating states from certified snapshots and priors. It is not a rebuild from plays.

## Retrieval (2026-11-14, owner-approved)

The owner approved one credentialed, read-only retrieval on 2026-11-14. It used the Preview read credential with GET, HEAD and LIST only; nothing was written to any bucket or database, and no model was run or scored. Exact object bytes were mirrored under `~/cfb_ratings_lab_v6/source/` at their original keys, with SHA-256 and size recorded in `_retrieval_index_control_2026-11-14.json` and `_retrieval_index_serving_2026-11-14.json` in that folder.

### Retrieved and verified

| Artifact | Result |
|---|---|
| Historical V5 control inputs (measurement manifest, retained rating manifest, snapshots, priors, rating states) | 319 objects, 10.0 MB. Both manifests match their pins (`10b380d6…`, `9d00e635…`). Loaded through `load_v5_control`, whose readers verify each child's hash before decoding: snapshots 142,960 rows, priors 4,536, rating states 35,740. Reloading from the local mirror alone, with no network source, gives the same shapes |
| Serving bridge bundle | SHA-256 `a507d0c7cba5419868eac5c0955853d3e2855fc857aabf36f5cd192d5e7a90f1`, equal to the pin in `model_manifest_v1.json` |
| Serving bridge manifest and its verifier manifest | Retrieved (`52022234…`, `dd144a2a…`); the verifier manifest names the same bridge-manifest and bundle hashes and reports state `verified` |
| `6a-rebuild-w6-20261012-r2` root manifest and 15 stage summaries | Retrieved (root manifest `9d218543…`). The run's data files (29 objects, about 23 MB) were listed, not fetched |

### How the serving bridge was fitted (from its manifest and bundle)

- Candidate `v5_game_adjusted_at_cutoff_v1`, the intended-update arm; run `v5-intended-update-corrected-w5-r1`; state `frozen`.
- Alpha-10 Ridge, `reference` head, fitted on all ten development seasons (2015 to 2019, 2021 to 2025), 8,935 rows. Calibration variance comes from 7,192 earlier-only residuals per target (margin 317.65, total 301.24).
- Its parent is the corrected rebuild `6a-rebuild-w5-20261007-r2`, not the `w6` rebuild that supplies the serving priors, terminal table, population and events.
- The run also holds `historical-states.parquet` (35,740 rows, 6.4 MB, raw SHA-256 `8df690ce…`): historical rating states for the operational recipe. It was listed, not fetched.
- Because the bundle is fitted through 2025, it cannot score 2022 to 2025 without leakage. No earlier-only historical predictions for the operational recipe were found in the run.

### Observations from the retrieved files (facts about the files, not new scoring)

- The bundle carries coefficients for the four standardized ratings only. `home_host` and `venue_unknown` are in `feature_order` but have no coefficient; the margin intercept is 7.43 points. The contribution section below shows why: both flags are constant and the fit drops non-varying features.
- Total coefficients per standardized rating are +1.66 (home offense), -0.99 (home defense), +0.51 (away offense), -1.11 (away defense), against 6.7 to 9.5 in absolute value for margin. If the four inputs were uncorrelated with unit spread, the predicted total would have a standard deviation of about 2.3 points before offsets. The actual spread still has to be measured in step 2, but the flat-totals question applies to the serving bridge as well as the historical one.
- Home offense moves the total about three times as much as away offense. Unexplained; a step 2 item.
- The `w6` rebuild contains its own `forecast/bundle.json` (`63476e48…`) that differs from the serving bundle in centers, scales (about 0.50 to 0.61 against 0.79 to 0.87) and coefficients. Its `ratings/summary.json` names candidate `ppp__rho_0_60__exposure`. It appears to be the historical update recipe on rebuilt data, and it is not what serves.
- So the serving model combines a bridge fitted on `w5`-rebuild intended-update states with priors and a terminal table from the `w6` rebuild. The second retrieval below shows those historical inputs are byte-identical between the two rebuilds.

### Second retrieval (2026-11-14, owner-approved): historical states and the `w5` rebuild manifests

Same method and credential. Indexed in `_retrieval_index_states_2026-11-14.json`.

| Artifact | Result |
|---|---|
| `historical-states.parquet` of the serving bridge run | 6,431,669 bytes; SHA-256 `8df690ce3d35ece3ae0bf9f68d7c6953e5907a8a7ef63f8e36fc35aa279ddaec`, equal to the bridge manifest and its verifier manifest. 35,740 rows, one candidate (`v5_game_adjusted_at_cutoff_v1`), 17,870 offense and 17,870 defense states, all ten development seasons. Columns: season, week, game, cutoff, team, role, mean, variance, prior mean, prior variance, usable exposure, evidence game IDs, explanation |
| `6a-rebuild-w5-20261007-r2` root manifest and 15 summaries | Root manifest SHA-256 `7865d35336b039f8983ee235c6855d2795a9b35233a779a7a67a959aee89d9b0`, equal to the parent named in the bridge manifest. Data files (about 23 MB) listed, not fetched |

Comparing the two rebuild root manifests object by object (run name normalized): the terminal table (`4dfdbbe3…`), 2026 priors (`6091ef53…`), raw population (`e35f6792…`), admitted events (`fda63e79…`), and the forecast feature frame, offsets and bundle are byte-identical in `w5` and `w6`, and the first four equal the pins in `model_manifest_v1.json`. The two rebuilds differ only in 2026 state files, three stage summaries and the underlying lake object versions. The bridge's parent and the serving inputs are therefore consistent for historical data.

This file is the historical rating-state set for the operational recipe. No statistic was computed from it beyond row counts and schema.

### Historical reproduction rerun (2026-11-14, owner-approved)

The owner approved rerunning `scripts/research/v5_intended_update_review.py` locally. It ran offline through the script's `--verified-cache` option, from a cache built out of the hash-verified local corpus and the control-input mirror (`~/cfb_ratings_lab_v6/cache-intended-update-2026-11-14/`, with `_index.json`). Output is in `~/cfb_ratings_lab_v6/output/intended-update-rerun-2026-11-14/`; the report's SHA-256 is `2cfef8be12c18cf6e587cc06a73f8d43775f72670f8240123df2b3ce90a32fd4`. Runtime 100 seconds. No bucket or database was touched.

Compared with the retained `2026-09-28-v5-intended-update-results.json`:

| Check | Result |
|---|---|
| Structure (every key in every section) | Identical |
| Numeric values: 2,543 across replica fidelity, the frozen-bridge difference, the sparse-graph checks, pooled, by-season and by-stage metrics for four arms, early diagnostics, and paired bootstrap comparisons | Largest absolute difference 2.8e-14 |
| Script's own gates: certified replica fidelity and the refitted bridge against the 7,318 frozen predictions (tolerance 1e-9) | Passed |
| Row counts of the 12 output files | Equal (35,740 states, 7,318 predictions, 5,318 early predictions per arm) |
| SHA-256 of the 12 output files | None equal |
| Whole-report bytes | Not identical, because the report embeds the 12 file hashes |

What this establishes: the retained experiment's reported results are reproduced to floating-point precision from the pinned inputs, including 2022 to 2025 margin MAE 14.3197 (historical replica) and 13.7443 (cutoff-specific repair). What it does not establish: row-by-row identity with the original output files. Those files are unavailable, and the differing hashes do not distinguish different rows from different parquet encoding; the cache was written without the script's original compression setting and library versions may differ. Agreement of 2,543 aggregates, including per-season and per-stage cells and seeded bootstrap intervals, makes different rows unlikely, but that is an inference.

### Operational state comparison (2026-11-14, owner-approved)

Row-level comparison of two rating-state sets for the same recipe (`v5_game_adjusted_at_cutoff_v1`): the serving bridge run's `historical-states.parquet` (rebuilt data) against the rerun's repaired arm (2026-09-21 inputs). States only; no bridge was fitted and no game was scored. Ratings are in standardized units (spread about 0.85 in both sets).

| Check | Result |
|---|---|
| Rows, columns, duplicates | 35,740 each; same columns; no duplicate keys |
| Keys (season, game, team, role) | Identical sets; none missing on either side |
| Week and forecast cutoff | Equal in all 35,740 rows |
| Contributing game sets | Equal in 35,698 rows; in 42 rows the serving set has one more game |
| States with any current-season evidence | 29,378 serving, 29,376 experiment |
| Usable exposure | Equal in 35,698 rows (largest difference 13 possessions) |
| Prior mean | Equal within 1e-9 in 3,850 rows; median absolute difference 0.013, 99th percentile 0.138, largest 0.859 |
| Rating mean | Equal within 1e-9 in 1,154 rows; median absolute difference 0.023, 90th percentile 0.097, 99th percentile 0.287, largest 0.864; correlation 0.9965; mean signed difference +0.003 |
| Population | FBS teams 33,452 rows (median difference 0.024); non-FBS 2,288 rows (median 0.014) |
| By season, FBS teams | Median difference 0.005 in 2015, 0.016 to 0.019 in 2016 to 2019, 0.022 in 2021, 0.041 to 0.045 in 2022 to 2025 |

What this establishes: the two sets agree on structure, timing and, in all but 42 rows, on which games contribute. They do not agree on values. The serving model's historical ratings are close to the experiment's but are not the same numbers, and the gap is about twice as large in 2022 to 2025 as in earlier seasons.

Differences identified in the comparison (the trace below corrects the first reading and narrows the second):

- **Priors differ in 31,890 rows** and are mostly identical only in 2015, the first season. This is consistent with the experiment holding the certified priors fixed (its report says all arms use the accepted preseason priors) while the serving run carries priors from its own earlier-season ratings. That reading is an inference from the pattern, not yet checked in the code that built the serving states.
- **The same game can carry a different observation value.** In the largest difference (Ohio State offense, 2023, before its second game) both sets use the same single game with the same 10 possessions, but its adjusted value is +0.65 in the serving set and -1.05 in the experiment. Candidate causes are the rebuild's 1,416 admitted scoring-event decisions and different standardization scales; the split is not attributed.

#### Trace of the differences (2026-11-14, owner-approved)

Sources: the builder that produced the serving states, read from git history (`scripts/pipeline/build_v5_intended_update_bundle.py` and `src/cks_picks_cfb/rebuild/successor_sources.py` at the parent of commit `bacb1e80`, which removed them); the rebuild's `baseline/admission_report.json`; and the per-game contributions stored in each state's explanation. Nothing was fetched or scored.

- **Same code, different inputs.** The builder calls the same replay as the experiment (`replay` with `V5_GAME_AT_CUTOFF`, `CutoffAdjustment`, `control.fixed_priors()`, `apply_fcs_pool`). With `--corrected-lock` it takes all nine historical frames (population, observations, terminal, outcomes, features, snapshots, priors, rating states) from the corrected rebuild instead of the 2026-09-21 parents. The update rule is not a source of difference.
- **Priors: my first reading was wrong.** Both sets mark every state `certified_fixed_prior: true`; neither carries priors from its own ratings. Each uses the fixed prior table of its own input lineage. Priors are identical in all 3,480 rows of 2015 and differ in almost every row from 2016 on (median difference 0.006 to 0.014 through 2021, 0.021 to 0.033 in 2022 to 2025). So the rebuild's prior table differs from the September one after the first season.
- **Possession counts did not change.** Across 170,337 contributions present in both sets, exposure is equal in every one. The differences are in the values attached to games, not in which possessions count.
- **Game values differ widely but mostly slightly.** Across those contributions the median absolute difference in adjusted value is 0.030, the 99th percentile 0.67, the largest 3.07. Of 28,487 distinct team-role source games, 8.7% differ by more than 0.25 at some cutoff and 0.4% by more than 1.0.
- **The pattern follows the rebuild's scoring corrections.** The share of team-role source games differing by more than 0.25 is 2.5% to 3.9% in 2015 to 2019 and 13.4% to 15.1% in 2021 to 2025. The admission report records 41 to 90 admitted scoring decisions per season in 2015 to 2019 and 193 to 241 in 2021 to 2025 (1,416 in total, 1,389 of them one cause, `dip_restore`). The match in pattern is consistent with the corrections driving the differences; it is not a game-by-game proof.
- **Evidence matters more than priors.** States with no current-season evidence differ by a median of 0.013; states with evidence by 0.026; among the latter the prior gap and the state gap correlate at only 0.15.

Not separated: how much of a game's value change is a direct points correction and how much is propagation through opponent adjustment or a changed standardization scale. That needs the rebuild's observation and terminal tables and its decisions file, which were listed but not fetched.

Consequence for the baselines: the 2022 to 2025 results documented for the repaired arm (margin MAE 13.744) describe the experiment's states, not the serving model's. Operational V5's historical accuracy is still unmeasured; it needs an earlier-only bridge fit on the serving states.

### Operational V5 historical scoring (2026-11-14, owner-approved)

The first new scoring in this work. One more read-only retrieval preceded it: the rebuild's `forecast/feature_frame.parquet` and `forecast/offsets.parquet`, both matching the hashes in the rebuild root manifest (indexed in `_retrieval_index_features_2026-11-14.json`).

| Field | Content |
|---|---|
| Question | What is the 2022 to 2025 accuracy of the serving recipe on the serving input lineage, with a bridge that never sees the scored season? |
| Changes | Against the repair experiment's repaired arm: the rating states (serving bridge run) and the feature frame with its offsets (rebuild) |
| Frozen | Game keys, outcomes, venue flags, completed-game stages, alpha-10 Ridge recipe, earlier-only calibration, evaluation code (`frame_with_candidate_states`, `common_bridge_predictions`, `scorecard`) |
| Refitted | The bridge, once per validation season, on strictly earlier seasons (2022 on 2015 to 2019 and 2021; 2025 on everything through 2024). The serving bundle's coefficients are not used |
| Population | 3,659 games per target, 2022 to 2025, the same keys as the frozen V5 predictions; FBS-involving games including FBS against FCS |
| Cannot show | The accuracy of the serving coefficients themselves (fitted through 2025); anything about 2026; independence, since these seasons are previously examined |

Checks before reading the result:

- The two feature frames agree on every game key, team name, outcome, venue flag, week and completed-game stage. They differ only in offsets: `offset_margin` in 5,406 of 8,935 games (largest 3.2 points) and `offset_total` in 8,480 (largest 7.0).
- Harness check: the same script, given the experiment's states and the September frame, reproduces the rerun's 7,318 predictions with a largest difference of exactly 0.
- The function's population check passed, so outcomes equal those of the frozen V5 predictions.

Pooled 2022 to 2025:

| Model | Margin MAE | Margin bias | Margin 90% coverage | Total MAE | Total bias | Total 90% coverage |
|---|---|---|---|---|---|---|
| Historical V5 (rerun) | 14.3197 | +0.05 | 91.1% | 13.6623 | -2.62 | 91.8% |
| Repaired arm, September inputs (rerun) | 13.7443 | +0.19 | 91.5% | 13.5067 | -2.39 | 92.3% |
| **Operational V5, historical** | **13.7424** | +0.19 | 91.3% | **13.4383** | -1.44 | 92.2% |

Operational V5 by season: margin MAE 14.06, 13.81, 13.91, 13.20; total MAE 13.83, 13.65, 13.15, 13.13.

By completed-game stage (margin MAE; margin bias):

| Stage | Games | Historical V5 | Operational V5 | Operational bias | Operational 90% coverage |
|---|---|---|---|---|---|
| 0 | 573 | 15.92 | 16.17 | +7.51 | 85.2% |
| 1 | 301 | 14.28 | 14.41 | +4.19 | 91.0% |
| 2 | 244 | 14.99 | 15.10 | +0.98 | 90.2% |
| 3 | 253 | 13.00 | 13.27 | -1.45 | 93.3% |
| 4+ | 2,288 | 14.00 | 12.95 | -2.07 | 92.8% |

Paired differences from the existing `paired_comparison` (90% interval, season/week blocks, 2,000 replicates, seed 20260928; this is the current function, not the interval the protocol amendment proposes):

- Operational against Historical V5: margin MAE lower by 0.577 (0.302 to 0.862); total lower by 0.224 (0.173 to 0.282).
- Operational against the September repaired arm: margin lower by 0.002 (-0.039 to 0.041); total lower by 0.068 (0.035 to 0.101).

Spread of predictions: predicted margin has a standard deviation of 13.17 points against 21.95 for actual margins; predicted total 1.57 points (range 50.1 to 62.3) against 16.90 for actual totals.

What this establishes, for Operational V5 on 2022 to 2025 with earlier-only fitting:

- Its margin accuracy equals the September repaired arm's; the corrected inputs moved ratings but not pooled margin error. Its totals are slightly better, with about one point less bias, which follows from the changed offsets.
- Flat totals are confirmed for the serving recipe: predicted totals vary by 1.57 points.
- Early-season weakness is confirmed: before a team's first game the margin bias is +7.51 points and 90% coverage is 85.2%; stages 0 to 3 are slightly worse than Historical V5 and stage 4+ is a full point better.
- The neutral-site finding is rechecked in the slice report below.

Outputs are in `~/cfb_ratings_lab_v6/output/operational-v5-historical-2026-11-14/` (predictions SHA-256 `298d9fe58c86385763f53e66e5eeebca0b177b8d8286f12123794c0d855f9999`, early predictions `62d62dec…`, `scorecard.json`).

### Slice report on Operational V5 (2026-11-14, owner-approved)

The existing slice functions (`error_slices.game_attributes`, `attach_slices`, `slice_table`; `site_context.game_context`) run on both models' predictions for 2021 to 2025 (4,546 games; 2021 from each model's earlier-only early-season group, as in the original report). No fitting. Error is actual minus prediction.

- Harness check: the Historical V5 column reproduces the published report cell for cell (for example neutral-site margin bias -4.320, stage 0 margin bias +6.790, week 2 margin bias +4.070).
- Venue and conference rows come from the cache written on 2026-11-12 (`game_site_context.parquet`), which has no manifest; its provenance is the earlier diagnostics run, not a pinned hash.
- Gap and totals terciles are cut from each model's own predictions, so those bins are not the same games in both columns. The partial-quarantine slice was not rerun.

Margin:

| Slice | Games | Historical MAE | Historical bias | Operational MAE | Operational bias | Operational 90% coverage |
|---|---|---|---|---|---|---|
| Home venue | 4,211 | 14.535 | +0.207 | 13.972 | +0.296 | 90.7% |
| Neutral site | 328 | 14.911 | -4.320 | 14.179 | -4.322 | 91.5% |
| Stage 0 | 721 | 16.398 | +6.790 | 16.558 | +7.350 | 84.6% |
| Stage 1 | 364 | 14.489 | +2.308 | 15.100 | +3.815 | 89.6% |
| Stage 2 | 302 | 15.246 | +0.438 | 15.863 | +0.787 | 88.1% |
| Stage 3 | 314 | 13.053 | -1.286 | 13.291 | -1.199 | 93.0% |
| Stage 4 | 2,845 | 14.219 | -2.100 | 13.090 | -2.368 | 92.4% |
| Week 1 | 687 | 15.647 | +1.990 | 15.611 | +2.484 | 87.8% |
| Week 2 | 410 | 15.400 | +4.070 | 16.582 | +5.845 | 84.9% |
| Week 3 | 353 | 15.586 | +2.844 | 15.684 | +2.967 | 88.1% |
| Week 4 | 326 | 13.774 | +0.601 | 13.977 | -0.091 | 92.3% |
| Weeks 5 to 8 | 1,098 | 13.548 | -2.153 | 13.214 | -2.013 | 92.3% |
| Weeks 9 to 12 | 1,160 | 14.391 | -0.698 | 12.756 | -1.232 | 92.6% |
| Weeks 13 to 16 | 512 | 14.901 | -3.072 | 13.121 | -3.262 | 92.4% |
| Conference game | 2,690 | 14.013 | -2.267 | 13.054 | -2.244 | 92.3% |
| Non-conference game | 1,856 | 15.388 | +3.011 | 15.369 | +3.150 | 88.4% |
| Power home team | 2,438 | 14.566 | +1.098 | 13.906 | +1.429 | 91.3% |
| Group of 5 home team | 1,952 | 14.477 | -1.668 | 13.981 | -1.867 | 90.2% |

Total:

| Slice | Games | Historical MAE | Historical bias | Operational MAE | Operational bias |
|---|---|---|---|---|---|
| Home venue | 4,211 | 13.493 | -2.290 | 13.258 | -1.091 |
| Neutral site | 328 | 15.253 | -3.841 | 15.050 | -2.987 |
| Conference game | 2,690 | 13.772 | -2.471 | 13.509 | -1.381 |
| Non-conference game | 1,856 | 13.397 | -2.285 | 13.214 | -0.991 |
| Lowest third of predicted totals | 1,516 | 13.567 | -2.790 | 13.514 | -2.623 |
| Middle third | 1,515 | 13.965 | -1.980 | 13.468 | -1.121 |
| Highest third | 1,515 | 13.325 | -2.415 | 13.183 | +0.078 |

What this establishes for Operational V5 on 2021 to 2025:

- **Neutral site is confirmed and unchanged:** margin bias -4.32 points over 328 games, the same as Historical V5. The repair did nothing for it, as expected when every game is forecast as a home game.
- **All of the repair's gain is in later and conference games.** Margin MAE falls by about 1.0 in conference games, 1.6 in weeks 9 to 12 and 1.8 in weeks 13 to 16. In non-conference games it is unchanged (15.37 against 15.39).
- **Early season is no better and in places worse.** Stages 0 to 2 and weeks 1 to 3 have equal or higher margin MAE than Historical V5; week 2 is 16.58 against 15.40 with bias +5.85 and 84.9% coverage.
- **Total bias is about one point smaller almost everywhere**, but it is uneven across the model's own predictions: the lowest third of predicted totals is still over-predicted by 2.6 points while the highest third is unbiased.

Full cells are in `~/cfb_ratings_lab_v6/output/operational-v5-historical-2026-11-14/slices_historical_vs_operational.json`.

### Contribution spread for Operational V5 (2026-11-15, owner-approved)

Each of the 7,318 Operational V5 predictions for 2022 to 2025 was rebuilt as intercept + four rating terms + offset, using the project's own design and target functions (`forecast/heads.py`: `_design`, `_target`) and the same alpha-10 Ridge per validation season. The rebuilt predictions equal the stored ones to 1.4e-14. No new model; this decomposes the predictions already scored.

Standard deviation of each term, in points:

| Term | Margin | Total |
|---|---|---|
| Home offense rating | 6.04 | 1.40 |
| Home defense rating | 4.81 | 0.44 |
| Away offense rating | 7.90 | 0.48 |
| Away defense rating | 6.66 | 0.67 |
| Four rating terms together | 12.98 | 1.37 |
| Offset | 0.81 | 0.89 |
| Prediction | 13.17 | 1.57 |
| Actual outcome | 21.95 | 16.90 |

Correlation of the prediction with the outcome: +0.606 for margin, +0.164 for total. The offset alone correlates +0.153 with actual margin and -0.022 with actual total.

Bridge coefficients per standardized rating, by validation season: margin 6.8 to 7.1 (home offense), 8.0 to 9.1 (home defense), -8.6 to -8.9 (away offense), -9.6 to -10.7 (away defense); total +1.37 to +1.75 (home offense), -0.56 to -0.97 (home defense), +0.47 to +0.61 (away offense), -0.97 to -1.06 (away defense).

What this establishes about the explanations for flat totals listed in step 2:

- **Venue flags contribute nothing, by construction.** `home_host` and `venue_unknown` equal 1.0 in every row, and `_design` drops any feature that does not vary. Home advantage lives only in the intercept (about 7.1 to 7.3 margin points), which every game receives, neutral-site games included.
- **Not sparse updates and not compressed ratings.** The same four ratings (raw spread 0.50 to 0.77) give margin predictions a spread of 13 points and a 0.61 correlation with outcomes.
- **The fitted total coefficients are small.** A one-standard-deviation change in a rating moves the predicted total by 0.5 to 1.75 points, against 7 to 11 points for margin. This is the main cause.
- **Cancellation is a secondary cause.** Offense and defense terms correlate -0.50 for totals, because a team's offense and defense ratings correlate +0.42 to +0.51. If the four terms were uncorrelated their sum would have a spread of 1.68 points; it is 1.37.
- **Offsets are not the cause, and add no totals signal.** They add 0.89 points of spread that is uncorrelated with actual totals.

Still unexplained: the home offense rating moves the total about three times as much as the away offense rating, in every validation season.

Interpretation, not a finding: the ratings measure opponent-adjusted scoring efficiency, which mostly cancels in a total (a strong team scores more and allows less), so a linear function of them has little to say about how many points a game will have. That points at inputs the bridge lacks, such as possession volume, more than at the rating update. Step 3's scoring accounting and possession-volume questions test this.

Outputs: `~/cfb_ratings_lab_v6/output/operational-v5-historical-2026-11-14/contribution_spread.json`.

### Upstream temporal check (2026-11-15, owner-approved)

Rule tested: every contributing source game precedes the target week, and its kickoff plus six hours is no later than the forecast cutoff. Local files only; nothing fetched. Six hours remains an availability assumption, and every serving state is labelled `historically_reconstructed`: these checks show the reconstruction is internally consistent, not when data was actually captured.

| Link in the chain | Evidence | Result |
|---|---|---|
| Rating-state evidence (serving states) | All 170,379 contributions in the 35,740 serving states, against kickoffs and weeks from the rebuild feature frame | 0 violations: same season, earlier week, available before cutoff. The cutoff equals the target game's kickoff in every state. The tightest case had 85 hours between availability and cutoff |
| Opponent adjustment | Code: `CutoffAdjustment.graph` admits only rows with an earlier week, kickoff plus six hours at or before the target kickoff, and not the target game | Rule implemented as stated |
| Opponent adjustment and update, empirically | Future-data removal on the September inputs, repaired arm: every 2024 observation from week 8 on deleted (13,184 rows), then a full replay | 0 of the 2,264 states for 2024 target weeks 1 to 8 changed, to the last bit; 1,402 of the 1,412 later 2024 states changed, so the test has power; no other season changed |
| Normalization | Code: `standardization` uses only terminal rows from seasons before the target season | Earlier-only |
| Priors | `prior_source_season` and `calendar_gap` in every serving state | Source season is earlier in every case; the gap matches. 2021 priors come from 2019 or earlier |
| Offsets | Rebuild feature frame | One league mean per season; the zero-offset bootstrap only in 2015; each side's completed-game count equals its number of earlier kickoffs in all 8,935 rows; usable games never exceed that; games where both sides have no usable games share a single offset pair per season |
| Bridge fitting | Kickoffs per fold | The latest training kickoff precedes the earliest test kickoff in all seven validation seasons; no 2020 rows |
| Calibration | Code: `_calibration_variance` uses validation seasons before the scored season, each fitted on seasons before it | Earlier-only |

Not covered: the removal test ran on the September inputs, because the rebuild's observation table is not local; it tests the shared code, not the serving inputs. Priors are a fixed table, so the removal test says nothing about how that table was built; only the source-season fields were checked. Offsets were checked for consistency, not recomputed. The certified measurement tables themselves (how each game's points per possession was derived) are upstream of all of this.

#### Defect found: postseason games are labelled week 1

Not a leak, but it affects every historical number in this contract.

- 415 of the 8,935 games (38 to 46 per season; 176 of the 3,659 scored in 2022 to 2025) kick off in December or January yet carry `week` 1. They are postseason games whose week numbering restarts.
- Because a source game must come from an earlier week, nothing qualifies for a week-1 target. All 1,660 serving states for these games have zero current-season evidence: bowl and playoff games are forecast from preseason priors alone, while the feature frame labels them completed-game stage 4. In the Historical V5 arm 1,479 of the same 1,660 states have none.
- Effect on the scored predictions (2022 to 2025, stage 4 rows): Operational V5 margin MAE is 12.84 over 2,112 regular-season games and 14.32 over the 176 postseason games (bias -4.59); total MAE 13.57 and 14.63. Excluding postseason games, pooled Operational V5 margin MAE is 13.713 (against 13.742 with them) and total 13.378 (against 13.438).
- The same rows contaminate earlier tables: the "week 1" slice mixes season openers with postseason games, and stage 4 includes prior-only forecasts. The bridge, including the serving bundle, was fitted with these rows in its training data.
- Production scope: the 2026 record ends with week 15 and no postseason game is served, so no published 2026 pick is affected. Whether the serving engine in `season/prepare.py` would treat a postseason week the same way was not examined.

This is recorded, not fixed. Whether to exclude, relabel or re-rate postseason games in the historical benchmark is an owner decision and would change the comparator numbers.

### Regular-season benchmark (owner decision 2026-11-15)

**Decision.** The owner decided on 2026-11-15 to exclude the postseason games from the historical benchmark ("Exclude them"). The benchmark then measures what the site serves, since the published record ends with the regular season.

**Rule.** A game is postseason when its `week` is 1 and it kicks off in December or January. Verified on the rebuild feature frame: in every season the last regular-season game (week 15 or 16, 8 to 14 December) precedes the first flagged game (14 to 20 December); no unflagged game kicks off after 15 December or in January; every unflagged week-1 game is in August or September. The 415 game IDs are saved in `postseason_game_ids.json` in the scoring output folder.

**Scope of what was done.** The existing predictions were filtered; no bridge was refitted. The 415 games are therefore still in the bridges' training and calibration rows. Whether to remove them there too is open (next executable scope).

Pooled 2022 to 2025, regular season only (3,483 games per target; 176 removed):

| Model | Margin MAE | Margin bias | Margin 90% coverage | Total MAE | Total bias | Total 90% coverage |
|---|---|---|---|---|---|---|
| Historical V5 | 14.2873 | +0.23 | 91.1% | 13.6116 | -2.61 | 91.9% |
| Repaired arm, September inputs | 13.7176 | +0.43 | 91.4% | 13.4503 | -2.37 | 92.3% |
| **Operational V5** | **13.7130** | +0.43 | 91.2% | **13.3782** | -1.41 | 92.3% |

Operational V5 by season (margin, total): 2022 14.03, 13.71; 2023 13.66, 13.71; 2024 13.94, 13.12; 2025 13.24, 12.99.

Paired differences, same method as `paired_comparison` (90% interval, 62 season/week blocks, 2,000 replicates, seed 20260928): Operational against Historical V5, margin MAE lower by 0.574 (0.283 to 0.871), total by 0.233 (0.179 to 0.295); Operational against the September repaired arm, margin by 0.005 (-0.038 to 0.046), total by 0.072 (0.037 to 0.107).

By completed-game stage, Operational V5 (margin MAE, bias, 90% coverage): stage 0, 573 games, 16.17, +7.51, 85.2%; stage 1, 301, 14.41, +4.19, 91.0%; stage 2, 244, 15.10, +0.98, 90.2%; stage 3, 253, 13.27, -1.45, 93.3%; stage 4, 2,112, 12.84, -1.86, 92.8% (Historical V5 stage 4: 13.92).

Slices that change, 2021 to 2025 regular season (4,332 games); these supersede the corresponding rows of the slice section above:

| Slice | Games | Historical margin MAE | Historical bias | Operational margin MAE | Operational bias | Operational 90% coverage |
|---|---|---|---|---|---|---|
| Week 1 (season openers only) | 473 | 15.94 | +4.75 | 16.18 | +5.89 | 85.8% |
| Stage 4 | 2,631 | 14.16 | -1.94 | 12.99 | -2.15 | 92.5% |
| Neutral site | 126 | 14.72 | -3.94 | 13.91 | -2.69 | 90.5% |
| Home venue | 4,202 | 14.55 | +0.19 | 13.98 | +0.29 | 90.6% |
| Non-conference game | 1,642 | 15.44 | +3.94 | 15.50 | +4.22 | 87.9% |

Totals at neutral sites, regular season: Operational MAE 14.92, bias -5.02 (126 games).

What changes in the findings:

- **Neutral site is a smaller question than reported.** Of the 328 neutral-site games, 202 were postseason games forecast from priors alone. On the 126 regular-season neutral-site games, Operational V5's margin bias is -2.69, not -4.32, and the sample is under half the size. The mechanism is unchanged (venue flags are constant; every game gets the home intercept), but the measured effect and the number of games it touches are both smaller.
- **Season openers are worse than reported.** With postseason games removed from "week 1", Operational V5's opening-week margin MAE is 16.18 with bias +5.89 and 85.8% coverage.
- **Non-conference games are slightly worse** (bias +4.22), and the late-season gain is unchanged.
- Flat totals and the contribution findings are unaffected in substance; they were measured on all 3,659 games.

### Still unavailable

- The 12 original row-level outputs of the 2026-09-28 repair experiment (not located in the listed prefixes). A rerun copy now exists locally.
- The bridge manifest's third parent, `rebuild/6a/6a-task4-w5-r2/receipt/receipt.json` (not in the approved scope).
- Lower-level play datasets, historical market lines for 2021 to 2024, and the original prepared artifacts the ratings audit could not recover.

## Next executable scope (needs owner approval)

1. Done 2026-11-14: `historical-states.parquet` and the `w5` rebuild manifests are in the local mirror.
2. Done 2026-11-14: the repair experiment was rerun offline and its retained results are reproduced to 2.8e-14 (see the rerun section). Row-level identity with the original files remains unproven.
3. Done 2026-11-14: the serving states were compared with the rerun's repaired arm row by row (see the state comparison section). They agree on structure and timing and differ in values.
4. Done 2026-11-14 as far as local files allow (see the trace): same update code, different input lineage; the differences follow the rebuild's scoring corrections. Optional follow-up: fetch the rebuild's observations, terminal table and decisions file to separate direct corrections from propagation.
5. Done 2026-11-14: Operational V5's historical predictions exist and are scored (see the scoring section).
6. Done 2026-11-14: the slice report was rerun on the Operational V5 predictions (see the slice section).
7. Done 2026-11-15: the spread of each rating term, bridge coefficient and offset is measured (see the contribution section).
8. Done 2026-11-15: the upstream temporal check passed (see that section). Work-order step 2 is complete apart from the limits listed there.
9. Done 2026-11-15: the owner decided to exclude the postseason games; the benchmark is recomputed on regular-season games by filtering (see that section).
10. Open: whether the 415 postseason rows are also removed from bridge training and calibration. That is a refit and would change every number slightly; it should be settled before any candidate is compared.
11. Then work-order step 3 (chronological baselines and scoring accounting), on approval.

## Work order

| Step | Work | Decision it supports |
|---|---|---|
| 1 | Name the three baselines; inventory dependencies | Are we studying the right model with reproducible inputs? |
| 2 | Replay parity, evidence coverage, variation of predictions and offsets | Are the apparent weaknesses implementation artifacts or modeling limits? |
| 3 | Simple chronological baselines; reconcile total-points accounting | What signal does the current model capture or omit? |
| 4 | Bounded venue, possession-volume and prior/update experiments | Which small changes show credible improvement? |
| 5 | Targeted residual screens; labelled hindsight experiments | Which remaining hypotheses deserve a candidate? |
| 6 | Apply the amended protocol; report market comparisons separately | What evidence supports advancing a finalist? |

### Step 2: parity and variation

- Two checks, in this order.
    - Historical reproduction: reproduce the retained repair experiment's states and predictions under its original inputs and fitting procedure.
    - Operational equivalence: establish that its measurements, priors, adjustment, update rules, offsets and bridge recipe correspond to the current serving lineage, and explain every difference. Differences are explained and approved, not silently forced into parity.
- Recipe is separate from fitted coefficients. Production applies a pinned exported bridge (`apply_exported_bridge` in `src/cks_picks_cfb/season/prepare.py`); the research runner refits chronologically (`common_bridge_predictions`). Historical benchmark predictions use earlier-only fitting. Applying a through-2025 bridge to 2022 to 2025 would leak evaluation outcomes.
- Parity requires identical keys and coverage, explicit duplicate and missing-row checks, a declared numerical tolerance, and a stated population (FBS against FBS separately from FBS against FCS).
- Temporal rule: every contributing source game must precede the target week, and its kickoff plus six hours must be no later than the forecast cutoff. Six hours is an availability assumption; it does not prove when historical data was captured. The check covers opponent-adjustment inputs, prior construction, normalization, offsets, bridge fitting and calibration, not only the final rating state.
- Evidence coverage by season and completed-game stage for both V5s.
- Spread of each piece of a prediction: the four ratings, each bridge contribution, the offset, the final margin and total. This tests sparse updates, compressed ratings, coefficients, feature cancellation and offsets as explanations for flat totals before pace is considered.
- Rerun the existing slice report on Operational V5 and state which earlier findings survive.

### Step 3: baselines and scoring accounting

- Chronological baselines (constant, home edge, carryover only) are reference points, not error floors.
- Scoring identity per game, reconciled to the final score: home eligible offensive points + away eligible offensive points + excluded offensive points + non-offense points + overtime + unresolved. The corpus `denominator` counts eligible regulation possessions only ([methodology](../../modeling/possession_rating_methodology.md), D2 to D4), so possessions times points per possession does not rebuild a total.
- Three separate totals questions: how much ratings, bridge contributions and offsets vary; how much observed possession volume explains after the fact; how much possession volume is predictable before kickoff. Observed possessions depend on game flow, so the second is not an attainable gain.

### Step 4: bounded experiments

Venue flag, a pregame possession-volume input, prior and update variants. Each uses the declaration template below. Flexible bridges are scored only on chronological out-of-sample predictions. One-at-a-time swaps miss interactions between layers and are reported with that caveat.

### Step 5: residual screens and hindsight experiments

- Residual patterns generate hypotheses only. Repeating team misses can mean slow updates, measurement bias, missing context, opponent effects or bridge misspecification; each explanation is then tested with a chronological ablation.
- The feature screen is small and limited to inputs whose availability at kickoff in the historical record is verified first.
- End-of-season ratings are a future-informed sensitivity test. They contain the evaluated game's own result and shift the bridge's input distribution, so a weak result does not show that better priors or updates have little value. No claim about the most improvement possible.

### Step 6: evaluation and market reporting

See the proposed amendments.

## Experiment declaration template

Every ablation or experiment records, before it runs:

| Field | Content |
|---|---|
| Question | The one narrow question it answers |
| Changes | Exactly what differs from the baseline |
| Frozen | What is held at the baseline |
| Refitted | What is refitted, and whether the bridge uses frozen coefficients or an earlier-only refit |
| Population | Seasons, game set, FBS/FCS scope |
| Cannot show | What a good or bad result does not establish |

## Proposed protocol amendments (not applied)

Each needs a dated entry in the [research protocol](../2026-11-12/02-offseason-research-protocol.md) and `conf/research/offseason_2027/protocol.yaml`, on separate owner approval.

1. **Comparator.** Change the comparator to Operational V5; keep Historical V5 as the reproducibility reference and Closed V6 as a historical comparator. The repaired model is better pooled but worse at some stages, so this is not uniformly a stricter threshold.
2. **Paired interval.** Retain season/week block resampling as the proposed primary method, compute a two-sided 95% interval, and document the dependence it captures (within a week) and omits (the same teams recurring across weeks). Specify any sensitivity analysis before candidates are evaluated. The 95% comparison interval is distinct from the model's 90% prediction intervals. `paired_comparison` needs an explicit confidence level to implement this.
3. **2022 to 2025.** Describe these seasons as previously examined temporal validation evidence. Exploration and tuning on 2015 to 2019 and 2021 remain useful but restore no independence. Before the next evaluation batch, freeze the candidate families, the comparison rules and how a finalist is chosen. A ledger of scoring runs records looks; it does not remove selection bias.
4. **2026.** Document prior exposure (the 215-game counterfactual of 2026-09-28, weekly scoring, and the repair work). Keep the restriction that no candidate is scored on 2026 until a final candidate, or a bounded pre-declared set, is frozen. Prospective confirmation is 2027 predictions.
6. **Benchmark population (decided 2026-11-15, to be written into the protocol with the other amendments).** The headline population is regular-season games only: 3,483 games per target for 2022 to 2025 instead of 3,659. Postseason games are identified by the rule in the regular-season benchmark section.
5. **Market.** Market comparison is reported only after football-based priorities are frozen, with identical game coverage, verified spread signs, quote provenance, and cutoff-time lines reported separately from closing lines. Using market results to steer research would be market-informed prioritization and needs its own explicit approval.

## Validation

`git diff --check`; `uv run mkdocs build --strict`; this contract is listed in the [plans index](../index.md). The inventory counts above were produced by reading and hashing every listed file.

## Handoff/amendments

Resume gate: owner approval of the next executable scope. Record amendments here with the reason, previous approach, revised approach and impact.
