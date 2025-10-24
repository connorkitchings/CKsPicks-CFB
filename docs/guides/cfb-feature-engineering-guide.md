# College Football Betting Model: Feature Engineering & Feature Selection Guide

## Introduction

This guide provides a comprehensive framework for advanced feature engineering and feature selection techniques specifically designed for college football betting models. Based on current research and industry best practices, this guide will help you move beyond basic opponent-adjusted statistics to build more sophisticated, computationally efficient models that can identify profitable betting opportunities.

## Current Model Assessment

Your existing model using opponent-adjusted statistics is a solid foundation, but there are several areas for improvement:

**Current Strengths:**

- Uses opponent-adjusted metrics (good baseline approach)
- Compares team statistics directly
- Presumably uses College Football Data API

**Areas for Enhancement:**

- Limited feature diversity and depth
- High computational complexity
- Lack of systematic feature selection
- Missing situational and contextual features
- No automated feature importance evaluation

## Part 1: Advanced Feature Engineering Framework

### 1.1 Core Feature Categories

#### **Basic Statistical Features (Enhanced)**

Beyond simple opponent-adjusted stats, create these enhanced metrics:

```python
# Efficiency Metrics (per possession/drive)
- Points per drive (offensive/defensive)
- Yards per play (YPP) adjusted for opponent strength
- Success rate (% of plays gaining >= 50% yards needed on 1st/2nd down, 100% on 3rd/4th)
- Explosive play rate (plays >= 20 yards)
- EPA (Expected Points Added) per play
- Third down conversion rate (opponent-adjusted)
- Red zone efficiency (touchdowns per red zone visit)
- Turnover margin per game
```

#### **Situational Features**

These capture context-dependent performance:

```python
# Game Situation Features
- Performance by quarter (1st, 2nd, 3rd, 4th)
- Performance in close games (within 7 points)
- Performance when leading/trailing
- Performance by down and distance
- Performance in different field positions
- Home/away performance differentials
- Conference vs non-conference performance
- Performance against ranked opponents
```

#### **Advanced Efficiency Metrics**

Based on modern college football analytics:

```python
# Drive-Based Metrics
- Average starting field position
- Drives ending in scores (%)
- Three-and-out rate
- Available yards percentage (actual yards / maximum possible yards)

# Time-Based Features
- Time of possession differential
- Plays per drive
- Seconds per play (pace of play)
- Late game performance (4th quarter point differential)
```

#### **Strength of Schedule Features**

Move beyond simple opponent win percentage:

```python
# Multi-layered SOS
- Opponent win percentage
- Opponent's opponent win percentage
- Average opponent FPI/rating
- Strength of victories (quality of teams beaten)
- Strength of losses (quality of teams lost to)
- Recent opponent strength (last 3 games weighted higher)
```

#### **Momentum and Trend Features**

Capture recent performance patterns:

```python
# Temporal Features
- Performance over last 3, 5, 7 games
- Improvement/decline trends in key metrics
- Rest days between games
- Performance after bye weeks
- Bowl game vs regular season performance
- Performance by month/time of season
```

#### **Team Composition Features**

Personnel and recruitment quality:

```python
# Recruiting Features
- Average recruiting class rating (last 4 years)
- Number of 4/5-star players by position group
- Experience metrics (returning starters)
- Transfer portal additions/losses impact

# Coaching Features
- Head coach tenure
- Coordinator changes (new offensive/defensive coordinators)
- Historical performance in similar situations
```

#### **External Factors**

Environmental and contextual elements:

```python
# Game Context
- Weather conditions (temperature, wind, precipitation)
- Elevation and travel distance
- Crowd size and noise level
- Rivalry game indicator
- Bowl game vs regular season
- Television coverage (primetime effect)
- Days of rest differential between teams
```

### 1.2 Advanced Feature Engineering Techniques

#### **Interaction Features**

Create features that capture relationships between variables:

```python
# Statistical Interactions
- Offensive efficiency * Defensive efficiency differential
- Pace of play * Scoring efficiency
- Turnover margin * Field position average
- Home field advantage * Conference strength

# Matchup-Specific Features
- Team A's rushing offense vs Team B's rushing defense
- Team A's passing efficiency vs Team B's pass defense ranking
- Style matchups (fast pace vs slow pace teams)
```

#### **Rolling Windows and Weighted Averages**

Instead of season-long averages, use time-weighted metrics:

```python
# Time-Weighted Features
- Exponentially weighted moving averages (recent games weighted more)
- Performance in last N games vs season average
- Injury-adjusted recent performance
- Momentum indicators (improving vs declining metrics)
```

#### **Opponent-Adjusted Advanced Statistics**

Build on your existing approach with these enhanced methods:

