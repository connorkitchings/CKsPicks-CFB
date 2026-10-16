# Session: Weeks 0–6 Preview chart rehearsal

## TL;DR

- **Worked On:** Resumed the owner-authorized chart rehearsal on branch `connorkitchings/charts-module` from clean commit `749ee12c`.
- **Outcome:** Prepared output verified, numerical parity passed, Preview release activated and live chart/core-page checks passed. PNG export visual acceptance failed on unwanted blue focus outlines.
- **Plan Contract:** `docs/plans/2026-10-16/01-charts-module.md`
- **Approval / Status:** User explicitly transferred and authorized the prepare → parity → Preview activation → inspection sequence in this chat. Contract remains In Progress.
- **Blockers:** Static PNG exports contain keyboard-focus rings; task 8 is not complete. Production remains separately owner-gated.
- **Next:** Fix export focus-ring rendering, commit through the owner, and re-verify before any production promotion.

## Context and Decisions

- No worktree changes existed at takeover. The interrupted prepare log had no completion line, but retained status inspection returned `passed` and verified the run-manifest/output hashes. No restart or artifact deletion was needed.
- Preparation used `WEEK=7 RECONSTRUCT=1 AS_OF=2026-10-16T15:49:50Z`, retaining the Week 7 pre-week forecast cutoff and completed Weeks 0–6 inputs. No Week 7 finals or Week 8 inputs were needed.
- The current release identity, payload checksum and activation receipt are recorded only in `docs/status.md`.
- No Production access, captures, paid calls, re-pinning, migrations, push, merge or commits occurred in this session. All tracked edits occurred after Preview activation and contain evidence only.

## Work Completed

- `run_season.py status`: passed, including retained output checksums. All 23 verification checks passed, including `team_chart_reconciliation` with zero violations.
- Chart coverage: 138 roster teams; 658 team-game rows / 329 games in Weeks 0–6; 1,378 adjusted rows in as-of windows 3–7; 21 `charts_v1` projection tables.
- Read-only Preview parity checked all 18 `core_v1` tables, totaling 54,745 rows. No missing/extra natural keys and no unexplained differences. Floats compared at absolute tolerance `1e-9`; equivalent UTC timestamps normalized to microseconds.
- Explicit parity exclusions: server `release_id`/`environment`; `code_sha`/`config_sha`; audit timestamps `created_at`, `updated_at`, `inserted_at`, `published_at`, `selected_at`, `graded_at`; provenance `source_manifest_sha256`, `source_versions`, `rating_manifest_sha256`, `measurement_manifest_sha256`, `payload_sha256`, `publication_id`, `spread_model_version`, `total_model_version`. Old/new run identity prefixes normalized; the publication compared by `(season, lineage)`. Prediction model-version strings incorporate the run and rating identity (`projection_serving.py`), so their changed suffixes are provenance rather than numerical model differences. Kickoff and cutoff timestamps were compared, not excluded.
- Staged and activated with `make season-release ENV=preview` and exact operator payload SHA plus expected previous release. Exit 0; activation returned a verified readback checksum. The old release remains retained.
- Real-data browser used `CFB_PUBLICATION_MODE=predictions CFB_PUBLICATION_SEASON=2026 PORT=3200 zsh scripts/ops/run_web_local.sh preview`; no fixture mode.
- Net-success bar counts for Weeks 0–6: **8, 43, 49, 57, 58, 56, 58**, respectively; all seven windows rendered.
- Efficiency offense, efficiency defense and adjusted scatters each rendered Through Weeks 2–6. Through Week 2 has 137 plotted teams; later windows have all 138. The early missing team is represented by the unavailable list.
- SEC filter leaves 16 active / 122 dimmed markers; search highlights Ohio State; table lists 138 rows. Keyboard navigation opens a team tooltip. Week selector successfully switches the rendered window.
- Five-team statistical spot-checks: Alabama, Clemson, Ohio State, Texas and Notre Dame; success rate and EPA/play for both roles in Through Weeks 2–6 (100 comparisons) agree with `team_season_stats` at `1e-9`. The displayed Through Week 6 offense table matches the rounded values (e.g. Alabama 49.7%, +0.332; Clemson 34.9%, +0.022; Ohio State 53.1%, +0.313; Texas 43.8%, +0.090; Notre Dame 54.2%, +0.374).
- Health: status `ok`, predictions mode, active Week 7, expected/predicted/lined **59/59/55**, and selected week agrees with current week. Picks has 59 matchup links; Results has 58 completed Week 6 matchup links. Ratings renders current V5 ratings; Performance retains spread 166–157–6 and total 163–164–1. Server requests returned 200; no application query errors were observed.

## PNG Export Finding

- Both Week 6 net-success and Through Week 6 adjusted exports download at **2000×1125**. Decode reports: bar 232/232 referenced sources, adjusted 276/276. Saved images were opened and visually inspected, not accepted on dimensions alone.
- **Failure:** the bar PNG includes blue full-height rectangles around every game; the adjusted PNG includes blue circles around every marker. The live charts do not show these unselected outlines.
- Static exports render `.focus-ring` shapes in `NetSuccessChart.tsx` and `ScatterChart.tsx` even with `interactive=false`. Their CSS-only hidden state is not preserved in these captures. Proposed bounded repair: omit interaction-only rings from noninteractive renders; keep live keyboard focus behavior. No source fix was made in this session.
- Download latency was substantial (about 54 seconds for bars and 170 seconds for adjusted); these are observations, not a performance guarantee. Efficiency PNG was not separately exported after confirming the shared scatter export defect.
- Retained ignored evidence under `artifacts/season/2026/preview/chart-rehearsal/`: `parity.json`, `stat-spotchecks.json`, `net-success-week6.png`, `adjusted-through-week6.png`. Read-only comparison/spot-check scripts were temporary files under `/private/tmp/`.

## Files Modified

- `docs/status.md` — current Preview release and incomplete export acceptance; Production unchanged.
- `docs/plans/2026-10-16/01-charts-module.md` — current contract status and export blocker.
- `session_logs/2026-10-16/02-charts-module-implementation.md` — resumed operational evidence.
- `session_logs/2026-10-16/03-preview-chart-rehearsal.md` — this session's evidence and handoff.

## Validation

- [x] Retained preparation checksums and 23 verification checks.
- [x] All 18 core-table parity checks and 100 raw-stat spot-checks.
- [x] Preview atomic release/readback and real-data browser checks above.
- [ ] PNG visual acceptance: failed on focus outlines; repair required.
- [x] `uv run --offline --no-sync mkdocs build --strict --quiet`: passed after replacing two new links to session logs outside the MkDocs source tree with code paths.
- [x] `git diff --check`: passed.
- [x] The rehearsal dev server on port 3200 was stopped; no commit, push or merge was performed.

## Amendments and Blockers

No model or data amendments. Static export visual defect blocks full chart acceptance. Preview recovery remains forward release of a corrected candidate; no unsupported Preview rollback was attempted.

## Handoff Notes

- **Resume at:** bounded rendering fix for static export focus rings, followed by owner commit and appropriate Preview re-verification. Keep the active release in `docs/status.md` as authority.
- **Watch out for:** no Production promotion is authorized. Week 8 is separate and still requires complete Week 7 finals, controller inputs, reviewed captures, exact exceptions, and clean committed inputs.
- **Proposed evidence commit:** `docs(charts): record Preview rehearsal and PNG export blocker`

**tags:** ["charts", "preview", "season", "verification"]
