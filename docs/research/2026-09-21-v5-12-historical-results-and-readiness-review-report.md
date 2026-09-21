# V5 Historical Results and Readiness Review Report

> **Permitted use:** `historical_readiness_review_only`  
> **Production activation authorized:** False  
> **Readiness recommendation:** `accepted_for_prospective_evaluation`  

## Executive Summary

The V5 historical foundation, possession efficiency measurements (r9), ratings (r9cert), expanding Ridge forecast bridge, and through-2025 final fit are mathematically verified, calibrated, and accepted for prospective evaluation. Prospective application to 2026 requires separate re-review and execution of Contracts 07-09.

## Certified Lineage and Closed Audit Blockers

All four Contract 10B foundation audit blocker findings have been resolved, independently verified, and closed:

- **audit-structural-001** (`closed`): Repair v2 verification imports producer computation — _Independent Repair verifier v3 with zero producer imports certified in Session 03_
- **audit-structural-002** (`closed`): Original forecast verification did not reconstruct stored outputs — _Independent 11D verifier reconstructed all 6 output datasets bit-exact in Session 09 (manifest 4cfe5ef8...)_
- **audit-ledger-score_reconciliation-1de3aaaf7d** (`closed`): 81 score-ledger excess team-game keys — _Corrected possession measurement scoring extraction certified in r9 with 0 excess keys in Session 03_
- **audit-forecast-final_fit_existence-b1bc852294** (`closed`): No through-2025 final forecast fit exists — _Through-2025 final fit rows added in 11C and verified in 11D with training_max=2025 in Session 08/09_

### Sealed Artifact Lineage

- **forecast:** `forecast-v1-20260921-5afd577-11c`
- **market_diagnostic:** `market-diagnostic-2025-v1-20260921`
- **measurement:** `possession-v1-measurements-20260921-r9`
- **rating:** `possession-v1-ratings-20260921-11d59ee-r9cert`
- **repair:** `repair-v2-20260909T1417Z`

## Population Verification

- Total prediction rows: 7318
- Total games: 3659
- Excluded rows: 0 (zero exclusions permitted; fully verified)
- Seasons: 2022, 2023, 2024, 2025

  - Season 2022: 896 games per target
  - Season 2023: 910 games per target
  - Season 2024: 919 games per target
  - Season 2025: 934 games per target

## Target: MARGIN

### Headline — 2025 Evaluation

  - N: 934
  - MAE: 14.160
  - RMSE: 18.056
  - Bias: -0.875
  - CRPS: 10.173
  - 50% coverage / width: 54.6% / 25.29
  - 80% coverage / width: 80.1% / 48.04
  - 95% coverage / width: 95.7% / 73.48

### Context Seasons (2022–2024)

**Season 2022:**
  - N: 896
  - MAE: 14.636
  - RMSE: 18.424
  - Bias: +0.818
  - CRPS: 10.374
  - 50% coverage / width: 52.5% / 25.87
  - 80% coverage / width: 82.1% / 49.15
  - 95% coverage / width: 95.8% / 75.17

**Season 2023:**
  - N: 910
  - MAE: 13.848
  - RMSE: 17.889
  - Bias: +0.259
  - CRPS: 10.026
  - 50% coverage / width: 56.6% / 25.67
  - 80% coverage / width: 83.0% / 48.77
  - 95% coverage / width: 95.5% / 74.59

**Season 2024:**
  - N: 919
  - MAE: 14.640
  - RMSE: 18.193
  - Bias: -0.350
  - CRPS: 10.316
  - 50% coverage / width: 49.5% / 25.41
  - 80% coverage / width: 81.7% / 48.28
  - 95% coverage / width: 95.8% / 73.84

### Pooled Results (2022–2025)

  - N: 3659
  - MAE: 14.320
  - RMSE: 18.140
  - Bias: -0.047
  - CRPS: 10.222
  - 50% coverage / width: 53.3% / 25.56
  - 80% coverage / width: 81.7% / 48.56
  - 95% coverage / width: 95.7% / 74.26

