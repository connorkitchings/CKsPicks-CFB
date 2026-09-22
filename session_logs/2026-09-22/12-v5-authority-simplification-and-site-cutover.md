# Session: V5 authority simplification and cutover code readiness

## TL;DR

- **Worked On:** Simplified V5 status and promotion policy, archived historical contracts, and added an explicit V5 serving adapter.
- **Outcome:** V5 model development is documented as complete and accepted. V4 remains public. Code can convert an independently verified live V5 forecast into the existing immutable weekly prediction-run format for Preview rehearsal; no live parent or publication was applied.
- **Plan Contract:** `docs/plans/2026-09-22/04-v5-authority-simplification-and-site-cutover.md`
- **Approval / Status:** User approved the proposed plan; contract remains In Progress until refreshed Week 4 parents, live verification, Preview publication/rollback rehearsal, and a separate activation decision.
- **Blockers:** Week 4 finals have not stabilized; new independently verified 07/08 parents and a live 09 manifest do not yet exist. The worktree was already dirty with the approved plan 03 tooling at session start and remains unstaged.
- **Next:** After Week 4 finals stabilize, refresh 07/08 under new immutable IDs; run 09 preflight/apply/verify/repeat; pin the verified forecast in a review copy of the V5 Preview config; rehearse Preview publication and V4 rollback; present the evidence for a separate activation decision.

## Context and Decisions

- The accepted 2022–2025 historical scorecard completes V5 model development. It does not supply a like-for-like point-in-time V4 comparison or prove V5 superiority.
- The former six-slate prelaunch gate is superseded. Contract 06 retains immutable prospective attempts and outcome-versioned monitoring, with diagnostic exclusions unchanged.
- Stabilized Week 4 finals and refreshed 07/08 manifests remain mandatory for the first current-state forecast. No 2026 outcome may refit this V5 identity.
- V4 remains the public model and rollback route; no production authorization was granted by code readiness.

## Work Completed

- Created `docs/modeling/v5_status.md` as the concise current authority and reduced the active plans index to 06–09 plus the cutover contract.
- Moved 37 completed/superseded V5 contracts into `docs/archive/v5-contracts/`, rebased their Markdown links, added an archive index, and made the V5 archive navigable in strict MkDocs.
- Updated AGENTS, README, architecture/quickstart/context, roadmap, methodology/evaluation references, contracts 06/09, and operations runbooks to separate model completion from live certification and site activation.
- Added `v5_weekly_serving_v1` with independent forecast reconstruction, exact manifest digest, serving-schedule binding, pregame market cutoff, complete margin/total coverage, preserved uncertainty, and explicit production activation gating.
- Routed V5 through standard weekly prediction-run output, preflight, and source snapshotting without requiring V4 Gold model-ready features. Retained the V4 pipeline path and config.
- Added focused serving, source-verifier, orchestration, timing, and documentation authority tests.

## Files Modified

- `docs/modeling/v5_status.md`, `docs/plans/index.md`, `docs/archive/v5-contracts/`, `mkdocs.yml` — current authority and preserved history.
- `AGENTS.md`, `README.md`, `.agent/CONTEXT.md`, `.codex/QUICKSTART.md`, roadmaps, modeling pages, V5 contracts, and runbooks — milestone and cutover policy.
- `src/cks_picks_cfb/inference/v5_serving.py`, `scripts/pipeline/generate_v5_weekly_bets.py`, `scripts/pipeline/generate_weekly_bets.py`, `scripts/pipeline/preflight.py`, `scripts/pipeline/snapshot_week_inputs.py`, `src/cks_picks_cfb/ops/__main__.py`, and `conf/weekly_bets/v5_preview_2026.yaml` — Preview serving path.
- Focused tests under `tests/` — schedule, timing, identity, source verification, and V4 compatibility.

## Validation

- [x] Focused V5, shadow, weekly pipeline, ops, artifact, and documentation tests: 189 passed.
- [x] `.venv/bin/ruff check .`
- [x] `.venv/bin/python contracts/validation.py`
- [x] `.venv/bin/mkdocs build --strict --quiet`
- [x] `git diff --check`
- [ ] Real Preview publication and rollback proof after refreshed Week 4 parents.

## Amendments and Blockers

- The planned cutover stages are sequential. This session completed documentation and code readiness; live 07/08/09 certification and real Preview rehearsal remain gated by future Week 4 finals.
- Existing unstaged plan 03 work was preserved. No Git staging or commit occurred.

## Handoff Notes

- **Resume at:** Verify stabilized Week 4 finals, then execute the 07 → 08 → 09 sequence with exact new Preview manifest IDs. Follow the Preview serving checklist in `docs/ops/v5_shadow_runbook.md`.
- **Watch out for:** A synthetic test or verified historical record is not a live V5 forecast. Do not set `production_activation_authorized: true`, publish to production, or count retrospective/diagnostic slates.

**tags:** ["v5", "ratings", "forecast", "documentation", "serving"]
