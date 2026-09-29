# Session: Task 3 preflight — complete 2026 rating generations

## TL;DR
- **Worked On:** Task 3 of `docs/plans/2026-09-29/v5-intended-update-2026-production-repair.md` — certified 2026 priors + pregame/current cutoffs through the selected slate, preflight only.
- **Outcome:** Preflight build and independent verification both pass locally. No repo code changed; no R2/Neon mutation. R2 `--apply` publication and Neon projection deferred (commit deferred per user decision; belong with Task 6 Preview rehearsal).
- **Plan Contract:** `docs/plans/2026-09-29/v5-intended-update-2026-production-repair.md` (`In Progress`).
- **Approval / Status:** User approved this Task 3 preflight plan (run ID `v5-intended-update-2026-ratings-v1`, determinism rebuild deferred to Task 6). Exact production release remains a later packet-specific decision.
- **Blockers:** None for preflight. `--apply` needs a clean checkout at the expected SHA; checkout is dirty by design.
- **Next:** Task 4 (versioned forecasts + replacement scores) preflight.

## Context and Decisions
- Preflight ran against read-only Preview R2 certified parents bound to the working-tree source lock (`eaecabec…`, 271 games, cutoffs post-W0…W4). Output to `/var/…/opencode/v5-intended-update/ratings-preflight` — never repository `./data/`.
- One environment fix was needed to run the scaffolding: `PYTHONPATH=.:src` (the build imports `contracts.teams`). No code edits; noted for the Task 6 runbook.
- Lockfile shows `M` vs HEAD — expected (Task 1's 2-line update); the manifest binds the working-tree lock SHA at runtime.
- Determinism rebuild deferred to Task 6 per user decision.

## Work Completed
- Built the 2026 season rating manifest (preflight, no `--apply`): priors + pregame/current generations with logical generation hashes.
- Independently verified with `verify_v5_intended_update_2026.py --local-output` (ratings_lab replay, tolerance 1e-9).
- Ran acceptance spot-checks, Ruff, focused tests, `git diff --check`.

## Files Modified
- None. Implementation files were pre-existing untracked scaffolding.
- `session_logs/2026-09-29/04-v5-intended-update-task3-preflight.md` — this log.

## Validation
- [x] Priors: 276 rows, no dupes; stored priors equal certified R2 source (verifier).
- [x] Pregame: 271 games, 1,084 role rows (4×271), 542 team rows (2×271).
- [x] Current: 5 generations × 138 teams (690 team / 1,380 role rows).
- [x] Generation hashes: 11 (`pregame_w0`–`w5`, `current_post_w0`–`w4`) recorded in manifest.
- [x] Prior-only fallback: 246/276 post-W0 states have empty evidence and equal certified prior mean/variance exactly.
- [x] Verifier: `verified`, max mean/variance delta `6.66e-16`, manifest bytes SHA `a15d76f3…`.
- [x] Manifest: `production_activation_authorized: false`, parents bound to lock SHA `eaecabec…`.
- [x] Focused estimator tests: 5 passed. Ruff format + lint: clean (3 files). `git diff --check`: clean.
- [ ] R2 `--apply` + verifier `--apply` deferred to Task 6 rehearsal after commit.
- [ ] Generation-stability (`--previous-manifest`) and idempotent-projection checks belong to Task 6 (single manifest exists; mechanism in place).
- [ ] Prepare-week gate change (exact manifest SHA + verified cutoff) is Task 3 scope but a code change — deferred alongside the projector to Task 6 rehearsal.

## Amendments and Blockers
- No architecture amendment. Preflight-only execution is within Task 3's acceptance sequence.
- Note for Task 6 runbook: Task 3 scripts require `PYTHONPATH=.:src`.

## Handoff Notes
- **Resume at:** Task 4 preflight (`build_v5_intended_update_forecasts.py` + serving/verify) against the Task 2 bundle (`30c4f1eb…`) and this Task 3 rating manifest.
- **Watch out for:** Week 5 kickoff `2026-10-02T00:00Z` — Task 4's prospective slate decision must re-check kickoff/freeze state. Keep replay vs prospective labeling distinct. No `--apply` until commit order is resolved.

**tags:** ["ratings", "v5", "production", "implementation", "task3"]
