# V2 Experiments Index

**Status**: Active (Post-V2 Reorganization)  
**Started**: 2025-12-XX (Week 1)  
**Legacy Archive**: See [`archive/experiments_legacy.md`](../archive/experiments_legacy.md) for pre-V2 experiments

---

## Purpose

Track all V2 modeling experiments (Phases 1-4). Each experiment must align with a feature group in [`feature_registry.md`](../project_org/feature_registry.md) and follow the [V2 workflow](../process/experimentation_workflow.md).

---

## Experiment Log

| Exp ID | Phase | Date       | Model    | Features              | Metrics (2024 Holdout)             | Promotion   | Notes                              |
| ------ | ----- | ---------- | -------- | --------------------- | ---------------------------------- | ----------- | ---------------------------------- |
| V2-001 | 1     | 2025-12-XX | Ridge    | minimal_unadjusted_v1 | RMSE: XX.X, Hit: XX.X%, ROI: XX.X% | ✅ Baseline | Phase 1 baseline established       |
| V2-002 | 2     | 2025-01-XX | Ridge    | opponent_adjusted_v1  | RMSE: XX.X, Hit: XX.X%, ROI: +X.X% | 🧪 Testing  | Testing opponent adjustment impact |
| V2-003 | 2     | 2025-01-XX | Ridge    | recency_weighted_v1   | RMSE: XX.X, Hit: XX.X%, ROI: +X.X% | 🧪 Testing  | Testing recency weighting impact   |
| V2-004 | 2     | 2025-01-XX | Ridge    | combined_v1           | RMSE: XX.X, Hit: XX.X%, ROI: +X.X% | 🧪 Testing  | Testing full legacy feature parity |
| V2-005 | 3     | 2025-02-XX | CatBoost | [promoted_features]   | RMSE: XX.X, Hit: XX.X%, ROI: +X.X% | TBD         | Phase 3: Model selection           |
| V2-006 | 3     | 2025-02-XX | XGBoost  | [promoted_features]   | RMSE: XX.X, Hit: XX.X%, ROI: +X.X% | TBD         | Phase 3: Model selection           |

**Status Legend**:

- ✅ **Baseline**: Official benchmark (Phase 1)
- 🧪 **Testing**: Candidate under evaluation
- ✔️ **Promoted**: Passed 5-gate promotion, now benchmark
- ❌ **Rejected**: Failed promotion gates
- 🏆 **Champion**: Production model (Phase 4)

---

## Promotion History

### Phase 1 Baseline

- **Exp V2-001**: Ridge + minimal_unadjusted_v1
- **Decision**: Established as baseline (no promotion test needed)
- **Date**: 2025-12-XX

### Phase 2 Feature Promotions

_(To be filled as experiments complete)_

### Phase 3 Model Promotions

_(To be filled as experiments complete)_

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

**Last Updated**: 2025-12-05  
**Next Experiment**: V2-001 (Baseline Establishment, Week 2)
