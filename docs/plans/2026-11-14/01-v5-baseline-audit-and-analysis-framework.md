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
| Operational V5 historical replay | Engine `IntendedUpdate` (`ratings/possession_intended_update.py`); historical states for the operational recipe are local and hash-verified (2026-11-14); no earlier-only predictions exist | Gap: needs a chronological bridge fit on those states plus offsets |
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

- The bundle carries coefficients for the four standardized ratings only. `home_host` and `venue_unknown` are in `feature_order` but have no coefficient; the margin intercept is 7.43 points. How `apply_exported_bridge` treats the two venue flags is not yet verified.
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

Differences identified so far, neither fully explained:

- **Priors differ in 31,890 rows** and are mostly identical only in 2015, the first season. This is consistent with the experiment holding the certified priors fixed (its report says all arms use the accepted preseason priors) while the serving run carries priors from its own earlier-season ratings. That reading is an inference from the pattern, not yet checked in the code that built the serving states.
- **The same game can carry a different observation value.** In the largest difference (Ohio State offense, 2023, before its second game) both sets use the same single game with the same 10 possessions, but its adjusted value is +0.65 in the serving set and -1.05 in the experiment. Candidate causes are the rebuild's 1,416 admitted scoring-event decisions and different standardization scales; the split is not attributed.

Consequence for the baselines: the 2022 to 2025 results documented for the repaired arm (margin MAE 13.744) describe the experiment's states, not the serving model's. Operational V5's historical accuracy is still unmeasured; it needs an earlier-only bridge fit on the serving states.

### Still unavailable

- The 12 original row-level outputs of the 2026-09-28 repair experiment (not located in the listed prefixes). A rerun copy now exists locally.
- Earlier-only historical predictions for the operational recipe (they would have to be produced by fitting the bridge chronologically on the retrieved states).
- The bridge manifest's third parent, `rebuild/6a/6a-task4-w5-r2/receipt/receipt.json` (not in the approved scope).
- Lower-level play datasets, historical market lines for 2021 to 2024, and the original prepared artifacts the ratings audit could not recover.

## Next executable scope (needs owner approval)

1. Done 2026-11-14: `historical-states.parquet` and the `w5` rebuild manifests are in the local mirror.
2. Done 2026-11-14: the repair experiment was rerun offline and its retained results are reproduced to 2.8e-14 (see the rerun section). Row-level identity with the original files remains unproven.
3. Done 2026-11-14: the serving states were compared with the rerun's repaired arm row by row (see the state comparison section). They agree on structure and timing and differ in values.
4. Explain the two value differences from the code and manifests that built the serving states (how its priors were formed; which observation values changed and why).
5. Produce Operational V5's historical predictions: an earlier-only chronological bridge fit on the serving states with the rebuild's offsets. This is the first new scoring and is not authorized until approved.
6. Then the rest of work-order step 2.

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
5. **Market.** Market comparison is reported only after football-based priorities are frozen, with identical game coverage, verified spread signs, quote provenance, and cutoff-time lines reported separately from closing lines. Using market results to steer research would be market-informed prioritization and needs its own explicit approval.

## Validation

`git diff --check`; `uv run mkdocs build --strict`; this contract is listed in the [plans index](../index.md). The inventory counts above were produced by reading and hashing every listed file.

## Handoff/amendments

Resume gate: owner approval of the next executable scope. Record amendments here with the reason, previous approach, revised approach and impact.