### Performance by Completed-Game Stage

**Stage 0:**
  - N: 573
  - MAE: 15.917
  - RMSE: 20.100
  - Bias: -6.423
  - CRPS: 11.341
  - 50% coverage / width: 49.2% / 25.57
  - 80% coverage / width: 76.4% / 48.58
  - 95% coverage / width: 93.7% / 74.29

**Stage 1:**
  - N: 301
  - MAE: 14.284
  - RMSE: 18.153
  - Bias: -2.436
  - CRPS: 10.207
  - 50% coverage / width: 53.2% / 25.54
  - 80% coverage / width: 82.4% / 48.53
  - 95% coverage / width: 96.0% / 74.22

**Stage 2:**
  - N: 244
  - MAE: 14.992
  - RMSE: 18.468
  - Bias: -0.649
  - CRPS: 10.510
  - 50% coverage / width: 49.2% / 25.55
  - 80% coverage / width: 80.3% / 48.54
  - 95% coverage / width: 95.5% / 74.24

**Stage 3:**
  - N: 253
  - MAE: 12.995
  - RMSE: 16.235
  - Bias: +1.498
  - CRPS: 9.274
  - 50% coverage / width: 56.9% / 25.56
  - 80% coverage / width: 85.8% / 48.56
  - 95% coverage / width: 98.4% / 74.27

**Stage 4+:**
  - N: 2288
  - MAE: 13.999
  - RMSE: 17.782
  - Bias: +1.758
  - CRPS: 10.017
  - 50% coverage / width: 54.4% / 25.56
  - 80% coverage / width: 82.7% / 48.56
  - 95% coverage / width: 95.9% / 74.26


## Target: TOTAL

### Headline — 2025 Evaluation

  - N: 934
  - MAE: 13.356
  - RMSE: 16.518
  - Bias: +2.910
  - CRPS: 9.389
  - 50% coverage / width: 52.0% / 23.87
  - 80% coverage / width: 82.0% / 45.35
  - 95% coverage / width: 97.2% / 69.36

### Context Seasons (2022–2024)

**Season 2022:**
  - N: 896
  - MAE: 14.093
  - RMSE: 17.573
  - Bias: +2.421
  - CRPS: 9.904
  - 50% coverage / width: 49.7% / 24.41
  - 80% coverage / width: 80.6% / 46.37
  - 95% coverage / width: 96.7% / 70.92

**Season 2023:**
  - N: 910
  - MAE: 13.903
  - RMSE: 17.223
  - Bias: +2.982
  - CRPS: 9.748
  - 50% coverage / width: 49.9% / 24.27
  - 80% coverage / width: 81.9% / 46.11
  - 95% coverage / width: 96.4% / 70.52

**Season 2024:**
  - N: 919
  - MAE: 13.316
  - RMSE: 16.694
  - Bias: +2.141
  - CRPS: 9.421
  - 50% coverage / width: 53.0% / 24.09
  - 80% coverage / width: 82.6% / 45.78
  - 95% coverage / width: 96.5% / 70.01

### Pooled Results (2022–2025)

  - N: 3659
  - MAE: 13.662
  - RMSE: 17.001
  - Bias: +2.615
  - CRPS: 9.612
  - 50% coverage / width: 51.2% / 24.16
  - 80% coverage / width: 81.8% / 45.90
  - 95% coverage / width: 96.7% / 70.19

### Performance by Completed-Game Stage

**Stage 0:**
  - N: 573
  - MAE: 13.290
  - RMSE: 16.802
  - Bias: +1.986
  - CRPS: 9.438
  - 50% coverage / width: 51.8% / 24.16
  - 80% coverage / width: 84.5% / 45.91
  - 95% coverage / width: 96.3% / 70.22

