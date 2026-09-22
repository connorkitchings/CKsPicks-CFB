# Session: V5 Live Research Tooling Completion and Gate Review

## TL;DR
- **Worked On:** Completed the code-ready live forecast, Contract 05 adapter, and Contract 06 evidence runner/verifier under the approved implementation plan; reviewed and hardened the Contract 09 schedule and preflight gates.
- **Outcome:** Forecast preflight/apply/verify/repeat and evidence preflight/apply/verify/repeat are implemented. The full 2026 schedule is checked against certified measurement facts, verification/apply bind the requested identity and partition plan, and Contract 08 accepts a newly refreshed certified 07 ID by exact URI and raw checksum. Synthetic tests pass. Operational certification remains gated on stabilized Week 4 finals and fresh independently verified Contract 07/08 manifests.
- **Plan Contract:** `docs/plans/2026-09-22/03-v5-live-research-tooling-completion.md`
- **Approval / Status:** User explicitly authorized implementation of the approved plan on 2026-09-22; code readiness only.
- **Blockers:** Week 4 finals have not stabilized for this task, so no live forecast or readiness run was made. Contract 06 has no qualifying slate.
- **Next:** After Week 4 finals stabilize, refresh and independently verify 07/08 under new IDs; then run Contract 09 preflight/apply/verify/repeat and live readiness. Start Contract 06 only on independently verified `ready`.

## Context and Decisions
- V4 remains the production champion. V5 remains Preview-only with `production_activation_authorized: false`.
- The live forecast is an outcome-free dataset and manifest; the historical 11C prediction schema and artifacts remain sealed.
- Live Contract 05 support is a versioned adapter. Existing cutoff, measured freeze, paired coverage, stabilization, and diagnostic exclusion rules remain in force.
- Contract 06 code completion does not open its gate or count synthetic evidence. No live apply, Preview R2 publication, Week 5 certification, 2026 outcome fitting, production write, Neon write, or web change occurred.

## Work Completed
- Implemented the Contract 09 Preview runner, independent reconstruction/verification, exact parent and Week 4 checks, immutable output publication, and idempotent repeat behavior.
- Extended Contract 05 readiness source loading and independent verification for the live candidate schema, including exact forecast coverage and pre-kickoff timing. Extended freeze lineage and preserved diagnostic-only classification.
- Implemented Contract 06 source collection, immutable evidence runner and independent verifier, attempt dispositions, corrected outcome linkage, football reports, separate authentic-quote diagnostics, and existing-category recommendations.
- Follow-up review enforces exact 2026 schedule facts (week, kickoff, home team, away team) against the certified Contract 07 population, rejects verifier identity drift, and rejects changed partition digests in preflight evidence before immutable output writes.
- Removed the stale Weeks 0–3 Contract 07 run-ID pin from the Contract 08 producer and verifier. The runner still requires the signed Preview 2026 measurement schema, full output set, and certification digest; the replay binds the selected new URI and raw checksum.
- Amended Contracts 05, 06, and 09; refreshed the V5 runbook, evaluation authority, roadmap, plans index, and this implementation log.

## Files Modified
- `docs/plans/2026-09-13/05-v5-prospective-readiness-and-shadow-tooling.md`, `docs/plans/2026-09-13/06-v5-prospective-evidence-and-recommendation.md`, and `docs/plans/2026-09-18/09-v5-2026-forecast-and-readiness.md` — live interface and code-readiness amendments.
- `docs/ops/v5_shadow_runbook.md`, `docs/modeling/evaluation.md`, `docs/planning/data-first-football-forecasting-roadmap.md`, and `docs/plans/index.md` — current sequence and gates.
- `src/cks_picks_cfb/data/`, `src/cks_picks_cfb/forecast/`, and `src/cks_picks_cfb/ratings/` — outcome-free live forecast, shadow adapter verification, and evidence implementation.
- `scripts/research/run_v5_live_forecast.py`, `scripts/research/run_v5_prospective_evidence.py`, `scripts/research/verify_v5_prospective_evidence.py`, and existing `run_v5_shadow_*.py` runners — Preview code paths.
- `scripts/research/run_data_first_possession_rating_replay.py`, `scripts/research/verify_data_first_possession_rating_replay.py`, and `tests/ratings/test_possession_live_replay.py` — allow and test refreshed Contract 07 identities in the Contract 08 replay.
- `docs/plans/2026-09-18/08-v5-2026-rating-state-replay.md` — records the refreshed-parent interface amendment.
- `conf/research/data_first_football_v1/` — live forecast, live shadow, and prospective evidence configs.
- `tests/test_live_forecast.py`, `tests/test_live_forecast_sources.py`, `tests/test_v5_shadow_readiness.py`, `tests/test_v5_shadow_freeze.py`, and `tests/ratings/test_prospective_v5*.py` — focused regression coverage.

## Validation
- [x] Focused forecast, Contract 08 replay, shadow readiness/freeze/score/verifier/rehearsal, documentation authority, and prospective evidence suite: 173 passed (follow-up run).
- [x] CLI `--help` for live forecast, evidence runner/verifier, and readiness/freeze/score runners.
- [x] Ruff checks for the repository and format check for the new Contract 08 test file.
- [x] Repository-wide format check surfaced 10 existing files with format drift, including the two Contract 08 runners; left them unformatted to avoid broad unrelated churn.
- [x] `python contracts/validation.py`.
- [x] `mkdocs build --strict --quiet`.
- [x] `git diff --check`.

## Amendments and Blockers
- Contract 08 now accepts its refreshed Contract 07 parent under a new ID; see Amendment 1 in the implementation plan and Amendment 3 in Contract 08.
- The Week 4 and refreshed-parent operational gate is intentionally outstanding. No live apply or readiness certification was run.

## Handoff Notes
- **Resume at:** After stabilized Week 4 finals, refresh and independently verify 07/08 under new immutable IDs, then run the Contract 09 Preview certification sequence.
- **Watch out for:** Never run operational apply before stabilized Week 4 finals and new independently verified Contract 07/08 parents. Contract 06 collection begins only after independently verified `ready`.

**tags:** ["modeling", "forecasting", "research", "contracts"]
