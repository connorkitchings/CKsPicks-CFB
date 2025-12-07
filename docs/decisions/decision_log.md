# Decision Log

**Status**: Active (Post-Reorganization)
**Started**: 2025-12-04
**Legacy Archive**: See [`archive/decision_log_legacy.md`](../../archive/decision_log_legacy.md) for pre-reorganization history

---

## Purpose

This log records all major modeling, architecture, and process decisions made during development. Each entry should include:

- **Date**: When the decision was made
- **Context**: What problem or situation prompted the decision
- **Decision**: What was decided (be specific)
- **Rationale**: Why this was chosen over alternatives
- **Impact**: What changed as a result
- **Artifacts**: Links to code, configs, experiments, or session logs

---

## Template

```markdown
## YYYY-MM-DD: [Decision Title]

- **Context**: [What prompted this decision?]
- **Decision**: [What was decided?]
- **Rationale**: [Why was this chosen?]
  1. Point 1
  2. Point 2
- **Impact**: [What changed?]
- **Artifacts**: [Links to related files, experiments, session logs]
```

---

## Decisions

### 2025-12-06: V2 Baseline Metrics Established

- **Context**: Completed Phase 1 setup. Trained Ridge regression on `minimal_unadjusted_v1` features (raw EPA/SR) for years 2019, 2021-2023, tested on 2024.
- **Decision**: Accept these metrics as the official V2 Benchmark (the "Floor").
- **Results**:
  - **RMSE**: 18.64 points (High, indicates noise in unadjusted stats)
  - **Hit Rate**: 50.6% (721 bets)
  - **ROI**: -3.35% (Below breakeven)
- **Rationale**: 
  - Validates the end-to-end V2 pipeline (Data -> Train -> Evaluate).
  - Confirms that raw stats alone are insufficient for profitability.
  - Sets a clear, beatable target for Phase 2 (Opponent Adjustment).
- **Impact**:
  - Phase 2 experiments must beat -3.35% ROI by +1.0% (target > -2.35%) to be promoted.
- **Artifacts**:
  - Experiment: `v2_baseline/linear`
  - Model: `models/linear.joblib`
  - Run ID: (Local MLflow run)

---

### 2025-12-05: V2 Experimentation Workflow Adoption

- **Context**: Post-reorganization, legacy models archived, need rigorous process to prevent regressions and measure improvements clearly. Previous development was rapid but lacked systematic evaluation.
- **Decision**: Adopt 4-phase V2 experimentation workflow:
  1. **Phase 1**: Baseline Establishment (Ridge regression, minimal features)
  2. **Phase 2**: Feature Engineering & Selection (test features with baseline model)
  3. **Phase 3**: Model Selection (test complex models with best features)
  4. **Phase 4**: Deployment & Monitoring (Champion Model to production)
- **Rationale**:
  1. **Incremental Complexity**: Start simple, add complexity only if justified by performance
  2. **Clear Attribution**: Isolate feature vs model contributions
  3. **Rigorous Gates**: 5-gate promotion system prevents false positives
  4. **Reproducibility**: All experiments tracked in MLflow, documented in decision log
- **Impact**:
  - All future modeling follows this workflow
  - No feature/model promoted without passing gates
  - Baseline becomes official benchmark
- **Artifacts**:
  - Process: [experimentation_workflow.md](../process/experimentation_workflow.md)
  - Framework: [promotion_framework.md](../process/promotion_framework.md)
  - Timeline: [12_week_implementation_plan.md](../process/12_week_implementation_plan.md)

---

### 2025-12-05: Pure V2 Rebuild (No Legacy Fallback)

