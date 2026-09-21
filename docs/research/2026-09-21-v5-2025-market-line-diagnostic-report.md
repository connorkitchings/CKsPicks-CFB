# V5 2025 Market-Line Diagnostic

> **Permitted use:** `diagnostic_comparison_only`  
> **Line semantics:** `provider_recorded_lines_postseason_capture` — these are provider-recorded lines captured post-season, NOT authentic timestamped pre-kickoff quotes. This report is NOT closing-line or CLV evidence.  
> **Production activation authorized:** false  
> **Readiness recommendation:** none — diagnostic comparison only; no effect on any gate, eligibility, Contract 11/12, or the 04/04B lifecycle.  
> **V4 comparison:** none  

## Entry identities

- Forecast entry record: `artifacts/research/data-first-football-v1/forecast-verification/conditional-v1/runs/conditional-v1-20260919-9265314-11a/verification-manifest.json` (11A-verified, SHA-pinned)
- Market dataset: `market_snapshots` version `e4061aab93b1e667a34ce780` (content SHA `6df93ed56b3fbcaea4434151099fe75794c3c9205f278d437895a170339cc5d9`)
- Market dataset URI: `lake/silver/dataset=market_snapshots/version=e4061aab93b1e667a34ce780/data.parquet`
- Replay input-ref agreement: `unanimous_16_of_16`
- Catalog state: `quarantined` (read-only lookup; quarantine untouched)
- Snapshot policy: `consensus_then_median_v1`

## Sign-convention validation

- Rows checked: 762
- r(V5 prediction, market-implied): 0.656
- r(V5 actual, V5 prediction): 0.457
- r(V5 actual, market-implied): 0.676
- Gates: `pass`

## Population accounting (2025)

### margin

- V5 2025 games: 934
- Lined games: 762
- Intersection games: 762
- Excluded (unlined, mostly FBS-FCS): 172

### total

- V5 2025 games: 934
- Lined games: 762
- Intersection games: 762
- Excluded (unlined, mostly FBS-FCS): 172

## Target: margin

### Overall (intersection)

  - N: 762
  - V5 MAE / RMSE / bias: 14.167 / 18.157 / +0.675
  - Market MAE / RMSE / bias: 11.846 / 15.057 / -0.700
  - MAE delta (market − V5): -2.321 95% CI [-2.967, -1.720]
  - Closer counts — V5: 315, market: 447, ties: 0

### Edge distribution (V5 − market-implied, descriptive only)

  - mean: +1.375, sd: 10.178
  - deciles p10/p25/p50/p75/p90: -12.51 / -5.59 / +1.38 / +8.05 / +14.92

### By completed-game stage

**Stage 0:**
  - N: 47
  - V5 MAE / RMSE / bias: 14.495 / 18.987 / -2.203
  - Market MAE / RMSE / bias: 12.415 / 15.235 / +0.223
  - MAE delta (market − V5): -2.080 95% CI [-4.507, +0.211]
  - Closer counts — V5: 20, market: 27, ties: 0

**Stage 1:**
  - N: 52
  - V5 MAE / RMSE / bias: 12.233 / 16.971 / -2.639
  - Market MAE / RMSE / bias: 11.212 / 14.516 / -1.385
  - MAE delta (market − V5): -1.022 95% CI [-3.601, +1.354]
  - Closer counts — V5: 22, market: 30, ties: 0

**Stage 2:**
  - N: 62
  - V5 MAE / RMSE / bias: 15.207 / 19.592 / -1.187
  - Market MAE / RMSE / bias: 12.343 / 16.257 / -2.778
  - MAE delta (market − V5): -2.864 95% CI [-5.088, -0.685]
  - Closer counts — V5: 25, market: 37, ties: 0

**Stage 3:**
  - N: 65
  - V5 MAE / RMSE / bias: 11.380 / 14.888 / -0.383
  - Market MAE / RMSE / bias: 11.346 / 14.863 / +0.331
  - MAE delta (market − V5): -0.034 95% CI [-1.624, +1.595]
  - Closer counts — V5: 35, market: 30, ties: 0

**Stage 4+:**
  - N: 536
  - V5 MAE / RMSE / bias: 14.543 / 18.381 / +1.593
  - Market MAE / RMSE / bias: 11.861 / 14.971 / -0.600
  - MAE delta (market − V5): -2.682 95% CI [-3.432, -1.942]
  - Closer counts — V5: 213, market: 323, ties: 0

## Target: total

### Overall (intersection)

  - N: 762
  - V5 MAE / RMSE / bias: 13.280 / 16.429 / +2.335
  - Market MAE / RMSE / bias: 12.366 / 15.332 / -0.234
  - MAE delta (market − V5): -0.914 95% CI [-1.323, -0.491]
  - Closer counts — V5: 340, market: 422, ties: 0

### Edge distribution (V5 − market-implied, descriptive only)

  - mean: +2.569, sd: 6.064
  - deciles p10/p25/p50/p75/p90: -5.47 / -1.17 / +2.94 / +6.84 / +10.01

### By completed-game stage

**Stage 0:**
  - N: 47
  - V5 MAE / RMSE / bias: 15.145 / 18.628 / +9.249
  - Market MAE / RMSE / bias: 12.761 / 15.879 / +6.824
  - MAE delta (market − V5): -2.384 95% CI [-3.634, -1.202]
  - Closer counts — V5: 13, market: 34, ties: 0

**Stage 1:**
  - N: 52
  - V5 MAE / RMSE / bias: 14.316 / 16.793 / -0.183
  - Market MAE / RMSE / bias: 14.014 / 16.268 / -2.947
  - MAE delta (market − V5): -0.302 95% CI [-1.857, +1.251]
  - Closer counts — V5: 26, market: 26, ties: 0

**Stage 2:**
  - N: 62
  - V5 MAE / RMSE / bias: 13.350 / 16.030 / +0.060
  - Market MAE / RMSE / bias: 13.444 / 16.461 / -2.815
  - MAE delta (market − V5): +0.094 95% CI [-1.250, +1.474]
  - Closer counts — V5: 28, market: 34, ties: 0

**Stage 3:**
  - N: 65
  - V5 MAE / RMSE / bias: 12.400 / 15.981 / +1.373
  - Market MAE / RMSE / bias: 11.500 / 14.399 / -0.808
  - MAE delta (market − V5): -0.900 95% CI [-2.167, +0.313]
  - Closer counts — V5: 30, market: 35, ties: 0

**Stage 4+:**
  - N: 536
  - V5 MAE / RMSE / bias: 13.115 / 16.286 / +2.353
  - Market MAE / RMSE / bias: 12.152 / 15.163 / -0.221
  - MAE delta (market − V5): -0.963 95% CI [-1.476, -0.449]
  - Closer counts — V5: 243, market: 293, ties: 0

## Evidence provenance

- Run ID: `market-diagnostic-2025-v1-20260921`
- Diagnostic manifest URI: `artifacts/research/data-first-football-v1/market-diagnostics/v1/runs/market-diagnostic-2025-v1-20260921/diagnostic-manifest.json`
- Diagnostic manifest raw SHA-256: `e879b6b4b5fec7a68bf8784ee4cf05db246d614277806dd553c7c06a79be2b81`

---
_This report is diagnostic comparison evidence only, computed from provider-recorded lines captured post-season. It is not closing-line or CLV evidence, not readiness evidence, not 2026 authorization, not a V4 comparison, and not prospective forecasting permission._
