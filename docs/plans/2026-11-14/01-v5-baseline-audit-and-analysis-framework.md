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

Interpretation, not a finding: the ratings measure opponent-adjusted scoring efficiency, which mostly cancels in a total (a strong team scores more and allows less), so a linear function of them has little to say about how many points a game will have. The suggestion made here on 2026-11-15 that possession volume is the missing input was tested in step 3 and is not supported; see that section.

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

### Regular-season benchmark, refitted (2026-11-15, owner-approved)

The owner approved removing the postseason games from bridge training and calibration as well ("Yes, refit without them"). The 415 games were dropped from the feature frames, the rating states and the frozen-prediction keys (8,520 games remain; 3,483 per target in 2022 to 2025), and all three baselines were refitted with the unchanged `common_bridge_predictions`: bridge per validation season on strictly earlier seasons, earlier-only calibration. **These are the benchmark numbers.**

Pooled 2022 to 2025 (filtered-only value from the previous section in brackets):

| Model | Margin MAE | Margin bias | Margin 90% coverage | Total MAE | Total bias | Total 90% coverage |
|---|---|---|---|---|---|---|
| Historical V5 | 14.2960 [14.2873] | +0.04 [+0.23] | 91.0% | 13.6062 [13.6116] | -2.59 | 91.9% |
| Repaired arm, September inputs | 13.7182 [13.7176] | +0.19 [+0.43] | 91.3% | 13.4412 [13.4503] | -2.33 | 92.3% |
| **Operational V5** | **13.7151** [13.7130] | +0.19 [+0.43] | 91.3% | **13.3709** [13.3782] | -1.36 | 92.3% |

Operational V5 by season (margin, total): 2022 14.04, 13.69; 2023 13.66, 13.70; 2024 13.95, 13.12; 2025 13.23, 12.99.

Operational V5 by completed-game stage (games; margin MAE, bias, 90% coverage; total MAE, bias): stage 0, 573; 16.08, +7.16, 85.5%; 13.16, -0.11. Stage 1, 301; 14.34, +3.92, 91.0%; 13.03, -1.46. Stage 2, 244; 15.11, +0.77, 90.2%; 12.50, -1.32. Stage 3, 253; 13.32, -1.66, 93.3%; 13.55, -1.06. Stage 4, 2,112; 12.87, -2.08, 92.9%; 13.56, -1.73. Historical V5 margin MAE by stage: 15.85, 14.24, 14.98, 13.00, 13.96.

Paired differences (62 season/week blocks, 2,000 replicates, seed 20260928), with the existing 90% interval and the two-sided 95% interval the protocol amendment proposes:

| Comparison | Target | MAE lower by | 90% interval | 95% interval |
|---|---|---|---|---|
| Operational against Historical V5 | Margin | 0.581 | 0.289 to 0.880 | 0.237 to 0.938 |
| Operational against Historical V5 | Total | 0.235 | 0.179 to 0.298 | 0.168 to 0.308 |
| Operational against September repaired arm | Margin | 0.003 | -0.040 to 0.044 | -0.049 to 0.050 |
| Operational against September repaired arm | Total | 0.070 | 0.035 to 0.106 | 0.029 to 0.112 |

Operational V5 prediction spread: margin 13.46 points against 22.09 actual (correlation +0.615); total 1.62 points against 16.86 actual (correlation +0.168).

What this establishes: removing the postseason rows from training barely moves accuracy (at most 0.009 in MAE) and removes about a quarter of a point of margin bias. The earlier findings stand on the refitted benchmark. Slice tables and the contribution decomposition have not been rerun on the refitted predictions; given the size of the change they are expected to move in the second decimal, but that is not verified.

Outputs: `~/cfb_ratings_lab_v6/output/regular-season-benchmark-2026-11-15/` (predictions and early predictions for the three baselines, `scorecards.json`; Operational V5 predictions SHA-256 begins `5651b023a440838b`).

### Work-order step 3: baselines, scoring accounting and possession volume (2026-11-15, owner-approved)

Regular-season games only (postseason removed). Local files; nothing fetched. Baselines and the Operational V5 row use the rebuild feature frame; the scoring ledger and possession counts come from the September corpus, because the rebuild's corrected event table is not local.

#### A. Chronological baselines, 2022 to 2025 (3,483 games, each fitted on strictly earlier seasons)

| Prediction | Margin MAE | Margin bias | Total MAE | Total bias |
|---|---|---|---|---|
| Zero | 18.427 | +8.24 | n/a | n/a |
| Mean of earlier seasons | 17.465 | +0.77 | 13.653 | -2.37 |
| Mean of earlier seasons plus the offset | 17.373 | +0.78 | 13.689 | -2.41 |
| Preseason priors only, through the bridge, plus the offset | 14.413 | -0.07 | 13.541 | -1.73 |
| Operational V5 | 13.715 | +0.19 | 13.371 | -1.36 |

"Preseason priors only" replaces each rating with its own prior mean from the serving states and refits the bridge the same way; offsets are unchanged and still update in-season. These are reference points, not error floors.

Margin MAE by completed-game stage, priors only against Operational V5: stage 0, 15.88 against 16.08; stage 1, 14.22 against 14.34; stage 2, 15.37 against 15.11; stage 3, 13.19 against 13.32; stage 4, 14.08 against 12.87.

What this establishes:

- **Margin:** priors account for about 3.05 of the 3.75 points by which Operational V5 beats the earlier-season mean; in-season updating adds 0.70. All of that 0.70 arrives at stage 4. Through a team's first three games the updated ratings are no better than its preseason prior, and at stages 0, 1 and 3 slightly worse.
- **Total:** Operational V5 beats predicting the earlier-season average for every game by 0.28 points of MAE. The offset makes the constant slightly worse (13.689 against 13.653).

#### B. Scoring accounting (September ledger, 8,520 regular-season games)

Identity per game: eligible regulation offense + excluded regulation offense + regulation non-offense + overtime + unresolved = final total.

- 8,003 games (93.9%) reconcile exactly with no unresolved event. The share is 95.8% to 98.2% in 2015 to 2019 and lower afterwards: 87.2% in 2021, 87.9% in 2022, 93.9% in 2023, 94.2% in 2024, 90.0% in 2025.
- 83 games have no ledger row. Eight games carry an unresolved event.

On the 8,003 reconciled games (mean final total 55.17, standard deviation 17.75):

| Category | Points per game | Share of points | Share of the total's variance |
|---|---|---|---|
| Eligible regulation offense | 47.66 | 86.4% | 80.4% |
| Excluded regulation offense | 2.71 | 4.9% | 9.5% |
| Regulation non-offense | 4.44 | 8.0% | 8.2% |
| Overtime | 0.37 | 0.7% | 1.8% |

What this establishes: about 14% of points and 20% of the variance in a game's total come from scoring the ratings do not measure. The observation table's eligible points equal the ledger's eligible category in all 8,033 games checked.

#### C. Possession volume (8,033 games with both offenses observed)

- Eligible regulation possessions per game (both offenses): mean 22.97, standard deviation 4.53. Points per eligible possession: mean 2.125, standard deviation 0.749.
- After the fact: possessions correlate +0.065 with the final total; points per possession correlate +0.772. Possessions and points per possession correlate -0.349. In logs, possessions account for 10.8% of the variation in eligible offensive points and points per possession for 89.2%.
- Before kickoff: the average of both teams' earlier-game possession counts (teams with at least three earlier games) correlates +0.220 with actual possessions in 2016 to 2019 and 2021 (2,716 games) and +0.246 in 2022 to 2025 (2,039 games), and +0.016 and +0.048 with the final total.
- Against Operational V5's total error: the pregame possession average correlates -0.006 with the residual in 2018, 2019 and 2021 (1,622 games) and +0.070 in 2022 to 2025. Even the actual possession count, known only afterwards, correlates +0.09.

What this establishes: **possession volume, measured as eligible regulation possessions, is not the missing totals input.** Game totals vary with scoring efficiency, not with the number of possessions, and what can be predicted of possession count says almost nothing about the total. This contradicts the interpretation offered in the contribution section above and the hypothesis in the first draft of this framework.