```python
# Ridge Regression Adjustment Method
# Instead of simple averaging, use ridge regression to adjust for opponent strength
def opponent_adjust_ridge(team_stats, opponent_ratings):
    # Fit ridge regression: team_performance ~ opponent_strength
    # Residuals represent opponent-adjusted performance

# Margin-Based Adjustments
- Points scored above/below expectation vs opponent
- Yards gained/allowed relative to opponent averages
- Efficiency metrics adjusted for opponent quality
```

### 1.3 Feature Scaling and Normalization

#### **Standardization Methods**

```python
# Z-Score Normalization
feature_standardized = (feature - feature_mean) / feature_std

# Min-Max Scaling (0-1 range)
feature_scaled = (feature - feature_min) / (feature_max - feature_min)

# Robust Scaling (less sensitive to outliers)
feature_robust = (feature - feature_median) / feature_IQR
```

#### **Distribution Handling**

```python
# Log Transformation for skewed distributions
feature_log = log(feature + 1)  # +1 to handle zeros

# Box-Cox Transformation
feature_boxcox = boxcox(feature)

# Rank-based Transformations
feature_rank = feature.rank(pct=True)  # Convert to percentile ranks
```

## Part 2: Feature Selection Framework

### 2.1 Filter Methods (Fast, Model-Independent)

#### **Correlation Analysis**

```python
# Remove highly correlated features (>0.7 correlation)
correlation_matrix = features.corr()
high_corr_pairs = find_correlation_pairs(correlation_matrix, threshold=0.7)

# Keep the feature with higher target correlation
for pair in high_corr_pairs:
    keep_feature = max(pair, key=lambda x: abs(target.corr(features[x])))
```

#### **Statistical Tests**

```python
# Chi-Square Test for categorical features
from sklearn.feature_selection import chi2, SelectKBest
selector = SelectKBest(score_func=chi2, k=20)

# Mutual Information for continuous features
from sklearn.feature_selection import mutual_info_regression
mi_scores = mutual_info_regression(X, y)

# Variance Threshold (remove low-variance features)
from sklearn.feature_selection import VarianceThreshold
selector = VarianceThreshold(threshold=0.01)
```

### 2.2 Wrapper Methods (Model-Dependent)

#### **Recursive Feature Elimination (RFE)**

Best practice for tree-based models like Random Forest:

```python
from sklearn.feature_selection import RFECV
from sklearn.ensemble import RandomForestRegressor

# Use cross-validated RFE
rf = RandomForestRegressor(n_estimators=100, random_state=42)
rfecv = RFECV(estimator=rf,
              step=1,
              cv=5,
              scoring='neg_mean_squared_error',
              min_features_to_select=10)

# Fit and get selected features
rfecv.fit(X, y)
selected_features = X.columns[rfecv.support_]
```

#### **Sequential Feature Selection**

```python
from sklearn.feature_selection import SequentialFeatureSelector

# Forward selection
sfs_forward = SequentialFeatureSelector(rf,
                                       n_features_to_select=25,
                                       direction='forward',
                                       cv=5)

# Backward elimination
sfs_backward = SequentialFeatureSelector(rf,
                                        n_features_to_select=25,
                                        direction='backward',
                                        cv=5)
```

### 2.3 Embedded Methods (Built into Model Training)

#### **Lasso Regularization (L1)**

```python
from sklearn.linear_model import LassoCV

# Lasso automatically selects features by setting coefficients to zero
lasso = LassoCV(cv=5, random_state=42)
lasso.fit(X, y)

# Get selected features (non-zero coefficients)
selected_features = X.columns[lasso.coef_ != 0]
```

#### **Tree-Based Feature Importance**

```python
# Random Forest Feature Importance
rf = RandomForestRegressor(n_estimators=200, random_state=42)
rf.fit(X, y)

# Get feature importance scores
importance_scores = pd.DataFrame({
    'feature': X.columns,
    'importance': rf.feature_importances_
}).sort_values('importance', ascending=False)

# XGBoost Feature Importance
import xgboost as xgb
xgb_model = xgb.XGBRegressor(random_state=42)
xgb_model.fit(X, y)

# Multiple importance types
importance_gain = xgb_model.feature_importances_
importance_split = xgb_model.get_booster().get_score(importance_type='weight')
```

### 2.4 Hybrid Approach (Recommended)

Combine multiple methods for robust feature selection:

