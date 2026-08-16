# 2026 Week 0 and Early-Season Evaluation Contract

The canonical production design evaluates spread and total independently for a
team's upcoming `game_1`, `game_2`, `game_3`, and `established` route. The
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

For games one through three, the tournament compares direct Ridge, direct
CatBoost, points-derived Ridge, and points-derived CatBoost. Team-side current
metrics are empirically shrunk to prior values using that team's own play,
drive, or completed-game exposure. The reviewed prior-strength grids are plays
`{50,100,200,400}`, drives `{5,10,20,40}`, and games `{1,2,4,8}`.

Historical quote data is optional betting research. It is never a model input
and it is not required to select, refit, or activate a Games 1–3 prediction
route. When quote data is later used for betting evaluation, it must be
timestamped; untimestamped legacy CFBD references remain ineligible.

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
eight canonical v3 routes (two targets × Games 1–3 plus established), not the
legacy ten completed-game routes.

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

The compatibility refit then produces an eight-route bundle:

```bash
make refit-game-ordinal \
  FEATURE_REF_URI=artifacts/preview/features/week0-training-ref.json \
  REPORT_URI=artifacts/preview/models/game-ordinal-routing-v2.json \
  BUNDLE_ID=week0-2026-v3-preview ENV=preview
```

The refitter substitutes the exact prior-only Ridge baseline for fallback cells
and marks only those routes ineligible for high-confidence presentation.
