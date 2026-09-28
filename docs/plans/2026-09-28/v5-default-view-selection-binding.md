# Default-View Selection Binding for V5 Ratings Serving

- **Status:** Implemented
- **Created:** 2026-09-28
- **Planner:** Sol
- **Approval source:** User explicitly authorized implementation of this exact plan path ("go", 2026-09-28 session)
- **Implementation log:** `session_logs/2026-09-28/05-followup1-implementation.md`
- **Commit policy:** Commit with implementation (contained web-only change; no migration)

## Goal

Eliminate the serving cases where the ratings default view (and historical tabs)
can label one generation while showing another's rows. After this change:

1. The default/current view derives its displayed period label **from the same
   rows it serves**, so label and data agree by construction in every
   projection-before-selection and rollback state.
2. Frozen history tabs backfill missing early-cohort teams from preseason priors
   pinned to the **cutoff-owning source**, not the currently selected source, so
   historical tabs stop moving when the site selection changes.
3. Duplicate-generation resolution is an explicit documented rule with tests.

No rating value, model artifact, R2 object, database row, or selection changes.
Current production is aligned, so no visible content change is expected on
deploy; this is a correctness hardening verified by new behavioral tests.

## Current State

Serving logic lives in `web/src/lib/v5.ts`:

- `getSelectedRatingSource` (line 18) resolves the rating manifest SHA from the
  newest `siteWeekSelections` row whose run has evidence class
  pending/replay/live.
- `getCurrentRatings` (line 30) serves `current`-class rows for the selected
  source at that source's max cutoff.
- `getRatingPeriods` (line 109) lists periods from **all** `current`-class rows
  regardless of source; `generations[0]` is the newest cutoff present.
- Default branch (lines 218–223): label comes from `generations[0]`, rows from
  `getCurrentRatings`. These diverge when a new generation is projected before
  the new forecast is selected, or when selection rolls back to an older run.
  Reproduced in the 2026-09-28 audit
  (`docs/research/2026-09-28-current-v5-ratings-audit.md`, P2 finding) by
  executing the branch with stubbed new-generation metadata and old rows.
- `getPreseasonPriors` (line 151) resolves the currently selected source and is
  reused for historical backfill (lines 197–201). The frozen design currently
  produces identical priors across generations, so no numerical discrepancy
  exists today; a rollback to a source lacking the full cohort, a missing
  source, or a future prior revision would move historical tabs.
- Frozen-tab dedup (lines 187–192) resolves duplicate generations at one cutoff
  by newest `createdAt` row per team. None exist today; the rule is implicit.
- Existing coverage (`web/src/lib/ratings.test.ts`) asserts on source text and
  the certified `WEEK_GENERATIONS` map; it does not exercise the
  label/rows/selection relationships. Web suite entry: `npm run
  test:publication` (node:test over `publication`, `run-selection`,
  `betting-format`, `ratings`).

## Proposed Approach

Bind by construction instead of by coincidence: derive every served label from
the rows served alongside it, and thread an explicit source identity into every
priors query. Extract the label-derivation and cutoff-ownership decisions into
pure, exported helpers so the behavioral tests run without a database; keep the
query layer thin. Alternatives considered and rejected: a Neon migration adding
an explicit baseline identity (heavier than needed while the frozen design
keeps identical priors — revisit if a prior revision is ever authorized); a
test-only mock of the drizzle `db` module (brittle against the cached query
layer; pure-helper tests plus wiring assertions cover the behavior).

## Scope

### Included

- Default-branch label/rows binding in `getWeeklyRatings`.
- Cutoff-owning-source resolution and its use for frozen-tab preseason backfill.
- Explicit duplicate-cutoff rule (newest row wins per team), documented and tested.
- Behavioral tests for projection-before-selection, rollback, missing/empty
  states, and backfill cohort completeness.
- Code comments and a short audit-follow-up note in `docs/modeling/v5_status.md`.

### Excluded

- Any change to rating values, the accepted V5 model, R2 artifacts, Neon rows,
  site selections, or publication mode.
- Neon migrations or schema changes.
- Prior-revision mechanics, a permanent-history baseline identity migration, or
  the cumulative-snapshot estimator review (separate Follow-up 2 research
  contract).
- Visual redesign of the ratings page; expected rendered output is unchanged.

## Affected Components and Contracts

- `web/src/lib/v5.ts` — `getWeeklyRatings` default branch, `getPreseasonPriors`
  signature, frozen-tab backfill query, `getRatingPeriods` unchanged.
- `web/src/lib/ratings.test.ts` (extend) or new
  `web/src/lib/default-view-selection.test.ts` wired into `test:publication`.
- `web/package.json` — only if a new test file must be added to the
  `test:publication` file list.
- `docs/modeling/v5_status.md` — audit-follow-up note recording the fix.
- No change to `contracts/`, Neon migrations, the pipeline, or the V6 lab.

## Implementation Tasks

### Task 1 — Derive the default period label from served rows

**Files:**

- `web/src/lib/v5.ts`

**Changes:**

- Extract an exported pure helper, e.g. `defaultPeriodForRows(rows)`, that maps
  a served `Rating[]` to its `PeriodMeta`: the rows' shared `cutoffUtc` looked
  up in `WEEK_GENERATIONS` (certified post-week label) or formatted as an
  "As of" date label; empty input returns `PRESEASON_META`.
