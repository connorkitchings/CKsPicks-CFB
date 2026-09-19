# V5-10B: Historical Foundation Audit — Findings Report

**Date:** 2026-09-19  
**Run ID:** `historical-audit-10b-20260919-full`  
**Code SHA:** `7a476648227b61d7eb17f2707e44104f4a752fe4`  
**Manifest URI:** `artifacts/research/data-first-football-v1/audits/historical-foundation-v1/runs/historical-audit-10b-20260919-full/audit-manifest.json`  
**Manifest SHA-256:** `0a95002ce42c28d2d588e3c6a0d327adbe95f95e0232ab16036ff8b6967aabe3`  
**Evidence SHA-256:** `edeebe85498f2b7935c3f03a31dde03cc44d08876ded45f8c8c42b7a67e84d42`

---

## Summary

The full-corpus historical-foundation audit is **complete and published** to the Preview
audit prefix. The publication is valid (independent verifier confirmed `publication_valid:
true`). All four findings are open blockers; Contract 11 is **not permitted** to start
until blockers are resolved. Contract 10 is **complete**: every finding has a severity,
disposition, `closure_state`, and closure criterion.

| Item | Value |
|---|---|
| Total checks | 93 |
| Failed checks | 3 |
| Total findings | 4 |
| Elapsed (dry run) | 504.5s |
| `finalized` | `true` |
| `production_activation_authorized` | `false` |
| `overall_disposition` | `prohibited_until_closed` |
| `contract11_permitted` | `false` |
| Publication valid | ✅ Yes |
| Idempotent repeat | ✅ `already_applied` |

---

## Corpus Scale

| Dataset | Rows |
|---|---|
| Adjusted history | 24,223,998 |
| Rating states | 2,144,400 |
| Team states | 1,072,200 |
| Bridge (forecast) | 758,160 |
| Possessions | 316,257 |
| Observations | 285,952 |
| Priors | 270,540 |
| Snapshots | 142,960 |
| Terminal | 8,580 |
| Measurement population | 8,936 |
| Forecast predictions | 7,318 |
| Scoring events | 78,418 |

Development seasons: 2015–2019 and 2021–2025 (2020 excluded).

---

## Findings

### Finding 001 — Repair v2 verification imports producer computation

- **finding_id:** `audit-structural-001`
- **check_id:** `independence.repair.boundary`
- **severity:** `blocker`
- **disposition:** `prohibited_until_closed`
- **closure_state:** `open`
- **affected_stages:** `[repair]`
- **description:** `scripts/research/verify_data_first_repair_v2.py` imports and calls
  producer compute from `scripts/research/run_data_first_repair_v2.py`, so Repair v2 does
  not meet the independent-reconstruction standard.
- **required_action:** Separate Repair verification from producer computation under a new
  identity through an approved corrective contract, then re-audit.
- **closure_criteria:** An independently reconstructed Repair verification passes the
  import boundary and behavioral matrix.
- **blocking_dependencies:** None.

### Finding 002 — Forecast verification does not reconstruct stored outputs

- **finding_id:** `audit-structural-002`
- **check_id:** `forecast.verification.reconstruction`
- **severity:** `blocker`
- **disposition:** `historical_evidence_only`
- **closure_state:** `open`
- **affected_stages:** `[forecasts]`
- **description:** `src/cks_picks_cfb/forecast/forecast_verification.py` validates
  manifest metadata and reference labels but never reads or reconstructs the stored
  forecast outputs, offsets, bridge fits, calibration, or selection.
- **required_action:** Close the forecast computation gap in Contract 11 with independent
  reconstruction of offsets, fits, calibration, and selection.
- **closure_criteria:** Contract 11 records signed verification of reconstructed outputs.
- **blocking_dependencies:** `[contract-11]`

### Finding 003 — Score-ledger excess keys across all development seasons

- **finding_id:** `audit-ledger-score_reconciliation-1de3aaaf7d`
- **check_id:** `corpus.ledger.score_reconciliation`
- **severity:** `blocker`
- **disposition:** `prohibited_until_closed`
- **closure_state:** `open`
- **affected_stages:** `[measurements]`
- **affected_artifacts:**
  - `artifacts/research/data-first-football-v1/possession-v1/measurements/runs/possession-v1-measurements-20260915-18fb0aa-r6/measurement-manifest.json`
  - `artifacts/research/data-first-football-v1/repair/v2/runs/repair-v2-20260909T1417Z/repair-manifest.json`
