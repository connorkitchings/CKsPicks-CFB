# Rollback Standard Operating Procedure (SOP)

**Purpose**: Guide for reverting to a previous Champion Model when performance degrades  
**Trigger**: Manual decision after reviewing monitoring dashboard  
**Status**: Active

---

## When to Rollback

### Rollback Recommended If:

1. **🔴 RED Status for 2+ Weeks**:

   - Dashboard shows critical thresholds breached
   - ROI dropped >5% below test
   - Hit rate <48% (hard floor)

2. **Personal Judgment**:
   - You review dashboard and lose confidence in model
   - Predictions seem off intuitively
   - Better safe than sorry

### Rollback NOT Needed If:

- 🟡 **YELLOW** status (1 warning) — Just monitor
- Short-term variance (1 bad week) — Wait for trend
- Overall still profitable — Keep running

**Philosophy**: Manual process = your judgment call. Trust the data but also trust your gut.

---

## Rollback Procedure

### Phase 1: Freeze Current Model (Immediate)

**Step 1**: Stop using current Champion for new predictions

```bash
# Don't run generate_weekly_bets.py until rollback complete
# If already running, let it finish but don't deploy picks
```

**Step 2**: Document the decision

Create entry in `docs/decisions/decision_log.md`:

```markdown
## 2025-XX-XX: Rollback to Previous Champion

- **Context**: Current model (champion_v2) underperforming
  - ROI last 4 weeks: X% (test was Y%)
  - Hit rate: X% (below threshold)
  - Dashboard status: 🔴 RED
- **Decision**: Rollback to previous Champion (champion_v1)
- **Rationale**: Metrics breached critical thresholds for 2+ weeks
- **Impact**: Resume using v1 model for Week XX predictions
```

---

### Phase 2: Load Previous Champion (Within 24 Hours)

**Step 3**: Identify previous Champion in MLflow

```bash
# List registered models
uv run python -c "
import mlflow
mlflow.set_tracking_uri('file://./artifacts/mlruns')
client = mlflow.MlflowClient()

models = client.search_registered_models()
for model in models:
    versions = client.search_model_versions(f'name=\"{model.name}\"')
    for v in versions:
        print(f'{model.name} v{v.version}: {v.tags}')
"

# Look for previous version with 'production' tag or highest version number - 1
```

**Step 4**: Load previous model artifact

```python
import mlflow

# Example: Load spread_ridge_v1 (previous Champion)
model_uri = "models:/spread_ridge/1"  # Version 1
model = mlflow.sklearn.load_model(model_uri)

# Save to production
import joblib
joblib.dump(model, "artifacts/models/production/champion_current/model.joblib")
```

**Step 5**: Verify model loaded correctly

```bash
# Test the Champion Model
uv run python -c "
import joblib
import pandas as pd

model = joblib.load('artifacts/models/production/champion_current/model.joblib')
dummy_data = pd.DataFrame({
    'home_off_epa_pp': [0.2],
    'home_def_epa_pp': [0.1],
    'away_off_epa_pp': [0.15],
    'away_def_epa_pp': [0.12]
})
prediction = model.predict(dummy_data)
print(f'Test prediction: {prediction[0]:.2f}')
"
```

---

### Phase 3: Validate on Recent Data (Within 48 Hours)

**Step 6**: Re-run predictions on last 2-3 weeks

```bash
# Example: Re-predict Week 14 using rollback model
uv run python scripts/prediction/generate_weekly_bets.py --week 14 --year 2025

# Compare to original predictions
diff data/production/predictions/2025/CFB_week14_bets_NEW.csv \
     data/production/predictions/2025/CFB_week14_bets_ORIGINAL.csv
```

**Step 7**: Check if predictions are different

- If identical: Model didn't actually change (rollback unnecessary)
- If different: Rollback working as expected

**Step 8**: Manually score rollback predictions (if old week completed)

```bash
# If week already played, score the rollback predictions
uv run python scripts/scoring/score_weekly_bets.py \
    --predictions data/production/predictions/2025/CFB_week14_bets_NEW.csv \
    --output data/production/scored/2025/CFB_week14_rollback_scored.csv
```

Compare:

- Current model ROI: X%
- Rollback model ROI: Y%

If rollback model performs better: **Proceed**  
If rollback model also bad: **Emergency protocol** (see below)

---

### Phase 4: Resume Operations (After Validation)

**Step 9**: Generate picks for upcoming week using rollback model

```bash
uv run python scripts/prediction/generate_weekly_bets.py --week 15 --year 2025
```

