# R1 Full-Corpus Recapture and Certification

- **Status:** In Progress
- **Created:** 2026-08-27
- **Planner:** Sol
- **Approval source:** User explicitly authorized implementation of the exact
  full-corpus successor-v2 plan in Codex on 2026-08-27.
- **Implementation log:**
  `session_logs/2026-08-27/13-r1-full-corpus-recapture-and-certification.md`
- **Commit policy:** Separate plan commit required before implementation.

## Goal

Recapture the complete successor-v2 historical corpus directly from CFBD for
2015–2019 and 2021–2025 without altering legacy projections, then publish an
immutable, run-scoped, coverage-certified R1 foundation. Observable success is
one exact ref set that passes every historical coverage and lineage gate and
authorizes R2 while leaving V4, candidate v1, and prior artifacts unchanged.

## Current State

The committed weekly play-capture hardening at `2c7018d` provides bounded,
resumable play requests and migration `0009`, but the active operation captures
only 2015–2018, imports the 2019 archive, reuses 2021–2025 refs, and can update
legacy compatibility projections. Historical Silver discovery is exact only
for manifest-backed plays. Measurement and state configs remain pinned to the
old 2021–2025 Phase artifacts.

Preview R2 source/destination credentials and CFBD credentials are configured.
Migration `0009` was applied through the isolated Preview environment after
verifying distinct Preview and migration credentials, and the 2015 Week 1
probe returned exactly 15,369 plays. On 2026-08-27, the automatic comparison
bootstrap correctly stopped before capture because the Preview catalog had no
validated 2019 legacy artifacts. Its immutable terminal report is
`artifacts/research/rating-successor-v2/r1/r1-full-corpus-20260827-95b0456/comparison-ref-set.failure.json`.
The approved exact legacy-2019 comparison restoration is now complete and
automatic preflight freezes it as comparison-only evidence. The active run is
`r1-full-corpus-20260828-929f331`, bound to code SHA `929f331`; it is
recapturing all ten permitted seasons directly from CFBD and has entered the
2015 play stage. Earlier partial runs and their immutable artifacts are
diagnostic-only because their code identity differs. No substitute evidence
may be selected.

## Proposed Approach

Use one committed, Preview-only R1 run identity across all ten permitted
seasons. Capture every source as immutable Bronze observations without calling
legacy `ingest_data()`. Close a run-scoped source manifest only after every
request verifies, then build all Silver and derived refs exclusively from that
manifest. Rebuild true-PPSO measurements and baseline states under new
successor-v2 identities and derive coverage evidence from the exact artifacts.

Previous 2019 and 2021–2025 refs remain comparison evidence. They never become
parents of the authoritative successor-v2 corpus.

## Scope

### Included

- Preview migration `0009`, abandoned-run reconciliation, and read-only sample verification.
- Capture-only teams, games, venues, game statistics, and weekly plays for all ten seasons.
- Exact source/derived manifests, Silver, byplay, drives, reconciliation, measurements, states, coverage, and cross-lineage audit.
- Operational runbook, tests, and deterministic recovery.

### Excluded

- 2020, 2026 outcomes, markets, production writes, V4/candidate-v1 changes, and R2–R4 evaluation.
- Any overwrite of `raw/*`, existing refs, bundles, Neon activation, or publication state.

## Affected Components and Contracts

- `prepare-rating-history` becomes policy-driven for all successor-v2 seasons and capture-only for every entity.
- A versioned `successor-history-source-set-v2` binds pipeline ID, code/config/policy SHAs, exact requests, captures, checksums, rows, game coverage, and attempt evidence.
- Historical Silver accepts an exact source-set manifest; broad catalog discovery is forbidden in this path.
- A run-scoped derived ref set exposes games, outcomes, plays, team stats, teams, venues, byplay, drives, reconciled team game, and source reconciliation by season.
- New measurement/state configurations cover exactly 2015–2019 and 2021–2025 under `artifacts/research/rating-successor-v2/r1/<run-id>/`.
- Certification computes coverage evidence from immutable refs; caller-authored coverage JSON is removed from the authoritative interface.

## Implementation Tasks

### Task 1 — Seal the Preview runtime and capture identity

**Changes:**

- Verify R2 backend, Preview/source credentials, CFBD credentials, and distinct Preview/production Neon URLs without exposing values.
- Apply migration `0009` only to Preview after the implementation commit.
- Bind the R1 pipeline record and every capture set to code SHA, capture/config SHA, season-lineage SHA, and the original request plan. Reject resume under any changed identity.
- Preserve the controlled 2015 Week 1 / 15,369-play probe and reconcile only the four abandoned 2015 inner runs whose outer pipeline/step are already failed.

**Acceptance criteria:** No capture can start without isolated Preview state; retries reuse only the original plan; no secret or production mutation occurs.

