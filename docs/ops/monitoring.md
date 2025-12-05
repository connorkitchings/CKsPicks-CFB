# Monitoring Dashboard

**Tool**: Streamlit  
**Location**: `dashboard/monitoring.py`  
**Update Frequency**: Manual (check when convenient)  
**Status**: To be implemented (Week 11)

---

## Overview

The **Monitoring Dashboard** provides decision support for evaluating Champion Model performance. Since the workflow is fully manual, this is a tool you check **when convenient** (not real-time alerts).

**Purpose**: Answer the question "Is my Champion Model still performing well?"

---

## Running the Dashboard

```bash
# Start Streamlit
streamlit run dashboard/monitoring.py

# Opens in browser at http://localhost:8501
```

---

## Dashboard Layout

### 1. Status Overview

```
┌─────────────────────────────────────────────────┐
│  CFB Model Monitoring Dashboard                │
│  Last Updated: 2025-12-05 13:00 EST            │
│  Status: 🟢 GREEN | 🟡 YELLOW | 🟠 ORANGE | 🔴 RED │
└─────────────────────────────────────────────────┘
```

**Status Levels**:

- 🟢 **GREEN**: All metrics within expected range
- 🟡 **YELLOW**: 1 warning threshold breached → Review in weekly sync
- 🟠 **ORANGE**: 2+ warnings OR 1 critical → Consider model change
- 🔴 **RED**: 2+ critical → Manual rollback recommended

---

### 2. Quick Stats (Last 4 Weeks)

```
┌─────────────────────────────────────────────────┐
│  Quick Stats (Last 4 Weeks)                    │
├─────────────────────────────────────────────────┤
│  ROI:        3.2%  (Test: 5.2%)  📉 -2.0%      │
│  Hit Rate:  51.5%  (Test: 52.2%) 📉 -0.7%      │
│  Volume:    14/wk  (Exp: 15/wk)  ✓ Normal      │
│  Bets:      56     (4 weeks total)             │
└─────────────────────────────────────────────────┘
```

---

### 3. ROI Trend Chart (12 Weeks)

Interactive line chart showing:

- Test ROI (horizontal reference line)
- Live ROI (rolling 4-week window)
- Warning threshold (test - 3%)
- Critical threshold (test - 5%)

**Implementation**:

```python
import streamlit as st
import plotly.graph_objects as go

fig = go.Figure()
fig.add_trace(go.Scatter(x=weeks, y=live_roi, name="Live ROI"))
fig.add_hline(y=test_roi, line_dash="dash", annotation_text="Test ROI")
fig.add_hline(y=test_roi - 0.03, line_dash="dot", line_color="orange")
fig.add_hline(y=test_roi - 0.05, line_dash="dot", line_color="red")
st.plotly_chart(fig)
```

---

### 4. Alert History

```
┌─────────────────────────────────────────────────┐
│  Alert History                                  │
├─────────────────────────────────────────────────┤
│  2025-12-01: 🟡 ROI dropped below warning      │
│  2025-11-24: 🟢 All metrics normal             │
│  2025-11-18: 🟠 Volume spike + calibration     │
└─────────────────────────────────────────────────┘
```

---

### 5. Detailed Metrics (Expandable Sections)

**Performance by Bet Type**:

- Spread vs Total
- Home vs Away
- Favorite vs Underdog

**Feature Drift Analysis**:

- KS tests for each feature
- Highlight features with p < 0.05 (significant drift)

**Calibration Analysis**:

- Predicted vs Actual scatter plot
- Mean absolute error by prediction bucket

**Weekly Breakdown**:

- Table with ROI, hit rate, volume per week

---

## Metrics Tracked

### Tier 1: Critical (Check Every Week)

| Metric            | Warning          | Critical           | Action            |
| ----------------- | ---------------- | ------------------ | ----------------- |
| ROI (4-week)      | < Test - 3%      | < Test - 5%        | Consider rollback |
| Hit Rate (4-week) | < Test - 2%      | < 48% (hard floor) | Review model      |
| Volume (weekly)   | < Expected × 0.5 | = 0                | Check thresholds  |

### Tier 2: Important (Check Biweekly)

| Metric            | Warning      | Action             |
| ----------------- | ------------ | ------------------ |
| Calibration Error | > Test × 1.2 | Review predictions |
| Max Losing Streak | > 8          | Check variance     |
| Avg Edge          | < Test × 0.8 | Review thresholds  |

### Tier 3: Diagnostic (Monthly)

| Metric                | Warning        | Action                  |
| --------------------- | -------------- | ----------------------- |
| Feature Drift (KS)    | p < 0.05       | Investigate data source |
| Home/Away Bias        | \|diff\| > 10% | Check home field        |
| Bet Type Distribution | Any < 10%      | Review policy           |

---

## Data Sources

The dashboard reads from:

1. **Scored Bets**: `data/production/scored/YYYY/CFB_weekWW_bets_scored.csv`
2. **Test Metrics**: Stored in MLflow for Champion Model
3. **Historical Baseline**: From initial model registration

**Schema** (`_bets_scored.csv`):

```csv
game_id,week,home_team,away_team,prediction,actual,bet_type,result,roi
12345,2,Alabama,Auburn,7.5,10.0,spread,win,0.91
```

---

## Implementation Steps (Week 11)

1. **Create Dashboard Script**:

   ```bash
   touch dashboard/monitoring.py
   ```

2. **Implement Components**:

   - [ ] Status indicator logic
   - [ ] Quick stats calculation
   - [ ] ROI trend chart (Plotly)
   - [ ] Alert history (from log file)
   - [ ] Expandable detailed sections

3. **Test on Legacy Data**:

   ```bash
   # Load 2025 Weeks 2-14 scored bets
   streamlit run dashboard/monitoring.py
   ```

4. **Document Usage**:
   - Add screenshots to this doc
   - Create user guide for reading dashboard

---

## Manual Rollback Decision

**When to rollback**:

- 🔴 RED status for 2+ consecutive weeks
- Hit rate <48% (hard floor)
- Personal judgment after reviewing dashboard

**How to rollback**:

1. Load previous Champion from MLflow registry
2. Re-run `generate_weekly_bets.py` with old model
3. Compare predictions to confirm different
4. Document rollback in decision log

**See**: [`rollback_sop.md`](./rollback_sop.md) for detailed procedure

---

## Future Enhancements

- [ ] Auto-refresh dashboard (cron job)
- [ ] Export weekly PDF report
- [ ] Email digest (optional, for major alerts)
- [ ] Model comparison view (current vs previous)

---

**Last Updated**: 2025-12-05  
**Status**: Design complete, implementation pending Week 11
