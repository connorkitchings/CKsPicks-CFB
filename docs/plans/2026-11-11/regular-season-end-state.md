# Regular-season end state (postseason option B)

- **Status:** Approved
- **Created:** 2026-11-11
- **Planner:** Sol
- **Approval source:** Owner chose option B on 2026-11-11 ("B is fine"): the official 2026 V5 record ends with the last regular-season week, and the site shows a clean "regular season complete" state. The owner approved this contract for implementation on 2026-11-11 ("1 approved"). Task 1 (final-week verification) and the stop gates still apply.
- **Implementation log:** `session_logs/2026-11-11/` (number assigned at implementation)
- **Commit policy:** Commit with implementation; one pull request into `dev`. A `dev` to `main` release is needed before the final close runs, because scheduled workflows run only from `main`.

## Goal and acceptance

Today the weekly controller stops at `FINAL_REGULAR_WEEK = 15` (`scripts/ops/weekly_automation.py:39`). `decide_close_week` returns `skip` ("week 16 is past the final regular-season week") when the active week is 15. Nothing then grades the final week's games, so Production would stay on the final-week slate with every game played and none graded, and the official record would silently omit the last week. The engine itself already allows a release with no next week (`--next-week` is optional in `scripts/pipeline/run_season.py`; `season/prepare.py` and `season/runner.py` set `active_week` to `through_week` when it is `None`).

Acceptance:

1. After every game of the final regular-season week is final, the automation (or an owner dispatch of close-week) produces and activates one **final close** release: all weeks through the final week graded, no next-week slate, `active_week` equal to the final week. The cumulative record includes the final week.
2. After that release, further scheduled runs skip cleanly (green, with a clear reason), never fail, and never open a postseason week.
3. The site shows an explicit "Regular season complete" state with the final cumulative record (and that postseason games are not part of the record), on the pages that today present the active week. No postseason data is ingested, predicted, graded or displayed.
4. The pre-final close from the second-to-last week still opens the final week exactly as today.
5. Existing behavior for every earlier week is unchanged (existing controller and release tests pass without edits to their expectations).

## Baseline and constraints

- Baseline: `dev` after PRs #33 and #34. The controller decision logic is `decide_close_week` and `Controller.detect` (`weekly_automation.py` lines 128 to 161 and 573 to 616). The data provider files bowls and the CFP under `season_type="postseason"` with restarting week numbers; `refresh_game_outcomes.py` and `data/team_stats.py` already fix `season_type` to regular.
- **Open fact that must be verified first (stop gate):** the last regular-season week in the 2026 schedule. The constant says 15 (conference championships, 2026-12-05). The Army–Navy game falls a week later and may be filed by the provider as regular-season week 16. Read the stored 2026 schedule capture (or one read-only schedule request with `season_type="regular"`) and report the maximum regular-season week and its games and dates. If it is 16, stop and ask the owner whether the record ends at 15 (Army–Navy excluded, stated on the site) or 16 (set the final week to 16). Do not choose silently.
- In scope: `scripts/ops/weekly_automation.py` (decision and the final-close path), `.github/workflows/weekly-season-update.yml` only if the final close needs a workflow input, `scripts/pipeline/run_season.py` and `scripts/pipeline/build_season_revision.py` only as far as a final close needs them (no next week), the matching tests, the web "regular season complete" state and its tests, `docs/ops/weekly_runbook.md`, `docs/status.md`.
- Out of scope: any postseason modeling, ingestion or display; any model, rating or feature change; changing completed-week grading rules; Production releases made by this work (the final close runs in its scheduled slot or by owner dispatch).
- Constraint: the final close must pass every existing gate (release parity, verification, Preview before Production, expected-previous check). No gate is relaxed.
- Constraint: the controller's final week stays a single named constant, set from the verified fact above, with the reason in a comment.

## Ordered changes

