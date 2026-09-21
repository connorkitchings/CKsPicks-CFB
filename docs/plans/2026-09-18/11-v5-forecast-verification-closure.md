# V5-11: Forecast Verification Closure

- **Status:** Draft
- **Created:** 2026-09-18
- **Planner:** Sol
- **Approval source:** Pending; this contract does not authorize research execution.
- **Implementation log:** Pending; create `session_logs/YYYY-MM-DD/NN-v5-forecast-verification-closure.md` when authorized.
- **Commit policy:** Separate code and certified-evidence checkpoints; user controls Git operations.

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