**Stage 1:**
  - N: 301
  - MAE: 13.380
  - RMSE: 16.678
  - Bias: +3.044
  - CRPS: 9.436
  - 50% coverage / width: 52.2% / 24.14
  - 80% coverage / width: 82.4% / 45.87
  - 95% coverage / width: 97.0% / 70.16

**Stage 2:**
  - N: 244
  - MAE: 12.922
  - RMSE: 16.263
  - Bias: +2.611
  - CRPS: 9.161
  - 50% coverage / width: 51.2% / 24.15
  - 80% coverage / width: 84.8% / 45.89
  - 95% coverage / width: 97.5% / 70.18

**Stage 3:**
  - N: 253
  - MAE: 13.684
  - RMSE: 16.988
  - Bias: +2.054
  - CRPS: 9.623
  - 50% coverage / width: 51.0% / 24.16
  - 80% coverage / width: 79.0% / 45.90
  - 95% coverage / width: 97.6% / 70.20

**Stage 4+:**
  - N: 2288
  - MAE: 13.869
  - RMSE: 17.171
  - Bias: +2.779
  - CRPS: 9.726
  - 50% coverage / width: 50.9% / 24.16
  - 80% coverage / width: 81.0% / 45.90
  - 95% coverage / width: 96.5% / 70.19

## Selection Evidence and Gates

- **Selected Horizon:** `expanding` (retained over `latest_five` per the prespecified gate: `latest_five` achieved <0.5% gain with non-positive bootstrap lower bounds).
- **Selected Heads:** `reference` (Ridge regression with fixed alpha=10.0).
- **Through-2025 Final Fit:** Verified for both margin and total across all 10 development seasons (2015,2016,2017,2018,2019,2021,2022,2023,2024,2025).

## Baseline and Comparison Disclosures

### Market Line Diagnostic Comparison (2025)

- Run ID: `market-diagnostic-2025-v1-20260921`
- Sample: 762 games
- Margin MAE: Model 14.38 vs Market 12.06 (Delta: -2.32)
- Total MAE: Model 13.20 vs Market 12.29 (Delta: -0.91)
- Disclosure: _Market line comparison is diagnostic-only from provider-recorded lines captured postseason. V5 relies strictly on football measurements without bookmaker market inputs._

### V4 Point-in-Time Comparison Disclosure

- Status: `unavailable`
- Disclosure: _V4 champion models were trained on 2021-2024 under feature schema v4/v5 without an equivalent 2022-2025 chronological point-in-time backtest under the V5 evaluation protocol._

## Next Steps & 2026 Prospective Governance

1. **Historical Foundation Accepted:** The historical methodology, verified dataset, and through-2025 final fit are formally certified.
2. **Live 2026 Application Withheld:** This review does **not** grant authority to apply V5 to live 2026 games or modify production champion models.
3. **Prerequisites for Live Prospective Evaluation:** Requires user acceptance of this review, followed by re-review and execution of deferred Contracts 07 (2026 measurement extension), 08 (2026 rating-state replay), and 09 (2026 forecast generation and live readiness).

## Evidence Provenance

- Scorecard Run ID: `readiness-v1-20260921-scorecard`
- Scorecard Manifest URI: `artifacts/research/data-first-football-v1/historical-scorecards/full-v1/runs/readiness-v1-20260921-scorecard/scorecard-manifest.json`
- Scorecard Manifest Raw SHA-256: `a8351fb3cabd7edbd1f78c961aa563a110b585db6c410e2b3f5973c8a2278b29`
- Entry Verification Manifest: `artifacts/research/data-first-football-v1/forecasts/runs/forecast-v1-20260921-5afd577-11c/verification/verifier-manifest.json`
- Entry Manifest Raw SHA-256: `ba60166bab17189209adca91e043338337b1a895c2d1637495abf1fa94ae0246`

---
_Official decision record for V5 Contract 12 (Historical Results and Readiness Review)._