- **Context**: Legacy models (CatBoost v5, XGBoost v5) archived. Question of whether to keep as "emergency fallback" or commit fully to V2.
- **Decision**: **"Burn the boats"** — Pure V2 only, no safety net from legacy models.
- **Rationale**:
  1. **Forces Commitment**: Prevents shortcuts back to legacy when V2 gets hard
  2. **Clean Slate**: No confusion about which system is "real"
  3. **Trust the Process**: Confidence that V2 rigor will match/exceed legacy performance
  4. **Acceptable Risk**: Worst case is Ridge baseline at breakeven, not catastrophic failure
- **Impact**:
  - Legacy models completely archived (not in production path)
  - If V2 experiments fail, Ridge baseline is the fallback
  - No hybrid system maintaining two parallel workflows
- **Artifacts**:
  - Archived: `legacy/src/models/`, `legacy/conf/experiment/`
  - Decision log entry: This entry

---

### 2025-12-05: Unadjusted Baseline Philosophy

- **Context**: Choice between starting from raw stats vs using opponent-adjusted stats as Phase 1 baseline. Opponent adjustment is known to improve performance, but adds complexity.
- **Decision**: Start from **unadjusted** EPA/SR (`minimal_unadjusted_v1`) as Phase 1 baseline.
- **Rationale**:
  1. **Absolute Floor**: Establishes true minimum performance before any feature engineering
  2. **Proves Value**: Forces us to demonstrate that opponent adjustment improves ROI (+1.0% in Phase 2)
  3. **Scientific Rigor**: Tests assumptions rather than inheriting them
  4. **Simplicity**: 4 features (home/away off/def EPA) is maximally interpretable
- **Impact**:
  - Phase 1 baseline uses raw, season-to-date EPA/SR
  - No opponent adjustment, no recency weighting, no special teams
  - Expected performance: 51-53% hit rate, near breakeven ROI
  - Opponent adjustment tested in Phase 2 as `opponent_adjusted_v1`
- **Artifacts**:
  - Baseline: [docs/modeling/baseline.md](../modeling/baseline.md)
  - Config: `conf/features/minimal_unadjusted_v1.yaml` (to be created)
  - Registry: [feature_registry.md](../project_org/feature_registry.md)

---

### 2025-12-05: Promotion Rigor Framework (5-Gate System)

- **Context**: Need clear, statistical criteria to prevent false positives when promoting features/models. Overfitting to holdout set is a real risk with manual evaluation.
- **Decision**: Implement **5-gate promotion system** with bootstrap testing and walk-forward validation:
  1. **Gate 1**: Performance threshold (Phase 2: +1.0% ROI, Phase 3: +1.5% ROI)
  2. **Gate 2**: Volume threshold (≥100 bets on 2024 holdout)
  3. **Gate 3**: Statistical significance (90-95% confidence via bootstrap)
  4. **Gate 4**: Stability (win 3/4 quarters in walk-forward test)
  5. **Gate 5**: No degradation (secondary metrics <10% worse)
- **Rationale**:
  1. **Prevents Overfitting**: Statistical tests reduce chance of promoting lucky experiments
  2. **Ensures Meaningfulness**: Volume + stability gates ensure real-world applicability
  3. **Protects Quality**: Gate 5 prevents trading ROI for worse predictions
  4. **Reproducible**: Scripted tests remove subjective judgment
- **Impact**:
  - Every feature set and model must pass ALL gates to be promoted
  - Promotion test script required for Phase 2/3
  - Gate 4 can be overridden with documented rationale
- **Artifacts**:
  - Framework: [promotion_framework.md](../process/promotion_framework.md)
  - Script: `scripts/evaluation/test_feature_promotion.py` (to be created Week 5)

---

### 2025-12-05: Manual Workflow (No Automated Alerts)

- **Context**: Monitoring system design question—should rollback be automated with email alerts, or manual with dashboard as decision support?
- **Decision**: **Manual workflow** — User runs all steps (data, train, predict, score) manually and checks monitoring dashboard when convenient. Rollback decisions are manual judgment calls.
- **Rationale**:
  1. **Simplicity**: No need for email servers, cron jobs, automation infrastructure
  2. **User Control**: Betting decisions are manual anyway, fits existing workflow
  3. **Avoid False Alarms**: Automated alerts could trigger unnecessarily on short-term variance
  4. **Dashboard Sufficient**: Streamlit dashboard provides all needed decision support
