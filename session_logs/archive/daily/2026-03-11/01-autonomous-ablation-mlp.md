# Session: Autonomous Ablation Framework + MLP Experiment

## TL;DR

- **Worked On:** Created autonomous ablation framework (inspired by karpathy/autoresearch) and tested neural networks (MLP) against gradient boosting
- **Completed:** Ran extended ablation with 10 candidates + MLP experiments
- **Blockers:** None - all experiments completed successfully
- **Next:** External market ratings (FPI, SP+, FEI) would provide information advantage; current models are break-even with market

## Changes Made

### New Files Created
- **File `conf/features/ablation_baseline.yaml`**: Minimal 8-feature baseline (EPA + Success Rate)
- **File `conf/research/ablation_config.yaml`**: Defines 10 ablation candidates
- **File `scripts/research/autonomous_ablate.py`**: Main autonomous loop script
- **File `scripts/research/test_mlp.py`**: Simple PyTorch MLP experiment

### Modified Files
- **File `scripts/research/autonomous_ablate.py`**: Added XGBoost support and new candidate types

## Testing

- [x] Health checks pass (ruff format + lint)
- [x] Tests pass (173 tests)
- [ ] Documentation updated

## Ablation Results (10 Candidates)

| Rank | Candidate | ROI | Hit Rate |
|------|-----------|-----|----------|
| 1 | **adjustment_iterations_4** | **+0.01%** | 52.7% |
| 2 | recency_alpha_0.3 | -0.004% | 52.2% |
| 3 | deeper_regularization | -0.004% | 52.2% |
| 4 | model_xgboost | -0.01% | 52.5% |
| 5 | raw_no_adjustment | -0.01% | 52.5% |
| 6 | baseline | -0.05% | 50.0% |
| 7-10 | Others | -0.02% to -0.06% | ~50% |

## MLP Experiment Results

| Metric | Value |
|--------|-------|
| **ROI** | **-0.58%** |
| **Hit Rate** | **52.1%** |
| RMSE | 18.84 |
| MAE | 14.70 |

## Key Findings

1. **Market Efficiency**: All models achieve ~50% hit rate, ~0% ROI - matching the market
2. **Best Config**: CatBoost with 4 opponent adjustment iterations (+0.01% ROI)
3. **MLP worse than GBM**: -0.58% vs +0.01% for CatBoost
4. **Adding features hurts**: More features = more noise, not more signal
5. **External ratings needed**: To beat the market, need information advantage (FPI, SP+, FEI)

## Notes for Next Session

**Resume at:** Data ingestion pipeline for external market ratings
**Context:** Internal features are exhausted - model matches market but has no edge
**Next steps:**
1. Investigate historical weekly SP+, FPI, FEI data ingestion
2. Or pivot to different betting markets (player props, in-game)
3. Or accept break-even as "free market efficiency"

**tags:** ["modeling", "ablation", "mlp", "catboost", "xgboost", "autoresearch"]
