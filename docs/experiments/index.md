# Experiments Index

**Status**: V2 log closed (historical); 2026 selection runs through sealed tournaments  
**Started**: 2025-12-06 (V2) · 2026-08-14 (2026 lineage)  
**Current Champion**: V4 ten-route bundle `week0-2026-v4-strict-20260818-r2` (2026-08-18)

---

## 2026 Model Lineage (Authoritative)

Selection for the 2026 season ran through sealed, result-only tournaments
(2022–2024 temporal OOF → locked 2025 → unchanged refit on 2021–2025), not the
V2 phase workflow. Historical market data is quarantined and never influences
selection or promotion.

| Bundle | Date | Basis | Outcome |
| --- | --- | --- | --- |
| `week0-2026-preview-20260814` (V2 preview) | 2026-08-14 | Display-fallback ten-route preview | First frozen Preview run (`2026w0-a0edb9e72cb1`); later fallback |
| `week0-2026-games-ordinal-v3-20260816-r2` (V3) | 2026-08-16 | Games-ordinal early routes, prediction-only | Rehearsed privately; 2 spread / 7 total lean diffs vs V2; became baseline lineage |
| **`week0-2026-v4-strict-20260818-r2` (V4)** | 2026-08-18 | Strict point-in-time reference, `prior_core` only | 🏆 **Champion** — sealed selection won 4/8 challenger routes (spread/game_1 direct_catboost −1.43 MAE; total/game_2–4 blends −0.5 to −1.5 MAE); locked 2025 passed all 8 routes; production activated (run `2026w0-79ec2aebcb00`) |

Key references: [Early-Season Regimes](../modeling/early_season_regimes.md) ·
[Week 0 Launch Contract](../plans/2026-08-18/week0-launch-execution.md) ·
[Decision Log](../decisions/decision_log.md) (2026-08-16/17/18 entries).

---

## V2 Experiment Log (Historical, Dec 2025)

The V2 4-phase workflow concluded with the Linear + `matchup_v1` champion
(spread +0.78% ROI, totals +6.35% ROI on the 2024 holdout). It is retained
below as a modeling-process reference; the 2026 execution superseded it.

### Spread Target

| Exp ID | Phase | Date       | Model    | Features              | RMSE  | Hit Rate | ROI    | Status          |
| ------ | ----- | ---------- | -------- | --------------------- | ----- | -------- | ------ | --------------- |
| V2-001 | 1     | 2025-12-06 | Ridge    | minimal_unadjusted_v1 | 18.64 | 50.6%    | -3.35% | ✅ Baseline     |
| V2-002 | 2     | 2025-12-07 | Ridge    | opponent_adjusted_v1  | 18.5  | 51.9%    | -0.97% | ✔️ Promoted     |
| V2-003 | 2     | 2025-12-07 | Ridge    | recency_weighted_v1   | 18.82 | 52.65%   | +0.52% | ✔️ Promoted     |
| V2-004 | 2     | 2025-12-07 | Ridge    | interaction_v1        | —     | 52.2%    | -0.26% | ❌ Rejected     |
| V2-005 | 3     | 2025-12-07 | CatBoost | opponent_adjusted_v1  | —     | 51.5%    | -1.76% | ❌ Rejected     |
| V2-006 | 3     | 2025-12-07 | XGBoost  | opponent_adjusted_v1  | —     | 52.0%    | -0.71% | ❌ Rejected     |
| V2-007 | 3     | 2025-12-07 | XGBoost  | (tuned w/ Optuna)     | —     | 51.7%    | -1.23% | ❌ Rejected     |
| V2-008 | 4     | 2025-12-07 | Ensemble | Linear+XGBoost 50/50  | —     | 50.8%    | -3.09% | ❌ Rejected     |
| V2-009 | 4     | 2025-12-07 | Stacking | Linear+XGB meta-LR    | —     | 49.6%    | -5.36% | ❌ Rejected     |
| V2-010 | 2     | 2025-12-08 | Ridge    | alpha sweep (0.1-0.5) | —     | 50-53%   | varies | ❌ No Change    |
| V2-011 | 2     | 2025-12-08 | Ridge    | matchup_v1 (16 feat)  | 18.82 | 52.79%   | +0.78% | 🏆 **Champion** |

### Totals Target