### Task 2 — Generalize capture-only full-corpus ingestion

**Changes:**

- Plan seasons from `successor_v2_season_lineage.yaml`; reject 2020, 2026, missing, duplicate, or extra seasons.
- Add bounded capture-only workers for teams, games, venues, and game statistics. Reuse the weekly sequential play worker for every permitted season.
- Never call `BaseIngester.ingest_data()` or rebuild shared compatibility projections. Successful Bronze captures and catalog rows are the only source writes.
- Run sequentially, record every attempt, stop on the first exhausted request, and resume the same pipeline ID by reusing verified captures.
- Close `successor-history-source-set-v2` only when every request/capture/checksum verifies; incomplete sets remain diagnostic-only.

**Acceptance criteria:** All ten seasons are captured under one identity; a stalled request leaves no running child or partial manifest; tests prove no `raw/*` write.

### Task 3 — Build exact run-scoped Silver and derived refs

**Changes:**

- Resolve every dataset's capture IDs from the completed source manifest, never a provider/season catalog query.
- Build run-scoped Silver and invoke the team-game pipeline with an output ref set so byplay, drives, reconciled team game, and source reconciliation are all addressable.
- Emit a derived ref set with exact season/dataset coverage and immutable parent checksums.
- Compare against existing 2019 and 2021–2025 refs. Fail on conflicting season/team/game identity or final scores; report compatible schema, row, play, and stat revisions.

**Acceptance criteria:** Every derived parent traces to the new source set; old refs remain unchanged and comparison-only; retries are byte-identical or collide closed.

### Task 4 — Rebuild measurements, states, and certification

**Changes:**

- Add successor-v2 true-PPSO measurement and fixed-rho baseline-state configs with the full historical season scope and new research prefix.
- Materialize season-scoped observations, pregame/terminal snapshots, component states, and team states from exact run refs.
- Compute coverage directly: completed games with plays, score-stream reconciliation, representative terminal teams, stable schemas, and key completeness.
- Publish the R1 ref set, cross-lineage report, and coverage report only after all seasons pass 90% play coverage, 94% score reconciliation, 90% representative terminal coverage, stable schemas, and zero 2020 lineage.

**Acceptance criteria:** `tournaments_permitted` is true only when every season passes; otherwise immutable diagnostics exist and R2 remains blocked.

## Testing Strategy

- Unit-test full-season planning, capture-only behavior, identity-bound resume, manifest closure, checksum verification, and 2020 rejection.
- Integration-test timeout/retry, partial failure, exact manifest Silver, byplay/drive refs, cross-lineage conflicts, true-PPSO coverage, and byte-identical reruns.
- Run data/catalog/ops/ratings/V4 boundary regressions, full pytest/coverage, scoped Ruff checks, contracts validation/sync, strict MkDocs, CLI smoke tests, and `git diff --check`.

## Risks and Edge Cases

- Recaptured history is reconstructed evidence observed in 2026 and must never claim historical capture time.
- Provider revisions may differ from old refs. Identity/score conflicts stop; compatible revisions are reported.
- Full capture may span multiple sessions. The same pipeline ID is mandatory; code changes require a new run.
- Calendar pressure cannot weaken coverage or permit partial downstream artifacts.

## Definition of Done

- [ ] Migration and runtime isolation are verified in Preview.
- [ ] Every permitted season has a complete exact source manifest.
- [ ] Run-scoped Silver, derived refs, measurements, states, and audits are immutable and reproducible.
- [ ] All R1 gates pass and `tournaments_permitted` is true, or a terminal failed report exists.
- [ ] Required validation and documentation pass with no V4/production changes.
- [ ] Implementation log is complete and plan status is `Implemented`.

## Amendments

Material changes to capture-only isolation, season scope, source authority,
coverage thresholds, or R2 authorization require a new Sol review.

### Amendment 1 — Automatic comparison-evidence bootstrap (2026-08-27)

The user explicitly authorized R1 to resolve and freeze its own comparison-only
legacy ref manifest from Preview catalog evidence. `--comparison-ref-set-uri`
is now an optional expert override rather than an operator prerequisite. The
preflight requires exact 2019 and 2021–2025 `games`, `game_outcomes`, and
`teams` refs; it excludes successor-v2 paths, rejects ambiguity, includes plays
and team-game stats only for revision diagnostics, and binds the resulting
manifest checksum into R1 source-set lineage. Missing evidence stops before
recapture with a diagnostic.

### Execution Result — Terminal comparison-evidence failure (2026-08-27)

The automatic Preview-catalog preflight found zero validated 2019 legacy
artifacts. It published the immutable failure report named above with a valid
checksum and stopped before creating any successor source-capture child run.
This is an expected fail-closed contract outcome, not authority to substitute
or recapture comparison evidence. R2 remains blocked.
