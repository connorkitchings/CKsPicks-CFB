# V5-11: Forecast Verification Closure

- **Status:** Implemented
- **Created:** 2026-09-18
- **Planner:** Sol
- **Approval source:** Original: pending. Decomposition authorized by the user on 2026-09-21 ("Ok, let's plan out the final steps of phase 11. Let's do it all"); executes via sub-contracts 11B/11C/11D (`docs/plans/2026-09-21/03-`, `04-`, `05-`).
- **Implementation log:** `session_logs/2026-09-21/06-v5-contract-11-decomposition-planning.md` (planning); `session_logs/2026-09-21/07-v5-11b-ratings-r9-rebuild.md`, `08-v5-11c-forecast-bridge-and-final-fit.md`, `09-v5-11d-forecast-verification-and-finding-closure.md` (execution).
- **Commit policy:** Separate code and certified-evidence checkpoints; user controls Git operations.
- **Closure record (2026-09-21):** Findings 002/004 closed. Finding 002: signed Preview verification record `artifacts/research/data-first-football-v1/forecasts/runs/forecast-v1-20260921-5afd577-11c/verification/verifier-manifest.json` (raw SHA `4cfe5ef8...`) reconstructing all six outputs including final-fit rows bit-exactly. Finding 004: targeted `corpus.forecast.final_fit_existence` pass (`max_training_season=2025`) on the 11C artifact. Contracts 04/04B return to Implemented via this decomposition; the original 04B artifact remains frozen historical evidence.

## Goal and entry gate

Close the independent computational-verification gap for historical V5 forecasts.
Begin only after Contract 10 resolves the forecast-related audit findings or an
approved amendment incorporates them. The existing forecast artifact remains
historical evidence; it cannot regain downstream eligibility until this contract
passes its full definition of done.

## Scope and allowed writes

Use the exact Repair, R6 measurement, and retained-rating parents. Independently
load parents and output datasets; reconstruct non-offense offsets, feature
frames, bridge fits, uncertainty calibration, and horizon selection; then compare
all required stored partitions and compact outputs. Verifier code must not import
forecast-producer modules. Write only a new signed Preview verification record.
Do not overwrite artifacts, tune the design, change V4, or write to production,
Neon, catalog, or web.

## Tasks

1. Implement independent source loading and reconstruction for every declared
   parent and forecast output.
2. Compare stored records, digests, row counts, selected heads/horizon, bridge
   parameters, calibration variances, and selection evidence exactly.
3. Add failure tests for missing datasets, corrupted outputs, wrong parents,
   chronological leakage, and producer perturbations, plus a positive bit-exact
   fixture using real output shapes.
4. Run a new evidence-bound verification against the existing artifact. If a
   recomputation changes any outcome, preserve the existing artifact and create
   a fresh identity only through an approved corrective contract.

## Acceptance and validation

The verifier reconstructs rather than trusts stored forecast outputs, rejects
all required negative cases, and records signed Preview evidence. Only then may
Contracts 04/04B return to `Implemented`; otherwise they remain `In Progress`.
Run focused tests, relevant full tests, scoped lint, strict MkDocs, and
`git diff --check`.

## Definition of done and amendments

- [ ] Contract 10 forecast findings are closed or approved into this contract.
- [ ] All parents and forecast outputs are independently reconstructed.
- [ ] Negative and positive reconstruction tests pass.
- [ ] Signed verification evidence records the exact result and artifact use.
- [ ] 04/04B lifecycle is updated only if all requirements pass.

Any design change, repaired historical computation, or artifact replacement
requires a new identity and an approved amendment before execution.

## Amendment 1 — Conditional historical-results lane (2026-09-19)
This Draft contract remains the full forecast-eligibility closure. It begins
only after completed 10B resolves forecast findings or formally incorporates
them, and it is the only contract that can return 04/04B to `Implemented`.
Implemented [11A](../2026-09-19/11a-v5-conditional-forecast-verification.md)
is a separate, earlier conditional reconstruction for
`conditional_historical_results_only`. A successful 11A does not alter this
contract's lifecycle, entry gate, verification scope, or 2026 restrictions.

## Amendment 2 — r9 descendant re-derivation and 11B/11C/11D decomposition (2026-09-21)

**Reason:** The corrective rebuild certified `possession-v1-measurements-20260921-r9`
and closed Findings 001/003, superseding the R6 measurement parent this contract
originally named. Contract 02's diagnosis requires r9-derived descendants in the
full lane; the existing rating and forecast artifacts descend from R6 and cannot
regain eligibility by verification alone. Findings 002/004 are incorporated into
Contract 11 by design (002 is explicitly Contract-11 scope).

**Original approach:** Verify the existing forecast artifact against the exact
Repair, R6 measurement, and retained-rating parents in one execution.

**Revised approach:** Execute full Contract 11 as three sequential sub-contracts:
11B (ratings rebuild from r9, `docs/plans/2026-09-21/03-...`), 11C (forecast
bridge rebuild from the new ratings plus the through-2025 final fit,
`docs/plans/2026-09-21/04-...`), 11D (independent verification of all
computations including the final fit, plus targeted closure of Findings 002/004,
`docs/plans/2026-09-21/05-...`). Closure uses signed Preview verification plus
targeted audit-check re-runs (the 001/003 precedent); no full 93-check re-audit.
A renewed full-corpus audit publication (to flip a published
`contract11_permitted` flag) is explicitly deferred to Contract 12 planning.

**Impact:** This umbrella contract closes when 11D lands and Findings 002/004
close; it then restores the 04/04B blocker via the decomposition record. The
original Phase 4B retained manifest remains prohibited as a forecasting parent;
11A/12A/10B evidence and the 04B artifact stay frozen historical records.
