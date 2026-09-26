# V5 Ratings Publication and Navigation

- **Status:** Implemented
- **Created:** 2026-09-26
- **Planner:** Sol
- **Approval source:** User review and approval with 5 amendments (2026-09-26)
- **Implementation log:** session_logs/2026-09-26/07-v5-ratings-publication-implementation.md
- **Commit policy:** Commit with implementation

## Goal

Provide user visibility into model team ratings and why teams are favored:
1. Publish certified V5 team ratings snapshots into production Neon (`v5_rating_snapshots`).
2. Re-enable the `/ratings` tab in site navigation (`SiteNav.tsx`).
3. Enhance `/ratings` with rank indices, authoritative methodology explainers (PPP semantics, offense/defense orientation, Ridge margin bridge, and narrowing uncertainty), and disambiguated empty states.
4. Link game cards (`GameRow.tsx`) directly to `/teams/[team]` detail views for seamless exploration from weekly predictions.
5. Reconcile `docs/ops/weekly_pipeline.md` and document the weekly rating projection ops command.

## Current State

- **Model Coexistence:** Production was cut over to V5 best-quote replay replacement runs `2026w{0..4}-v5replay-bestquote-20260926-r3` on 2026-09-26 (`docs/modeling/v5_status.md`). Predictions and ratings both belong to the accepted V5 possession model family (`v5-possession-ppp-rho060-exposure`). There is zero model mismatch.
- **Neon Database Audit:**
  - Migrations `0013_v5_public_selection.sql`, `0014_v5_restricted_pipeline_role.sql`, and `0015_v5_pipeline_grants.sql` are applied on both Preview and Production.
  - Preview `v5_rating_snapshots` holds 452 rows matching SHA `0c7bca598dcf5a377b7c619edba7eca34bb31dd7c61d489d47c06a5bfc38e3f0`.
  - Production `v5_rating_snapshots` has 0 rows.
  - Production `prediction_runs` for Weeks 0–4 already carry `rating_manifest_sha256 = '0c7bca598dcf5a377b7c619edba7eca34bb31dd7c61d489d47c06a5bfc38e3f0'`.
  - Production `v5_release_policy` has 1 row.
  - `web/src/lib/v5.ts:getSelectedRatingSource(2026)` already dynamically resolves to this exact SHA on production.
- **Replay Artifact Lineage:**
  - Replay manifest: `artifacts/research/data-first-football-v1/possession-v1/rating-replay/runs/possession-v1-rating-replay-20260922-fcaa571/retained-rating-replay-manifest.json`
  - Replay SHA-256: `0c7bca598dcf5a377b7c619edba7eca34bb31dd7c61d489d47c06a5bfc38e3f0`
  - Verifier manifest: `artifacts/research/data-first-football-v1/possession-v1/rating-replay/runs/possession-v1-rating-replay-20260922-fcaa571/verification/verifier-manifest.json`
  - Verifier state: `verified`; candidate: `ppp__rho_0_60__exposure`.
  - Dry run of `publish_v5_ratings.py` verified 452 rows and parent lineage.

## Proposed Approach

1. Project the 452 verified snapshots into production Neon using the restricted role wrapper `scripts/ops/with_production_pipeline_env.sh` and ops command `project-v5-ratings` (or direct script under active lease).
2. Update web components: add "Ratings" to `SiteNav.tsx`, add ranking column and authoritative copy from `docs/modeling/possession_rating_methodology.md` to `ratings/page.tsx`, and make team names clickable in `GameRow.tsx:TeamLine`.
3. Add unit tests for the updated ratings page and game row components in `web/`.
4. Reconcile `docs/ops/weekly_pipeline.md` framing to reflect V5 production status and document the weekly `project-v5-ratings` cadence.

## Scope