Limits: possessions here are eligible regulation possessions, not plays, time of possession or seconds per play, so clock tempo is untested. The pregame average orders a team's games by week; 57 team-weeks hold two games, so a handful of averages may include a same-week game. The correlations on 2022 to 2025 are descriptions of examined seasons.

Outputs: `~/cfb_ratings_lab_v6/output/step3-2026-11-15/` (`step3_results.json`, priors-only predictions).

### Step 4A results: early-season error attribution (2026-11-15, owner-approved)

A diagnostic on the existing regular-season predictions (2022 to 2025, 3,483 games per target). Nothing was refitted and no market data was used. Bias is actual minus prediction (positive means the home margin or total was under-predicted), the convention of the earlier sections.

**Checks.** Operational V5 margin MAE 13.7151 and total 13.3709, and priors-only margin MAE 14.4125, recomputed from the joined frame, equal the recorded figures. Stage counts per target: 573, 301, 244, 253 and 2,112 for stages 0 to 4. Of 3,483 games, one (Tarleton State as away team in 2022) has no prior row. Returning production is missing for the 484 FCS away teams (expected, CFBD returning production covers FBS only; no home team is FCS), and for 71 team-games of programs in their first FBS seasons (James Madison, Jacksonville State, Sam Houston State, Kennesaw State, Delaware, Missouri State). Those are labelled "no CFBD data" in the tables.

**Group definitions.** Prior rank: quartile of the team's net prior within the season. The net prior is the offense prior **plus** the defense prior, not offense minus defense as the plan stated: the defense rating is oriented higher-is-better (the bridge gives home defense a positive and away defense a negative margin coefficient), and the sum correlates +0.56 with the margin against +0.10 for the difference. Prior source: "default" if either unit fell back to the neutral prior for lack of a predecessor, else "carried over". Returning production: tercile of `percentPPA` within the season among FBS teams that CFBD lists. Conference tier from each season's CFBD membership: P4 is the SEC, Big Ten, Big 12, ACC and Notre Dame, plus the Pac-12 in 2022 and 2023 (its last seasons as a power conference); G5 is other FBS; FCS/other is everything else.

**Caveat.** The CFBD files were captured on 2026-11-15, so it is not verified that they were available at each historical kickoff. That is acceptable for a diagnostic and not for a model input. Pulled files and SHA-256 values: `~/cfb_ratings_lab_v6/source/cfbd-2026-11-15/`. Cells below 30 games are marked †.

#### Findings

By stage (margin; games, Operational V5 MAE / bias, priors-only MAE / bias):

| Stage | Games | Operational V5 | Priors only |
|---|---|---|---|
| 0 | 573 | 16.08 / +7.16 | 15.88 / +5.33 |
| 1 | 301 | 14.34 / +3.92 | 14.22 / +2.07 |
| 2 | 244 | 15.11 / +0.77 | 15.37 / +0.26 |
| 3 | 253 | 13.32 / -1.66 | 13.18 / -1.93 |
| 4 | 2,112 | 12.87 / -2.08 | 14.08 / -1.65 |

1. **The stage 0 bias is not a constant offset.** The bridge intercept is 7.38, 7.43, 7.44 and 7.57 margin points for 2022 to 2025 (the training mean of the target, which is the Ridge intercept; **corrected 2026-11-15**: the first version of this section quoted 7.10 to 7.26, taken from the earlier fit that still included postseason games, which does not match the refitted benchmark predictions), and the stage 0 bias is +6.8, +7.9, +6.7 and +7.2 by season, so it is stable. But it reverses sign with experience (+7.16 at stage 0, -2.08 at stage 4) while the intercept does not move; the mean outcome is a home margin of 24 to 26 at stage 0 and 2 to 4 at stage 4, because openers are mostly mismatches. A single shift that zeroes the stage 0 to 3 bias (+3.68) would lower stage 0 MAE from 16.08 to 15.17 at most (0.91) and would push stage 4 bias to -5.77 and its MAE from 12.87 to 13.60. Removing the whole stage 0 bias, even in sample, leaves 15.17.
2. **The bias depends on the matchup.** At stage 0, P4 hosts against FCS and G5 opponents are under-predicted by +12.00 (192 games) and +13.28 (86), while P4 against P4 (45) is over-predicted by 3.39. G5 at home against FCS is +6.57 (190); G5 against G5 (42) -5.05; G5 hosts against P4 visitors are over-predicted by 14.43 (17 games, †). By home prior rank the bias rises with the host's strength (Q2 +3.2, Q3 +6.2, Q4 +9.4). Returning production shows no clean gradient (home terciles +4.3, +8.7, +8.2).
3. **Priors alone show the same pattern, so it comes from the prior and the bridge, not from updating.** At stage 0 the two predictions correlate 0.94 and differ by 4.7 points on average, and the slice biases move together (P4 v FCS/other +8.94 for priors, +12.00 for V5). At stages 1 to 3 the V5 prediction moves 8 to 10 points on average from the prior, yet its MAE differs from priors-only by -0.26 to +0.14, so the updating changes predictions without improving them until stage 4 (V5 beats priors by 1.21 there). At stage 0 the V5 bias is 1.8 points larger than priors-only (+7.16 against +5.33) with the same MAE; this contract does not establish why.
4. **Teams on the default prior are the clearest prior-quality failure, but a small one.** Away teams with a default (neutral) prior at stage 0: 60 games, V5 MAE 20.41, bias +16.24 (priors only +15.68), against 512 carried-over games at 15.56 / +6.07. Home teams on a default prior number 2 at stage 0 and are not usable.
5. **Totals show no early-season problem.** Operational V5 total MAE at stages 0 to 4 is 13.16, 13.03, 12.50, 13.55, 13.56 and bias -0.11, -1.46, -1.32, -1.05, -1.73 (positive bias = under-predicted; the sign convention is the same). Priors-only totals are within 0.36 of those. Nothing in the early-season totals points to the prior, the intercept or update speed.

#### What this implies for step 4B

- **Dominant factor:** none of the three alone. The best-supported answer is the prior and bridge together: a home-edge level that is right on average but wrong for lopsided matchups, which are concentrated at stage 0 (P4 hosts against weaker teams are under-predicted by 12 to 13 points; the same slice at stage 4 is +4.75 on 51 games). A constant intercept explains at most 0.91 of the 16.08 stage 0 MAE and cannot also serve stage 4. Update speed is not the cause at stage 0 (there is nothing to update) and does not help at stages 1 to 3.
- **Worth declaring in B:** a stage-dependent blend or shift is bounded by the 0.91 gain above and the stage 4 damage of a global shift, so a stage-specific intercept must be tested against stage 4 unchanged. A variant that lets the home margin depend on the rating gap (a larger slope for mismatches), or on conference tier, targets the pattern in finding 2 and has more room than an intercept change; it needs a declared form before it runs.
- **Limits.** Cells are pooled over four seasons and share outcomes with the benchmark, so the groupings describe where the error sits and cannot show that any variant would help. Tier and prior-rank groups overlap (P4 hosts are mostly high-ranked priors), so the tables cannot separate quality from conference. The 2022 to 2025 seasons are already examined.

#### Detail tables (margin unless stated)

**Margin by home team prior-rank quartile** (n; Operational V5 MAE / bias; priors-only MAE / bias; † = fewer than 30 games)

| Group | Stage 0 | Stages 1-3 | Stage 4 |
|---|---|---|---|
| Q1 low | 12†; 16.11 / +7.44; 17.09 / +10.39 | 14†; 13.85 / +2.11; 16.49 / +8.85 | 39; 12.23 / -4.80; 13.38 / +7.64 |
| Q2 | 99; 14.95 / +3.22; 15.36 / +3.91 | 130; 16.26 / -0.46; 15.16 / +1.41 | 400; 13.18 / -5.45; 14.28 / -2.49 |
| Q3 | 203; 16.36 / +6.22; 17.00 / +4.96 | 284; 13.96 / -0.78; 14.60 / -1.63 | 784; 13.19 / -2.49; 14.41 / -1.33 |
| Q4 high | 259; 16.28 / +9.39; 15.14 / +5.91 | 370; 13.78 / +3.24; 13.56 / +0.95 | 889; 12.48 / -0.08; 13.73 / -1.97 |

