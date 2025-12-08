# V2 Experiments Index

**Status**: Active  
**Started**: 2025-12-06  
**Current Champion**: Linear + `recency_weighted_v1` (Spread +0.52% ROI, Totals +5.3% ROI)

---

## Purpose

Track all V2 modeling experiments (Phases 1-4). Each experiment must align with a feature group in [`feature_registry.md`](../project_org/feature_registry.md) and follow the [V2 workflow](../process/experimentation_workflow.md).

---

## Experiment Log

### Spread Target

| Exp ID | Phase | Date       | Model    | Features              | RMSE  | Hit Rate | ROI    | Status          |
| ------ | ----- | ---------- | -------- | --------------------- | ----- | -------- | ------ | --------------- |
| V2-001 | 1     | 2025-12-06 | Ridge    | minimal_unadjusted_v1 | 18.64 | 50.6%    | -3.35% | ✅ Baseline     |
| V2-002 | 2     | 2025-12-07 | Ridge    | opponent_adjusted_v1  | 18.5  | 51.9%    | -0.97% | ✔️ Promoted     |
| V2-003 | 2     | 2025-12-07 | Ridge    | recency_weighted_v1   | 18.82 | 52.65%   | +0.52% | 🏆 **Champion** |
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

### Phase 2 Feature Promotions (Dec 7)

- **Exp V2-002**: Ridge + opponent_adjusted_v1 → **PROMOTED** (+2.38% ROI lift)
- **Exp V2-003**: Ridge + recency_weighted_v1 → **PROMOTED TO CHAMPION** (+0.52% ROI)
- **Exp V2-004**: Interaction terms → **REJECTED** (degraded performance)

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

- **Training**: 2019, 2021, 2022, 2023 (exclude 2020)
- **Test (Holdout)**: 2024 (locked for all V2 experiments)
- **Deployment**: 2025 (live production)

**Rationale**:

- 2020 excluded due to COVID (shortened season, opt-outs)
- 2024 provides stable, recent holdout
- 2025 is current live season

---

## Related Documentation

- [V2 Workflow](../process/experimentation_workflow.md) — 4-phase process
- [Promotion Framework](../process/promotion_framework.md) — 5-gate criteria
- [Feature Registry](../project_org/feature_registry.md) — Feature group tracking
- [Decision Log](../decisions/decision_log.md) — All promotion decisions
- [Legacy Experiments](../archive/experiments_legacy.md) — Pre-V2 history

---

**Last Updated**: 2025-12-08  
**Next Experiment**: Further feature engineering (matchup-specific, alpha tuning) or CFP deployment
