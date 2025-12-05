# 12-Week V2 Implementation Plan

**Start Date**: 2025-12-09 (Week 1)  
**End Date**: 2026-02-27 (Week 12)  
**Goal**: Operationalize V2 workflow from Ridge baseline to Champion Model

---

## Timeline Overview

```
Weeks 1-2:   Foundation & Baseline
Weeks 3-4:   Data Quality System
Weeks 5-6:   Feature Experiments (Phase 2)
Weeks 7-10:  Model Selection (Phase 3)
Weeks 11-12: Monitoring Dashboard & Final Polish
```

---

## Week-by-Week Plan

### **Week 1: Environment & Data Generation** (Dec 9-15)

**Goal**: Get data pipeline working, set up environment

**Tasks**:

- [ ] Verify `CFB_MODEL_DATA_ROOT` is set correctly
- [ ] Generate processed data for all years:
  ```bash
  for year in 2019 2021 2022 2023 2024; do
      uv run python scripts/pipeline/run_pipeline_generic.py --year $year
  done
  ```
- [ ] Verify data quality (no missing files, schemas match)
- [ ] Confirm MLflow tracking URI configured

**Deliverables**:

- ✅ All processed data available (`byplay`, `drives`, `team_game`, `team_season`, `team_season_adj_iterations`)
- ✅ Data validation passed
- ✅ MLflow accessible

**Time Estimate**: 8-10 hours (mostly waiting for data generation)

---

### **Week 2: Baseline Establishment (Phase 1)** (Dec 16-22)

**Goal**: Train Ridge baseline, establish benchmark

**Tasks**:

- [ ] Create `conf/features/minimal_unadjusted_v1.yaml`
- [ ] Update `src/features/v1_pipeline.py` to load from `team_season` (not `team_season_adj`)
- [ ] Train Ridge baseline:
  ```bash
  PYTHONPATH=. uv run python src/train.py \
      model=linear \
      features=minimal_unadjusted_v1 \
      training.train_years=[2019,2021,2022,2023] \
      training.test_year=2024
  ```
- [ ] Log to MLflow experiment `v2_baseline`
- [ ] Document metrics in decision log
- [ ] Save baseline results for comparison

**Deliverables**:

- ✅ Ridge baseline trained successfully
- ✅ Metrics documented (RMSE, Hit Rate, ROI on 2024)
- ✅ MLflow experiment created
- ✅ Baseline becomes official benchmark

**Expected Metrics**:

- RMSE: 12-14 points
- Hit Rate: 51-53%
- ROI: -2% to +2%

**Time Estimate**: 4-6 hours

**📌 Milestone 1**: V2 Baseline Established ✅

---

### **Week 3: Data Quality Framework** (Dec 23-29)

**Goal**: Build validation checks for data integrity

**Tasks**:

- [ ] Create `scripts/validation/validate_ingestion.py`:
  - Schema validation (required columns present)
  - Null checks (critical fields non-null)
  - Range checks (e.g., EPA in [-10, 10])
- [ ] Create `scripts/validation/validate_aggregation.py`:
  - Distribution checks (means within historical range)
  - Outlier detection (flag >3σ anomalies)
  - Completeness checks (all teams present)
- [ ] Create `scripts/validation/validate_features.py`:
  - Feature drift detection (KS tests vs 2024 baseline)
  - Correlation checks (features not perfectly correlated)
- [ ] Document in `docs/ops/data_quality.md`

**Deliverables**:

- ✅ Validation scripts operational
- ✅ Documentation complete
- ✅ Can run full pipeline with validation gates

**Time Estimate**: 6-8 hours

---

### **Week 4: Data Quality Integration** (Dec 30-Jan 5)

**Goal**: Integrate validation into pipeline, test on all years

**Tasks**:

- [ ] Add validation calls to `scripts/pipeline/run_pipeline_generic.py`
- [ ] Re-run pipeline for all years with validation
- [ ] Fix any data quality issues discovered
- [ ] Create validation report template for future runs