```python
def hybrid_feature_selection(X, y, target_features=30):
    """
    Multi-stage feature selection combining filter, wrapper, and embedded methods
    """

    # Stage 1: Filter Method - Remove low variance and highly correlated features
    # Remove features with variance < 0.01
    variance_selector = VarianceThreshold(threshold=0.01)
    X_var = variance_selector.fit_transform(X)

    # Remove highly correlated features
    corr_matrix = pd.DataFrame(X_var).corr().abs()
    high_corr_pairs = find_high_correlation_pairs(corr_matrix, threshold=0.85)
    features_to_remove = remove_correlated_features(high_corr_pairs, X, y)
    X_filtered = X.drop(columns=features_to_remove)

    # Stage 2: Embedded Method - Use tree-based importance
    rf = RandomForestRegressor(n_estimators=100, random_state=42)
    rf.fit(X_filtered, y)

    # Select top 50 features by importance
    importance_scores = rf.feature_importances_
    top_features_idx = np.argsort(importance_scores)[-50:]
    X_embedded = X_filtered.iloc[:, top_features_idx]

    # Stage 3: Wrapper Method - RFE for final selection
    rfecv = RFECV(estimator=rf, step=1, cv=5, min_features_to_select=target_features)
    rfecv.fit(X_embedded, y)

    final_features = X_embedded.columns[rfecv.support_]

    return final_features, rfecv
```

## Part 3: College Football Specific Considerations

### 3.1 Data Leakage Prevention

**Critical Rules:**

- Never use future information in features
- Be careful with season-long averages early in season
- Account for when information becomes available
- Use proper time-based cross-validation

```python
# Example: Proper time-series split for college football
def time_series_split(data, test_weeks=4):
    """
    Split data ensuring no look-ahead bias
    """
    # Sort by date
    data = data.sort_values(['season', 'week'])

    # Use first N-4 weeks for training, last 4 weeks for testing
    train_data = data[data['week'] <= data['week'].max() - test_weeks]
    test_data = data[data['week'] > data['week'].max() - test_weeks]

    return train_data, test_data
```

### 3.2 Handling College Football Specifics

#### **Early Season Challenges**

```python
# Weight features based on sample size
def early_season_weighting(current_week, feature_value, season_avg):
    """
    Blend current season performance with prior season for early weeks
    """
    if current_week <= 4:
        weight_current = current_week / 6.0  # Gradually increase current season weight
        return weight_current * feature_value + (1 - weight_current) * season_avg
    else:
        return feature_value
```

#### **Conference Effects**

```python
# Account for conference strength and play style differences
conference_adjustments = {
    'SEC': {'scoring_adj': 1.1, 'defense_adj': 1.15},
    'Big Ten': {'scoring_adj': 1.05, 'defense_adj': 1.1},
    'Big 12': {'scoring_adj': 1.15, 'defense_adj': 0.95},
    # etc.
}
```

### 3.3 Model Calibration Considerations

Based on research showing calibration is more important than accuracy for betting:

```python
# Calibration-focused model selection
from sklearn.calibration import CalibratedClassifierCV
from sklearn.isotonic import IsotonicRegression

# Calibrate probability predictions
calibrated_model = CalibratedClassifierCV(base_model, method='isotonic', cv=5)

# Evaluate calibration quality
def calibration_score(y_true, y_prob, n_bins=10):
    """
    Calculate calibration error for probability predictions
    """
    bin_boundaries = np.linspace(0, 1, n_bins + 1)
    bin_lowers = bin_boundaries[:-1]
    bin_uppers = bin_boundaries[1:]

    ece = 0
    for bin_lower, bin_upper in zip(bin_lowers, bin_uppers):
        in_bin = (y_prob > bin_lower) & (y_prob <= bin_upper)
        prop_in_bin = in_bin.mean()

        if prop_in_bin > 0:
            accuracy_in_bin = y_true[in_bin].mean()
            avg_confidence_in_bin = y_prob[in_bin].mean()
            ece += np.abs(avg_confidence_in_bin - accuracy_in_bin) * prop_in_bin

    return ece
```

## Part 4: Implementation Workflow

### 4.1 Recommended Development Process

1. **Start with expanded features but simple selection**
   - Implement 50-100 features from categories above
   - Use simple correlation-based filtering initially
   - Get baseline model working

2. **Implement systematic feature selection**
   - Add variance threshold and correlation filtering
   - Implement tree-based importance selection
   - Add RFE for final feature set

3. **Optimize for computational efficiency**
   - Profile code to identify bottlenecks
   - Cache expensive feature calculations
   - Use incremental learning where possible

4. **Validate with proper cross-validation**
   - Use time-based splits
   - Test on multiple seasons
   - Focus on calibration metrics

### 4.2 Feature Engineering Pipeline