**Margin by away team prior-rank quartile** (n; Operational V5 MAE / bias; priors-only MAE / bias; † = fewer than 30 games)

| Group | Stage 0 | Stages 1-3 | Stage 4 |
|---|---|---|---|
| Q1 low | 217; 14.67 / +5.89; 14.42 / +0.53 | 79; 14.13 / +6.76; 16.35 / +2.44 | 43; 13.06 / -6.76; 20.01 / -14.60 |
| Q2 | 180; 18.14 / +10.54; 17.78 / +9.62 | 190; 14.13 / +4.28; 14.56 / +3.97 | 412; 12.75 / -1.62; 14.20 / -3.16 |
| Q3 | 101; 16.87 / +8.02; 17.12 / +8.77 | 281; 14.90 / +1.18; 14.58 / +0.39 | 795; 13.42 / -3.32; 14.26 / -2.90 |
| Q4 high | 70; 13.77 / +0.63; 13.58 / +3.41 | 247; 13.60 / -3.07; 12.91 / -3.57 | 862; 12.41 / -0.92; 13.56 / +0.86 |
| nan | 4†; 18.12 / +12.92; 14.78 / +12.22 | 1†; 26.69 / +26.69; 20.92 / +20.92 | - |
| no data | 1†; 20.70 / +20.70; 30.23 / +30.23 | - | - |

**Margin by home prior source** (n; Operational V5 MAE / bias; priors-only MAE / bias; † = fewer than 30 games)

| Group | Stage 0 | Stages 1-3 | Stage 4 |
|---|---|---|---|
| carried over | 571; 16.06 / +7.12; 15.86 / +5.27 | 793; 14.27 / +1.13; 14.19 / +0.10 | 2101; 12.87 / -2.08; 14.09 / -1.70 |
| default (no predecessor) | 2†; 19.23 / +19.23; 20.52 / +20.52 | 5†; 11.87 / +10.26; 23.32 / +23.32 | 11†; 13.22 / -2.38; 12.42 / +7.64 |

**Margin by away prior source** (n; Operational V5 MAE / bias; priors-only MAE / bias; † = fewer than 30 games)

| Group | Stage 0 | Stages 1-3 | Stage 4 |
|---|---|---|---|
| carried over | 512; 15.56 / +6.07; 15.36 / +4.06 | 785; 14.31 / +1.21; 14.20 / +0.20 | 2100; 12.86 / -2.10; 14.06 / -1.62 |
| default (no predecessor) | 60; 20.41 / +16.24; 20.05 / +15.68 | 13†; 11.00 / -0.21; 16.85 / +3.04 | 12†; 15.33 / +1.22; 16.98 / -7.19 |
| no data | 1†; 20.70 / +20.70; 30.23 / +30.23 | - | - |

**Margin by home returning-production tercile** (n; Operational V5 MAE / bias; priors-only MAE / bias; † = fewer than 30 games)

| Group | Stage 0 | Stages 1-3 | Stage 4 |
|---|---|---|---|
| T1 low | 184; 15.99 / +4.30; 15.99 / +2.38 | 253; 14.27 / +0.60; 14.31 / -1.52 | 686; 12.94 / -3.43; 14.29 / -4.41 |
| T2 | 191; 16.02 / +8.74; 15.85 / +6.77 | 268; 15.06 / +0.60; 14.78 / -0.09 | 691; 13.00 / -1.65; 14.10 / -0.76 |
| T3 high | 193; 16.11 / +8.19; 15.70 / +6.42 | 267; 13.51 / +2.24; 13.35 / +1.91 | 714; 12.68 / -1.20; 13.85 / -0.09 |
| no CFBD data | 5†; 19.86 / +12.20; 19.64 / +16.46 | 10†; 11.88 / +3.71; 22.04 / +9.71 | 21†; 13.05 / -2.41; 14.42 / +5.87 |

**Margin by away returning-production tercile** (n; Operational V5 MAE / bias; priors-only MAE / bias; † = fewer than 30 games)

| Group | Stage 0 | Stages 1-3 | Stage 4 |
|---|---|---|---|
| T1 low | 69; 16.64 / +6.03; 15.23 / +5.58 | 240; 14.24 / +1.45; 13.89 / +1.89 | 696; 12.81 / -1.74; 13.86 / +0.20 |
| T2 | 60; 15.89 / -1.15; 15.71 / -0.77 | 216; 14.52 / +0.33; 13.67 / -1.40 | 696; 12.69 / -2.41; 13.54 / -2.31 |
| T3 high | 58; 12.60 / +2.73; 12.66 / +3.41 | 232; 14.03 / -0.86; 14.09 / -2.30 | 696; 13.09 / -2.06; 14.68 / -2.56 |
| no CFBD data | 385; 16.51 / +9.29; 16.47 / +6.45 | 110; 14.23 / +6.62; 16.48 / +5.25 | 24†; 13.65 / -3.08; 18.68 / -10.11 |
| no data | 1†; 20.70 / +20.70; 30.23 / +30.23 | - | - |

**Margin by home conference tier** (n; Operational V5 MAE / bias; priors-only MAE / bias; † = fewer than 30 games)

| Group | Stage 0 | Stages 1-3 | Stage 4 |
|---|---|---|---|
| G5 | 249; 15.91 / +3.17; 16.43 / +1.61 | 341; 15.05 / -0.95; 14.97 / -1.53 | 1025; 13.11 / -3.49; 13.97 / -2.36 |
| P4 | 324; 16.20 / +10.23; 15.45 / +8.18 | 457; 13.66 / +2.79; 13.70 / +1.57 | 1087; 12.64 / -0.76; 14.18 / -0.99 |

**Margin by away conference tier** (n; Operational V5 MAE / bias; priors-only MAE / bias; † = fewer than 30 games)

| Group | Stage 0 | Stages 1-3 | Stage 4 |
|---|---|---|---|
| FCS/other | 382; 16.54 / +9.30; 16.50 / +6.47 | 102; 13.96 / +7.22; 16.45 / +6.59 | - |
| G5 | 128; 15.74 / +7.26; 15.19 / +6.61 | 401; 15.24 / +2.05; 14.58 / +2.12 | 1064; 13.10 / -2.99; 14.02 / -1.85 |
| P4 | 62; 13.84 / -6.42; 13.23 / -4.77 | 295; 13.01 / -2.07; 13.02 / -4.50 | 1048; 12.64 / -1.16; 14.14 / -1.46 |
| no data | 1†; 20.70 / +20.70; 30.23 / +30.23 | - | - |

**Margin by tier matchup (home v away)** (n; Operational V5 MAE / bias; priors-only MAE / bias; † = fewer than 30 games)

| Group | Stage 0 | Stages 1-3 | Stage 4 |
|---|---|---|---|
| G5 v FCS/other | 190; 16.22 / +6.57; 16.98 / +3.96 | 68; 15.12 / +8.00; 16.75 / +6.31 | - |
| G5 v G5 | 42; 14.62 / -5.05; 14.75 / -3.71 | 217; 15.08 / -2.07; 14.37 / -1.62 | 1013; 13.08 / -3.38; 13.98 / -2.29 |
| G5 v P4 | 17†; 15.64 / -14.43; 14.43 / -11.58 | 56; 14.83 / -7.52; 15.12 / -10.72 | 12†; 16.11 / -12.56; 13.48 / -7.84 |
| P4 v FCS/other | 192; 16.85 / +12.00; 16.02 / +8.94 | 34; 11.62 / +5.65; 15.84 / +7.16 | - |
| P4 v G5 | 86; 16.28 / +13.28; 15.41 / +11.65 | 184; 15.44 / +6.90; 14.83 / +6.53 | 51; 13.48 / +4.75; 14.82 / +7.02 |
| P4 v P4 | 45; 13.17 / -3.39; 12.78 / -2.20 | 239; 12.58 / -0.79; 12.53 / -3.04 | 1036; 12.60 / -1.03; 14.15 / -1.38 |
| P4 v no data | 1†; 20.70 / +20.70; 30.23 / +30.23 | - | - |

