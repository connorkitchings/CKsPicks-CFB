# Session: Transformation Review and Replacement Contract Reset

## TL;DR

- **Worked On:** Persisted the approved Astra review and six replacement execution contracts; synchronized active research authority.
- **Outcome:** Documentation reset implemented. Corrective research is approved but unexecuted; original Phase 4B is prohibited as a new forecasting parent.
- **Plan Contract:** `docs/plans/2026-09-08/transformation-review-and-authority-reset.md`
- **Approval / Status:** User's “PLEASE IMPLEMENT THIS PLAN” on 2026-09-08 explicitly authorized the documentation-only reset and approved the replacement package. Review status Implemented; six future contracts Approved.
- **Blockers:** None for documentation. Research advancement depends on repaired inputs and new passing predecessor artifacts.
- **Next:** User reviews/commits documentation; separate Terra task implements the exact repair contract.

## Context and Decisions

- Start Session and Plan Session workflows were read during the preceding review.
- Prior read-only review verified R2 configuration and selected sealed artifacts;
  this persistence task performed no new data I/O and required no external drive.
- Findings: same-game Phase 4B context, constant coaching features, roster
  continuity that counts transfers, 32 completed games omitted from Phase 3,
  and recruiting-window coverage limitations. See the canonical review evidence
  table for exact metrics, identities, checksum types and dispositions.
- User chose mandatory ratings, learned preseason priors, early-season
  advancement with full-season guardrails, the original bounded core repeat,
  one Kalman challenger without adaptive volatility, Ridge and NB2 forecasting,
  diagnostic-only polls/direct models, and bounded existing-provider gap filling.
- Preserved original artifacts/findings and previous session logs. Updated
  execution authority with dated supersession banners rather than rewriting
  historical results.

## Work Completed

- Saved the review and six approved replacement contracts with shared provenance,
  chronology, population, identity, validation and amendment rules.
- Specified repair, measurement replay, learned priors, rating dynamics, pregame
  context, forecast uncertainty/calibration and prospective update boundaries.
- Replaced current Phase 5 advancement claims and stale Phase 4A status.
- Distinguished raw-object hashes from canonical manifest checksums.
- Added a navigation entry for the review and checked the complete active queue.

## Files Modified

- `docs/plans/2026-09-08/` — review and six replacement execution contracts.
- `docs/planning/data-first-football-forecasting-roadmap.md`, `docs/planning/roadmap.md`, `docs/plans/index.md` — current corrective authority and retained history.
- `docs/plans/2026-09-07/` — five superseded execution contracts with replacement links.
- `docs/plans/2026-09-06/06-transformation-documentation-and-phase3-plus-resequence.md`, `docs/plans/2026-09-05/02-data-repair-and-recertification.md` — supersession/corrective notices.
- `AGENTS.md`, `.agent/CONTEXT.md`, `README.md`, `docs/index.md` — onboarding and current checkpoint.
- `docs/modeling/measurement_catalog.md`, `docs/modeling/evaluation.md`, `docs/modeling/rating_system_requirements.md` — current interfaces, evaluation rules and historical boundary.
- `mkdocs.yml` — review navigation.
- This session log.

## Validation

- [x] `uv run pytest tests/test_data_first_documentation_authority.py -q --no-cov` — 3 passed.
- [x] Strict MkDocs — initial `uv run mkdocs build --strict --quiet` passed; final `.venv/bin/mkdocs build --strict --quiet` passed. Used the installed binary when the repeated uv invocation hit sandbox cache access restrictions.
- [x] Seven-file metadata, relative-link, active-queue, approval and supersession checks — passed.
- [x] Active-authority search for stale advancement/raw-checksum claims — no matches in checked active pages.
- [x] `git diff --check` — passed.
- No model tests or phase execution were needed for documentation-only changes.

## Amendments and Blockers

None. Concrete numerical/serialization defaults are recorded in the approved
contract package for reproducible future execution. Any material change must
follow its amendment process before inspecting affected results.

## Handoff Notes

- **Resume at:** `docs/plans/2026-09-08/data-first-repair-and-recertification-v2.md` in a separate implementation task.
- **Watch out for:** Preserve unrelated changes in `scripts/pipeline/publish_to_db.py`, `score_to_db.py`, `score_weekly_bets.py`, `src/cks_picks_cfb/data/silver/builders.py`, `src/cks_picks_cfb/ops/__main__.py`, `.opencode/`, and session log `06-week1-score-and-week2-publish.md`. This task did not edit them or execute Git mutations.
- **Suggested commit:** `docs: reset data-first roadmap with reviewed corrective contracts`

Copy-ready next-task prompt:

```text
Use the repository-local implement-plan skill and implement the approved contract at:

docs/plans/2026-09-08/data-first-repair-and-recertification-v2.md

Treat it and its linked common contract as authoritative. Preserve unrelated
worktree changes, execute only the repair scope, run its validation, and stop
for material conflicts. This request explicitly authorizes implementation.
```

**tags:** ["data-first", "documentation", "planning", "review", "ratings"]
