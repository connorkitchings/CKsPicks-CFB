# Betting Policy & Risk Management

This document establishes the comprehensive betting policy, unit sizing methodology, bankroll management, and risk controls for the cfb_model betting system.

> 🔗 **Related**: [Open Decision OPEN-005](open_decisions.md#open-005-betting-unit-sizing-methodology) | [Model Evaluation](model_evaluation_criteria.md) | [Modeling Baseline](modeling_baseline.md)

---

## Betting Policy Overview

### Core Principles

1. **Risk Management First**: Preservation of capital is the primary objective
2. **Statistical Edge Required**: Only bet when model indicates significant advantage
3. **Disciplined Approach**: Consistent application of sizing and selection rules
4. **Bankroll Protection**: Never risk more than predetermined limits
5. **Continuous Monitoring**: Ongoing assessment of strategy effectiveness

### Betting Universe

- **Sports**: College Football (FBS) only
- **Bet Types**: Point spreads (primary), totals (future expansion)
- **Season**: Regular season games, exclude bowl games initially
- **Markets**: Against-the-spread (ATS) bets only
- **Timing**: Bets placed mid-week (Wednesday), held until game completion

---

## Unit Sizing Methodology

### Option A: Fixed Fractional (RECOMMENDED for MVP)

**Formula**: Bet Size = Base Unit × Edge Multiplier

```python
def calculate_bet_size_fixed_fractional(
    bankroll: float,
    base_fraction: float = 0.02,  # 2% of bankroll
    model_edge: float,
    edge_multiplier_cap: float = 2.0
) -> float:
    \"\"\"
    Calculate bet size using fixed fractional method

    Args:
        bankroll: Current total bankroll
        base_fraction: Base percentage of bankroll per bet (default 2%)
        model_edge: Model's predicted edge in points
        edge_multiplier_cap: Maximum multiplier for large edges

    Returns:
        Bet size in dollars
    \"\"\"
    base_unit = bankroll * base_fraction

    # Edge-based multiplier (larger edges = larger bets)
    edge_multiplier = min(1 + (model_edge - 3.5) / 10, edge_multiplier_cap)

    return base_unit * edge_multiplier
```

**Configuration**:

- **Base Unit**: 2% of bankroll
- **Edge Scaling**: +10% bet size per additional point of edge
- **Maximum Bet**: 4% of bankroll (2x multiplier cap)
- **Minimum Edge**: 3.5 points (consistent with selection criteria)

**Advantages**:

- ✅ Simple to implement and understand
- ✅ Automatically scales with bankroll growth/decline
- ✅ Conservative approach suitable for MVP
- ✅ Edge-based sizing rewards higher confidence bets

**Example**:

```
Bankroll: $10,000
Base Unit: $200 (2%)
Model Edge: 7.5 points
Edge Multiplier: 1 + (7.5 - 3.5) / 10 = 1.4
Bet Size: $200 × 1.4 = $280
```

### Option B: Kelly Criterion (Implemented)

**Formula**: Bet Size = Bankroll × Kelly Fraction

```python
def calculate_kelly_fraction(
    win_probability: float,
    odds: int = -110,
    fractional_kelly: float = 0.25
) -> float:
    \"\"\"
    Calculate Kelly Criterion fraction

    Args:
        win_probability: Model's estimated win probability
        odds: American odds (default -110)
        fractional_kelly: Fraction of full Kelly (default 25%)

    Returns:
        Kelly fraction (percentage of bankroll to bet)
    \"\"\"
    # Convert American odds to decimal odds
    if odds > 0:
        decimal_odds = (odds / 100) + 1
    else:
        decimal_odds = (100 / abs(odds)) + 1

    # Kelly formula: (bp - q) / b
    # where b = decimal_odds - 1, p = win_prob, q = lose_prob
    b = decimal_odds - 1
    p = win_probability
    q = 1 - win_probability

    kelly_fraction = (b * p - q) / b

    # Apply fractional Kelly for risk management
    return max(0, kelly_fraction * fractional_kelly)
```

**Configuration (Current Defaults)**:

- **Fractional Kelly**: 25% of full Kelly recommendation (`--kelly-fraction 0.25`)
- **Kelly Cap**: 25% cap before applying fractional Kelly (`--kelly-cap 0.25`)
- **Base Unit**: 2% of bankroll (`--base-unit-fraction 0.02`) for unit reporting
- **Win Probability**: Derived from a normal CDF using ensemble std-dev as sigma
- **ATS/OU Pricing**: Uses provider odds when present; falls back to -110
- **Confidence Filters**: Spread std-dev ≤ 2.0, Total std-dev ≤ 1.5 by default

### Option C: Confidence-Based Sizing (Advanced)

```python
def calculate_confidence_based_size(
    bankroll: float,
    model_edge: float,
    prediction_confidence: float,  # 0-1 scale
    base_fraction: float = 0.015
) -> float:
    \"\"\"
    Size bets based on both edge and model confidence
    \"\"\"
    base_unit = bankroll * base_fraction

    # Combine edge and confidence
    sizing_factor = (model_edge / 5.0) * prediction_confidence
    sizing_factor = min(sizing_factor, 2.5)  # Cap at 2.5x

    return base_unit * sizing_factor
```

---

### Report Fields (ATS/OU)

- Decision fields: `bet_spread`, `bet_total`, `edge_spread`, `edge_total`
- Uncertainty fields: `predicted_spread_std_dev`, `predicted_total_std_dev`
- Kelly sizing: `kelly_fraction_spread`, `kelly_fraction_total`, `bet_units_spread`, `bet_units_total`, `bet_units`

## Bankroll Management

### Bankroll Structure

#### Starting Bankroll

- **Minimum Recommended**: $5,000 (allows 250 base units at 2%)
- **Target Starting Amount**: $10,000 (allows 500 base units)
- **Risk Tolerance**: Only bet money you can afford to lose completely

#### Bankroll Segmentation

```
Total Bankroll: $10,000
├── Active Betting Capital: $8,000 (80%)
├── Reserve Fund: $1,500 (15%)
└── Operating Expenses: $500 (5%)
```

- **Active Betting Capital**: Used for bet sizing calculations
- **Reserve Fund**: Emergency buffer, only used if active capital drops >50%
- **Operating Expenses**: Data subscriptions, hosting, tools

#### Bankroll Adjustment Triggers

**Growth Triggers** (Increase betting bankroll):

- **+25% Growth**: Increase active capital by 20% of gains
- **+50% Growth**: Increase active capital by 50% of gains
- **Review Frequency**: Monthly

**Decline Triggers** (Reduce betting exposure):

- **-20% Decline**: Reduce base unit size by 25%
- **-35% Decline**: Reduce base unit size by 50%, activate risk review
- **-50% Decline**: STOP BETTING, full strategy review required

**Example Bankroll Management**:

```python
def adjust_bankroll(
    current_bankroll: float,
    starting_bankroll: float,
    performance_roi: float
) -> Dict[str, float]:
    \"\"\"Adjust bankroll based on performance\"\"\"

    change_pct = (current_bankroll - starting_bankroll) / starting_bankroll

    if change_pct >= 0.50:  # +50% or more
        new_active = current_bankroll * 0.85  # Increase active allocation
        base_unit_multiplier = 1.0
        status = \"AGGRESSIVE_GROWTH\"

    elif change_pct >= 0.25:  # +25% to +49%
        new_active = current_bankroll * 0.82
        base_unit_multiplier = 1.0
        status = \"MODERATE_GROWTH\"

    elif change_pct >= -0.20:  # -20% to +24%
        new_active = current_bankroll * 0.80  # Normal allocation
        base_unit_multiplier = 1.0
        status = \"NORMAL\"

    elif change_pct >= -0.35:  # -20% to -34%
        new_active = current_bankroll * 0.75  # Reduce exposure
        base_unit_multiplier = 0.75  # Smaller bets
        status = \"RISK_REDUCTION\"

    elif change_pct >= -0.50:  # -35% to -49%
        new_active = current_bankroll * 0.70
        base_unit_multiplier = 0.50
        status = \"HIGH_RISK\"

    else:  # -50% or worse
        new_active = 0  # Stop betting
        base_unit_multiplier = 0
        status = \"STOP_BETTING\"

    return {
        'active_capital': new_active,
        'base_unit_multiplier': base_unit_multiplier,
        'status': status,
        'change_pct': change_pct
    }
```

---

## Risk Controls

### Pre-Bet Risk Checks

#### 1. Model Requirements

```python
def validate_bet_eligibility(
    game_data: Dict,
    model_prediction: float,
    betting_line: float,
    model_confidence: float = None
) -> Tuple[bool, str]:
    \"\"\"
    Validate if a game meets betting criteria

    Returns:
        (eligible, reason)
    \"\"\"
    # Check 1: Both teams have minimum games played
    if (game_data['home_games_played'] < 4 or
        game_data['away_games_played'] < 4):
        return False, \"Insufficient game history\"

    # Check 2: Model edge meets threshold
    edge = abs(model_prediction - betting_line)
    if edge < 3.5:
        return False, f\"Edge too small: {edge:.1f} points\"

    # Check 3: Prediction is reasonable
    if abs(model_prediction) > 45:
        return False, f\"Prediction outside reasonable range: {model_prediction}\"

    # Check 4: Model confidence (if available)
    if model_confidence and model_confidence < 0.6:
        return False, f\"Model confidence too low: {model_confidence:.1%}\"

    # Check 5: Game timing (no games within 2 hours)
    if game_data.get('starts_in_hours', 48) < 2:
        return False, \"Game starts too soon\"

    return True, \"Eligible\"
```

#### 2. Portfolio Risk Limits

```python
def check_portfolio_limits(
    active_bets: List[Dict],
    new_bet_size: float,
    bankroll: float
) -> Tuple[bool, str]:
    \"\"\"
    Check portfolio-level risk limits
    \"\"\"
    # Current exposure
    current_exposure = sum(bet['amount'] for bet in active_bets)
    total_exposure = current_exposure + new_bet_size

    # Limit 1: Maximum portfolio exposure
    max_exposure = bankroll * 0.15  # 15% max exposure
    if total_exposure > max_exposure:
        return False, f\"Portfolio exposure limit: {total_exposure:.0f} > {max_exposure:.0f}\"

    # Limit 2: Maximum bets per week
    if len(active_bets) >= 12:
        return False, \"Maximum weekly bet limit reached (12)\"

    # Limit 3: Maximum single bet size
    max_single_bet = bankroll * 0.05  # 5% max single bet
    if new_bet_size > max_single_bet:
        return False, f\"Single bet too large: {new_bet_size:.0f} > {max_single_bet:.0f}\"

    return True, \"Within limits\"
```

### Position Limits

#### Daily/Weekly Limits

- **Maximum Bets Per Week**: 12 games
- **Maximum Single Bet**: 5% of bankroll
- **Maximum Weekly Exposure**: 15% of bankroll
- **Same-Game Limits**: 1 bet per game (no parlays)

#### Seasonal Limits

- **Maximum Drawdown**: -50% of starting bankroll triggers stop
- **Consecutive Loss Limit**: 8 consecutive losses triggers review
- **Win Rate Floor**: Hit rate below 45% for 4 weeks triggers review

### Emergency Procedures

#### Performance-Based Circuit Breakers

```python
def check_circuit_breakers(performance_metrics: Dict) -> Dict[str, Any]:
    \"\"\"
    Check if any circuit breakers should trigger
    \"\"\"
    breakers = {}

    # Circuit Breaker 1: Hit rate collapse
    if (performance_metrics['recent_4_week_hit_rate'] < 0.40 and
        performance_metrics['total_bets_recent'] >= 20):
        breakers['hit_rate_collapse'] = {
            'triggered': True,
            'action': 'PAUSE_BETTING',
            'reason': f\"Hit rate dropped to {performance_metrics['recent_4_week_hit_rate']:.1%}\"
        }

    # Circuit Breaker 2: Excessive drawdown
    if performance_metrics['current_drawdown'] > 0.40:
        breakers['excessive_drawdown'] = {
            'triggered': True,
            'action': 'REDUCE_SIZING',
            'reason': f\"Drawdown reached {performance_metrics['current_drawdown']:.1%}\"
        }

    # Circuit Breaker 3: Model malfunction
    if performance_metrics['prediction_rmse'] > 20:
        breakers['model_malfunction'] = {
            'triggered': True,
            'action': 'EMERGENCY_REVIEW',
            'reason': f\"RMSE spiked to {performance_metrics['prediction_rmse']:.1f}\"
        }

    return breakers
```

#### Circuit Breaker Actions

1. **PAUSE_BETTING**: Stop all new bets until review completed
2. **REDUCE_SIZING**: Cut bet sizes by 50% until performance improves
3. **EMERGENCY_REVIEW**: Immediate deep dive analysis required
4. **STOP_BETTING**: Complete halt until strategy overhaul

---

## Bet Selection Policy

### Selection Criteria (All Must Be Met)

1. **Model Edge**: ≥ 3.5 points difference from betting line
2. **Team History**: Both teams played ≥ 4 games this season
3. **Prediction Range**: Model prediction between -45 and +45 points
4. **Data Quality**: No missing critical features for either team
5. **Game Timing**: Bet placed >2 hours before kickoff

### Enhanced Selection Rules (Optional Filters)

```python
def enhanced_selection_filter(
    game: Dict,
    model_output: Dict,
    historical_performance: Dict
) -> Tuple[bool, str]:
    \"\"\"
    Apply enhanced selection criteria
    \"\"\"
    reasons = []

    # Filter 1: Avoid division mismatches (optional)
    if (abs(game['home_team_rating'] - game['away_team_rating']) > 30 and
        model_output['edge'] < 7.0):
        reasons.append(\"Large talent gap with small edge\")

    # Filter 2: Weather considerations (future)
    if game.get('weather_concerns', False):
        reasons.append(\"Severe weather expected\")

    # Filter 3: Model uncertainty (if available)
    if model_output.get('prediction_std', 0) > 12:
        reasons.append(\"High model uncertainty\")

    # Filter 4: Historical edge performance
    similar_edges = historical_performance.get('similar_edge_performance', {})
    if (similar_edges.get('hit_rate', 0.6) < 0.55 and
        similar_edges.get('sample_size', 0) > 10):
        reasons.append(\"Poor historical performance on similar edges\")

    return len(reasons) == 0, \"; \".join(reasons)
```

### Bet Sizing Decision Matrix

| Model Edge | Confidence | Base Multiplier | Max Bet |
| :--------: | :--------: | :-------------: | :-----: |
|  3.5-5.0   |    Any     |      1.0x       |   2%    |
|  5.0-7.0   |    High    |      1.3x       |  2.6%   |
|  5.0-7.0   |    Low     |      1.1x       |  2.2%   |
|  7.0-10.0  |    High    |      1.6x       |  3.2%   |
|  7.0-10.0  |    Low     |      1.3x       |  2.6%   |
|   10.0+    |    High    |      2.0x       |  4.0%   |
|   10.0+    |    Low     |      1.5x       |  3.0%   |

---

## Performance Monitoring & Review

### Daily Monitoring

```python
def daily_risk_check() -> Dict[str, Any]:
    \"\"\"Daily risk and performance monitoring\"\"\"
    return {
        'current_exposure': calculate_current_exposure(),
        'bankroll_health': assess_bankroll_health(),
        'pending_games': get_pending_game_count(),
        'circuit_breaker_status': check_all_circuit_breakers(),
        'alerts': generate_risk_alerts()
    }
```

**Daily Risk Alerts**:

- Exposure >10% of bankroll
- Pending games >8
- Bankroll decline >5% in single day
- Model prediction anomalies

### Weekly Performance Review

**Key Metrics**:

- Hit rate (weekly and season-to-date)
- ROI (weekly and season-to-date)
- Units won/lost
- Average edge per bet
- Largest wins and losses
- Risk-adjusted returns (Sharpe ratio)

**Review Questions**:

1. Are we meeting performance thresholds?
2. Is bet sizing appropriate for current bankroll?
3. Are there patterns in wins/losses?
4. Should any risk controls be adjusted?
5. Is model performance stable?

### Monthly Strategy Review

**Comprehensive Analysis**:

- Model calibration assessment
- Feature importance changes
- Betting market efficiency trends
- Competitive landscape shifts
- Technology/process improvements

**Decision Points**:

- Bankroll reallocation
- Risk control adjustments
- Model enhancement priorities
- Process optimization opportunities

---

## Risk Management Framework

### Risk Categories

#### 1. Model Risk

- **Definition**: Risk that model predictions are systematically wrong
- **Mitigation**: Regular backtesting, performance monitoring, model validation
- **Monitoring**: RMSE tracking, hit rate analysis, calibration plots

#### 2. Market Risk

- **Definition**: Risk from betting market efficiency improvements
- **Mitigation**: Continuous model improvement, feature engineering
- **Monitoring**: Edge detection rates, line movement analysis

#### 3. Operational Risk

- **Definition**: Risk from system failures, data issues, execution problems
- **Mitigation**: Robust systems, data validation, backup procedures
- **Monitoring**: Data quality checks, system uptime, error rates

#### 4. Capital Risk

- **Definition**: Risk of significant capital loss
- **Mitigation**: Position sizing, portfolio limits, circuit breakers
- **Monitoring**: Drawdown tracking, exposure limits, bankroll health

#### 5. Behavioral Risk

- **Definition**: Risk from deviating from systematic approach
- **Mitigation**: Strict policies, automated checks, emotional discipline
- **Monitoring**: Policy compliance, manual override tracking

### Risk Assessment Matrix

| Risk Type         | Probability | Impact | Risk Score | Mitigation Priority |
| :---------------- | :---------: | :----: | :--------: | :-----------------: |
| Model Degradation |   Medium    |  High  |    High    |       ⬆️ High       |
| Market Efficiency |     Low     |  High  |   Medium   |       ⬆️ High       |
| System Failure    |     Low     | Medium |    Low     |      ➡️ Medium      |
| Capital Loss      |   Medium    |  High  |    High    |       ⬆️ High       |
| Behavioral Drift  |   Medium    | Medium |   Medium   |      ➡️ Medium      |

---

## Implementation Guidelines

### Phase 1: MVP Implementation

1. **Fixed Fractional Sizing**: 2% base unit with edge scaling
2. **Basic Risk Controls**: Portfolio limits, minimum edge thresholds
3. **Simple Monitoring**: Weekly performance reports
4. **Manual Oversight**: Human review of all bets before placement

### Phase 2: Enhanced Risk Management

1. **Dynamic Sizing**: Kelly Criterion or confidence-based sizing
2. **Advanced Controls**: Circuit breakers, model health monitoring
3. **Automated Monitoring**: Real-time alerts and dashboards
4. **Performance Analytics**: Detailed attribution analysis

### Phase 3: Sophisticated Portfolio Management

1. **Multi-Model Ensemble**: Risk distribution across models
2. **Market Making**: Two-way pricing and arbitrage detection
3. **Alternative Bet Types**: Totals, props, live betting
4. **Professional Tools**: Risk management software integration

---

## Policy Review & Updates

### Review Schedule

- **Weekly**: Performance and risk metrics
- **Monthly**: Strategy and sizing parameters
- **Quarterly**: Complete policy review
- **Annually**: Comprehensive strategy overhaul

### Change Management Process

1. **Proposal**: Document proposed changes with rationale
2. **Testing**: Backtest changes on historical data
3. **Approval**: Review and approve changes
4. **Implementation**: Deploy with monitoring
5. **Documentation**: Update all related documents

### Version Control

- All policy changes tracked in decision log
- Historical performance under different policies maintained
- Rollback procedures defined for each policy element

---

_Last Updated: 2025-10-02_
_Next Review: After 4 weeks of live implementation_  
_Policy Version: 1.0 (MVP)_
