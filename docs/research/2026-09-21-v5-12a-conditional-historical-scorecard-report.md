# V5 Conditional Historical Scorecard

> **Permitted use:** `conditional_historical_results_only`  
> **Production activation authorized:** false  
> **Readiness recommendation:** none — this scorecard answers the 2025
> historical question only; it cannot clear any blocker or replace the
> full audit and final review.

## Frozen artifact identities

- **forecast:** `forecast-v1-20260917-4600ddd-04b`
- **measurement:** `possession-v1-measurements-20260915-18fb0aa-r6`
- **rating:** `possession-v1-ratings-20260917-d029526-cert`
- **repair:** `repair-v2-20260909T1417Z`

## Open limitations (from Contract 10B audit)

- **audit-structural-001** (prohibited_until_closed): Repair v2 verification imports producer computation
- **audit-structural-002** (historical_evidence_only): Original forecast verification did not reconstruct stored outputs
- **audit-ledger-score_reconciliation-1de3aaaf7d** (prohibited_until_closed): 81 score-ledger excess team-game keys
- **audit-forecast-final_fit_existence-b1bc852294** (historical_evidence_only): No through-2025 final forecast fit exists

## Population

- Source rows: 7318
- Included rows: 7318
- Excluded rows: 0 (malformed/duplicate/non-finite rows block publication; exclusions are zero)
- Games: 3659
- Seasons: 2022, 2023, 2024, 2025

  - 2022: 896 rows per target
  - 2023: 910 rows per target
  - 2024: 919 rows per target
  - 2025: 934 rows per target

## Target: margin

### Headline — 2025

  - N: 934
  - MAE: 14.382
  - RMSE: 18.381
  - Bias: -0.842
  - CRPS: 10.340
  - 50% coverage / width: 55.139% / 25.65
  - 80% coverage / width: 79.872% / 48.74
  - 95% coverage / width: 94.754% / 74.54

### Context — 2022–2024

**2022:**
  - N: 896
  - MAE: 15.135
  - RMSE: 18.921
  - Bias: +0.716
  - CRPS: 10.677
  - 50% coverage / width: 50.335% / 26.14
  - 80% coverage / width: 80.915% / 49.67
  - 95% coverage / width: 95.647% / 75.96
**2023:**
  - N: 910
  - MAE: 14.119
  - RMSE: 18.147
  - Bias: +0.124
  - CRPS: 10.196
  - 50% coverage / width: 55.385% / 26.02
  - 80% coverage / width: 82.088% / 49.43
  - 95% coverage / width: 95.055% / 75.60
**2024:**
  - N: 919
  - MAE: 14.954
  - RMSE: 18.535
  - Bias: -0.459
  - CRPS: 10.521
  - 50% coverage / width: 49.075% / 25.76
  - 80% coverage / width: 81.610% / 48.95
  - 95% coverage / width: 96.083% / 74.86

### Pooled 2022–2025

  - N: 3659
  - MAE: 14.645
  - RMSE: 18.496
  - Bias: -0.124
  - CRPS: 10.432
  - 50% coverage / width: 52.501% / 25.89
  - 80% coverage / width: 81.115% / 49.19
  - 95% coverage / width: 95.381% / 75.23

### By completed-game stage

**Stage 0:**
  - N: 573
  - MAE: 16.678
  - RMSE: 20.930
  - Bias: -7.692
  - CRPS: 11.883
  - 50% coverage / width: 47.818% / 25.90
  - 80% coverage / width: 73.997% / 49.21
  - 95% coverage / width: 92.147% / 75.26
**Stage 1:**
  - N: 301
  - MAE: 14.488
  - RMSE: 18.534
  - Bias: -3.095
  - CRPS: 10.406
  - 50% coverage / width: 52.492% / 25.88
  - 80% coverage / width: 82.060% / 49.17
  - 95% coverage / width: 96.013% / 75.20
**Stage 2:**
  - N: 244
  - MAE: 15.604
  - RMSE: 19.029
  - Bias: -0.335
  - CRPS: 10.847
  - 50% coverage / width: 47.951% / 25.88
  - 80% coverage / width: 80.738% / 49.18
  - 95% coverage / width: 95.902% / 75.21
**Stage 3:**
  - N: 253
  - MAE: 13.101
  - RMSE: 16.466
  - Bias: +1.494
  - CRPS: 9.381
  - 50% coverage / width: 54.545% / 25.89
  - 80% coverage / width: 86.166% / 49.19
  - 95% coverage / width: 98.024% / 75.24
