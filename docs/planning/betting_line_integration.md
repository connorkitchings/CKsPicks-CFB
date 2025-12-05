# Betting Line Integration Implementation Plan

## Objective

**Good News**: Betting lines data already exists in `CFB_MODEL_DATA_ROOT` for 2023-2025!

Now we need to:

1. Load betting lines from the data root
2. Join with existing predictions
3. Calculate true ATS performance metrics
4. Backtest realistic ROI

## Current Status

✅ **Data Available**: Betting lines for 2023, 2024, 2025 stored at:

```
/Volumes/CK SSD/Coding Projects/cfb_model/raw/betting_lines/
├── year=2023/week=1-15/
├── year=2024/week=1-16/
└── year=2025/...
```

❓ **Missing Data**: Betting lines for 2019, 2021-2022 (user mentioned CFBD has these)

> [!IMPORTANT] > **Question**: Should we backfill 2019, 2021-2422 betting lines before proceeding, or start with 2023-2025 analysis first?

## Proposed Changes

### Phase 1: Load & Aggregate Betting Lines

#### [NEW] [load_betting_lines.py](file:///Users/connorkitchings/Desktop/Repositories/cfb_model/scripts/analysis/load_betting_lines.py)

Utility to load betting lines data:

- Read CSV files from data root
- Aggregate multiple sportsbooks (consensus lines)
- Handle missing data gracefully
- Support filtering by year/week

**Key Fields Available**:

- `spread` - closing spread
- `spread_open` - opening spread
- `over_under` - closing total
- `over_under_open` - opening total
- `home_moneyline` / `away_moneyline`
- `provider` - sportsbook name (DraftKings, Bovada, etc.)

**Aggregation Logic**:

- Use consensus (mean) across sportsbooks for primary lines
- Prefer Pinnacle if available (sharper)
- Fall back to single source if others missing

---

### Phase 2: Integration with Predictions

#### [MODIFY] [walk_forward_validation.py](file:///Users/connorkitchings/Desktop/Repositories/cfb_model/scripts/walk_forward_validation.py)

- Join predictions with betting lines at save time
- Include line columns in output CSV
- Add option to specify which line type (open vs. close)

#### [NEW] [ats_performance.py](file:///Users/connorkitchings/Desktop/Repositories/cfb_model/scripts/analysis/ats_performance.py)

Comprehensive ATS analysis:

- Calculate hit rate by edge threshold
- ROI calculation (accounting for vig)
- Kelly criterion optimal bet sizing
- Line value analysis (model vs. market)

---

### Phase 3: Backtesting & Reporting

#### [NEW] [backtest_betting.py](file:///Users/connorkitchings/Desktop/Repositories/cfb_model/scripts/backtest_betting.py)

Simulate betting strategy on historical data:

- Input: Predictions + Lines + Bankroll strategy
- Output: Week-by-week P&L, final ROI, max drawdown
- Support multiple strategies (flat betting, Kelly, etc.)

#### [MODIFY] [analyze_calibration.py](file:///Users/connorkitchings/Desktop/Repositories/cfb_model/scripts/analyze_calibration.py)

Add ATS-specific visualizations:

- Prediction edge vs. actual cover margin
- ROI by confidence level
- Line value scatter plots

---

### Phase 4: Weekly Production Pipeline

#### [NEW] [weekly_predictions_pipeline.py](file:///Users/connorkitchings/Desktop/Repositories/cfb_model/scripts/production/weekly_predictions_pipeline.py)

Automated workflow:

1. Fetch current week's games
2. Fetch current betting lines
3. Generate predictions
4. Calculate edges
5. Output recommended bets (CSV / email)

## Verification Plan

### Automated Tests

- Unit tests for API client (mock responses)
- Integration test: fetch real data, validate schema
- Backtest smoke test: run on 2024 data, verify ROI calculation

### Manual Verification

1. **Data Quality Check**: Spot-check 10 games from each season, verify lines match historical records
2. **ATS Calculation Validation**: Manually verify ATS outcomes for sample games
3. **ROI Sanity Check**: Ensure backtested ROI is reasonable (not 500% or -90%)

### Acceptance Criteria

- [ ] Successfully fetch and store betting lines for 2024 season
- [ ] Join lines with existing predictions
- [ ] Calculate ATS hit rate >52.4% at some edge threshold
- [ ] Generate backtest report showing realistic P&L curve

## Implementation Order

1. **Load Betting Lines** (2-3 hours): Build loader, aggregate consensus lines
2. **Join with Predictions** (2 hours): Modify walk_forward or create join script
3. **ATS Metrics** (2-3 hours): Calculate hit rates, ROI by edge threshold
4. **Backtesting** (3-4 hours): Simulate betting strategies
5. **Reporting** (2 hours): Update performance reports
6. **Backfill 2019, 2021-2022** (1-2 hours): If needed, run ingester for missing years

**Total Estimate**: 12-16 hours

## Risks & Mitigations

| Risk                               | Impact                      | Mitigation                                             |
| ---------------------------------- | --------------------------- | ------------------------------------------------------ |
| No free historical data            | Can't backtest past seasons | Purchase historical dataset or start tracking from now |
| API rate limits                    | Slow data collection        | Implement caching, batch requests                      |
| Line inconsistency between sources | Inaccurate ATS calculations | Use consensus lines or primary source (Pinnacle)       |
| Missing lines for some games       | Reduced dataset             | Handle gracefully, log missing data                    |

## Next Steps

1. **Select API Provider**: Review options and make decision
2. **API Key Setup**: Register and obtain credentials
3. **Proof of Concept**: Fetch one week of lines to validate approach
4. **Full Implementation**: Follow implementation order above
