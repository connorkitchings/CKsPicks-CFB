# Session: Data-First Football Forecasting Planning

## TL;DR

- **Worked On:** High-level project review and a new repository-to-forecasting implementation program.
- **Outcome:** Approved roadmap and seven phase contracts persisted; new research authority replaces pending R3/R4 while preserving V4 and completed evidence.
- **Plan Contract:** `docs/plans/2026-09-05/00-repository-architecture-and-documentation-alignment.md` (next implementation)
- **Approval / Status:** User approved the full plan and explicitly targeted Phase 0 on 2026-09-05; all seven contracts are `Approved`.
- **Blockers:** Phase 0 must run in a fresh implementation task under the repository's Sol-to-Terra workflow.
- **Next:** Implement Phase 0, beginning with operating-baseline and dependency mapping.

## Context and Decisions

- V4 remains the live production champion and rollback authority.
- New research order is Phase 0 architecture, data audit, repair, measurements,
  simple ratings, spread/total forecasting, then prospective evidence.
- 2015-2019 and 2021-2025 are development data in the new namespace; 2020 is
  excluded; future pre-kickoff freezes provide independent evidence.
- The target population is every game involving at least one FBS team.
- Timestamped lines are comparison evidence only. Betting decisions are deferred.
- Total recurring data cost is capped at $15/month including the reported $4
  CFBD subscription; no purchase was authorized.
- Phase 0 uses staged structural cleanup and preserves production plus named
  research benchmarks. Other historical work remains recoverable at pinned commits.

## Work Completed

- Added the governing data-first roadmap.
- Added full Phase 0-6 implementation contracts.
- Updated current authority documents and marked pending R3/R4 superseded.
- Preserved completed R1/R2 and candidate evidence as audit-subject history.

## Files Modified

- `docs/planning/data-first-football-forecasting-roadmap.md` - governing roadmap.
- `docs/plans/2026-09-05/` - seven approved implementation contracts.
- `docs/index.md`, `README.md`, `AGENTS.md`, `.agent/CONTEXT.md` - current authority alignment.
- `docs/planning/roadmap.md`, `docs/plans/index.md` - operational/history and contract status alignment.
- `docs/modeling/` authority pages - scoped data-first policy notes.
- Superseded R3/R4 and governing historical-expansion plan metadata.

## Validation

- [x] `uv run mkdocs build --quiet`
- [x] `git diff --check`
- [x] Authority search and link review; remaining `market decision` language is
  scoped to historical rating requirements/roadmap and preceded by the new
  authority notice.

## Amendments and Blockers

- None. Documentation persistence intentionally contains no Phase 0 code or
  repository reorganization.

## Handoff Notes

- **Resume at:** Read and implement `docs/plans/2026-09-05/00-repository-architecture-and-documentation-alignment.md` in a fresh task.
- **Watch out for:** Do not move/delete code before dependency mapping and baseline evidence; do not run live production mutations for validation.

**tags:** ["planning", "architecture", "data-quality", "ratings", "forecasting"]