**Stage 4+:**
  - N: 2288
  - MAE: 14.224
  - RMSE: 17.988
  - Bias: +2.006
  - CRPS: 10.145
  - 50% coverage / width: 53.934% / 25.89
  - 80% coverage / width: 82.255% / 49.19
  - 95% coverage / width: 95.760% / 75.23

## Target: total

### Headline — 2025

  - N: 934
  - MAE: 13.200
  - RMSE: 16.388
  - Bias: +2.102
  - CRPS: 9.307
  - 50% coverage / width: 52.784% / 23.80
  - 80% coverage / width: 82.120% / 45.21
  - 95% coverage / width: 97.002% / 69.15

### Context — 2022–2024

**2022:**
  - N: 896
  - MAE: 14.048
  - RMSE: 17.504
  - Bias: +0.844
  - CRPS: 9.854
  - 50% coverage / width: 50.112% / 24.37
  - 80% coverage / width: 81.473% / 46.30
  - 95% coverage / width: 96.652% / 70.82
**2023:**
  - N: 910
  - MAE: 13.772
  - RMSE: 17.075
  - Bias: +1.791
  - CRPS: 9.658
  - 50% coverage / width: 50.440% / 24.22
  - 80% coverage / width: 82.308% / 46.02
  - 95% coverage / width: 96.923% / 70.38
**2024:**
  - N: 919
  - MAE: 13.174
  - RMSE: 16.633
  - Bias: +1.085
  - CRPS: 9.364
  - 50% coverage / width: 53.645% / 24.02
  - 80% coverage / width: 83.460% / 45.64
  - 95% coverage / width: 96.300% / 69.80

### Pooled 2022–2025

  - N: 3659
  - MAE: 13.543
  - RMSE: 16.899
  - Bias: +1.461
  - CRPS: 9.542
  - 50% coverage / width: 51.763% / 24.10
  - 80% coverage / width: 82.345% / 45.79
  - 95% coverage / width: 96.720% / 70.03

### By completed-game stage

**Stage 0:**
  - N: 573
  - MAE: 13.214
  - RMSE: 16.724
  - Bias: +0.792
  - CRPS: 9.383
  - 50% coverage / width: 52.705% / 24.11
  - 80% coverage / width: 83.770% / 45.81
  - 95% coverage / width: 96.510% / 70.05
**Stage 1:**
  - N: 301
  - MAE: 13.084
  - RMSE: 16.439
  - Bias: +1.744
  - CRPS: 9.273
  - 50% coverage / width: 54.153% / 24.08
  - 80% coverage / width: 82.724% / 45.76
  - 95% coverage / width: 97.342% / 69.99
**Stage 2:**
  - N: 244
  - MAE: 12.841
  - RMSE: 16.161
  - Bias: +1.354
  - CRPS: 9.091
  - 50% coverage / width: 51.230% / 24.09
  - 80% coverage / width: 86.066% / 45.77
  - 95% coverage / width: 97.951% / 70.01
**Stage 3:**
  - N: 253
  - MAE: 13.648
  - RMSE: 16.917
  - Bias: +0.858
  - CRPS: 9.585
  - 50% coverage / width: 50.593% / 24.10
  - 80% coverage / width: 81.818% / 45.79
  - 95% coverage / width: 97.628% / 70.03
**Stage 4+:**
  - N: 2288
  - MAE: 13.750
  - RMSE: 17.077
  - Bias: +1.669
  - CRPS: 9.661
  - 50% coverage / width: 51.399% / 24.10
  - 80% coverage / width: 81.600% / 45.79
  - 95% coverage / width: 96.460% / 70.03

## Evidence provenance

- Run ID: `conditional-v1-20260921-scorecard`
- Scorecard manifest URI: `artifacts/research/data-first-football-v1/historical-scorecards/conditional-v1/runs/conditional-v1-20260921-scorecard/scorecard-manifest.json`
- Scorecard manifest raw SHA-256: `0f4fbf33c27d85b535fb7a6e224f2aee6433ccf76d6a182e0caf85e751a0ba23`
- Entry record: `artifacts/research/data-first-football-v1/forecast-verification/conditional-v1/runs/conditional-v1-20260919-9265314-11a/verification-manifest.json`

---
_This report is conditional historical development evidence only. It is not readiness evidence, 2026 authorization, a V4 comparison, or prospective forecasting permission._
