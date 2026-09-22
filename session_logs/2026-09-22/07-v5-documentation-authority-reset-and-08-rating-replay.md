# Session: V5 Documentation Authority Reset and Contract 08 Reconciliation

## TL;DR

- **Worked On:** Task 1 of [the V5 documentation reset and completion-sequence contract](../../docs/plans/2026-09-22/02-v5-documentation-reset-and-completion-sequence.md), followed by Contract 08 runner and Preview-parent reconciliation.
- **Outcome:** Active documentation now reflects the accepted September 22 V5 state and the `07 → 08 → 09 → 06 → conditional Phase 7` sequence. The first Contract 08 implementation check found that no live replay runner or independent live verifier exists yet; the historical runner is deliberately sealed to the R6/Repair-v2 60-candidate tournament.
- **Plan Contract:** `docs/plans/2026-09-22/02-v5-documentation-reset-and-completion-sequence.md` — In Progress; Task 1 complete.
- **Approval / Status:** User explicitly authorized the contract on 2026-09-22.
- **Blockers:** Contract 08 needs a narrow implementation amendment that specifies a distinct live replay runner/verifier and its immutable 2026 preseason-input binding. The approved contract already requires an explicit amendment before sealed 03/11B code may admit a 2026 parent.
- **Next:** Amend Contract 08 with the isolated live-replay interfaces, then implement and certify it. Do not alter the historical tournament runner or its artifacts.

## Context and Decisions

- The canonical data-first roadmap is now the detailed status authority. Active entry points report that historical V5 development is accepted, all four findings are closed, Contract 07 is Implemented with 157 live games through Week 3, and Contract 08 is next.
- Dated Contract 10B/11A/12A evidence remains in place. The documentation labels 10B's then-open findings as historical at-publication state and records their later closure.
- Read-only Preview R2 inventory found all Contract 08 parents: live measurement manifest `possession-v1-measurements-20260922-2026c`, Repair-2026 `repair-2026-20260922T145500Z`, historical 11B rating manifest `possession-v1-ratings-20260921-11d59ee-r9cert`, plus existing 2026 recruiting, returning-production, and coaching snapshots dated 2026-08-14. No provider capture is required.
- `run_data_first_possession_ratings.py` only accepts the historical R6/Repair-v2 parent contract and recomputes the full 60-candidate selection tournament. Its independent verifier has the same historical-parent boundary. Reusing either would violate Contract 08's no-reselection and historical-byte-stability requirements.

## Work Completed

- Added orchestration contract `02-v5-documentation-reset-and-completion-sequence.md` and marked Task 1 complete.
- Updated README, documentation home, assistant guides, quickstart, operations and data-first roadmaps, plans index, methodology, measurement, evaluation, rating requirements, and repository boundaries.
- Updated authority regression tests to require the current live sequence while preserving dated conditional/audit records.
- Inspected Contract 08's runner, verifier, input interfaces, and live Preview parents without writing R2, Neon, production, or web state.

## Files Modified

- `README.md`, `docs/index.md`, `AGENTS.md`, `.agent/CONTEXT.md`, `.codex/QUICKSTART.md` — active checkpoint reset.
- `docs/planning/roadmap.md`, `docs/planning/data-first-football-forecasting-roadmap.md`, `docs/plans/index.md` — canonical sequence and lifecycle reset.
- `docs/modeling/` and `docs/architecture/repository_boundaries.md` — current V5 authority alignment.
- `tests/test_data_first_documentation_authority.py` — current-sequence coverage and historical-record handling.
- `docs/plans/2026-09-22/02-v5-documentation-reset-and-completion-sequence.md` — governing contract.

## Validation

- [x] `uv run pytest tests/test_data_first_documentation_authority.py` — 38 passed.
- [x] `uv run python contracts/validation.py` — passed.
- [x] `uv run mkdocs build --strict --quiet` — passed.
- [x] `git diff --check` — passed.

## Amendments and Blockers

- The Contract 08 implementation interface is a material unresolved detail, not a failing data gate. Its exact approved text requires a separate amendment before admitting a 2026 replay parent to sealed historical code.

## Handoff Notes

- **Resume at:** Amend `docs/plans/2026-09-18/08-v5-2026-rating-state-replay.md` to use a dedicated 2026 single-candidate replay runner and a verifier-owned counterpart. Bind r9-derived historical terminal state, live 2026 measurement/repair manifests, and the three existing 2026 preseason snapshots by exact immutable reference.
- **Watch out for:** The historical runner and verifier are sealed to R6/Repair-v2 and the 60-candidate selection tournament. Do not add a CLI-only parent override, reuse the selection path, or apply an R2 run while the repository is uncommitted; the existing runner's apply gate requires a clean committed worktree.

**tags:** ["v5", "documentation", "authority", "contract-08", "rating-replay"]
