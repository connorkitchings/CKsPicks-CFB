# R1 Manifest-Declared Play-Coverage Remediation

- **Status:** In Progress
- **Created:** 2026-08-28
- **Planner:** Sol
- **Approval source:** User approved the proposed R1 remediation in Codex on 2026-08-28 ("go").
- **Implementation log:** `session_logs/2026-08-28/02-r1-manifest-declared-play-coverage-remediation.md`
- **Commit policy:** Separate plan and implementation commits; user executes Git operations.

## Goal

Allow the successor-v2 R1 pipeline to represent explicitly recorded CFBD play omissions as coverage loss rather than fabricated or silently accepted data, then complete a fresh full-corpus R1 certification. Observable success is a passing immutable coverage report with `tournaments_permitted: true`, or a terminal diagnostic report if any existing R1 threshold fails.

## Current State

The Preview run `r1-full-corpus-20260828-929f331` completed Bronze capture for 2015–2019 and 2021–2025 and closed its exact source-set manifest. Its first derived build stopped in 2015 because seven completed games have no play-derived team rows. The exact play-capture manifest declares those same seven game IDs as CFBD omissions, giving 717 of 724 completed games (99.03%) with plays. R1 policy requires at least 90% play coverage, but the shared builder currently treats every missing team-game row as a blocking conflict before R1 coverage certification can apply its threshold.

The failed run and all of its artifacts remain immutable diagnostic evidence. R2 is blocked until a new R1 coverage report permits tournaments.

## Proposed Approach

Keep the shared reconciliation strict by default. Add an opt-in, manifest-bound exception only for R1: a completed game with zero team-game rows is `incomplete_source` and nonblocking only when its ID is listed in the exact season's immutable play-capture manifest. The normal R1 certification computes the resulting coverage from immutable refs and enforces the existing 90% gate.

The code change creates a new R1 code identity, so the corrected execution uses one fresh Preview run ID and recaptures every permitted season. It never uses the failed run's source set as an authoritative parent.

## Scope

### Included

- Manifest parsing and validation for declared missing CFBD play game IDs.
- An opt-in team-game builder interface and R1-only orchestration wiring.
- Reconciliation and pipeline tests, then a fresh full R1 Preview run through certification and deterministic rerun verification.
- Contract/index/session-log updates.

### Excluded

- Changes to the 90% R1 play-coverage threshold, score-reconciliation or terminal-team gates, CFBD captures, historical labels, or source authority.
- 2020 or 2026 outcomes; V4, candidate v1, markets, Neon production, publication, and R2–R4 execution.

## Affected Components and Contracts

- `reconcile_completed_games()` gains an optional, explicit allowlist for zero-row games; absent an allowlist it retains current strict behavior.
- `scripts/pipeline/build_team_game_dataset.py` accepts an optional `--play-capture-manifest-uri`, validates the manifest, and passes its exact declared omissions to reconciliation.
- `prepare-rating-history` supplies the corresponding per-season manifest only to successor R1 derived builds.
- The successful corrected run must still satisfy `conf/ratings/successor_v2_season_lineage.yaml` and the existing R1 certification interface unchanged.

## Implementation Tasks

### Task 1 — Add manifest-bound incomplete-source reconciliation

**Files:**

- `src/cks_picks_cfb/data/reconciliation.py`
- `scripts/pipeline/build_team_game_dataset.py`

**Changes:**

- Parse all `missing_game_ids` from the manifest's request entries; require a complete play-capture manifest for the supplied season, reject malformed, duplicate, out-of-scope, or extra-game evidence.
- Classify a zero-row completed game as nonblocking `incomplete_source` only when listed in that validated manifest allowlist. Preserve its game ID and manifest-bound reason in reconciliation details.
- Keep one-row, unexpected zero-row, team identity, final-score, and team-stat metric conflicts blocking. Do not change callers that omit the new manifest argument.

**Acceptance criteria:**

- The seven 2015 recorded omissions no longer block the derived build.
- An undeclared missing game still fails closed.
- Production/V4 behavior is unchanged with no manifest argument.

### Task 2 — Wire the exception only into R1

**Files:**

- `src/cks_picks_cfb/ops/__main__.py`

**Changes:**

- Pass `captures/<season>/plays.json` into only the successor R1 `build_team_game_dataset.py` invocations.
- Retain the complete source-set and all existing identity, preview-isolation, capture-only, and no-`raw/*` guards.

**Acceptance criteria:**

- Every successor season is bound to its own run-scoped capture manifest.
- No non-R1 operation receives the opt-in exception.

### Task 3 — Validate and rerun R1 under a fresh identity

**Changes:**

- Commit the implementation before any R1 data operation; use a fresh `r1-full-corpus-...` Preview run ID.
- Recapture all permitted seasons, build exact Silver/derived refs, measurements, states, cross-lineage evidence, and certification.
- Run the identical invocation once more to verify immutable, byte-identical recovery.

**Acceptance criteria:**

- Certification writes `tournaments_permitted: true` only if all existing R1 gates pass. Any failed gate produces diagnostics and leaves R2 blocked.

## Testing Strategy

- Unit-test declared versus undeclared zero-row games, partial rows, malformed manifests, duplicated IDs, and unchanged strict defaults.
- Test R1 orchestration passes the exact per-season manifest; test other builder callers do not.
- Reconstruct 2015 from the failed immutable evidence and assert 724 completed games, 717 covered games, and exactly the seven manifest-declared omissions.
- Run focused data/ops/ratings tests, full pytest and coverage, Ruff, contract validation/sync, strict MkDocs, CLI smoke checks, and `git diff --check`.

## Risks and Edge Cases

- A manifest exception must never hide an unexpected loss of provider data; it applies only to declared zero-row games and certification remains the coverage authority.
- A code change requires a fresh capture identity. Earlier artifacts are not inputs to the corrected R1 lineage.
- Missing play rows must not be imputed from game results or team statistics.

## Definition of Done

- [ ] Strict-default and R1 opt-in behavior are implemented and tested.
- [ ] A fresh full-corpus Preview R1 run reaches immutable certification.
- [ ] Certification permits R2, or an immutable terminal report explains the failing existing gate.
- [ ] The exact rerun is verified and required validation passes.
- [ ] Documentation and session log are updated; this plan is `Implemented`.

## Amendments

Material changes to the source allowlist, coverage thresholds, source-parent rules, or R2 authorization require a new Sol review.
