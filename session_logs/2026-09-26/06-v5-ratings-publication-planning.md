# Session: V5 Ratings Publication and Navigation Planning

## TL;DR
- **Worked On:** Investigated production and preview database state, verified artifact lineage and linkage mechanisms, and drafted/revised a decision-complete implementation contract for publishing V5 team ratings to production Neon, re-enabling the `/ratings` site navigation, linking game predictions to team ratings, and establishing the weekly rating projection cadence.
- **Outcome:** Approved implementation contract saved at `docs/plans/2026-09-26/03-v5-ratings-publication-and-navigation.md` incorporating 5 user amendments. Sol planning complete.
- **Plan Contract:** `docs/plans/2026-09-26/03-v5-ratings-publication-and-navigation.md`
- **Approval / Status:** User review and approval with 5 minor amendments (2026-09-26); Status: `Approved`.
- **Blockers:** None.
- **Next:** Open a fresh Terra task to execute `docs/plans/2026-09-26/03-v5-ratings-publication-and-navigation.md`.

## Context and Decisions
- **Model Coexistence:** Confirmed production was cut over to V5 best-quote replay replacement runs (`2026w{0..4}-v5replay-bestquote-20260926-r3`) earlier today (`v5-bestquote-replacement-review-2026-09-26`). Both live predictions and ratings belong to the identical V5 possession model family (`v5-possession-ppp-rho060-exposure`). Zero model mismatch exists.
- **Neon Audit Findings:**
  - Preview holds 452 snapshots for SHA `0c7bca598dcf5a377b7c619edba7eca34bb31dd7c61d489d47c06a5bfc38e3f0`.
  - Production `v5_rating_snapshots` currently has 0 rows.
  - Production `prediction_runs` for Weeks 0–4 already carry `rating_manifest_sha256 = '0c7bca598dcf5a377b7c619edba7eca34bb31dd7c61d489d47c06a5bfc38e3f0'`.
  - Production `getSelectedRatingSource(2026)` already dynamically resolves to this SHA.
  - `publish_v5_ratings.py` dry-run verified 452 rows and parent lineage with zero errors.
- **Access Path & Lease Guardrails:** Production commands must execute via `scripts/ops/with_production_pipeline_env.sh` under restricted role `cks_prod_pipeline` with active pipeline lease.
- **Methodology Copy Authority:** Rating explanations must cite `docs/modeling/possession_rating_methodology.md` verbatim (scoring efficiency per possession against average FBS opponent under standard conditions; separate offense/defense ratings with uncertainty; Ridge bridge margin).
- **Ops Cadence:** The ops command `project-v5-ratings` is already implemented in `src/cks_picks_cfb/ops/__main__.py:2002-2018`. No `v5_cycle.py` code changes are needed; only `docs/ops/weekly_pipeline.md` documentation reconciliation is required.

## Work Completed
- Ran read-only database inspections across Preview and Production Neon.
- Validated dry-run execution of `publish_v5_ratings.py`.
- Formulated decision-complete implementation contract covering all 6 critique requirements.
- Incorporated user's 5 amendments into approved contract `docs/plans/2026-09-26/03-v5-ratings-publication-and-navigation.md`.
- Updated `docs/plans/index.md` active contracts table.

## Files Modified
- `docs/plans/2026-09-26/03-v5-ratings-publication-and-navigation.md` - Created approved implementation contract
- `docs/plans/index.md` - Added contract to active contracts index
- `session_logs/2026-09-26/06-v5-ratings-publication-planning.md` - Created planning session log

## Validation
- [x] Read-only Preview & Production Neon queries verified
- [x] `uv run python scripts/pipeline/publish_v5_ratings.py --rating-manifest-uri ... --environment production` dry-run passed (452 rows)
- [x] `npm --prefix web run typecheck` passed (0 errors)
- [x] `npm --prefix web run lint` passed (0 errors)
- [x] `make contracts-check` passed
- [x] `git diff --check` passed

## Amendments and Blockers
- Incorporated 5 minor amendments from user approval:
  1. Production access path uses `scripts/ops/with_production_pipeline_env.sh` and restricted role `cks_prod_pipeline`; cites migrations 0013, 0014, 0015.
  2. Fixed line reference to live serving writer (`v5_serving.py:178-194`).
  3. Quoted `docs/modeling/possession_rating_methodology.md` for methodology copy.
  4. Framed `docs/ops/weekly_pipeline.md` reconciliation post-cutover without altering `v5_cycle.py`.
  5. Included UI details (rankings, focus-visible styling, web test requirements, exceptional rollback semantics).

## Handoff Notes
- **Resume at:** Start Terra implementation task with contract `docs/plans/2026-09-26/03-v5-ratings-publication-and-navigation.md`.
- **Watch out for:** Never run bare `uv run ... --apply` against production; always wrap with `zsh scripts/ops/with_production_pipeline_env.sh`.

**tags:** ["planning", "ratings", "v5", "ops", "web"]