**Total by tier matchup (home v away)** (n; Operational V5 MAE / bias; priors-only MAE / bias; † = fewer than 30 games)

| Group | Stage 0 | Stages 1-3 | Stage 4 |
|---|---|---|---|
| G5 v FCS/other | 190; 13.31 / +0.16; 13.49 / -1.50 | 68; 14.01 / +0.61; 14.44 / -1.30 | - |
| G5 v G5 | 42; 14.11 / -1.39; 14.48 / -2.26 | 217; 14.03 / -0.30; 14.27 / -1.15 | 1013; 14.03 / -0.99; 14.27 / -1.83 |
| G5 v P4 | 17†; 16.47 / +2.16; 16.46 / +1.37 | 56; 12.82 / -1.94; 12.94 / -2.53 | 12†; 14.64 / +2.76; 15.36 / +2.77 |
| P4 v FCS/other | 192; 12.04 / +2.41; 12.01 / +1.37 | 34; 9.35 / +0.28; 9.34 / -0.98 | - |
| P4 v G5 | 86; 14.10 / -2.84; 14.17 / -3.37 | 184; 11.96 / -1.87; 12.37 / -1.96 | 51; 11.52 / -1.43; 11.31 / -1.32 |
| P4 v P4 | 45; 13.23 / -6.91; 13.08 / -6.78 | 239; 13.25 / -2.35; 13.35 / -1.93 | 1036; 13.18 / -2.52; 13.30 / -2.06 |
| P4 v no data | 1†; 18.79 / +18.79; 18.88 / +18.88 | - | - |

**Total by home returning-production tercile** (n; Operational V5 MAE / bias; priors-only MAE / bias; † = fewer than 30 games)

| Group | Stage 0 | Stages 1-3 | Stage 4 |
|---|---|---|---|
| T1 low | 184; 13.73 / -1.30; 13.90 / -2.46 | 253; 12.18 / -2.54; 12.49 / -3.08 | 686; 13.62 / -1.61; 13.82 / -2.07 |
| T2 | 191; 13.47 / +0.64; 13.41 / -0.42 | 268; 13.58 / -0.99; 13.81 / -1.39 | 691; 13.83 / -1.90; 14.01 / -1.93 |
| T3 high | 193; 12.43 / +0.48; 12.51 / -0.44 | 267; 13.12 / -0.24; 13.29 / -0.40 | 714; 13.26 / -1.84; 13.39 / -1.84 |
| no CFBD data | 5†; 7.85 / -7.85; 10.05 / -10.05 | 10†; 17.25 / -5.63; 17.77 / -7.62 | 21†; 12.76 / +3.84; 12.91 / +2.11 |

Outputs: `~/cfb_ratings_lab_v6/output/step4a-2026-11-15/step4a_attribution_results.json` (every stage-by-group cell with game counts, the intercept check for each season and stage, and the pull hashes). The analysis script was ad hoc and is not in the repository.

### Step 4B results: stage-specific intercept and rating-gap variants (2026-11-15, owner-approved)

Run as declared above (candidates B1, B1s, B2; B3 not run). The margin bridge was refitted earlier-only for each validation season with the added terms (alpha-10 Ridge on standardized inputs, the same recipe and target as the baseline); the totals bridge and everything upstream were untouched. The baseline was rebuilt from the serving states and the rebuild feature frame with the postseason excluded, and **reproduces the stored Operational V5 margin predictions for 2022 to 2025 exactly (largest difference 0.0; MAE 13.7151)**. Bias is actual minus prediction. Outputs: `~/cfb_ratings_lab_v6/output/step4b-2026-11-15/step4b_variants_results.json`. The script was ad hoc and is not in the repository.

**Selection on the tuning seasons (2016, 2017, 2018, 2019, 2021; 1,662 stage 0 to 3 games; each season fitted on strictly earlier seasons, so 2016 trains on 2015 alone):**

| Candidate | Stage 0 to 3 MAE / bias | Stage 4 MAE / bias |
|---|---|---|
| Baseline | 15.99 / +0.51 | 14.81 / -5.67 |
| B1 (one early intercept) | 16.05 / -2.45 | 14.26 / -2.99 |
| B1s (intercept per stage) | 15.80 / -2.15 | 13.33 / -0.38 |
| B2 (B1 plus rating-gap term) | 16.07 / -2.14 | 14.20 / -2.89 |

**Under the declared rule no candidate is selected.** The rule needs a stage 0 to 3 MAE gain of at least 0.2 and a smaller bias magnitude than the baseline; B1s gains 0.19 and its bias magnitude is larger (2.15 against 0.51), B1 and B2 are worse than the baseline. The pooled figure is dominated by 2016 and 2017, whose bridges train on one and two seasons: there the baseline early bias is -4.55 and -2.19 and the candidates go further negative (B1 -5.13 and -6.39), the opposite sign from every later season (+2.8 to +3.3). That is an instability of very short training windows, not evidence about the candidates, but the rule did not exempt those seasons.

**Reported once on 2022 to 2025 (1,371 stage 0 to 3 games; examined evidence, not a selection):**

| Candidate | Stage 0 to 3 MAE / bias | Stage 0 MAE / bias | Stage 4 MAE / bias | All games MAE |
|---|---|---|---|---|
| Baseline | 15.01 / +3.68 | 16.08 / +7.16 | 12.87 / -2.08 | 13.715 |
| B1 | 14.81 / +0.21 | 15.41 / +4.18 | 12.71 / +0.20 | 13.539 |
| B1s | 14.47 / +0.14 | 15.15 / +0.15 | 12.67 / +0.15 | 13.380 |
| B2 | 14.86 / +0.31 | 15.52 / +4.52 | 12.75 / +0.19 | 13.582 |

