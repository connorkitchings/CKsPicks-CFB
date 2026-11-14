# V5 baseline audit and model analysis framework

- **Status:** Draft
- **Created:** 2026-11-14
- **Planner:** Sol
- **Approval source:** The owner approved writing this Draft and running the local read-only inventory on 2026-11-14, after two rounds of review. Approval to execute any step of the work order is the next gate and is given per step.
- **Implementation log:** `session_logs/2026-11-14/02-baseline-audit-contract-and-inventory.md` (this Draft and the inventory only)
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

- **No historical replay of Operational V5 exists.** The repair experiment used the 2026-09-21 parents. The serving model takes its priors, terminal table, historical population and events from the 2026-10-12 rebuild (`6a-rebuild-w6-20261012-r2`) and applies a pinned bridge bundle. The experiment therefore differs from serving in input lineage as well as in bridge fitting.
- **How the serving bridge bundle was fitted** (seasons, rating lineage, penalty) is not established from the repository. It needs the bridge manifest.
- Whether a local-verified cache from the repair run (`--verified-cache`) survives anywhere.
- Historical market lines for 2021 to 2024 (only the 2025 diagnostic is known).
- The original prepared artifacts the [ratings audit](../../modeling/v5_offense_defense_ratings_audit_2026.md) could not recover.

### Capability table

| Capability | Code | Runs offline today |
|---|---|---|
| Historical V5 bridge-level scoring and slicing | `ratings_lab/evaluation.py`, `error_slices.py`, `total_bias.py` | Yes, from the corpus (last demonstrated by the 2026-11-12 diagnostics run; not rerun today) |
| Closed V6 scorecards | `evaluation.scorecard` on the verified prediction stages | Yes |
| Historical V5 rating-state replay | `ratings_lab/v5_control.py` | No: needs the control inputs from source |
| Repair-arm replay | `scripts/research/v5_intended_update_review.py` | No: needs the same inputs |
| New measurements from plays | `Corpus.read_byplay`, `ratings_lab/measurements.py` | No: needs lower-level datasets |
| Operational V5 historical replay | Engine `IntendedUpdate` (`ratings/possession_intended_update.py`); no historical runner found | No: gap |
| Paired comparison per protocol | `evaluation.paired_comparison` returns 90% season/week intervals | Gap against the written protocol |

`replay_v5_control` reproduces downstream rating states from certified snapshots and priors. It is not a rebuild from plays.

## Next executable scope (needs owner approval)

1. One credentialed, read-only retrieval into a hash-verified local cache: the Historical V5 control inputs, the serving bridge manifest and bundle, and the manifests for the `6a` rebuild inputs.
2. Read the bridge manifest and record how the serving bridge was fitted.
3. Then work-order step 2.

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
