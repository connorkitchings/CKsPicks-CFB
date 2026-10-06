# Session: Stage 7A Release Foundations Planning

## TL;DR
- **Worked On:** Persisted the approved decision-complete Stage 7A implementation contract.
- **Outcome:** Contract approved for the exact requested path; no implementation code, migration, database, authorization, serving, or web changes were made.
- **Plan Contract:** [Stage 7A Release Foundations](../../docs/plans/2026-10-06/01-stage7a-release-foundations.md), governed by Contract 04 Amendment 2 and Appendix B.
- **Approval / Status:** The user explicitly requested implementation of the plan naming this exact contract path on 2026-10-06. The plan requires a separate user-run commit before a fresh implementation task.
- **Blockers:** User commit of the plan contract and planning log; later Preview migration application requires a separate operator authorization.
- **Next:** User commits the two planning documents, then a fresh Terra task uses `implement-plan` with the exact contract path.

## Context and Decisions
- Baseline is clean `dev` HEAD `320436f1d13b38068b9e21a2ea64d41a755c1551`; Stage 6B is Implemented with Preview-only evidence.
- Contract 04 and Appendix B govern table names and behavior. Migration 0022 is the current repository tip; the new schema files are numbered 0023 and 0024.
- Existing authorization registries are `public.v5_model_bundle_approvals` and `public.v5_intended_update_release_authorizations`. The new revocation table validates against these real tables.
- The v2 batch controller and its exact rollback capability are Stage 7A code, exercised only in isolated databases. Stage 7B chooses N and performs the concrete cutover and live Preview rehearsal.
- The plan preserves separate user-run authorization/revocation actions and requires separately authorized Preview migration operations. Stage 7A makes no serving-state or authorization writes.

## Work Completed
- Added `docs/plans/2026-10-06/01-stage7a-release-foundations.md` with approved schema, grants, guards, controller, web behavior, validation, stop conditions, and handoff gates.
- Added this planning log. Did not update `docs/status.md`, since no live run or week state changed.

## Validation
- [x] `git diff --check`
- [x] `.venv/bin/python contracts/validation.py` — passed. The `make contracts-check` wrapper could not access a protected uv cache directory in this sandbox; its underlying validator passed directly.
- [x] `uv run mkdocs build --quiet`

## Amendments and Blockers
- No Contract 04 amendment was made. Preview schema application and all actual serving/cutover operations remain outside this planning persistence step.

## Handoff Notes
- **Resume at:** After the user commits the contract and planning log, open a fresh implementation task with the repository-local `implement-plan` skill and `docs/plans/2026-10-06/01-stage7a-release-foundations.md`.
- **Watch out for:** Verify each database migration ledger and actual inherited role privileges before any Preview schema application. Do not choose N or mutate serving state in Stage 7A.

**tags:** ["release", "stage7a", "schema", "authorization", "web"]