- Rewrite the default branch (current lines 218–223) to serve
  `getCurrentRatings(season)` rows and return `defaultPeriodForRows(ratings)`
  as the period meta. Delete the `generations[0]` label path for the default
  view. Frozen-target, week-param, and preseason-param branches are unchanged.
- The served label must always match the served rows by construction; no branch
  may pair a newest-generation label with selected-source rows again.

**Acceptance criteria:**

- Projection-before-selection fixture (newer cutoff present in periods, rows
  from older selected source): default returns the older cutoff's label.
- Rollback fixture (selection older than newest generation): same binding.
- Aligned state: output identical to today's production behavior.
- Empty ratings: preseason meta with empty rows.

**Validation:**

- Unit tests on the pure helper with fixture rows; source-text or wiring test
  that the default branch no longer references `generations[0]`.
- `npm run test:publication`, `npm run lint`, `npm run typecheck` in `web/`.

### Task 2 — Pin frozen-tab backfill to the cutoff-owning source

**Files:**

- `web/src/lib/v5.ts`

**Changes:**

- Add an exported pure-or-query helper resolving the owning source for a frozen
  cutoff: the `sourceManifestSha256` of the newest `createdAt`
  `current`-class row at that cutoff (same ordering the frozen query already
  uses per team). Export it for tests.
- Change `getPreseasonPriors(season)` internals to accept an explicit source
  SHA (e.g. `getPreseasonPriors(season, sourceSha?)`, defaulting to the
  selected source to preserve the preseason tab's "active model state"
  meaning). Frozen-tab backfill (current lines 197–201) passes the
  cutoff-owning source.
- Missing-owner-source or missing-priors-for-owner edge: backfill skips with
  the row's existing `fallbackReason` lineage visible; never silently borrow
  another source's priors. Document the newest-row-wins duplicate rule in a
  comment at the frozen query.

**Acceptance criteria:**

- Frozen tab with selection moved to a newer source still backfills from the
  cutoff owner's priors (fixture: owner source A, selected source B, assert
  backfilled rows carry A's cohort values).
- Owner source lacking preseason rows: tab serves frozen rows only, no
  cross-source borrowing, fallback lineage visible.
- Preseason tab behavior unchanged (selected source).
- Duplicate-cutoff fixture: newest row wins per team, deterministically.

**Validation:**

- Behavioral tests with fixture row sets covering owner-vs-selected divergence,
  missing owner priors, and duplicate cutoffs.
- `npm run test:publication`, `npm run lint`, `npm run typecheck` in `web/`.

### Task 3 — Test wiring and docs note

**Files:**

- `web/src/lib/ratings.test.ts` or `web/src/lib/default-view-selection.test.ts`
- `web/package.json` (only if a new test file needs adding to `test:publication`)
- `docs/modeling/v5_status.md`

**Changes:**

- Cover Tasks 1–2 with node:test behavioral tests using fixture `Rating[]`
  rows (no database). Keep the existing source-text tests passing; extend the
  certified-cutoff assertions if new cutoffs exist.
- Add a short audit-follow-up note to `v5_status.md` recording that the
  default-view binding and backfill pinning are fixed, linking this contract.
  No methodology equation changes.

**Acceptance criteria:**

- `test:publication` passes including new tests; suite count increases and is
  recorded in the implementation log.
- Docs note present; `uv run mkdocs build --quiet` passes.

**Validation:**

- `npm run test:publication` in `web/`; `uv run mkdocs build --quiet`;
  `git diff --check`.

## Testing Strategy

- Unit/behavioral (node:test, no DB): pure helpers plus fixture-driven branch
  behavior for all four states — aligned, projection-before-selection,
  rollback, empty/missing.
- Regression: full `test:publication` suite, web `lint` + `typecheck`, and a
  production `next build` (`npx nx run web:build` or `npm run build` in `web/`)
  before handoff.
- No pipeline tests affected; no live-Data verification required beyond
  confirming current production output is unchanged (read-only `/ratings`
  readback optional, not a gate).

## Risks and Edge Cases

- Unknown future cutoffs (not in `WEEK_GENERATIONS`) must keep "As of" date
  labels via the existing formatter — preserved by deriving from rows.
- ISR caching (`cache()` + 5-minute revalidate) means the fix takes effect on
  next revalidation; no cache-busting mechanics in scope.
- If the owner-source query ever returns no rows for a historical cutoff,
  tabs must degrade to frozen-rows-only rather than borrowing — fail-closed,
  matching the publication boundary.
- Expected rendered output is unchanged in the aligned state; any pixel or
  content diff against production `/ratings` in the aligned state is a defect.

## Definition of Done

- [ ] Default label derives from served rows in all states; no
  newest-generation-label path remains on the default branch.
- [ ] Frozen backfill pinned to cutoff-owning source; newest-row-wins rule
  documented and tested.
- [ ] New behavioral tests pass; `test:publication`, `lint`, `typecheck`,
  `web:build` green.
- [ ] `uv run mkdocs build --quiet` and `git diff --check` pass.
- [ ] `docs/modeling/v5_status.md` follow-up note recorded.
- [ ] Implementation session log created; plan status updated to `Implemented`.
- [ ] No model, artifact, selection, or migration change.

## Amendments

None yet. A material change to the serving query shape, a decision to add a
Neon baseline-identity migration, or any rating-value impact requires a new
approved amendment before implementation continues.
