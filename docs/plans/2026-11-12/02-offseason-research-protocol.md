# Pre-registered offseason research protocol

- **Status:** Draft
- **Created:** 2026-11-12
- **Planner:** Sol
- **Approval source:** Pending. The owner approves the thresholds in the Protocol section before any 2026 residual is examined.
- **Implementation log:** Pending (documentation only; `session_logs/2026-11-12/NN-research-protocol.md`)
- **Commit policy:** Separate plan commit before any diagnostics run, so the registration date is verifiable in git history.

## Goal and acceptance

Write down, while 2026 is still unseen as a holdout, how any offseason model candidate will be compared and adopted. The offseason rules in the [backlog](../../planning/offseason-2027-backlog.md) say gates are written before any run; this contract is that record.

Acceptance: the Protocol section is approved and committed before the diagnostics report ([contract 03](03-prediction-error-diagnostics.md)) or any candidate run starts; no later amendment loosens a threshold without a dated amendment entry.

## Baseline and constraints

- Frozen V5 (the accepted 2026-09-21 source family) is the comparison model. The closed V6 ratings lab (`RETAINED_AS_BENCHMARK` on 2026-09-30, did not beat V5) supplies the `v5-common` bridge reference and the evaluation code: `src/cks_picks_cfb/ratings_lab/evaluation.py` (`scorecard`, `paired_comparison`, `common_bridge_predictions`, `frozen_v5_predictions`) and the template `conf/research/ratings_lab_v1/protocol.yaml`.
- 2026 is the clean holdout. No feature, prior, threshold or model choice may use 2026 results or betting win/loss slices ([betting policy](../../modeling/betting_policy.md), [evaluation](../../modeling/evaluation.md)).
- Out of scope: running any candidate, changing V5, releases, the public record.
- Assumption to confirm: the lab's research bucket credentials (`CFB_R2_LAB_*`) are not in `.env`, so lab runs use the local-output exception until the owner provisions the bucket (tracked in the backlog).

## Protocol (to be approved)

- **Populations:** development seasons 2021 to 2025; headline seasons 2022 to 2025 (the corpus of 7,318 frozen V5 rows); 2021 only through the bridge's rolling-origin errors. Earlier seasons in the lab protocol (2015 to 2019) may be used to fit a candidate but never for the headline.
- **Targets:** home-minus-away margin and total points, scored separately.
- **Metrics:** MAE, RMSE, bias, Gaussian CRPS, 90% interval coverage and width, each pooled, by season and by completed-game stage, from `scorecard`.
- **Comparison:** paired bootstrap against frozen V5 and against `v5-common`, 2,000 replicates, seed `20260928`, resampling games.
- **Adoption thresholds (proposal; the owner edits before approval):** a candidate is eligible only if, on the 2022 to 2025 headline, the paired 95% interval for the MAE difference versus V5 excludes zero in the candidate's favor on the target it claims; no season's MAE is worse than V5's by more than 0.10 points; 90% interval coverage stays within 87% to 93%; and Weeks 0 to 4 are not worse than V5.
- **Holdout rule:** a candidate is frozen (code, parameters, hashes recorded) before any 2026 scoring. 2026 is scored once, week by week at the original information time, after the 2026-12-13 final close. A failed 2026 score ends that candidate; it is not tuned and rerun.
- **Market data:** closing-line value (from the [near-kickoff capture](01-near-kickoff-line-capture.md)) and betting results are monitoring views, never selection criteria.
- **Logging:** every candidate run records the commit, the protocol hash, the seed and the output hashes.

## Ordered changes

1. Owner edits and approves the thresholds above. Acceptance: the Status line records approval and date.
2. Add `conf/research/offseason_2027/protocol.yaml` copying the lab protocol keys, with the approved values and explicit `holdout_season: 2026` and `holdout_scored_once: true` entries. Acceptance: loads with the lab's existing protocol loader (confirm the loader accepts the new keys; if not, stop and return to Sol).
3. Link the protocol from the backlog and `docs/modeling/evaluation.md`.

## Validation

`git diff --check`, `uv run mkdocs build --strict`, and the contract is listed in `docs/plans/index.md`. Boundary check: the protocol file parses and its seed and replicate count equal the lab's values.

## Handoff/amendments

Resume gate: owner approval of the thresholds. Next action: task 2. Amendments are dated entries here stating the reason and the previous and revised values; loosening a threshold after any 2026 residual has been viewed is not allowed.