- **Impact**:
  - No automated email alerts or notifications
  - Dashboard runs on-demand: `streamlit run dashboard/monitoring.py`
  - Rollback is manual process following SOP
  - Alert levels (Green/Yellow/Orange/Red) are informational, not actionable triggers
- **Artifacts**:
  - Dashboard: [monitoring.md](../ops/monitoring.md) (to be implemented Week 11)
  - Rollback: [rollback_sop.md](../ops/rollback_sop.md)

---

### 2025-12-05: Data Quality Before Feature Experiments

- **Context**: Original 12-week plan had data quality in Weeks 11-12 (after experiments). Risk of discovering data issues too late.
- **Decision**: **Move data quality system to Weeks 3-4** (immediately after baseline establishment, before feature experiments).
- **Rationale**:
  1. **Prevent Garbage Experiments**: Must validate data integrity before trusting experiment results
  2. **Early Detection**: Catch API changes, schema drift, outliers before they affect modeling
  3. **Confidence in Results**: Can trust promotion tests if data quality is assured
  4. **Buffer for Fixes**: Weeks 3-4 provide time to fix issues before Phase 2
- **Impact**:
  - Timeline shifted: Weeks 3-4 = Data Quality, Weeks 5-6 = Feature Experiments
  - 3-layer validation system (ingestion, aggregation, features)
  - All years (2019, 2021-2024) must pass validation before experiments
- **Artifacts**:
  - Framework: [data_quality.md](../ops/data_quality.md)
  - Scripts: `scripts/validation/*.py` (to be created Weeks 3-4)
  - Plan: [12_week_implementation_plan.md](../process/12_week_implementation_plan.md)

---

### 2025-12-04: Repository Reorganization

- **Context**: The repository had grown organically with scattered documentation, multiple overlapping doc directories (operations/, project_org/, guides/), and no clear entry point. The decision log itself had 185 entries spanning rapid November 2024 development cycles, making it difficult to find current state.
- **Decision**:
  1. **Create `docs/guide.md`** as the canonical single source of truth for all documentation
  2. **Reorganize docs** into clear buckets:
     - `docs/process/` — How we work (ML workflow, dev standards, AI templates)
     - `docs/modeling/` — What we build (baseline, features, betting policy, evaluation)
     - `docs/ops/` — How we run (weekly pipeline, MLflow, data paths)
     - `docs/planning/` — Where we're going (roadmap, active initiatives)
     - `docs/research/` — Exploratory work (PPR PRDs, prototypes)
     - `docs/archive/` — Historical/obsolete docs
  3. **Create `archive/` at repo root** for unused scripts, configs, and notebooks
  4. **Archive legacy decision log** and start fresh with clearer structure
  5. **Purge stale artifacts** (MLflow runs, old predictions) while preserving 2025 Week 15 predictions
- **Rationale**:
  1. **Single source of truth** reduces cognitive load for developers and AI assistants
  2. **Clear buckets** make it obvious where to find and add documentation
  3. **Fresh decision log** allows us to focus on current state without historical baggage
  4. **Artifact cleanup** removes confusion from old experiments and failed approaches
- **Impact**:
  - All documentation now navigable from `docs/guide.md`
  - Old directories (`operations/`, `project_org/`, `guides/`) removed
  - Decision log reset to focus on post-reorg decisions
  - Artifacts directory cleaned (except Week 15 predictions)
- **Artifacts**:
  - Plan: `docs/repo_cleanup_plan.md`
  - Session: `session_logs/2025-12-04/02.md`
  - Legacy decisions: `archive/decision_log_legacy.md`

---

<!-- New decisions go here, most recent at top -->