| Exp ID   | Phase | Date       | Model  | Features             | RMSE  | Hit Rate | ROI    | Status          |
| -------- | ----- | ---------- | ------ | -------------------- | ----- | -------- | ------ | --------------- |
| V2-T-001 | 2     | 2025-12-07 | Linear | recency_weighted_v1  | —     | ~54%     | +5.3%  | ✔️ Promoted     |
| V2-T-002 | 2     | 2025-12-08 | Linear | matchup_v1 (16 feat) | 16.83 | 55.7%    | +6.35% | 🏆 **Champion** |

**Status Legend**:

- ✅ **Baseline**: Official benchmark (Phase 1)
- ✔️ **Promoted**: Passed 5-gate promotion, replaced benchmark
- ❌ **Rejected**: Failed promotion gates
- 🏆 **Champion**: Current production model

---

## Promotion History

### Phase 1 Baseline (Dec 6)

- **Exp V2-001**: Ridge + minimal_unadjusted_v1
- **Metrics**: RMSE 18.64, Hit Rate 50.6%, ROI -3.35%
- **Decision**: Established as baseline

### Phase 2 Feature Promotions (Dec 7–8)

- **Exp V2-002**: Ridge + opponent_adjusted_v1 → **PROMOTED** (+2.38% ROI lift)
- **Exp V2-003**: Ridge + recency_weighted_v1 → **PROMOTED** (+0.52% ROI, superseded by matchup_v1)
- **Exp V2-004**: Interaction terms → **REJECTED** (degraded performance)
- **Exp V2-011**: Ridge + matchup_v1 → **PROMOTED TO CHAMPION** (+0.78% spread ROI, +6.35% totals ROI)

### Phase 3 Model Selection (Dec 7)

- **All models REJECTED**: CatBoost, XGBoost, and tuned XGBoost failed to beat linear baseline
- **Key Learning**: Linear model is highly robust; complex models overfit

### Phase 4 Ensembling (Dec 7)

- **V2-008**: Linear+XGBoost ensemble → **REJECTED** (-3.09% ROI)
- **V2-009**: Stacking with meta-learner → **REJECTED** (-5.36% ROI)
- **Key Learning**: Naive averaging and stacking don't improve on single linear model

---

## Usage Guidelines

### Before Running an Experiment

1. **Assign Experiment ID**: Use format `V2-XXX` (sequential)
2. **Define Feature Set**: Create Hydra config in `conf/features/` if new
3. **Register in Feature Registry**: Add row to [`feature_registry.md`](../project_org/feature_registry.md)
4. **Document Phase**: Specify which workflow phase (1, 2, 3, or 4)

### After Running an Experiment

1. **Log to MLflow**: Ensure run logged with proper experiment name
2. **Record Metrics**: Add key metrics (RMSE, Hit Rate, ROI) to table above
3. **Run Promotion Tests**: Use `scripts/evaluation/test_feature_promotion.py`
4. **Update Status**: Mark as Promoted, Rejected, or Champion
5. **Document Decision**: Add entry to [`decision_log.md`](../decisions/decision_log.md)

### Experiment Config Example

```yaml
# conf/experiment/02_test_adjusted_features.yaml
defaults:
  - override /model: linear
  - override /features: opponent_adjusted_v1

experiment:
  name: v2_phase2_adjusted
  phase: 2
  description: "Testing opponent adjustment impact on Ridge baseline"
```

---

## Data Split (Locked)

**Critical Rule**: Never change this split without explicit approval

- **2026 policy (authoritative)**: select with 2022–2024 temporal OOF, lock
  2025 for one anti-regression test, refit the unchanged design on 2021–2025
- **V2 policy (historical)**: test on 2024 (locked holdout); deployed 2025

**Rationale**:

- 2020 excluded due to COVID (shortened season, opt-outs)
- 2019 serves only as prior-quality lineage for early 2021
- No result from the locked test year may influence design selection

---

## Related Documentation

- [V2 Workflow](../process/experimentation_workflow.md) — 4-phase process
- [Promotion Framework](../process/promotion_framework.md) — 5-gate criteria
- [Feature Registry](../project_org/feature_registry.md) — Feature group tracking
- [Decision Log](../decisions/decision_log.md) — All promotion decisions
- [Legacy Experiments](../archive/experiments_legacy.md) — Pre-V2 history

---

**Last Updated**: 2026-08-19  
**Next**: 2026 season game-week operations; post-season tournament review
