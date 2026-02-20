# Session: CatBoost Walk-Forward CV

## TL;DR
- **Worked On:** Running CatBoost with walk-forward CV to compare to Ridge baseline
- **Completed:** 4-fold CV complete, comparison report generated
- **Key Finding:** CatBoost has 41% lower variance than Ridge (±3.12% vs ±5.30%)
- **Recommendation:** Prefer CatBoost for deployment due to stability

## Results

### CatBoost Walk-Forward
```
ROI: -3.20% ± 3.12%
Hit Rate: 50.7% ± 1.6%
RMSE: 19.30 ± 0.49

Per-Fold:
- fold_2021: ROI=0.91% (handles limited data well)
- fold_2022: ROI=-2.64%
- fold_2023: ROI=-6.27%
- fold_2024: ROI=-4.80%
```

### vs Ridge Walk-Forward
```
ROI: -3.11% ± 5.30%
Hit Rate: 50.7% ± 2.8%
RMSE: 18.99 ± 0.86
```

### Comparison
- **ROI:** Essentially tied (-3.20% vs -3.11%)
- **Variance:** CatBoost 41% more stable (±3.12% vs ±5.30%)
- **Hit Rate:** Identical (50.7%)
- **RMSE:** Ridge slightly better (18.99 vs 19.30)

## Key Finding

**CatBoost is Much More Stable:**
- Smaller range: [-6.27%, 0.91%] vs [-8.66%, 2.55%]
- Better handles limited training data (fold_2021: +0.91% vs -6.45%)
- More predictable deployment outcomes
- Lower risk of extreme negative folds

## Files Generated
- `artifacts/cross_validation/model_comparison_walk_forward.txt`
- Updated `MEMORY.md` with CatBoost results

## Next Steps
1. Test external features (extended_v1) with walk-forward CV
2. Consider ensemble methods combining Ridge + CatBoost
3. Explore new data sources to improve base performance

**tags:** ["cv", "catboost", "walk-forward", "model-comparison"]
