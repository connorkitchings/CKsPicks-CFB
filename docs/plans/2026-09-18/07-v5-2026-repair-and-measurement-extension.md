# V5-07: 2026 Repair and Possession Measurement Extension

- **Status:** Approved
- **Created:** 2026-09-18
- **Planner:** Sol
- **Approval source:** User approved the three-contract 2026 extension plan on 2026-09-18 with decisions: Repair extension (not V4-Silver-direct), three layered contracts, full season from Week 0. Implementation explicitly deferred.
- **Implementation log:** Pending; create one log per execution session (measurement preflight/apply/verify/repeat).
- **Commit policy:** Separate code and certified-evidence checkpoints; user executes Git.

## Goal, current state, and entry gate

Extend the certified V5 measurement lineage to live 2026 data so downstream
rating replay (08) and forecasting (09) have eligible parents. The certified R6
parent `possession-v1-measurements-20260915-18fb0aa-r6` covers only 2015–2019
and 2021–2025; readiness for any 2026 slate resolves `schedule` as `missing`
("no schedule rows for 2026"), and Contract 06 cannot collect evidence until
this chain exists. The [common contract](../2026-09-13/v5-ratings-successor-roadmap-and-contracts.md)
is binding.

**Entry gate:** Preview 2026 Silver is synced through the latest completed week
(games, game_outcomes, plays, team_game_stats via the existing `prepare-week`
ops path — fast-path ops task, not this contract). This contract starts only
when 2026 Silver refs for Weeks 0–current exist in Preview R2.

**Historical-first deferral (2026-09-18):** Do not execute this approved
contract until Contracts 10-12 close, the user explicitly accepts the historical
readiness review, and 07 is re-reviewed against the frozen design, exact eligible
artifacts, through-2025 final fit/calibration, prior inputs, and timestamp
provenance. A later `live` timing class does not convert retrospective work into
prospective evidence.

There are no 2026 measurement rows at planning time. Historical R6 rows are not
modified, re-certified, or inherited as 2026 evidence.

## Approach, scope, and interfaces

Produce a new Repair-2026 extension run (new run-ID, preserving the verified
Repair v2 chain) and a new certified 2026 possession measurement manifest (new
run-ID, `live` timing) covering the full 2026 season from Week 0 through the
latest completed week. Admit a `live` timing class for 2026 rows through a
methodology amendment; historical reconstructed-only guarantees stay intact.

Stage: `measurement`. Consume the Preview 2026 Silver refs plus the existing
certified Repair v2 manifest as the historical anchor. Output versioned
`population`, `possessions`, `scoring_events`, `observations`, `snapshots`,
`adjusted_history`, `terminal`, `coverage` datasets for 2026 and a terminal
`measurement-manifest.json` with `production_activation_authorized: false`.
No Neon/production/web writes.

The 2026 measurement manifest becomes the sole eligible measurement parent for
Contract 08. The historical R6 manifest remains the sole eligible parent for
historical replay; neither substitutes for the other.

## Implementation tasks

### Task 1 — Admit `live` timing and extend season validation

Amend the methodology to admit a `live` timing class for 2026 season rows:
source-capture timestamps and effective times substantiate availability (the
V4 weekly pipeline already records these), distinct from
`historically_reconstructed` rows. Update `schema_contracts.py` timing
allow-lists so 2026 datasets accept `live` while every historical dataset
continues to require `historically_reconstructed`. Extend season validation so
a 2026 measurement config accepts 2026 in addition to the development seasons;
2020 remains forbidden everywhere; the historical R6 config and its
8936/8935 population reconciliation counts are untouched.

**Acceptance:** Authority tests pass with both timing classes admitted in
their respective scopes; a 2026 config validates; a historical config still
rejects any non-reconstructed row and any 2020 inclusion.

**Validation:** Focused schema/timing unit tests; `uv run mkdocs build --quiet`;
existing authority tests unchanged in outcome.

### Task 2 — Repair-2026 extension run

Execute a new Repair run covering 2026 completed games (Weeks 0–current),
anchored on the certified Repair v2 manifest
(`repair-v2-20260909T1417Z`) as the historical parent. Reuse the Repair v2
capture and reconciliation logic; bind the exact 2026 Silver input refs
(games, outcomes, plays) in the run manifest. New run-ID; independent
verification of population, sources, and reconciliation; idempotent repeat.

**Acceptance:** Certified Repair-2026 manifest in Preview R2 with exact input
refs, passing preflight/apply/verify/repeat; historical Repair v2 artifact
byte-identical and untouched.

**Validation:** Repair runner preflight + apply + independent verifier +
idempotent repeat; R2 inventory confined to the Preview research prefix.

### Task 3 — 2026 possession measurement certification

Execute the possession measurement pipeline against the certified Repair-2026
parent for the full 2026 season (Week 0 through latest completed week) under
a new versioned config (2026 seasons pinned, `live` timing, same adjustment
procedure, floors, fallbacks, and exposure settings as R6). Full
preflight/apply/independent-verify/idempotent-repeat cycle in Preview; terminal
`measurement-manifest.json` published last with
`production_activation_authorized: false`.

**Acceptance:** Certified 2026 measurement manifest in Preview R2; all eight
possession datasets present for 2026 weeks; readiness `schedule` source
resolves against 2026 rows; manifest recorded as the sole eligible 08 parent.

**Validation:** Measurement preflight + apply + independent verifier +
idempotent repeat; focused unit tests for 2026 population/timing boundaries;
`git diff --check`.

## Testing strategy

Focused unit tests for the `live` timing amendment (admission scope,
historical rejection preserved), 2026 season validation (2020 still
forbidden), and 2026 population boundaries. Full certification cycles
(preflight/apply/verify/repeat) for the Repair-2026 and measurement runs.
Strict MkDocs and `git diff --check` for documentation updates. No mirror
tests for certification-only runs beyond the existing verifier suites.

## Risks, definition of done, and amendments

2026 play-by-play completeness for early weeks depends on CFBD finals lag
(24–48h); incomplete weeks remain blockers, never backfilled with
reconstructed substitutes. The `live` amendment must not weaken any
historical reconstructed-only guarantee. Sealed code (season pins, parent
run-IDs, reconciliation counts) requires explicit amendment per layer.

- [ ] `live` timing admitted with historical guarantees intact; authority tests pass.
- [ ] Certified Repair-2026 manifest in Preview (preflight/apply/verify/repeat).
- [ ] Certified 2026 measurement manifest in Preview (preflight/apply/verify/repeat).
- [ ] Historical R6 and Repair v2 artifacts byte-identical and untouched.
- [ ] No production/Neon/web writes; manifest carries `production_activation_authorized: false`.
- [ ] Reports, plan index, roadmap status, contract lifecycle, and session logs are current.

Follow the common amendment process for timing, season, population, or
procedure changes. While 2026 measurement certification is incomplete, leave
this contract In Progress and Contract 08 unstarted.
