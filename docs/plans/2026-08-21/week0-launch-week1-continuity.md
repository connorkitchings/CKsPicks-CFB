# 2026 Week 0 Launch and Week 1 Continuity

- **Status:** In Progress
- **Created:** 2026-08-21
- **Planner:** Sol
- **Approval source:** User explicitly approved and requested implementation of this plan in the current task on 2026-08-21.
- **Implementation log:** `session_logs/2026-08-21/01-week0-launch-week1-continuity.md`
- **Commit policy:** Commit with implementation; git operations remain user-controlled.

## Goal

Preserve the approved Week 0 soft launch while making postgame scoring fail
closed and producing fresh, point-in-time-correct Week 1 features and route
assignments. Success means canonical Week 0 data can be ingested from CFBD's
provider Week 1, partial finals cannot score a run, the weekly pipeline can
prepare immutable Week 1 Gold, and Preview readiness/publish can prove the
transition before any production Week 1 expansion.

## Current State

- Production is healthy in fail-closed market mode with active run
  `2026w0-55de0317120d` and 8/8 predicted/lined coverage.
- The repository is clean on `main`; 361 tests and current CI pass.
- Markets map canonical to provider weeks, but plays and game stats do not.
- `close-week` scores mutable `raw/games` rows by week and can publish a
  partially scored run.
- The latest live `point_in_time_matchups` has all 2026 Week 1-4 rows routed as
  preseason with zero current-season features.
- R2 is authoritative and immutable; Neon is the catalog/control plane and
  derived serving database. No operation may use a project-local `./data/`.

## Proposed Approach

Make canonical-week resolution a shared ingestion behavior, bind scoring to an
immutable outcomes reference and the frozen run's exact game set, and add a
resumable `prepare-week` operation that rebuilds cumulative 2026 Silver and
Gold from explicit captures. Add target-week freshness/routing checks before
publication and retain the frozen V4 historical baseline/model lineage.

## Scope

### Included

- Canonical-week plays/game-stats ingestion.
- Complete, immutable outcome-bound scoring with auditable cancellation waivers.
- `prepare-week` CLI/Make workflow through a Preview-ready Week 1 dataset.
- Live Gold freshness/routing validation.
- Numeric edge explanation, publication tests in CI, and current runbook/roadmap updates.

### Excluded

- Executing future production publishes, freeze, Vercel mode changes, Week 0
  close, or Week 1 production scope expansion without the required live timing
  and user approvals.
- Pick'em submission, new model selection, established-route tournament, or
  calibrated uncertainty.
- Database migrations.

## Affected Components and Contracts

- Weekly ingesters and canonical week policy under `src/cks_picks_cfb/data/`
  and `scripts/data/ingest_week.py`.
- Ops orchestration, preflight/audits, scoring, and feature builders under
  `src/cks_picks_cfb/ops/` and `scripts/pipeline/`.
- `make prepare-week YEAR=... WEEK=... AS_OF=... ENV=...`.
- Scored artifact manifest v2, with immutable outcome lineage and waivers.
- Prediction-mode web copy and CI publication-boundary coverage.

## Implementation Tasks

### Task 1 — Canonical weekly ingestion

- Resolve the requested canonical week against the checked-in policy and raw
  schedule, query every required provider week, and filter plays/game stats to
  the exact canonical game IDs.
- Preserve ordinary-season behavior when canonical and provider weeks match;
  record canonical/provider metadata in source captures.
- Add focused Week 0/provider Week 1 tests.

### Task 2 — Fail-closed scoring

- Build/use an explicit immutable `game_outcomes` ref in `close-week` and pass
  it to scoring with the frozen run's exact game IDs.
- Reject missing or non-final outcomes before writing a scored artifact or
  changing run state. Allow only explicit game-ID/reason cancellation waivers;
  waived games receive no grades.
- Publish scored-manifest v2 with result URI/checksum/version/capture lineage
  and waiver metadata; retain legacy/manual fallback outside the ops path.

### Task 3 — Resumable Week 1 preparation

- Add `prepare-week` to ops and Make with explicit year, target week, cutoff,
  environment, and resumable run ID support.
- Ingest completed 2026 sources, build cumulative 2026 Silver games/outcomes/
  plays/team-game stats, reconcile team-game data, combine 2021-2026 history,
  and rebuild temporal/core/model-ready Gold with 2026 inference-only.
- Use run-scoped immutable refs and the frozen historical baseline lineage;
  do not rerun selection.

### Task 4 — Readiness and snapshot guards

- Require target-week Gold rows, freshness relative to completed outcomes,
  independently correct completed-game counts/regimes, and current features
  for teams with prior completed games.
- Make stale Gold fail readiness and `publish-week` before prediction or
  activation.

### Task 5 — Launch UI, CI, and operations docs

- Explain that numeric edge is model-market disagreement magnitude, not
  confidence or expected profit; do not add qualitative bands or thresholds.
- Run publication-boundary tests in CI.
- Remove stale hardcoded active-run claims from current operational docs and
  record the live health endpoint as the authority.

## Testing Strategy

- Unit tests cover canonical/provider mapping, exact game filtering, complete
  and partial finals, cancellation waivers, checksums, idempotency, byes,
  route transitions, future leakage, stale Gold, and state-machine resume.
- Run the full Python suite, Ruff format/lint, contracts validation, MkDocs,
  web lint/typecheck/publication tests/build, and `git diff --check`.
- Preview live execution is deferred until Week 0 is complete; the code-level
  definition of done includes a fixture-backed Week 1 transition rehearsal.

## Risks and Edge Cases

- Canonical Week 0 and canonical Week 1 can share CFBD provider Week 1, so
  every weekly source must filter by exact canonical game IDs.
- Byes route by the less-experienced team and cannot be inferred from week
  number alone.
- Postponed games remain incomplete; canceled games require explicit waivers.
- Immutable refs must be run-scoped so retries cannot overwrite another run.
- No production state or Vercel publication mode changes are authorized here.

## Definition of Done

- [ ] Canonical Week 0 weekly ingestion is tested for all weekly sources.
- [ ] Partial results cannot create or publish a scored run.
- [ ] `prepare-week` produces validated Week 1-ready Gold in fixture/integration tests.
- [ ] Stale or incorrectly routed Gold blocks readiness and publish.
- [ ] Edge explanation and CI publication tests are present.
- [ ] Full validation passes and documentation/session log are updated.
- [ ] Plan status is updated to `Implemented`.

## Amendments

None.