**Step 10**: Deploy picks as normal

- Review `data/production/predictions/2025/CFB_week15_bets.csv`
- Place bets manually
- Continue with standard weekly workflow

**Step 11**: Update monitoring dashboard

- Add note: "Rolled back to v1 on 2025-XX-XX"
- Continue tracking with dashboard
- If rollback model also struggles → Emergency protocol

---

## Emergency Protocol (Both Models Failed)

### Situation: Current AND Previous Champion both failing

**Symptoms**:

- Rollback model also shows ROI <-5%
- Previous model also has hit rate <48%
- Both models failing validation

**Actions**:

1. **Halt All Automated Betting**:

   - Don't generate new picks
   - Don't place new bets

2. **Root Cause Analysis**:

   - [ ] Check data source — Has CFBD API changed?
   - [ ] Check schema — Are features still correct?
   - [ ] Check external factors — New rules? Playoff format change?
   - [ ] Check betting lines — Are they still from same source?

3. **Manual Review**:

   - Inspect recent games manually
   - Look for patterns (all home teams? All favorites?)
   - Compare predictions to eye test

4. **Decision Options**:

   **Option A**: Data issue found → Fix and re-validate

   ```bash
   # Fix data pipeline
   # Re-run aggregation
   # Re-train both models
   # Test on last 4 weeks
   ```

   **Option B**: External factor (e.g., rule change) → Retrain on recent data

   ```bash
   # Include 2025 data in training
   # Retrain from scratch
   # Careful: small sample size risk
   ```

   **Option C**: Models genuinely broken → Pause season

   - Document findings
   - Plan off-season rebuild
   - Resume next year with V2 workflow lessons

---

## Rollback Event Log Template

**Location**: `session_logs/YYYY-MM-DD/rollback_event.md`

```markdown
# Rollback Event Log

**Date**: YYYY-MM-DD  
**Triggered By**: [🔴 RED status | Manual judgment | Hit rate collapse]  
**Current Model**: spread_catboost_v2  
**Rollback Model**: spread_ridge_v1

## Metrics Snapshot

| Metric   | Test (2024) | Current (Last 4 Weeks) | Rollback (Last 4 Weeks) |
| -------- | ----------- | ---------------------- | ----------------------- |
| ROI      | 5.2%        | 0.8%                   | 3.5%                    |
| Hit Rate | 52.2%       | 48.1%                  | 50.8%                   |
| Volume   | 15/week     | 12/week                | 14/week                 |

## Investigation Findings

[What was discovered? Data issue? Model drift? Seasonality?]

## Decision

- [x] Option: Rollback to previous Champion (v1)
- [ ] Option: Emergency protocol (halt betting)

## Actions Taken

1. [Timestamp] Froze current model
2. [Timestamp] Loaded previous model from MLflow
3. [Timestamp] Validated on Week 14 data
4. [Timestamp] Rollback model showed better ROI (+2.7% vs current)
5. [Timestamp] Generated Week 15 picks with rollback model
6. [Timestamp] Resumed operations

## Lessons Learned

[What did we learn? How can we prevent this in the future?]

## Follow-Up

- [ ] Monitor rollback model for next 4 weeks
- [ ] Investigate why current model failed
- [ ] Consider retraining during off-season
```

---

## Prevention Strategies

**How to avoid needing rollbacks**:

1. **Rigorous Promotion** — Use 5-gate system religiously
2. **Data Quality Checks** — Validate data at every pipeline stage
3. **Quarterly Reviews** — Don't wait for dashboard to turn red
4. **Walk-Forward Testing** — Test on recent weeks before deployment
5. **Conservative Thresholds** — Better to miss some bets than make bad ones

---

## FAQs

**Q**: How do I know which version is the "previous" Champion?  
**A**: Check MLflow model registry tags or decision log for last promotion date.

**Q**: Can I rollback to a model from 2+ versions ago?  
**A**: Yes, but prefer most recent Champion first. If that also fails, try older.

**Q**: What if I already placed bets with the bad model?  
**A**: Too late for this week. Just rollback for next week's picks.

**Q**: Should I re-run the promotion tests on the rollback model?  
**A**: Optional. If you have time, yes (validation is good). If urgent, trust the original promotion.

---

## Related Documentation

- [Monitoring Dashboard](./monitoring.md) — How to check if rollback needed
- [Decision Log](../decisions/decision_log.md) — Document all rollback decisions
- [MLflow Guide](./mlflow_mcp.md) — How to load models from registry

---

**Last Updated**: 2025-12-05  
**Owner**: V2 Operations Team