```python
class CollegeFootballFeatureEngine:
    def __init__(self):
        self.feature_selectors = {}
        self.scalers = {}

    def create_base_features(self, games_df, stats_df):
        """Create basic statistical features"""
        # Implement basic stats, opponent adjustments
        pass

    def create_situational_features(self, games_df):
        """Create situational and contextual features"""
        # Implement home/away, conference, rivalry features
        pass

    def create_advanced_features(self, base_features):
        """Create interaction and derived features"""
        # Implement interaction terms, rolling averages
        pass

    def select_features(self, X, y, method='hybrid'):
        """Apply feature selection pipeline"""
        if method == 'hybrid':
            return self.hybrid_feature_selection(X, y)
        # Other selection methods

    def fit_transform(self, X, y):
        """Complete feature engineering pipeline"""
        # Create features
        features = self.create_base_features(X)
        features = self.create_situational_features(features)
        features = self.create_advanced_features(features)

        # Select features
        selected_features = self.select_features(features, y)

        # Scale features
        scaled_features = self.scale_features(selected_features)

        return scaled_features
```

### 4.3 Monitoring and Iteration

```python
# Track feature importance over time
def monitor_feature_drift(model, X_train, X_current):
    """
    Monitor if feature importance is changing over time
    """
    train_importance = model.feature_importances_

    # Retrain on recent data
    recent_model = clone(model)
    recent_model.fit(X_current[-1000:], y_current[-1000:])
    recent_importance = recent_model.feature_importances_

    # Calculate importance drift
    importance_correlation = np.corrcoef(train_importance, recent_importance)[0, 1]

    return importance_correlation
```

## Part 5: Computational Optimization

### 5.1 Reduce Model Complexity

```python
# Instead of comparing all opponent-adjusted stats:
# 1. Pre-select most predictive features
# 2. Use efficient data structures
# 3. Cache computations

class EfficientCFBModel:
    def __init__(self):
        self.feature_cache = {}
        self.model_cache = {}

    def cache_opponent_adjustments(self, season_data):
        """Pre-compute and cache expensive opponent adjustments"""
        for team in season_data['team'].unique():
            self.feature_cache[team] = self.compute_opponent_adj_stats(team, season_data)

    def predict_game(self, team_a, team_b):
        """Fast prediction using cached features"""
        features_a = self.feature_cache.get(team_a)
        features_b = self.feature_cache.get(team_b)

        if features_a is None or features_b is None:
            return self.compute_on_demand(team_a, team_b)

        # Fast prediction using pre-computed features
        return self.model.predict([features_a - features_b])[0]
```

### 5.2 Incremental Updates

```python
# Update features incrementally rather than recomputing everything
def update_features_incremental(current_features, new_game_data):
    """
    Update running statistics without full recomputation
    """
    # Update rolling averages
    # Update opponent adjustments
    # Update trend features
    pass
```

## Part 6: Validation and Backtesting

### 6.1 Proper Cross-Validation

```python
def college_football_cv_split(data, n_splits=5):
    """
    Time-aware cross-validation for college football
    """
    # Split by seasons, not random sampling
    seasons = sorted(data['season'].unique())

    for i in range(len(seasons) - n_splits + 1):
        train_seasons = seasons[i:i+3]  # 3 seasons for training
        val_season = seasons[i+3:i+4]   # 1 season for validation

        train_idx = data[data['season'].isin(train_seasons)].index
        val_idx = data[data['season'].isin(val_season)].index

        yield train_idx, val_idx
```

### 6.2 Betting-Specific Metrics

```python
def evaluate_betting_model(predictions, actual_results, betting_lines):
    """
    Evaluate model performance from betting perspective
    """
    # ROI calculation
    roi = calculate_roi(predictions, betting_lines, actual_results)

    # Hit rate by confidence level
    confidence_bins = pd.cut(predictions['confidence'], bins=5)
    hit_rates = actual_results.groupby(confidence_bins).mean()

    # Calibration error
    calibration_error = calculate_calibration_error(predictions['probability'], actual_results)

    return {
        'roi': roi,
        'hit_rates': hit_rates,
        'calibration_error': calibration_error,
        'sharpe_ratio': calculate_sharpe_ratio(roi)
    }
```

## Conclusion

This comprehensive feature engineering and selection framework will help you:

1. **Expand beyond basic opponent-adjusted stats** with situational, temporal, and interaction features
2. **Systematically select the most predictive features** using proven statistical methods
3. **Reduce computational complexity** through efficient feature selection and caching
4. **Build more robust models** that generalize better to new data
5. **Focus on betting profitability** rather than just prediction accuracy

The key is to implement this framework incrementally - start with expanded features, add systematic selection, then optimize for computational efficiency. Always validate using proper time-based cross-validation and betting-specific metrics.

Remember: in sports betting, a well-calibrated model that correctly estimates probabilities is more valuable than a highly accurate model that provides overconfident predictions.