1. **Verify the final regular-season week** (read-only; see the stop gate above). Output: the maximum regular-season week, its games and kickoff dates, recorded in the implementation log.
2. **Feasibility check of a no-next-week release** in the disposable test setup: `advance-week` builder arguments and `prepare` without `--next-week` for the final week, including `season_verification_v2` and parity expectations (no next-week predictions or lines, `projection_serving` with `active_week == through_week`). Output: a short written finding and a failing test per gap. Stop gate: if the engine needs more than small, local changes (new tables, schema changes, or a change to verification rules), stop and return to Sol with the finding.
3. **Controller.** Replace the `skip` at `nxt > final_week` with a `run` decision that marks the close as final (a field on `Decision` or a distinct action) when the final week's games are all final and nothing is left to open; keep `stop` when any final-week game lacks a final score and `skip` once the release already carries the final week as `through_week`. Pass no next week to the builder and `prepare`. Skip reasons stay explicit. Tests: the decision table around the boundary (week 14 to 15 unchanged, week 15 incomplete, week 15 complete, already final, after final), plus a run through the controller's existing fake dependencies.
4. **Web state.** When the active release's active week equals the final week, every game in it is final, and no later week exists, show a "Regular season complete" notice with the final record, using the existing week-phase helpers in `web/src/lib/slate.ts`. Keep all browsing of past weeks unchanged. Tests: unit tests for the state helper; `make web-e2e` fixture for the final state.
5. **Documentation.** Runbook section "End of the regular season" (what runs, what the owner checks, what is deliberately not done), `docs/status.md` Open items (remove the postseason item, record the decision and the final week), and a note in `docs/modeling/record_methodology.md` that the official record covers the regular season only.

## Validation

- `PYTHONPATH=src:. uv run pytest tests/test_weekly_automation.py tests/test_season_release.py -q` and the full suite `PYTHONPATH=src:. uv run pytest tests -q -n 4`; `uv run ruff format --check .`; `uv run ruff check .`; `make contracts-check`.
- Web: `make web-e2e` (required for a web change before any `dev` to `main` release).
- Controller `plan-only` dispatch after the `dev` to `main` release confirms detection, with no provider call or write.
- `git diff --check`, `uv run mkdocs build --strict -q`, session log.
- Release evidence for the real final close (owner-observed, not part of this PR): Preview then Production activation receipts, `/api/health` showing the final week with no next slate, the Model page record including the final week, and a following scheduled run that skips with the final-state reason.
- Stop gates: the final-week verification (task 1), the engine feasibility finding (task 2), any need to edit an existing test expectation, any change needed in verification or parity gates.

## Handoff/amendments

- Approval and resume gate: approved 2026-11-11. Implementation starts at task 1 and may not start the controller change before the final-week fact is recorded.
- Timing: the work must reach `main` before the final regular-season week completes (early December 2026). Production releases and the final close itself need the owner's usual go-ahead; the automation's normal automatic activation covers the scheduled case.
- Amendments: a mechanical amendment may proceed if architecture, interfaces, scope and acceptance are unchanged; a material conflict returns to Sol. Record each amendment with reason, previous approach, revised approach and impact.
  - 2026-11-11, mechanical (task 3): the controller decides a final close only when the week after the final week has no scheduled games. Previous approach: replace the `skip` at `nxt > final_week` unconditionally with a final `run`. Revised approach: the existing test `test_close_week_skips_past_final_regular_week` supplies week-16 games and expects `skip`, and acceptance 5 forbids editing existing expectations, so games present past the final week still skip ("past the final regular-season week") and an empty week 16 (the verified provider state) runs the final close. Impact: none on acceptance; a provider-added week 16 skips loudly in the log instead of closing.
  - 2026-11-11, mechanical (task 2/3): the final close passes parity as `--completed-week 15 --upcoming-week 15` and the live health probe expects week 15, so neither gate script changes. The revision builder is called unchanged with `--week 16` (its week-to-forecast convention); no builder, engine or schema change was needed.
  - 2026-11-11, mechanical (task 4): the web notice is computed in `web/src/app/(games)/page.tsx` from the active week, the final-week constant `FINAL_REGULAR_WEEK = 15` in `web/src/lib/slate.ts` (a second copy of the controller constant, commented as a mirror), the games' phase and the published weeks; the e2e fixture uses a UI-test-only `?finalWeek=4` parameter.
