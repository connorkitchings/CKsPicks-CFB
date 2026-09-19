# V5-11A: Conditional Forecast Verification

- **Status:** Draft
- **Created:** 2026-09-19
- **Planner:** Sol
- **Approval source:** Pending; this contract records future conditional work and is not authorized for execution by the documentation reset.
- **Implementation log:** Pending; create `session_logs/YYYY-MM-DD/NN-v5-11a-conditional-forecast-verification.md` when separately authorized.
- **Commit policy:** Separate verifier-code and Preview-evidence checkpoints; user controls Git operations.

## Goal and entry gate

Independently reconstruct the frozen historical forecast artifact solely to
establish whether a conditional historical scorecard may be calculated. This is
not the full forecast-eligibility closure in [Contract 11](../2026-09-18/11-v5-forecast-verification-closure.md).

Begin only with completed Contract 10A lineage/preflight evidence, these exact
frozen parents, and a recorded list of open foundation limitations:

| Role | Identity |
| --- | --- |
| Repair | `repair-v2-20260909T1417Z` |
| Measurements | `possession-v1-measurements-20260915-18fb0aa-r6` |
| Ratings | `possession-v1-ratings-20260917-d029526-cert` |
| Forecasts | `forecast-v1-20260917-4600ddd-04b` |

All source/output references must be resolved recursively from those manifests.
Development evidence is limited to 2015–2019 and 2021–2025; reject 2020 and
2026 everywhere. The entry record must name the Repair verifier-dependence and
forecast-verification limitations still open at that time.

## Conditional-use boundary

Only a passing verification may create a signed Preview record with permitted
use exactly `conditional_historical_results_only`. That status permits the
V5-only historical scorecard in Contract 12A. It never restores forecast
eligibility; authorizes a 2025 final fit, 2026 replay, live forecast,
production promotion, market comparison, or V4 change; changes the lifecycle
of 04/04B; or satisfies a Contract 06–09 gate.

Every record and readable report must name the four frozen identities above,
their exact parent/output hashes, and every unresolved limitation. Conditional
historical results are development evidence, never prospective evidence.

## Scope, interfaces, and allowed writes

Build a verifier from generic storage readers, schema contracts, and signing
utilities. It must not import the forecast producer or call producer
computations. Independently load exact parents and outputs; reconstruct offsets,
features, fitted heads, calibration, and horizon selection under frozen rules;
then compare every required stored output, digest, count, and selection record.

On a pass, write only a signed Preview verification record and terminal manifest
under:

```text
artifacts/research/data-first-football-v1/forecast-verification/conditional-v1/runs/<run-id>/
```

The terminal manifest is written last and carries
`permitted_use: conditional_historical_results_only` and
`production_activation_authorized: false`. No catalog, Neon, production, web,
V4, market, parent-artifact, or model/configuration writes are allowed.

If any reconstruction comparison fails, preserve all historical artifacts and
publish verification-failure evidence only. Do not calculate or publish any
scorecard values. A changed computation requires a separately approved
corrective contract and a fresh artifact identity.

## Tasks and acceptance criteria

1. Verify manifest signatures, identity, raw/canonical hashes, schema, row
   counts, parent references, and rejected seasons before decoding data.
2. Independently reconstruct every stored forecast computation and compare all
   required partitions and compact outputs exactly.
3. Add positive and negative tests for wrong parents, missing datasets,
   corrupted outputs, chronological leakage, and producer-only perturbations.
4. Run a clean, evidence-bound Preview verification; independently re-read its
   signed outputs and require an idempotent repeat.

The contract passes only when all comparisons and negative tests pass and the
independent re-read agrees exactly. A mismatch is a valid failure record, not a
partial pass and not permission for Contract 12A.

## Definition of done and amendments

- [ ] 10A lineage/preflight evidence and exact frozen parents are reverified.
- [ ] Independent reconstruction compares every required forecast output.
- [ ] Required negative tests and a positive frozen fixture pass.
- [ ] Signed Preview evidence is independently re-read and idempotent.
- [ ] The evidence states `conditional_historical_results_only`, all frozen
  identities/hashes, and open limitations.

This contract does not replace Contract 10B or full Contract 11. Changes to the
design, sources, artifact identities, conditional-use boundary, or comparison
scope require an approved amendment before execution.
