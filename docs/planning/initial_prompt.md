# College Football Betting System Development Prompt

## Project Overview

Develop a college football betting system that predicts point spreads and over/unders for FBS games
using historical play-by-play data. The system will provide weekly betting recommendations through
a web interface.

## Technical Foundation

- **Base Template**: <https://github.com/connorkitchings/cfb_model.git>
- **Language**: Python
- **Data Source**: CollegeFootballData.com API (API key available)
- **Storage**: Local Parquet (pyarrow) via a storage backend abstraction (Supabase deprecated; see Decisions)
- **Interface**: Web application for displaying weekly picks

## Data Specifications

### Historical Scope

- **Time Period**: 2014-2024 (CFP era), excluding the 2020 season.
- **Game Coverage**: FBS regular season games only
- **Data Foundation**: Play-by-play data, ingested via the API, will be the primary source. The
  system will build its own analytical dataset from this raw data.

### Data Hierarchy

Transform play-by-play data into multiple analytical levels:

1. **Play-level**: Individual play metrics and outcomes

2. **Game-level**: Team performance aggregations
3. **Season-level**: Cumulative team statistics and trends

### Feature Engineering

Derive opponent-adjusted betting indicators from play-by-play data:

- **MVP Focus**: The initial implementation will focus on basic, foundational stats (e.g., yards
  per play, turnover rates) to establish the end-to-end pipeline.
- **Future Enhancements**: More complex features will be added in later phases.
- **Efficiency Metrics**: Yards per play (offense/defense)
- **Success Rate**: Down and distance success rates
- **EPA/Explosion Metrics**: Expected Points Added and explosive play rates
- **Fremeau-Style Metrics**: Implement offensive and defensive efficiency metrics based on Bill
  Connelly/Brian Fremeau's methodologies, calculated using available play-by-play data rather than
  external sources
- **Red Zone Performance**: Scoring efficiency inside the 20-yard line
- **Situational Performance**: 3rd down, 4th down, and other critical situations
- **Rushing Metrics**: Yards per carry, success rate, explosive run rate
- **Passing Metrics**: Yards per attempt, completion rate, explosive pass rate
- **Rolling Averages**: 3-game and 5-game rolling performance windows
- **Opponent Adjustment**: All metrics adjusted for strength of opposition faced

## Model Architecture

### Training Strategy

- **Historical Training**: All previous seasons (2014-2023) form the base training dataset
- **In-Season Updates**: Weekly model updates incorporating current season data for improved predictions
- **Validation Method**: Time-based walk-forward cross-validation simulating real-world betting scenarios
- **Training Window**: Models can only use data from previous weeks/seasons
- **Season Integration**: Current season data essential for in-season predictions

### Prediction Targets

1. **Against the Spread (ATS)**: Primary focus for MVP
2. **Point Spreads**: Predict team margin of victory with opponent adjustments
3. **Output Format**: Show predicted spreads vs. consensus lines and best available lines to
   identify value

### Modeling Approach

- **Initial Method**: Linear regression for interpretability and baseline performance
- **Explainability**: SHAP (SHapley Additive exPlanations) for "Reason Codes"
- **Expandability**: Architecture supports future ML model integration (Phase 3)
- **Validation**: Robust time-based walk-forward cross-validation framework

## Operational Workflow

### Automated Pipeline Schedule

- **Tuesday 8:00 AM EST**: GitHub Actions pipeline automatically triggers to ingest previous
  weekend's game data
- **Pipeline Execution**: System retrains model and generates predictions for upcoming week's games
- **Deployment**: Recommendations published to private Streamlit interface
- **Betting Window**: Recommendations begin in Week 4 of season (minimum sample size)
- **Irregular Scheduling**: System handles Thursday/Friday games and bye weeks automatically after
  Week 1

### Sportsbook Integration

- **Primary Lines**: Use consensus lines from CollegeFootballData.com
- **Line Selection**: Opening lines (captured Tuesday morning for weekly predictions)
- **Value Identification**: Also identify best available lines relevant to model predictions
- **Future Enhancement**: Line movement tracking and analysis (Phase 3)