**Deliverables**:

- ✅ Pipeline validates data at each stage
- ✅ All years pass validation
- ✅ Validation report generated

**Time Estimate**: 4-6 hours

**📌 Milestone 2**: Data Quality Assured ✅

---

### **Week 5: Feature Engineering Prep** (Jan 6-12)

**Goal**: Define Phase 2 feature candidates, implement promotion testing framework

**Tasks**:

- [ ] Create `scripts/evaluation/test_feature_promotion.py`:
  - Implement 5-gate promotion testing
  - Bootstrap resampling (1000 iterations)
  - Walk-forward quarterly validation
  - Generate promotion report
- [ ] Define feature candidates:
  - `opponent_adjusted_v1.yaml` (4-iteration adjustment)
  - `recency_weighted_v1.yaml` (last-3-game weighting)
  - `combined_v1.yaml` (both together)
- [ ] Create Hydra configs for each

**Deliverables**:

- ✅ Promotion testing framework operational
- ✅ 3 feature configs ready
- ✅ Can test against baseline programmatically

**Time Estimate**: 6-8 hours

---

### **Week 6: Feature Experiments (Phase 2)** (Jan 13-19)

**Goal**: Run feature experiments, promote winner

**Tasks**:

- [ ] **Experiment 01**: Ridge + opponent_adjusted_v1
- [ ] **Experiment 02**: Ridge + recency_weighted_v1
- [ ] **Experiment 03**: Ridge + combined_v1
- [ ] Run 5-gate promotion tests for each
- [ ] Select best feature set (if any pass gates)
- [ ] Update feature registry
- [ ] Document decision in decision log

**Promotion Gates**:

1. ROI lift ≥ +1.0%
2. Volume ≥ 100 bets
3. Bootstrap confidence > 90%
4. Win 3/4 quarters
5. No degradation >10%

**Deliverables**:

- ✅ 3 experiments logged in MLflow
- ✅ Best feature set promoted (or baseline remains if none pass)
- ✅ Benchmark updated

**Time Estimate**: 8-10 hours

**📌 Milestone 3**: Phase 2 Complete (Features) ✅

---

### **Week 7: Model Selection Prep (Phase 3)** (Jan 20-26)

**Goal**: Set up CatBoost and XGBoost, prepare for training

**Tasks**:

- [ ] Create `conf/model/catboost_v1.yaml`
- [ ] Create `conf/model/xgboost_v1.yaml`
- [ ] Create `src/models/v2_catboost.py` wrapper
- [ ] Create `src/models/v2_xgboost.py` wrapper
- [ ] Test on small dataset (verify working)

**Deliverables**:

- ✅ CatBoost and XGBoost configs ready
- ✅ Model wrappers working
- ✅ Can train on promoted feature set

**Time Estimate**: 4-6 hours

---

### **Week 8: Model Experiments Part 1** (Jan 27-Feb 2)

**Goal**: Train CatBoost, test for promotion

**Tasks**:

- [ ] **Experiment 04**: CatBoost + promoted_features
- [ ] Hyperparameter grid search (or use sensible defaults)
- [ ] Run 5-gate promotion tests (stricter: 95% confidence, +1.5% ROI)
- [ ] Document results

**Deliverables**:

- ✅ CatBoost experiment logged
- ✅ Promotion test results
- ✅ Decision: promote or keep Ridge

**Time Estimate**: 6-8 hours (training time)

---

### **Week 9: Model Experiments Part 2** (Feb 3-9)

**Goal**: Train XGBoost, test for promotion

**Tasks**:

- [ ] **Experiment 05**: XGBoost + promoted_features
- [ ] Hyperparameter grid search (or use sensible defaults)
- [ ] Run 5-gate promotion tests
- [ ] Document results

**Deliverables**:

