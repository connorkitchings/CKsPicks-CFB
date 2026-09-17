# Session: V5-04 Execution Decomposition Planning

## TL;DR
- **Worked On:** Decomposed the approved V5-04 contract into two dependency-ordered execution contracts.
- **Outcome:** Draft 04A covers offsets, bridge registry, horizon tournament, and no-write evidence. Draft 04B covers calibration, freeze, immutable materialization, independent verification, idempotency, and certification. User approved the decomposition on 2026-09-17; 04A is Approved for Terra, 04B stays Draft.
- **Plan Contracts:** `docs/plans/2026-09-17/01-v5-forecast-offsets-bridge-and-horizons.md` (Approved) and `docs/plans/2026-09-17/02-v5-forecast-calibration-and-certification.md` (Draft).
- **Approval / Status:** User approved the decomposition on 2026-09-17. 04B is dependency-blocked until 04A is implemented, validated, committed, and has reviewed deterministic preflight evidence.
- **Blockers:** None for planning. 04B implementation is blocked on 04A completion.
- **Next:** Open a fresh Terra task with the repository-local `implement-plan` skill and the exact 04A path.

## Context and Decisions
- The split follows the 03A/03B precedent: the boundary is the complete deterministic no-write preflight, not an intermediate model artifact.
- Calibration, freeze, immutable publication, and independent verification stay together in 04B so a partial artifact cannot be mistaken for a certified candidate.
- Investigation confirmed the R6 scoring ledger carries the needed categories (`regulation_non_offense` 4,475 events; `period_class` regulation/OT; per-event team + schedule participants for for/against). No forecast/calibration/horizon code exists yet.
- The 04 producer may reuse sealed 03 replay machinery with horizon-bounded fitting inputs; only the 04B verifier must be independent. Trajectories stay continuous; only fitted parameters vary by horizon.
- The split changes no V5-04 source, registry, fold, gate, schema, or production boundary.

## Work Completed
- Authored both full execution contracts and linked them from the approved umbrella V5-04 contract.
- Flipped 04A Draft → Approved with approval source; 04B remains Draft per the dependency gate.
- Verified ledger category availability with a read-only Preview R2 query (78,418 scoring events, 10 partitions).

## Files Modified
- `docs/plans/2026-09-17/01-v5-forecast-offsets-bridge-and-horizons.md` — new, Approved.
- `docs/plans/2026-09-17/02-v5-forecast-calibration-and-certification.md` — new, Draft.
- `docs/plans/2026-09-13/04-v5-forecast-bridge-and-fitting-window.md` — execution-decomposition section + approval record.
- `session_logs/2026-09-17/01-v5-04-execution-decomposition-planning.md` — this log.

## Validation
- [x] `uv run mkdocs build --quiet`
- [x] `git diff --check`

## Amendments and Blockers
- None. This is a mechanical execution decomposition under the approved umbrella contract.

## Handoff Notes
- **Resume at:** Open a fresh Terra task and implement only `docs/plans/2026-09-17/01-v5-forecast-offsets-bridge-and-horizons.md` with the repository-local `implement-plan` skill. Do not begin 04B work in that task.
- **Watch out for:** The 24.2M-row R6 adjusted history plus the full 03 replay under two horizons is the costliest computation in the program; the contract mandates partition streaming and reuse of 03's fitted-parameter replay inputs.

**tags:** ["v5", "forecasting", "planning", "horizons", "calibration"]
