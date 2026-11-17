# Final site corrections and limited polish

- **Status:** Implemented 2026-11-16 locally on `dev`; not pushed or deployed
- **Created:** 2026-11-16
- **Approval source:** Owner approved the complete revised conversational plan with “Please implement the plan.” on 2026-11-16.
- **Implementation log:** `session_logs/2026-11-16/01-final-site-corrections.md`
- **Commit policy:** Commit bounded changes locally in `codex/final-site-polish`, integrate into local `dev`, then finalize the closeout. No push or deployment.
- **Parent contract:** [Site redesign and analytical usability](../2026-11-15/site-redesign-and-analytical-usability.md).

## Goal and acceptance

Preserve the approved layout, typography, navigation and mobile filter arrangement. Correct stale chart shares, hidden keyboard search results, Trends clearing and dark compact chart-dot visibility. Limit presentation polish to wrapped matchup team/role headings and the two full-detail disclosure indicators.

Implementation is complete after focused behavioral tests, fresh visual checks, independent code review, `make check`, `make web-e2e`, whitespace checks and local integration. No public API, schema, model or data-release changes.

## Baseline and constraints

- Baseline: clean local `dev` at `bd073c06`, ten commits ahead of the recorded remote; worktree `.worktrees/codex-final-site-polish`.
- The read-only review inspected real Preview data at 320/390/820/1440px in both themes. No page-level overflow or browser errors; twelve phone accessibility scans found no serious/critical violations.
- Suite-specific evidence: current web publication/unit suite 514 passed / 1 skipped; previous session browser baseline 483 passed / 10 skipped, not rerun during the review.
- The Teams hub already reads server search parameters. Keep the clearing fix client-side; add no production query reads to team profiles and preserve their query guard and `revalidate = 300`. Compare build classification under identical settings before and after.
- Work in a worktree. Preserve unrelated changes and prior local commits. Local-only implementation; no push, deployment, schema, modeling, ingestion or serving-data writes.

## Ordered changes

1. Audit all chart-export callers against rendered inputs: chart, season, week/window, side, metric, conference, highlighted/comparison teams, and data snapshots that can change without remounting. Retain centralized theme/dimension/background/title/filename coverage. Close actual gaps without a general caching framework.
2. Add keyboard-only active-option scrolling with `scrollIntoView({ block: "nearest" })`, preserving focus, active descendant and the live region. Mouse hover must not trigger scrolling.
3. Preserve explicit `team=` as a cleared first Trends team, with the initial default allowed only for an absent parameter. Preserve empty state through hub updates, normalization and `/ratings` redirect; retain nonempty aliases.
4. Give compact dark-theme scatter dots a theme-aware 1px perimeter at least 3:1 against the chart background. Preserve team fills, current light rendering, desktop logos, exports and hit areas.
5. Wrap full matchup team names with Offense/Defense on separate lines and rank chips retained. Add decorative open/closed chevrons to Full unit statistics and Full rating breakdown; retain native summary interaction and touch sizing.

## Validation

- Exports: prepared-image invalidation for every audited input; verify a subsequent image uses the new comparison. In-flight tests hold rendering at an explicit gate, confirm it started, change input, release, await stale-export completion and the enabled action, and only then assert no share/download. Frame counts/quiet-period `drainRender` are not completion evidence.
- Trends: clearing, reload, view changes, unrelated filters/periods, Back/Forward, `/ratings?view=trends&team=` forwarding and nonempty aliases.
- Search: first/last-result visibility, ArrowUp/Down, Enter, Escape, live-region compatibility and no mouse-induced jumps.
- Visual: fresh inspected 320/390px captures in both themes for long matchup names and dark-colored teams; desktop checks, 320px overflow, existing touch-target specification and accessibility scans. No new user-supplied screenshots are required; physical iPhone/Safari images are supplementary.
- Run `make check`, `make web-e2e`, `git diff --check` and code review before integration. Name each suite and result separately.

## Handoff/amendments

Finish implementation worker sessions before cleanup. From the primary checkout, verify cleanliness and ancestry, then use `git reset --keep <reviewed-tip>` only after proving the tip retains current `dev`. Reconcile any cherry-pick divergence and verify equivalence first; never discard unmatched commits. Verify the integrated tree and remove the worktree from the primary checkout. Finalize session-log Outcome and Next after integration/cleanup and commit closeout locally. No push.

Mechanical amendments may proceed only within the existing scope and acceptance criteria. Material conflicts require a revised plan.

### Implementation evidence and mechanical amendments

- Export audit: all five `ChartFrame` callers now supply rendered-data fingerprints (scatter, net success, game log, trajectory and market board). ChartFrame adds shared view/selection context; ExportActions retains theme, background, dimensions, title and filename. Equivalent JSON snapshots retain identity; changes in ordering or unused fields can conservatively invalidate. Payloads are bounded by roster, season and slate, with no new queries or eager image generation.
- The existing quiet-frame unmount helper was removed. A test-installed optional completion observer runs after the export action's final cleanup, including after unmount; the default runtime has no observer. Tests wait for the font gate to start and the action to settle before checking absent side effects. This is internal test observability, not a user-facing API.
- A single focused Node render test uses existing fixture data and local loader stubs to exercise the five actual chart callers. Equivalent cloned datasets reuse a prepared image; changed plotted values invalidate it. Five focused cases passed before the final full gate.
- The first focused run found a test-only locator mismatch (`textbox` versus the input's `searchbox` role), corrected without changing the control. The first full browser run found missing text whitespace between wrapped team-name and role spans; literal whitespace now preserves text/accessible content while the visual block layout remains.
- Matching baseline and changed fixture builds report identical route classifications. Team-profile server query guards and `revalidate = 300` are unchanged.
- Fresh real-Preview inspection at 320px found that sharing a heading row with the dot and rank forced ordinary words to break. The narrow layout therefore gives the name/role the full column and places the dot/rank on another line; desktop placement remains intact. This stays within the approved heading-wrapping adjustment, and the browser check now verifies word-width capacity as well as overflow.

### Completion

- `make check` passed on the final production changes: Python 2,546 passed / 12 skipped; web publication/unit 519 passed / 1 skipped; Worker 14 passed; Ruff, contracts, quality registry, strict docs, web lint/typecheck/build passed. Subsequent test-only navigation synchronization passed fresh lint/typecheck.
- Final `CI=1 make web-e2e`: 495 passed / 10 skipped, no retries. The strengthened Trends history test also passed twelve repetitions with retries disabled. An earlier unrelated away/home ordering flake passed six focused repetitions; no unresolved new failure remains.
- Security/reliability/accessibility, design/simplicity, correctness/testing and performance reviews completed. The two test-evidence gaps were closed and re-reviewed; no actionable finding remains.
- After integration, 56 real Preview page/viewport/theme checks at 320/390/820/1440px returned 200 with zero page overflow and zero browser errors. Fresh 320/390px light/dark matchup captures and desktop captures were inspected; the corrected name/role layout is readable and dark dots are visible. Health confirms predictions mode and full active-week coverage. No physical Safari/iPhone test was performed.
- Clean `dev` was proved an ancestor of the reviewed tip and moved with `git reset --keep`; tracked web/contract content matched. The implementation worktree and branch were removed from the primary checkout after workers finished. Outcome/Next were finalized only after this integration and cleanup, in a temporary documentation-only worktree. No push or deployment.