### Included
- Projecting certified replay ratings `possession-v1-rating-replay-20260922-fcaa571` to production `v5_rating_snapshots`.
- Re-enabling `/ratings` link in `web/src/components/SiteNav.tsx`.
- UI updates to `web/src/app/ratings/page.tsx` (rankings, methodology card, empty states).
- UI link in `web/src/components/GameRow.tsx` from team name to `/teams/[team]`.
- Frontend unit tests for new rendering behavior.
- Ops documentation update in `docs/ops/weekly_pipeline.md`.

### Excluded
- No changes to `v5_cycle.py` component order (the `project-v5-ratings` ops command already exists in `ops/__main__.py:2002-2018`).
- No changes to model mathematics or feature engineering.
- No new database migrations (0013, 0014, 0015 already provide the required schema and roles).

## Affected Components and Contracts

- `scripts/pipeline/publish_v5_ratings.py`
- `scripts/ops/with_production_pipeline_env.sh`
- `web/src/components/SiteNav.tsx`
- `web/src/app/ratings/page.tsx`
- `web/src/components/GameRow.tsx`
- `web/src/test/` (new/updated tests)
- `docs/ops/weekly_pipeline.md`
- `docs/modeling/v5_status.md` (reference)

---

## Implementation Tasks

### Task 1 — Project Verified Rating Snapshots to Production Neon

**Files:**
- None (operational execution via existing script and restricted wrapper)

**Execution:**
Execute using the restricted `cks_prod_pipeline` role via `scripts/ops/with_production_pipeline_env.sh`:
```bash
zsh scripts/ops/with_production_pipeline_env.sh \
  uv run python -m cks_picks_cfb.ops project-v5-ratings \
    --environment production \
    --rating-manifest-uri artifacts/research/data-first-football-v1/possession-v1/rating-replay/runs/possession-v1-rating-replay-20260922-fcaa571/retained-rating-replay-manifest.json
```
*(Alternative direct invocation under acquired pipeline lease):*
```bash
zsh scripts/ops/with_production_pipeline_env.sh \
  uv run python scripts/pipeline/publish_v5_ratings.py \
    --rating-manifest-uri artifacts/research/data-first-football-v1/possession-v1/rating-replay/runs/possession-v1-rating-replay-20260922-fcaa571/retained-rating-replay-manifest.json \
    --environment production \
    --apply
```

**Acceptance criteria:**
- Production `v5_rating_snapshots` contains exactly 452 rows matching SHA `0c7bca598dcf5a377b7c619edba7eca34bb31dd7c61d489d47c06a5bfc38e3f0`.
- Read-only query confirms snapshot counts match Preview exactly.

**Validation:**
- Read-only SQL query checking row count, source run ID, and SHA.

---

### Task 2 — Re-Enable Navigation Tab and Enhance Ratings UI

**Files:**
- `web/src/components/SiteNav.tsx`
- `web/src/app/ratings/page.tsx`
- `web/src/components/GameRow.tsx`

**Changes:**
1. `SiteNav.tsx`:
   Add `["Ratings", "/ratings"]` to `items`.
2. `ratings/page.tsx`:
   - Add rank column (`#1`, `#2`, ...) in the table based on sorted position.
   - Add authoritative methodology explainer quoting `docs/modeling/possession_rating_methodology.md`:
     - Scoring efficiency per possession (PPP) against an average FBS opponent under standard conditions.
     - Offense and Defense are oriented so higher is better.
     - Game forecast margin is derived from possession ratings via the through-2025 Ridge bridge with earlier-only non-offense offsets.
     - Uncertainty (`±`) represents one standard deviation of team rating, narrowing as game evidence accumulates.
   - Disambiguate empty states:
     - `ratings.length === 0`: "No certified ratings published for the 2026 season yet."
     - `visible.length === 0`: "No teams match '{query}'."
   - Keep parameterization clean; retain ISR `revalidate = 300`.
