# 2026 Week 0 and Early-Season Evaluation Contract

The production design evaluates spread and total independently for each of `preseason`, `one_game`, `two_games`, `three_games`, and `established`. Week 0 is a live public week and routes every matchup through the zero-game model.

Model features must be reproducible before kickoff and cannot include spreads, totals, moneylines, or other bookmaker values. Market data enters only after prediction for edge, grading, ROI, and drawdown calculations.

## Frozen chronology and lineage

- Selection folds: train 2021/test 2022, train 2021–2022/test 2023, and train 2021–2023/test 2024.
- Locked test: train 2021–2024 and evaluate 2025 once after the design is frozen.
- Final 2026 refit: the unchanged design trains on 2021–2025.
- 2019 is not a labeled season; it is allowed only as the last normal prior-quality source for early 2021.
- 2020 is excluded from labeled rows, features, lineage, tuning, testing, and refitting.

For one through three games, the tournament compares direct hybrid Ridge, direct hybrid CatBoost, and a preseason/current prediction blend. Blend weights are selected separately for spread and total from 2022–2024 OOF predictions and satisfy `w0 = 1 >= w1 >= w2 >= w3 >= w4 = 0`.

## Required promotion report

Each target/regime report contains MAE, RMSE, calibration bias, hit rate, ROI, graded volume, 95% bootstrap intervals, maximum drawdown, per-season results, and transition diagnostics. The five gates apply to pooled 2022–2024 OOF rows:

1. Meaningful lift over the frozen baseline.
2. At least 100 graded out-of-fold bets.
3. A 95% bootstrap confidence interval supporting the lift.
4. Temporal stability across folds and the locked year.
5. No greater than 10% degradation in MAE, calibration, volume, or drawdown.

The locked 2025 test applies the 10% anti-regression guard but does not independently require 100 bets. Candidate choice is made before viewing 2025: lowest OOF MAE wins, with direct Ridge, blend, then direct CatBoost as the simplicity order inside a 0.10 MAE tie. A failed cell remains visible but `high_confidence_eligible=false`.

Given one immutable CSV of out-of-fold predictions, freeze the ten-cell report and routing manifest with:

```bash
PYTHONPATH=.:src uv run python scripts/pipeline/evaluate_regimes.py \
  --oof-csv /explicit/path/early-season-oof.csv \
  --blend-weights-json /explicit/path/early-season-oof.weights.json \
  --output-uri artifacts/production/models/regime-routing-v1.json
```

The command fails if any target/regime cell is absent, if 2025 affected selection, or if 2019/2020 appear as labeled data or forbidden lineage.

After the routing report is immutable, refit its unchanged design and publish the
checksummed ten-route bundle:

```bash
make refit-week0-bundle \
  FEATURE_REF_URI=artifacts/preview/features/week0-training-ref.json \
  REPORT_URI=artifacts/preview/models/regime-routing-v1.json \
  BUNDLE_ID=week0-2026-v1 ENV=preview
```

The refitter substitutes direct Ridge only for `display_fallback` cells and marks
those routes ineligible for high-confidence presentation.