Paired gain in stage 0 to 3 MAE with a 90% bootstrap interval: B1 0.20 (0.05 to 0.36), B1s 0.54 (0.33 to 0.76), B2 0.15 (-0.01 to 0.31). B1s improves three of four seasons (2022 15.56 to 14.96, 2023 14.27 to 13.37, 2025 14.30 to 13.52) and is 0.11 worse in 2024. Frozen-coefficient versions (baseline coefficients kept, added terms fitted on the baseline's training residuals) give gains of 0.26, 0.51 and 0.19 for B1, B1s and B2 on 2022 to 2025 and none on the tuning seasons.

**Post hoc, not part of the declared rule:** restricting the tuning comparison to 2018, 2019 and 2021 (bridges trained on three or more seasons; the early group the project's evaluation code already registers) gives stage 0 to 3 MAE 16.07 for the baseline against 15.88 (B1), 15.54 (B1s) and 15.88 (B2), with stage 4 MAE 13.35 against 13.19, 13.14 and 13.18. That matches the 2022 to 2025 pattern. This subset was chosen after seeing the results and cannot support selection.

What this shows:

1. **The rating-gap term adds nothing.** B2 does not beat B1 (14.86 against 14.81 on 2022 to 2025; 15.88 for both on 2018 to 2021). On the declared criterion B2 fails.
2. **A per-stage intercept captures what the 4A ceiling said it could, and more.** B1s lowers stage 0 MAE from 16.08 to 15.15 (0.93; 4A's bound was 0.91) and also lowers stage 4 MAE from 12.87 to 12.67 and stage 4 bias from -2.08 to +0.15. The reason is that the bridge's single intercept is pulled upward by openers, which are mostly mismatches with large home margins; separate stage terms (fitted effects +11.4, +7.0, +2.1 and +0.7 points for stages 0 to 3 in the last fit) free the stage 4 level. This refines the 4A note that a global shift cannot serve both ends: one pooled early shift cannot, per-stage terms can.
3. **The matchup pattern from 4A is not fixed; it moves.** At stage 0, B1s zeroes the mean bias but leaves the matchup spread: Power 4 hosts against FCS and G5 teams fall from +12.00 and +13.28 to +5.51 and +5.39, while Power 4 against Power 4 goes from -3.39 to -12.47 (MAE 13.17 to 16.22) and G5 against G5 from -5.05 to -12.92 (MAE 14.62 to 17.19). The improvement comes from the lopsided games, which are the majority at stage 0, and balanced games get worse. Conference tier (B3) is the declared variant that could address this and was not run.

Limits: the 2022 to 2025 seasons were already examined, so the confirmation figures are not independent; the selection rule failed on the tuning seasons; one season (2024) goes the other way; a stage-specific intercept for stage 0 rests on the stage 0 bias being stable across seasons, which 4A showed for 2022 to 2025 only; totals were not examined.

Decision for the owner: (a) accept the declared outcome (no candidate selected) and change nothing; (b) amend the rule to score tuning from 2018 and select B1s, a post hoc change that the 2022 to 2025 evidence then cannot confirm; (c) keep B1s as the leading candidate and test it forward on the 2026 season's early weeks, which no analysis has touched; (d) separately approve B3 (needs a 2015 to 2019 CFBD membership pull) to address the balanced-game cost.

### Step 4B continued: conference tier, B3 (2026-11-15, owner-approved)

The owner chose to test B3 and approved the CFBD pull of team membership for 2015 to 2019 (read-only, `get_teams`; files and SHA-256 values in `~/cfb_ratings_lab_v6/source/cfbd-2026-11-15/`, hashes in `sha256_teams_2015_2019.json`). B3 is as declared: B1 plus two early-only indicators, a Power 4 host against a weaker (G5 or FCS/other) visitor, and a weaker host against a Power 4 visitor. Tiers use each season's membership; Power 4 is the SEC, Big Ten, Big 12, ACC and Notre Dame, plus the Pac-12 through 2023. Every game matched a CFBD team record. Same baseline (reproduced exactly), same earlier-only fitting. Outputs: `~/cfb_ratings_lab_v6/output/step4b-2026-11-15/step4b_b3_results.json`.

Stage 0 to 3 and stage 4 margin MAE / bias:

| Candidate | Tuning 2016 to 2021, stages 0 to 3 | Tuning, stage 4 | 2022 to 2025, stages 0 to 3 | 2022 to 2025, stage 4 |
|---|---|---|---|---|
| Baseline | 15.99 / +0.51 | 14.81 / -5.67 | 15.01 / +3.68 | 12.87 / -2.08 |
| B1 | 16.05 / -2.45 | 14.26 / -2.99 | 14.81 / +0.21 | 12.71 / +0.20 |
| B1s | 15.80 / -2.15 | 13.33 / -0.38 | 14.47 / +0.14 | 12.67 / +0.15 |
| **B3** | **15.30 / -2.26** | 14.21 / -2.84 | **14.09 / +0.10** | 12.71 / +0.21 |

**Against the declared rule on the tuning seasons:** B3 gains 0.68 stage 0 to 3 MAE (rule: at least 0.2), improves stage 4 MAE (14.81 to 14.21) and stage 4 bias magnitude (5.67 to 2.84), and beats B1 and B1s by 0.75 and 0.49 (rule: more than 0.10). It **fails the bias condition** (early bias magnitude 2.26 against 0.51), for the same reason as every candidate: 2016 and 2017 have a negative bias (-4.68 and -6.09) after short training windows. By the letter of the rule B3 is not selected. Its MAE is lower than the baseline in all five tuning seasons, 2016 and 2017 included (15.70 against 16.12, 15.32 against 15.59, 15.22 against 15.97, 14.04 against 14.87, 16.27 against 17.40).

**On 2022 to 2025 (examined seasons, reported once):** paired MAE gain over the baseline for B3 is 0.93 (90% interval 0.68 to 1.18) against 0.54 for B1s and 0.20 for B1; B3 over B1 is 0.72 (0.51 to 0.93). B3 improves all four seasons (2022 15.56 to 14.74, 2023 14.27 to 13.45, 2024 15.94 to 15.06, 2025 14.30 to 13.12), including 2024 where B1s was worse. Stage 4 MAE improves from 12.87 to 12.71. The stage 0 mean bias is still +2.98 under B3 because one early indicator cannot absorb it.

**It addresses the 4A matchup pattern.** Stage 0 bias by matchup on 2022 to 2025 (games; baseline, B1s, B3): Power 4 host v FCS/other (192) +12.00, +5.51, +3.65; Power 4 v G5 (86) +13.28, +5.39, +3.27; Power 4 v Power 4 (45) -3.39, -12.47, -5.14; G5 v Power 4 (17, below 30) -14.43, -22.72, -5.71; G5 v G5 (42) -5.05, -12.92, -6.24. B3 reduces the lopsided-game bias without the cost to balanced games that B1s had (Power 4 v Power 4 MAE 13.17, 16.22 for B1s, 13.38 for B3). In the final fit the two tier terms are +9.7 points for a Power 4 host against a weaker visitor and -10.8 for the reverse, early only. The rating-gap term B2 did not capture this, so the conference-tier information is not in the ratings at stages 0 to 3.

**Post hoc, not part of the rule:** on 2018, 2019 and 2021 only (bridges with three or more training seasons), B3 gives stage 0 to 3 MAE 15.17 against 16.07 for the baseline with bias -0.22 against +3.06, and meets every declared condition there. Adding the same tier terms to the per-stage intercept (B1s plus tier, a candidate not on the declared list, labelled exploratory) gives 2022 to 2025 stage 0 to 3 MAE 13.90 (gain 1.11, 0.83 to 1.40; stage 0 bias -0.03) and 15.35 on the tuning seasons; it was not selected or confirmed.

Limits: the 2022 to 2025 seasons were examined before, so the confirmation figures are not independent; the tuning seasons fail the bias condition and the short-window result is a property of how the rule was set; conference tier is public before kickoff, but the files were captured on 2026-11-15, so historical availability is unverified; tier and prior quality overlap, so the term cannot say whether quality or conference carries the signal; Power 4 membership is a judgement for the Pac-12 (counted through 2023); the model change was fitted only on margin and totals were not examined.

#### Holdout declaration for the owner's chosen test (c), not yet run

The owner accepted testing the leading candidate on seasons no analysis has touched. Correction to the earlier recommendation: the early weeks of 2026 are already played (the season is in its final weeks), so they cannot be a forward test; they are a holdout whose outcomes are known but whose scores no analysis here has used. A genuinely forward test is the early weeks of 2027. Declared now, before any 2026 score exists:

| Field | Content |
|---|---|
| Question | Do B1s and B3 lower stage 0 to 3 margin MAE against Operational V5 on 2026 regular-season games, with stage 4 not worse? |
| Candidates | B1s and B3 as defined above, no others. Bridge refitted on 2015 to 2025, earlier-only; the baseline is the same refit without the added terms. |
| Population | 2026 regular-season games at completed-game stages 0 to 3, and stage 4 as the comparison; postseason excluded. |
| Pass condition | Stage 0 to 3 MAE gain of at least 0.2 over the baseline, stage 4 MAE no more than 0.05 above it, and stage 0 to 3 bias magnitude smaller than the baseline's. Report the game count; if fewer than 300 stage 0 to 3 games are usable, say so and treat the result as indicative. |
| Needs before running | 2026 serving states, outcomes and offsets confirmed present locally (not yet checked) and CFBD 2026 team membership (a further read-only pull, needs approval). |
| Cannot show | Forward performance: the outcomes are known. The 2027 season is the clean forward test. |

#### 2026 holdout result (2026-11-15, owner-approved retrieval and run)

The owner approved a read-only fetch from the Preview bucket (read credential only) of the 2026 state and forecast files of rebuild run `6a-rebuild-w6-20261012-r2`: `states_2026/` pregame roles, teams, population, priors and summary, and `forecast/` offsets, offset team-games and feature frame. Files and SHA-256 values: `~/cfb_ratings_lab_v6/source/preview-2026-11-15/`; the two files that have a hash in the earlier retrieval index match it, and the other sizes equal the listing. Outputs: `~/cfb_ratings_lab_v6/output/step4b-2026-11-15/step4b_holdout_2026_results.json`.

What the 2026 data allows: pregame ratings for 329 games in weeks 0 to 6 (cutoff 2026-10-11), final scores from the local 2026 finals, tiers from the local 2026 schedule (Pac-12 counted as G5, as in 2024 and 2025). Stages were rebuilt as the smaller of the two teams' completed-game counts, capped at 4; the same rule reproduces every 2025 stage label exactly. **The forecast offsets stop at 2025, so every arm, baseline included, uses a zero offset in 2026** (the 2015 to 2025 offsets average 0.007 with standard deviation 0.84, so this adds noise but does not shift the bias). The bridge was fitted on 2015 to 2025 with the real offsets. The 2026 rating states carry a different candidate name from the historical states (`ppp__rho_0_60__exposure__game_at_cutoff_v1` against `v5_game_adjusted_at_cutoff_v1`) and a similar but not identical rating scale (offense mean 0.43, standard deviation 0.72, against 0.60 and 0.82 pooled); that they are the same recipe is not verified, so the baseline here is not the served model.

Margin MAE / bias (games):

| Candidate | Stages 0 to 3 (293) | Stage 0 (86) | Stage 1 (67) | Stage 2 (71) | Stage 3 (69) | Stage 4 (36) |
|---|---|---|---|---|---|---|
| Baseline | 14.10 / +0.41 | 15.40 / +4.83 | 13.13 / -1.44 | 14.98 / -1.69 | 12.52 / -1.14 | 13.83 / +0.02 |
| B1s | 14.15 / -2.48 | 15.18 / -3.44 | 13.93 / -5.68 | 14.64 / -1.69 | 12.58 / +1.00 | 14.55 / +2.32 |
| B3 | 13.47 / -2.75 | 14.20 / -0.10 | 12.56 / -4.89 | 14.09 / -4.14 | 12.83 / -2.56 | 14.43 / +2.34 |

Against the declared pass condition (gain at least 0.2, stage 4 MAE no more than 0.05 above, smaller bias magnitude):

- **B1s fails all three.** Gain -0.05 (90% bootstrap interval -0.52 to +0.42), stage 4 MAE +0.72, bias magnitude 2.48 against 0.41.
- **B3 meets the gain condition and fails the other two.** Gain +0.62 (0.18 to 1.07); stage 4 MAE +0.60 over the baseline on 36 games; bias magnitude 2.75 against 0.41. By the letter of the rule it does not pass.

Reading it: the stage 0 to 3 count is 293, below the 300 declared as the minimum for more than an indicative result, and stage 4 has only 36 games, so the stage 4 condition rests on very little. B3's gain comes from stage 0 (15.40 to 14.20) and shows the 4A pattern again: Power 4 hosts against G5 teams (40 games) go from a bias of +11.7 to +1.7. The bias condition fails because the added early terms over-correct in 2026: stage 1 bias is -5.68 under B1s and -4.89 under B3 against -1.44 for the baseline, where the stage terms fitted on 2015 to 2025 (about +7 points at stage 1) are larger than 2026 needs. That is the instability the tuning seasons showed (2016 and 2017), here in a season with a full training window.

Overall: B3's MAE gain has now appeared in all five tuning seasons, all four seasons of 2022 to 2025 and the 2026 holdout, but no candidate has passed the declared bias condition on any evidence, and the 2026 data are not a forward test (outcomes were known). No change to Operational V5 is supported by the declared rules. The clean forward test is the early weeks of 2027, and it needs the candidate fixed in advance, with early stage terms shrunk or bias-checked as a declared part of the design if the owner wants a version that passes the bias condition.

### Benchmark population: FBS-vs-FBS headline, FBS-vs-FCS secondary (owner decision 2026-11-15)

The owner decided that the headline population is **FBS-vs-FBS games**, with FBS-vs-FCS games reported separately because they should carry some signal. Basis: the release universe of the weekly slate is FBS-vs-FBS (`docs/status.md`: Week 10 "62 FBS-vs-FBS games; the 63rd ... Wake Forest 77, Merrimack 0, is FBS-vs-FCS and outside the release universe"), and the market diagnostic notes that unlined games are mostly FBS-vs-FCS. Earlier figures in this contract that pool both (13.7151 and 13.3709 over 3,483 games) remain correct for the pooled population and are labelled as such. Outputs: `~/cfb_ratings_lab_v6/output/step4a-2026-11-15/step4a_population_split_results.json`. One 2022 game (Tarleton State) has no tier and is in neither group.

**Why the split matters.** FBS-vs-FCS games exist only at early stages (484 of the 1,371 games at stages 0 to 3, none at stage 4), so comparing early with late stages also compares opponent types. Their actual home margin is +31.1 against +7.7 for early FBS-vs-FBS games.

Margin, 2022 to 2025 (games; actual mean margin; Operational V5 MAE / bias; priors only MAE / bias):

| Population and stage | Games | Actual | Operational V5 | Priors only |
|---|---|---|---|---|
| **FBS v FBS, all stages** | **2,998** | +4.4 | **13.35 / -1.22** | 14.07 |
| FBS v FBS, stage 0 | 190 | +11.5 | 15.12 / +2.80 | 14.55 / +2.90 |
| FBS v FBS, stage 1 | 201 | +8.6 | 14.62 / +2.25 | 13.23 / -0.15 |
| FBS v FBS, stage 2 | 242 | +7.3 | 15.05 / +0.73 | 15.26 / +0.18 |
| FBS v FBS, stage 3 | 253 | +4.6 | 13.32 / -1.66 | 13.18 / -1.93 |
| FBS v FBS, stages 0 to 3 | 886 | +7.7 | 14.47 / +0.84 | 14.05 / +0.08 |
| FBS v FBS, stage 4 | 2,112 | +3.2 | 12.87 / -2.08 | 14.08 / -1.65 |
| FBS v FCS, stages 0 to 3 | 484 | +31.1 | 15.99 / +8.86 | 16.49 / +6.49 |

Total: FBS v FBS 13.49 / -1.77 for Operational V5 (13.67 priors only) over 2,998 games; FBS v FCS 12.62 / +1.13 (12.74 priors only) over 484.

**FBS-vs-FBS reading (the headline).** In the population that is published, the early-season bias is small (+0.84 at stages 0 to 3, +2.80 at stage 0), and priors alone are at least as accurate as Operational V5 through stage 1 (14.55 against 15.12; 13.23 against 14.62) and roughly equal at stages 2 and 3, before in-season updating pays off at stage 4 (12.87 against 14.08). So for the published games the early-season issue is that one-game updating and the pooled bridge do not beat the priors early, not a large mean bias. This changes how 4A should be read: the large stage 0 bias (+7.16) and the intercept discussion belong mostly to FBS-vs-FCS games.

**FBS-vs-FCS signal.** The predictions carry ranking signal but are mis-levelled:

- Correlation of the margin prediction with the actual margin is +0.39 (priors only +0.35); the games ordered by prediction have actual margins of +23.0, +30.7 and +39.6 across the low, middle and high thirds (predicted +9.3, +21.9, +35.6). The slope of actual on prediction is 0.61.
- The prediction level is wrong: bias +8.86, and the raw MAE 15.99 is worse than a constant (the mean margin of earlier FBS-vs-FCS games, MAE 15.52). The model's home edge and rating scale are fitted on FBS games.
- **An earlier-only linear map fixes it.** Fitting actual margin on the baseline prediction for earlier FBS-vs-FCS games (slope 0.59 to 0.62, intercept 14.3 to 16.0 in every season) gives MAE 14.24 against 16.00 raw (gain 1.77, 90% interval 1.24 to 2.30) and 15.53 for the constant (gain 1.30, 0.81 to 1.82), better than both in all four seasons. This is a post hoc diagnostic on the examined seasons, not a candidate, and uses the 2016 to 2021 baseline predictions recomputed in step 4B.
- Winner picks carry no value: the home team wins 95.5% of these games and the model picks the home team 96.9% of the time with 94.4% accuracy. Any value is in margin size (blowout ranking), not who wins.
- Totals: Operational V5 12.62 against 12.87 for a constant (correlation +0.11, bias +1.13), a small gain.
- No market comparison is possible (these games are mostly unlined).

Consequences for the work order: step 4B's candidates were judged on the pooled early population, so their gains (B3 especially) partly reflect FBS-vs-FCS games; whether they help the FBS-vs-FBS population is not shown here and is the next measurement. Reporting rule from here: every table gives FBS-vs-FBS as the headline with FBS-vs-FCS separate, and pooled figures only labelled as pooled.

#### Step 4B candidates rescored on FBS-vs-FBS only (2026-11-15, owner-approved)

The saved 4B predictions were split by opponent type. No refit: the candidates were still fitted on the pooled population, only the scoring population changes. Outputs: `~/cfb_ratings_lab_v6/output/step4b-2026-11-15/step4b_fbs_vs_fbs_rescore.json`. Margin MAE / bias; gains are over the baseline with 90% paired bootstrap intervals.

FBS-vs-FBS, 2022 to 2025 (886 games at stages 0 to 3, 2,112 at stage 4):

| Population / stage | Games | Baseline | B1 | B1s | B3 |
|---|---|---|---|---|---|
| Stage 0 | 190 | 15.12 / +2.80 | 15.04 / -0.78 | 15.74 / -5.40 | **13.35 / -1.63** (gain 1.77; 0.97 to 2.59) |
| Stage 1 | 201 | 14.62 / +2.25 | 14.39 / -1.80 | 14.52 / -2.96 | 13.43 / -1.62 |
| Stage 2 | 242 | 15.05 / +0.73 | 15.32 / -3.26 | 14.99 / +0.79 | 14.56 / -2.74 |
| Stage 3 | 253 | 13.32 / -1.66 | 14.04 / -5.70 | 12.92 / -0.23 | 13.43 / -4.30 |
| Stages 0 to 3 | 886 | 14.47 / +0.84 | 14.68 / -3.09 (gain -0.21) | 14.45 / -1.68 (gain 0.02) | **13.72 / -2.69** (gain 0.75; 0.42 to 1.08) |
| Stage 4 | 2,112 | 12.87 / -2.08 | 12.71 / +0.20 | 12.67 / +0.15 | 12.71 / +0.21 |
| All stages | 2,998 | 13.34 / -1.22 | 13.30 / -0.77 | 13.20 / -0.39 | 13.01 / -0.65 |

FBS-vs-FCS, stages 0 to 3 (485 games): baseline 16.00 / +8.88; B1 15.04 / +6.23; B1s 14.51 / +3.46 (gain 1.50); B3 14.75 / +5.21 (gain 1.25).

Other populations: on the tuning seasons FBS-vs-FBS stages 0 to 3 (1,108 games) the baseline is 16.01 / -1.81, B1 16.34, B1s 16.01 (gain 0.00), B3 15.32 / -4.33 (gain 0.70; 0.41 to 1.00), and B3 is better than the baseline in all five tuning seasons. The 2026 holdout population contains no FCS games, so its figures (B3 gain 0.62; B1s -0.05) were already FBS-vs-FBS.

What this shows:

1. **B1s's gain was an FBS-vs-FCS effect.** On the published games it gains 0.02 at stages 0 to 3 and is worse at stage 0 (15.74 against 15.12, with a bias of -5.40); its 0.54 pooled gain came from FBS-vs-FCS games (gain 1.50) and the stage 4 shift. B1 is worse than the baseline on FBS-vs-FBS (-0.21).
2. **B3 has a real FBS-vs-FBS gain.** 0.75 over stages 0 to 3 (1.77 at stage 0), better than the baseline in all four seasons of 2022 to 2025 (14.94 to 14.01, 13.76 to 13.16, 15.37 to 14.71, 13.83 to 13.01), in all five tuning seasons and on the 2026 holdout. The conference-tier terms therefore help within the published games, not only against FCS opponents (they separate Power 4 hosts from G5 visitors; the rating gap B2 did not).
3. **Declared rule on FBS-vs-FBS.** B3 meets the gain condition (0.75, at least 0.2) and stage 4 (12.71, below the baseline's 12.87), and fails the bias condition again: early bias -2.69 against +0.84 (tuning -4.33 against -1.81). The early indicator is fitted on pooled rows, including FBS-vs-FCS games, so it is too large for FBS-vs-FBS games, and the over-correction follows.
4. **The bridge intercept is inflated by FCS games, which explains the stage 4 gain.** For 2022 to 2025 the training mean target (the Ridge intercept) is 7.38 to 7.57, but it is a blend: 4.1 to 4.2 for FBS-vs-FBS training games and 29.0 to 29.5 for the 13% that are FBS-vs-FCS. For published games the single intercept is therefore about 3 points high, consistent with the baseline's FBS-vs-FBS stage 4 bias of -2.08. Every candidate improves FBS-vs-FBS stage 4 (MAE 12.71, 12.67, 12.71 against 12.87; gains 0.16 to 0.20, intervals above zero), which fits the early rows no longer pulling the intercept; this is consistent with, not proof of, that mechanism.

Consequence for the work order: the next candidate to declare, if the owner wants one, is a bridge that does not let FBS-vs-FCS games set the FBS-vs-FBS level (an FBS-vs-FCS indicator, or fitting on FBS-vs-FBS games), combined with the tier terms. It is not yet declared or run.

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
10. Done 2026-11-15: the postseason rows are removed from training, calibration and scoring, and the three baselines are refitted (see the refitted benchmark section). Operational V5: margin MAE 13.7151, total MAE 13.3709 over 3,483 games.
11. Optional: rerun the slice tables and contribution decomposition on the refitted predictions.
12. Done 2026-11-15: work-order step 3 (see that section).
13. Before step 4, revise its list of bounded experiments in light of steps 2 and 3: the possession-volume experiment has lost its basis; the venue experiment covers 126 regular-season games; the early-season result (updated ratings no better than priors through three games) and the total's efficiency variation are the larger open questions. This is an owner decision. List approved 2026-11-15 (step 4 section); no experiment approved to run.

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

### Step 4: bounded experiments (revised list, owner-approved 2026-11-15; running each experiment still needs its own approval)

Steps 2 and 3 changed what is worth testing. The original list was venue, a pregame possession-volume input, and prior and update variants. Revised:

| Item | Status | Reason |
|---|---|---|
| Pregame possession-volume input | Withdrawn | Possession volume correlates +0.065 with the final total and +0.016 to +0.048 before kickoff (step 3 section C). |
| Venue flag | Kept, narrowed | Applies to 126 regular-season neutral-site games (bias -2.69), so it can show direction but has little power. |
| Early-season error attribution, then prior and update variants | Kept, moved first | Stages 0 to 3 are no better than preseason priors; stage 0 margin bias is +7.16 and week-1 openers 473 games, MAE 16.18, bias +5.89. |
| Totals head: shrinkage and feature form | Replaces the possession item | Predicted totals vary by about 1.6 points against 16.9 actual because the fitted total coefficients are small and offense and defense terms cancel (correlation -0.50). |
| Non-conference bias (+4.22) | Moved to step 5 | It overlaps early season and FCS games; screen it after the early-season attribution. |

Order: A, then B, then C. D after B. Each result decides whether the next runs.

**A. Early-season error attribution (diagnostic, no new model).**

| Field | Content |
|---|---|
| Question | Is the stage 0 to 3 error mainly the prior's quality, the bridge's home-edge intercept, or the speed of in-season updating? |
| Changes | Nothing is refitted differently. Split the existing stage 0 to 3 residuals of Operational V5 and of the priors-only prediction by team group (returning starters, prior rank, conference tier), and compare the intercept with the stage's mean outcome. |
| Frozen | Operational V5 states, priors, bridge recipe, the regular-season population and the earlier-only refit. |
| Refitted | Nothing beyond the existing earlier-only refit. |
| Population | Regular-season 2022 to 2025, 3,483 games; 2021 only where the earlier work already used it. |
| Cannot show | Causation, or that any change would help; the seasons are already examined. |

**B. Prior and update variants (conditional on A).**

| Field | Content |
|---|---|
| Question | Does a stage-dependent blend of prior and in-season rating, or a stage-specific bridge intercept, lower stage 0 to 3 margin error and bias without raising stage 4 error? |
| Changes | Only the blend weight or intercept, chosen from a small list declared before it runs. |
| Frozen | Measurements, priors, adjustment, update rules and every stage 4 rating. |
| Refitted | Bridge, earlier-only, labelled as such. Frozen-coefficient variants are reported separately. |
| Population | Tuned on 2015 to 2019 and 2021 where inputs exist; 2022 to 2025 reported as previously examined evidence. |
| Cannot show | Independent confirmation; a gain at stages 0 to 3 says nothing about totals. |

**B declarations (drafted 2026-11-15 after step 4A, owner-accepted direction; not approved to run).** The owner accepted the recommendation to declare a rating-gap variant together with a stage-specific intercept as its baseline. Every candidate is listed here before anything runs. Nothing else may be added after results are seen.

| Field | Content |
|---|---|
| Question | Does letting the early-season home margin depend on the rating gap lower stage 0 to 3 margin MAE and bias beyond what a stage-specific intercept does, without raising stage 4 error? |
| Candidates (complete list) | **B1, intercept only:** a separate home-edge intercept for stages 0 to 3 pooled (one value), fitted as an extra indicator in the earlier-only bridge. **B1s, per stage:** one intercept for each of stages 0, 1, 2, 3. **B2, rating gap:** B1 plus an interaction of the stage 0 to 3 indicator with the home-minus-away net rating (the sum of the four bridge terms), so mismatches can scale differently early. **B3, conference tier (conditional):** B1 plus indicators for Power 4 host against a weaker (G5 or FCS) visitor and for the reverse, early only. B3 needs conference membership for the tuning seasons, which is not pulled (only 2021 to 2025 is); it runs only if the owner separately approves that CFBD pull. |
| Changes | Only the added bridge terms listed above, for rows at completed-game stages 0 to 3. Stage 4 rows use the existing bridge terms and receive no new term. |
| Frozen | Measurements, priors, adjustment, update rules, every rating at every stage, the alpha-10 Ridge recipe, the regular-season population (postseason excluded), earlier-only calibration, and the totals bridge. |
| Refitted | The margin bridge only, earlier-only, labelled as such. For each validation season the bridge sees only earlier seasons; the stage 4 coefficients may move because the fit is joint, so stage 4 is checked, not assumed unchanged. Frozen-coefficient versions (new terms added to the stored coefficients) are reported separately. |
| Population | Tuned and selected on 2015 to 2019 and 2021 where the inputs exist, earlier-only within that range. 2022 to 2025 (3,483 games, stages 573, 301, 244, 253, 2,112) are reported once, as previously examined evidence, and are not used to choose among candidates. Cache check (2026-11-15, read-only): the feature frame carries ratings, outcomes and completed-game stages for 2015 to 2019 and 2021, with 1,975 regular-season stage 0 to 3 games (790 at stage 0; 322 to 338 per season) after removing the postseason ids, so there is enough data to tune on. Operational V5 predictions exist only for 2022 to 2025, so the baseline for the tuning seasons has to be recomputed with an expanding earlier-only fit, and 2015 has no earlier seasons to train on; the first scored tuning season is 2016. |
| Pass condition (declared now) | Selected on the tuning seasons, then confirmed on 2022 to 2025: pooled stage 0 to 3 margin MAE below Operational V5's 15.01 (pooled over the 1,371 stage 0 to 3 games; bias +3.68) and stage 0 to 3 absolute bias below it, with stage 4 margin MAE no more than 0.05 above 12.87 and stage 4 bias magnitude no larger than 2.08. A candidate that gains stage 0 to 3 MAE by less than 0.2 is reported as no gain. Measured spread (paired bootstrap, 5,000 resamples, 1,371 stage 0 to 3 games of 2022 to 2025): the standard error of a paired MAE difference is 0.10 for an intercept-sized change (Operational V5 against itself with its in-sample mean bias removed, which gains 0.25 in sample, so about 2.6 standard errors but optimistic because it is fitted on the same games) and 0.23 for a large change (Operational V5 against priors alone, difference 0.09). The 0.2 threshold is about two standard errors for an intercept-sized change and under one for a large one. The 0.05 stage 4 guard has not been measured against resampling noise and may be inside it. Both thresholds remain proposals for the owner to confirm. Expect B1 to be borderline at 0.2. |
| Reference points from 4A | A single pooled shift that zeroes the stage 0 to 3 bias can lower stage 0 MAE by at most 0.91 and, applied globally, worsens stage 4 (MAE 13.60). B2 and B3 are justified only if they beat B1 and B1s by a margin larger than that noise. |
| Cannot show | Independent confirmation; a gain on stages 0 to 3 says nothing about totals or about stage 4 beyond the stated guard. B2 cannot separate rating gap from tier because they overlap; B3, if run, cannot separate quality from conference. A gain on 2022 to 2025 that is not present on the tuning seasons is not a result. |

**C. Totals head: shrinkage and feature form.**

| Field | Content |
|---|---|
| Question | Is the flat total caused by over-shrinking and cancellation inside the bridge, or by ratings that carry little totals signal? |
| Changes | The total head only: ridge strength, and a sum-of-offense-and-defense feature in place of the four separate terms. The margin head is untouched. |
| Frozen | Rating states, offsets, the margin head, and the intervals' construction. |
| Refitted | Total head, earlier-only; the alpha list is declared before it runs. |
| Population | Same as B. |
| Cannot show | That a better total exists; the unexplained 80% of total variance may be game-level efficiency noise. A result near the 13.37 total MAE means ratings hold little more totals signal. |

**D. Venue flag.**

| Field | Content |
|---|---|
| Question | Does using the stored neutral-site flag instead of a constant home flag reduce the neutral-site bias? |
| Changes | The flag only; `_design` currently drops it because it is constant, so it must vary. |
| Frozen | Everything else. |
| Refitted | Bridge, earlier-only. |
| Population | 126 regular-season neutral-site games in 2021 to 2025 plus the home games, to check nothing else moves. |
| Cannot show | The size of the home edge, or an effect that survives 126 games of noise. |

Flexible bridges are scored only on chronological out-of-sample predictions. One-at-a-time swaps miss interactions between layers and are reported with that caveat. Market results play no part in choosing among these.

Owner approved the list and order on 2026-11-15. Still open before B and C run: confirm that tuning may use 2015 to 2019 and 2021 only where the retained inputs exist, and say what to do where they do not. Running A needs a separate go-ahead.

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
6. **Benchmark population (decided 2026-11-15, to be written into the protocol with the other amendments).** The headline population is regular-season games only: 3,483 games per target for 2022 to 2025 instead of 3,659. Postseason games are identified by the rule in the regular-season benchmark section and are removed from bridge training and calibration as well as scoring (owner decision 2026-11-15).
5. **Market.** Market comparison is reported only after football-based priorities are frozen, with identical game coverage, verified spread signs, quote provenance, and cutoff-time lines reported separately from closing lines. Using market results to steer research would be market-informed prioritization and needs its own explicit approval.

## Validation

`git diff --check`; `uv run mkdocs build --strict`; this contract is listed in the [plans index](../index.md). The inventory counts above were produced by reading and hashing every listed file.

## Handoff/amendments

Resume gate: owner approval of the next executable scope. Record amendments here with the reason, previous approach, revised approach and impact.