3. `GameRow.tsx`:
   - In `TeamLine` (covering both predictions and market rows), wrap team name in a `Link` to `/teams/${encodeURIComponent(name)}`.
   - Preserve text truncation styling and add `hover:text-accent-ink hover:underline focus-visible:rounded focus-visible:outline-2 focus-visible:outline-accent`.

**Acceptance criteria:**
- Clicking "Ratings" in navigation loads the ratings table.
- Table shows Rank, Team, Overall, Offense, Defense, Uncertainty.
- Clicking any team name on the home page navigates to `/teams/[team]`.
- Empty search vs empty table are visually distinct.

**Validation:**
- `npm --prefix web run lint`
- `npm --prefix web run typecheck`
- `npm --prefix web run build`

---

### Task 3 — Add Frontend Tests for Ratings & Team Links

**Files:**
- `web/src/test/ratings.test.tsx` (or appropriate test file)

**Changes:**
- Add tests verifying:
  - Rank numbering renders correctly on `/ratings`.
  - Methodology card renders authoritative explanation.
  - Empty search vs unpopulated ratings render distinct text.
  - `GameRow` renders clickable team links with correct accessibility and hrefs.

**Acceptance criteria:**
- Frontend test suite passes cleanly.

**Validation:**
- `npm --prefix web test` (or `npx nx run web:test`)

---

### Task 4 — Reconcile Ops Documentation & Cadence

**Files:**
- `docs/ops/weekly_pipeline.md`

**Changes:**
- Reconcile framing in `docs/ops/weekly_pipeline.md`: update legacy statements (lines 5, 11–25) that said "Preview only until activation" now that V5 best-quote replay is the active production model.
- Document `project-v5-ratings` as the standard operational step following `publish` in the weekly operating cycle.
- Explicitly state that no `v5_cycle.py` modification is required because `ops/__main__.py:2002-2018` already houses the CLI command.
- Note the exceptional rollback procedure:
  ```sql
  -- Run via with_production_pipeline_env.sh under active pipeline lease:
  DELETE FROM v5_rating_snapshots WHERE source_manifest_sha256 = '<sha>';
  ```

**Acceptance criteria:**
- Documentation accurately reflects current production architecture and weekly runbook steps.

---

## Testing Strategy

1. **Database:** Read-only verification before and after apply on production Neon.
2. **Type Safety & Lint:** `npm --prefix web run typecheck` and `npm --prefix web run lint`.
3. **Contracts:** `make contracts-check`.
4. **Web Build:** `npm --prefix web run build`.
5. **Component Tests:** Jest/Vitest tests in `web/` covering new ratings UI elements and team links.
6. **Browser Smoke Test:** Verify `/`, `/ratings`, and `/teams/[team]` locally or via Preview deployment.

---

## Risks and Edge Cases

- **Production Credentials:** Must use `scripts/ops/with_production_pipeline_env.sh` which sources restricted `cks_prod_pipeline` role from Keychain. Owner/admin URL must never be used.
- **Idempotency:** `v5_rating_snapshots` uses `ON CONFLICT (snapshot_id) DO NOTHING`. Multiple runs of `project-v5-ratings` are safe and no-op on existing rows.
- **Fail-Closed:** If rating snapshots are absent or query fails, web app gracefully renders empty/unavailable status without crashing or affecting the `/` predictions page.

---

## Definition of Done

- [x] Certified replay rating snapshots (452 rows) published to production Neon.
- [x] Navigation tab `/ratings` visible and active on site.
- [x] Ratings page displays rank numbers, authoritative methodology explainer, and disambiguated empty states.
- [x] Prediction cards link team names to team detail pages.
- [x] Frontend tests added and passing.
- [x] `make contracts-check`, `npm run lint`, `npm run typecheck`, and `npm run build` pass.
- [x] `docs/ops/weekly_pipeline.md` reconciled and updated.
- [x] Session log created in `session_logs/2026-09-26/`.
- [x] Contract status updated to `Implemented`.