- **description:** 81 team-game keys across all development seasons record more ledger
  points than their repaired final score. Ledger points must never exceed a repaired
  final; shortfalls (2,725 keys) are separately reported and expected for possession
  sub-sequence filtering.
- **excess_by_season:** 2015: 4, 2016: 2, 2017: 2, 2018: 3, 2019: 1, 2021: 12, 2022: 13,
  2023: 13, 2024: 14, 2025: 17 (total: 81)
- **excess_keys_sha256:** `b72f18e1236e01f42d9a5d9b90db6d3d4b0f167de19b59a8f1bd7565801741ed`
- **example_keys:** `(2015, 400603867, Kentucky)`, `(2015, 400763563, Illinois)`,
  `(2015, 400763611, Incarnate Word)`, `(2015, 400763616, Marshall)` … (8 examples
  in evidence record)
- **required_action:** Approve a corrective contract that repairs the defect and replaces
  the affected evidence under a new identity, or record renewed evidence that the
  observation is benign.
- **closure_criteria:** The check passes on renewed evidence, or a corrective contract
  closes the finding with a recorded disposition.
- **blocking_dependencies:** None.

### Finding 004 — No through-2025 final forecast fit exists

- **finding_id:** `audit-forecast-final_fit_existence-b1bc852294`
- **check_id:** `corpus.forecast.final_fit_existence`
- **severity:** `blocker`
- **disposition:** `historical_evidence_only`
- **closure_state:** `open`
- **affected_stages:** `[forecasts]`
- **affected_artifacts:**
  - `artifacts/research/data-first-football-v1/forecasts/runs/forecast-v1-20260917-4600ddd-04b/forecast-manifest.json`
- **description:** The current forecast artifact has `max_training_season=2024`. A
  complete through-2025 final fit does not exist and is not reproducible from the
  current artifact.
- **required_action:** Approve a corrective contract that repairs the defect and replaces
  the affected evidence under a new identity, or record renewed evidence that the
  observation is benign.
- **closure_criteria:** The check passes on renewed evidence, or a corrective contract
  closes the finding with a recorded disposition.
- **blocking_dependencies:** None (but closing this finding is part of Contract 11 scope).

---

## Gate Evaluation

| Gate key | Value | Meaning |
|---|---|---|
| `contract11_permitted` | `false` | Open blockers prevent Contract 11 from starting |
| `upstream_blocker_open` | `true` | Findings 001 and 003 are upstream blockers |
| `forecast_findings_pending` | `true` | Findings 002 and 004 are forecast blockers |

**Publication validity** (manifest–verifier agreement) and **Contract 11 gate** (finding
closure) are separate decisions. This publication is valid. Contract 11 may not start.

---

## Verification Record

```
verified:           true
publication_valid:  true
manifest_sha256:    0a95002ce42c28d2d588e3c6a0d327adbe95f95e0232ab16036ff8b6967aabe3
run_id:             historical-audit-10b-20260919-full
checks:             93
failed_checks:      [corpus.forecast.final_fit_existence,
                     corpus.ledger.score_reconciliation,
                     independence.repair.boundary]
findings:           4
```

Idempotent repeat: `state: already_applied` on full identity + digest + output-hash match.

---

## Permitted Use

The published audit evidence is `prohibited_until_closed` overall. It may be used as:

- Historical evidence of the audit's findings and the corpus population counts.
- The entry gate record for Contract 11 (once blockers are resolved).
- Supporting documentation for corrective contracts.

It may **not** be used for:

- Any production activation, forecast eligibility, or 2026 application.
- Clearing the Contract 11 entry gate before all four findings have `closure_state:
  closed` or `incorporated_into_contract_11`.

---

## Next Steps

| Priority | Action |
|---|---|
| 1 | **Corrective contract for Finding 003** (score-ledger excess): diagnose whether the 81 excess keys are a Repair data defect or a measurement attribution error; repair under a new artifact identity |
| 2 | **Corrective contract for Finding 001** (Repair verifier independence): reconstruct Repair verification without importing the producer |
| 3 | **Contract 11** (Forecast verification closure): independently reconstruct offsets, bridge fits, calibration, and selection; closes Findings 002 and 004 |
| 4 | **Contract 12** (Historical results + readiness review): after all blockers closed and Contract 11 complete |

_Generated: 2026-09-19 | Contract: `docs/plans/2026-09-18/10b-v5-full-corpus-audit-execution.md`_
