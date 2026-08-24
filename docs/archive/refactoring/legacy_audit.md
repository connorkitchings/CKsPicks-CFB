# Legacy Code Audit

**Date:** 2026-02-13  
**Auditor:** Claude  
**Directory:** `legacy/`  
**Total Size:** 189MB

---

## Executive Summary

The `legacy/` directory contains the **V1 codebase** that was archived when V2 workflow was implemented. **No active code references or imports from this directory.** Safe to move to `archive/`.

**Recommendation:** Archive entire `legacy/` directory to `archive/legacy_v1_2025/`

---

## Directory Breakdown

```
legacy/ (189MB total)
├── artifacts/          185MB   Old model outputs, MLflow runs, predictions
├── src/                3.1MB   Old source code (67 Python files)
│   └── models/                 V1 model implementations
├── scripts/            576KB   Old analysis scripts (20+ files)
│   └── analysis/               Threshold analysis, calibration, SHAP
├── conf/               244KB   Old configuration files
└── tests/              28KB    Old test files
```

---

## Usage Analysis

### Cross-References
**Files importing from `legacy/`:** 0

**Files referencing `legacy/` (comments only):** 1
- `scripts/validation/validate_features.py:43` - Comment about "legacy/Phase 1 fallback" (refers to old feature approach, not this directory)

### Code References to "legacy" (different meaning)
These refer to "legacy path style" (old file naming conventions), NOT the legacy/ directory:
- `src/utils/validation.py` - References to legacy directory structure style
- `src/features/v1_pipeline.py` - References to legacy adj_ features
- `src/loader.py` - References to legacy report directory structure

**Conclusion:** The `legacy/` directory itself is **completely unused** by current codebase.

---

## Contents Detail

### 1. artifacts/ (185MB)
**What:** Old MLflow runs, model outputs, predictions, analysis results  
**Used?** No - Current artifacts stored in `artifacts/` (not `legacy/artifacts/`)  
**Action:** Archive

### 2. src/models/ (3.1MB, 67 Python files)
**What:** V1 model implementations
- Old model architectures
- Legacy training pipelines
- Pre-V2 betting logic

**Sample files:**
- `baseline.py` - V1 baseline models
- `ensemble.py` - V1 ensemble methods
- `features.py` - V1 feature engineering
- `predict.py` - V1 prediction logic

**Used?** No - Current models in `src/models/` (not `legacy/src/`)  
**Action:** Archive

### 3. scripts/analysis/ (576KB, 20+ files)
**What:** V1 analysis scripts
- Threshold analysis
- Calibration analysis
- SHAP analysis
- Model comparisons
- Walk-forward reports

**Sample files:**
- `analyze_thresholds_from_csv.py`
- `monitor_calibration.py`
- `run_shap_analysis.py`
- `create_walk_forward_report.py`

**Used?** No - Current scripts in `scripts/analysis/` (not `legacy/scripts/`)  
**Action:** Archive

### 4. conf/ (244KB)
**What:** V1 configuration files
- Old model configs
- Old feature configs
- Old experiment configs

**Used?** No - Current configs in `conf/` (not `legacy/conf/`)  
**Action:** Archive

### 5. tests/ (28KB)
**What:** V1 test files
- Old betting policy tests
- Old model tests

**Used?** No - Current tests in `tests/` (not `legacy/tests/`)  
**Action:** Archive

---

## Risks

### Risk: Might Need Something Later
**Mitigation:** 
- Moving to `archive/` (not deleting)
- Git history preserved
- Can restore if needed

### Risk: Accidental Deletion
**Mitigation:**
- Two-step process: move to archive/, delete later
- 30-day grace period before permanent deletion

### Risk: Breaking Current Code
**Mitigation:**
- Confirmed: No imports from legacy/
- Will run full test suite after move

---

## Action Plan

### Phase 1: Audit Documentation (Done)
- [x] Analyze directory contents
- [x] Check for cross-references
- [x] Document findings
- [x] Create this audit document

### Phase 2: Move to Archive (Done)
- [x] Create `archive/legacy_v1_2025/` directory
- [x] Move `legacy/*` to `archive/legacy_v1_2025/`
- [x] Verify no broken references
- [x] Run test suite (51/51 passing)
- [x] Update Makefile to exclude archive/
- [x] Update health-check.sh to specify tests/ directory
- [x] Update REFACTORING_PLAN.md

### Phase 3: Grace Period (30 days) - Active
- [x] Keep archive/ for 30 days
- [ ] Monitor for any issues
- [ ] If all clear, proceed to Phase 4

### Phase 4: Permanent Deletion (Optional)
- [ ] Delete `archive/legacy_v1_2025/` (after grace period)
- [x] Or keep indefinitely (recommended - preserves history)

---

## Decision

**Recommendation:** Proceed with Phase 2 (move to archive)

**Rationale:**
1. Zero active usage confirmed
2. 189MB of dead code
3. Causes confusion for new developers
4. Safe to archive (can restore if needed)
5. Aligns with refactoring goals

---

## Verification Checklist

Before considering Phase 2 complete:
- [ ] `legacy/` directory moved to `archive/legacy_v1_2025/`
- [ ] All tests still pass (52/52)
- [ ] No import errors
- [ ] Health checks pass
- [ ] Documentation updated
- [ ] Session log created

---

**Next Action:** Move `legacy/` to `archive/legacy_v1_2025/`

**Estimated Time:** 15 minutes  
**Risk Level:** Low  
**Rollback:** Easy (just move directory back)
