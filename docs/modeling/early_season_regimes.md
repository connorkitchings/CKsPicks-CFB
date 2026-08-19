# 2026 Week 0 and Early-Season Evaluation Contract

The canonical production design evaluates spread and total independently for a
team's upcoming `game_1`, `game_2`, `game_3`, `game_4`, and `established` route. The
first game has zero completed-game observations; it is not a preseason game.
A matchup uses the route of its least-experienced team, while each team keeps
its own completed-game count and shrinkage weight. Legacy labels
(`preseason`, `one_game`, `two_games`, and `three_games`) remain readable for
historic artifacts only.

Model features must be reproducible before kickoff and cannot include spreads, totals, moneylines, or other bookmaker values. Market data enters only after prediction for edge, grading, ROI, and drawdown calculations.

## Frozen chronology and lineage

- Selection folds: train 2021/test 2022, train 2021–2022/test 2023, and train 2021–2023/test 2024.
- Locked test: train 2021–2024 and evaluate 2025 once after the design is frozen.
- Final 2026 refit: the unchanged design trains on 2021–2025.
- 2019 is not a labeled season; it is allowed only as the last normal prior-quality source for early 2021.
- 2020 is excluded from labeled rows, features, lineage, tuning, testing, and refitting.

For games one through four, the tournament compares direct Ridge, direct
CatBoost, points-derived Ridge, and points-derived CatBoost. Team-side current
metrics are empirically shrunk to prior values using that team's own play,
drive, or completed-game exposure. The reviewed prior-strength grids are plays
`{50,100,200,400}`, drives `{5,10,20,40}`, and games `{1,2,4,8}`.

Historical quote data is optional betting research. It is never a model input
and it is not required to select, refit, or activate a Games 1–3 prediction
route. When quote data is later used for betting evaluation, it must be
timestamped; untimestamped legacy CFBD references remain ineligible.

## V4 immutable feature references

V4 covers feature lineage for 2021–2026: 2021 supplies the first OOF training
fold, 2022–2024 select the design, 2025 remains locked until selection is
sealed, 2021–2025 refit the winner, and 2026 is inference-only.

The strict reference is activation-eligible and starts with verified prior
performance plus current-season shrinkage. Returning production, transfers,
recruiting, coaching, roster continuity, preseason rankings, and talent are
additive candidate families only when every required team-season has immutable
source provenance with an effective time before that season's first kickoff.
Talent is all-or-nothing. Historic data retrieved later without that evidence
belongs to a separate `reconstructed` research reference; its reports cannot
select routes, refit bundles, pass readiness, or publish predictions.

```bash
PYTHONPATH=src uv run python scripts/pipeline/build_v4_preseason_feature_reference.py \
  --core-ref-uri artifacts/preview/refs/history/point-in-time-core.json \
  --track strict --as-of 2026-08-17T16:00:00Z \
  --output-ref-uri artifacts/preview/refs/v4/strict-preseason-team.json \
  --manifest-uri artifacts/preview/refs/v4/strict-preseason-team.manifest.json \
  --environment preview

make assemble-model-ready YEAR=2026 ENV=preview AS_OF=2026-08-17T16:00:00Z \
  CORE_REF_URI=... BASELINES_REF_URI=... \
  PRESEASON_FEATURES_REF_URI=artifacts/preview/refs/v4/strict-preseason-team.json \
  FEATURE_TRACK=strict OUTPUT_REF_URI=artifacts/preview/refs/v4/model-ready-strict.json
```

## Required promotion report

Each result-only target/regime report contains MAE, RMSE, calibration bias,
sample count, paired MAE-lift bootstrap intervals, and per-season results. The
predictive gates apply to pooled 2022–2024 OOF rows:

1. Meaningful lift over the frozen baseline.
2. At least 150 out-of-fold games.
3. A positive lower bound on the paired 95% bootstrap MAE-lift interval.
4. Better MAE in at least two of the three selection seasons.
5. No greater than 10% degradation in RMSE or absolute bias.

The locked 2025 test applies the same 10% MAE/RMSE/bias anti-regression guard.
Candidate choice is made before viewing 2025: lowest OOF MAE wins, with blend,
direct Ridge, points-derived Ridge, direct CatBoost, then points-derived
CatBoost as the simplicity order inside a 0.10 MAE tie. A failed challenger
reverts to the prior-only baseline. `high_confidence_eligible` means
predictive validation only; it is not a profitability claim.

Selection and locked validation are deliberately separate commands. Selection
must contain only 2022–2024 rows; its report SHA is a required input to the
guarded 2025 baseline and candidate stages. The resulting final report contains
ten canonical V4 routes (two targets × Games 1–4 plus established).  The
Game 4 tournament includes the unchanged established model as an explicit
candidate; it is not retournamented.

```bash
make generate-game-ordinal \
  STAGE=selection FEATURE_REF_URI=artifacts/preview/features/week0-training-ref.json \
  OUTPUT=/tmp/game-ordinal-selection.csv ENV=preview

make evaluate-game-ordinal \
  STAGE=selection CANDIDATES=/tmp/game-ordinal-selection.csv \
  BLEND_WEIGHTS=/tmp/game-ordinal-selection.blend-weights.json \
  FEATURE_REF_URI=artifacts/preview/features/week0-training-ref.json \
  REPORT_URI=artifacts/preview/models/game-ordinal-selection-v2.json ENV=preview
```

After the selection report is immutable, generate the guarded 2025 baseline,
assemble a new model-ready Gold ref, and run the locked candidate/evaluation
commands with `SELECTION_REPORT_URI` set to that immutable report.

The refit then produces the ten-route bundle (two targets × Games 1–4 plus the
established anchor; V3-era bundles produced an eight-route compatibility
bundle):

```bash
make refit-game-ordinal \
  FEATURE_REF_URI=artifacts/preview/features/week0-training-ref.json \
  REPORT_URI=artifacts/preview/models/game-ordinal-routing-v2.json \
  BUNDLE_ID=week0-2026-v4-strict ENV=preview
```

The refitter substitutes the exact prior-only Ridge baseline for fallback cells
and marks only those routes ineligible for high-confidence presentation.

## Sealed outcome (2026-08-18)

The V4 tournament completed under the
[Week 0 launch contract](../plans/2026-08-18/week0-launch-execution.md):

- **Strict reference shipped `prior_core` only** — every additive preseason
  family (returning production, transfers, recruiting, coaching, roster
  continuity, rankings, talent) lacked pre-kickoff effective-time evidence for
  all required team-seasons; talent remains empty at the provider. This is the
  accepted `prior_only_fallback` launch posture (no further rechecks).
- **Sealed 2022–2024 selection** (design SHA `ae34ddc7…`): 4 of 8 challenger
  routes beat baseline — spread/game_1 direct_catboost (−1.43 MAE) and
  total/game_2–4 blends (−0.5 to −1.5 MAE).
- **Locked 2025:** all 8 challenger routes passed the anti-regression guard
  (spread/game_1 +0.61 MAE, within tolerance).
- **Refit on 2021–2025** produced the ten-route bundle
  `week0-2026-v4-strict-20260818-r2` (config `conf/weekly_bets/v4_2026.yaml`).
- **Week 0 routing:** all 8 opening-slate games route to `game_1` —
  spread/game_1 = direct CatBoost; total/game_1 = prior-quality baseline
  fallback (the failed-challenger case above).
- Research-only 2025 betting simulation on quarantined legacy lines: +17.9
  units combined (+3.1% ROI); no market-dependent promotion gate was treated
  as passed.