- ✅ XGBoost experiment logged
- ✅ Promotion test results
- ✅ Decision: promote or keep previous Champion

**Time Estimate**: 6-8 hours (training time)

---

### **Week 10: Champion Model Selection** (Feb 10-16)

**Goal**: Select Champion Model, register for deployment

**Tasks**:

- [ ] Compare all candidates:
  - Ridge + baseline
  - Ridge + promoted_features
  - CatBoost + promoted_features (if passed)
  - XGBoost + promoted_features (if passed)
- [ ] Select Champion based on ROI and promotion gates
- [ ] Register to MLflow Model Registry
- [ ] Document decision in decision log
- [ ] **If no model beats Ridge**: Ridge remains Champion

**Deliverables**:

- ✅ Champion Model selected and registered
- ✅ Ready for Phase 4 (Deployment)

**Time Estimate**: 2-4 hours

**📌 Milestone 4**: Phase 3 Complete (Models) ✅

---

### **Week 11: Monitoring Dashboard** (Feb 17-23)

**Goal**: Build Streamlit dashboard for ongoing monitoring

**Tasks**:

- [ ] Create `dashboard/monitoring.py`:
  - Load scored bets from CSV
  - Calculate rolling 4-week ROI
  - Display alert status (Green/Yellow/Orange/Red)
  - Show trend charts (12 weeks)
  - Feature drift analysis (KS tests)
- [ ] Create `docs/ops/monitoring.md` guide
- [ ] Test on legacy 2025 bets (Weeks 2-14)

**Deliverables**:

- ✅ Dashboard runs locally: `streamlit run dashboard/monitoring.py`
- ✅ Documentation complete
- ✅ Can monitor Champion Model performance

**Time Estimate**: 6-8 hours

---

### **Week 12: Final Polish & Documentation** (Feb 24-27)

**Goal**: Complete all documentation, prepare for production

**Tasks**:

- [ ] Update `docs/guide.md` with full V2 workflow
- [ ] Create `docs/ops/rollback_sop.md`
- [ ] Update `docs/experiments/index.md` with V2 experiments
- [ ] Update `README.md` with V2 overview
- [ ] Link validation across all docs
- [ ] Final decision log entries
- [ ] Create walkthrough.md showing end-to-end flow

**Deliverables**:

- ✅ All documentation up-to-date
- ✅ V2 workflow fully documented
- ✅ Ready for 2026 season

**Time Estimate**: 4-6 hours

**📌 Milestone 5**: V2 Workflow Operational ✅

---

## Success Criteria

By Feb 27, 2026:

1. ✅ **Ridge Baseline** trained and benchmarked
2. ✅ **Data Quality** system operational
3. ✅ **Feature Engineering** Phase 2 complete (1+ feature set tested)
4. ✅ **Model Selection** Phase 3 complete (Champion selected)
5. ✅ **Monitoring Dashboard** operational
6. ✅ **Documentation** 100% aligned with V2
7. ✅ **No Legacy Code** in production path

**Acceptance Test**: Can you run the entire workflow (data → train → predict → score → monitor) using only V2 code and process?

---

## Risk Mitigation

### Risk: Data generation failures

**Mitigation**: Test on 1 year first, then scale to all years

### Risk: No features/models pass promotion gates

**Mitigation**: Ridge baseline remains Champion (acceptable outcome)

### Risk: Timeline slippage

**Mitigation**: Prioritize Phase 1-2 over Phase 3-4; adjust timeline as needed

### Risk: Unexpected data quality issues

**Mitigation**: Week 3-4 buffer for fixing issues before experiments

---

## Checkpoints

**End of Week 2**: Baseline established → Continue or reassess?  
**End of Week 6**: Phase 2 complete → Champion features identified?  
**End of Week 10**: Phase 3 complete → Champion model selected?  
**End of Week 12**: V2 operational → Ready for production?

---

**Last Updated**: 2025-12-05  
**Owner**: V2 Implementation Team