## Performance Tracking

### Success Metrics

- **Primary**: Win rate (winning bets / total bets)
- **Secondary**:
  - Units won/lost
  - Return on Investment (ROI)
  - Performance by bet type (spreads vs. totals)
  - Weekly/monthly performance trends

### Reporting Dashboard

- Real-time performance tracking
- Historical bet results with context
- Model accuracy metrics
- Profit/loss visualization

## Database Schema (Supabase) [Deprecated]

> Note: The project has pivoted from Supabase to a local Parquet storage backend with per-partition
> manifests and validation utilities. This section remains for historical context. See
> `docs/cfbd/data_ingestion.md` and `docs/project_org/project_charter.md` for the current storage
> architecture and validation workflow.

### Core Tables

- `games`: Game information and results
- `plays`: Individual play-by-play records
- `team_stats`: Aggregated team performance metrics
- `predictions`: Model predictions and actual outcomes
- `bets`: Recommended bets and their results
- `performance`: Tracking metrics and ROI data

### Data Pipeline & System Monitoring

- **Automated Data Ingestion**: Tuesday 8 AM EST pipeline via GitHub Actions
- **ETL Validation**: Handle missing/inconsistent data by skipping affected games
- **Pipeline Logging**: Comprehensive logging for successful runs, data issues, and prediction generation
- **Error Handling**: Graceful degradation when CollegeFootballData.com is unavailable
- **Data Freshness**: Validation to ensure predictions use current data
- **Model Training Pipeline**: Weekly model updates with new in-season data

## Streamlit Interface Requirements

### User Experience & Access Control

- **Authentication**: Single shared password protection for entire application
- **Target Audience**: Data-dense interface for sophisticated users familiar with betting and
  analysis
- **Design Priority**: Actionable insights over aesthetic polish
- **Deployment**: Streamlit Cloud for easy access by small group

### Core Interface (MVP)

1. **Current Week Picks**: Focus exclusively on upcoming week's recommendations
2. **Pick Details**: For each recommended bet display:
   - The pick (e.g., Team A +7.5)
   - Model's predicted spread
   - Consensus sportsbook line
   - Best available line
   - Value edge (≥3 points required)
   - "Reason Codes" (top 3 SHAP features driving prediction)
3. **Sorting Options**:
   - Default: Sort by value edge (highest first)
   - Alternative: Sort by kickoff time
4. **No Visualizations**: Text-based data presentation for MVP

## Future Expansion Considerations

### Phase 2 Enhancements

- **Over/Under Predictions**: Expand model to predict totals
- **Historical Performance Dashboard**: ROI and win rate tracking over time
- **Betting Unit Recommendations**: Size recommendations based on edge confidence
- **Enhanced User Management**: Individual user logins if needed

### Phase 3 Advanced Features

- **Advanced ML Models**: Test XGBoost, RandomForest against baseline
- **Line Movement Analysis**: Incorporate opening vs. closing line movement
- **Additional Data Sources**: Weather data, injury reports, advanced metrics
- **Model Performance Monitoring**: Automated alerts for accuracy degradation

### Scalability

- Multi-user support for sharing picks
- API development for external consumption
- Mobile app development
- Additional sports integration framework

## Success Criteria

### Minimum Viable Product (MVP)

- Functional web interface displaying weekly picks
- Automated data pipeline from CFB Data API
- Basic regression model producing spread/total predictions
- Performance tracking showing win rate above 52.4% (break-even threshold)

### Success Benchmarks

- **Technical**: System runs reliably with weekly updates
- **Predictive**: Win rate consistently above break-even
- **Business**: Positive ROI over multiple weeks of betting
- **User**: Clean, informative interface providing actionable insights

## Development Priority

1. Data pipeline and database setup
2. Feature engineering from play-by-play data
3. Basic regression model development
4. Web interface for displaying picks
5. Performance tracking and reporting
6. Model refinement and optimization

This system should serve as a solid foundation for college football betting while maintaining
flexibility for future enhancements and model improvements.
