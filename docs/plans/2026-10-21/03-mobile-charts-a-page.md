# Contract A: Mobile chart page

- **Status:** In Progress
- **Created:** 2026-10-21
- **Planner:** Sol
- **Approval source:** Owner explicitly authorized implementation of this exact Draft path in the 2026-10-21 user message: "Use implement-plan to implement Contract A only"; B and C remain outside authorization.
- **Implementation log:** `session_logs/2026-10-21/03-mobile-charts-a-implementation.md`.
- **Commit policy:** Separate planning commit, followed by independent implementation/release decisions for A and B. Owner executes Git operations.

## Goal and acceptance

Make the ordinary mobile Stats page usable without an inspector. This is independently shippable. Complete means all five visible chart families work at 320/390/430px without page-level horizontal overflow, essential chart text is readable at base size, controls and selected-item information remain reachable with the keyboard open, and real iPhone Safari and Android Chrome acceptance evidence is recorded. Passing emulation alone does not close A or authorize B.

## Baseline and constraints

Inspected `dev` at `c892b669`. Scatters use a 1000 x 640 viewBox inside a minimum-760px horizontal scroll area. The game-log metric group was measured at about 314px within a 288px controls area on a 320px viewport, producing page overflow. Existing pointer handlers support selection; there is no custom pan/pinch or modal infrastructure.

Preserve SVG, national scatter geometry/domains/averages, existing export content and dimensions, desktop layout, the publication gate, and the hidden rating-trajectory chart. No pipeline, database, release-cache, Production activation, inspector, custom gesture, or browser-history work. The earlier owner direction against a phone-specific scatter arrangement remains in force.

Related contracts: [B: inspector](04-mobile-charts-b-inspector.md), [C: evaluation](05-mobile-charts-c-evaluation.md). A must not include B's shared-state ownership refactor.

## Ordered changes

### 1. Mobile navigation and settings

Below 640px replace scrolling chart tabs with a two-column grid of the five ready chart chips, in registry order; the final chip spans both columns. Desktop navigation remains unchanged. Keep the current settings summary visible. Move week/window, side, metric and conference controls into a settings drawer; keep the team finder directly available on supported charts. Render one active settings control tree. Use 44px touch targets for controls, including week arrows, metric options, team options and Clear. Wrap long choices rather than overflowing.

Use native `dialog` for the settings sheet, with an accessible name, initial focus, Escape dismissal and focus restoration. Do not create history entries. Use 100dvh, safe-area padding and contained scrolling. Save body positioning/styles and scroll position when locking the background; restore on dismissal or navigation rather than relying solely on overflow:hidden. Subscribe to visualViewport resize/scroll events to constrain the sheet and team results above the keyboard, with a layout-viewport fallback. Scroll the active result into view and remove subscriptions on cleanup.

### 2. Readable chart presentation

| Chart | Mobile presentation and settings |
| --- | --- |
| Net success | Existing horizontal game rows; week and conference; full-row tap targets. |
| Efficiency | Existing national scatter and scrolling; through week, side, conference, team, and supported metric. |
| Adjusted PPA | Existing national scatter and scrolling; through week, conference and team. |
| Possession | Existing national scatter and scrolling; through week, conference, team and Points/PPA. |
| Game log | Horizontal game rows in stacked offense and defense panels; conference, team and supported metric. |

Measure rendered text sizes. Compensate essential SVG tick/axis/quadrant font sizes for the base viewBox-to-container scale to achieve at least 12 CSS pixels. Update margins and label placement to prevent collisions; do not simply enlarge text into overlaps. Preserve scatter geometry/minimum width and export typography. Do not require expansion to read the base chart.

Give game-log rows two logical bands: opponent/week/site/result context, then value/bar/weekly FBS benchmark. Wrap long names further rather than truncating essential information. Both panels share one increasing numeric scale, labeled offense higher-is-better and defense-allowed lower-is-better. Preserve chronology, negative values, zero, missing observations, benchmark meaning and existing season summaries. Row targets are at least 44px and may grow to fit content.

Show every net-success game by default. Tall slates are accepted; no top-N filtering or virtualization.

### 3. Selection and team search

On mobile show selected-item details outside the plot, replacing floating tooltips; preserve desktop hover and keyboard behavior. Scatter selection uses screen-pixel distance, not overlapping enlarged hitboxes: consider points within 24px; select the nearest unless another candidate is within 8px of its distance. For ambiguity offer up to three nearest teams as labeled buttons, using stable team-name ordering for equal distances; team search remains available for other choices. An empty-area tap clears transient selection. Ignore taps after native scrolling or pointer cancellation.

Implement team-search Arrow Up/Down, Enter, Escape, aria-activedescendant/active-option announcement and active-result scrolling. Preserve current URL/default/highlight behavior and retained-release capability restrictions. Selection remains local to the current chart in A.

### 4. Evidence and documentation

Record changed interfaces/behavior and scoped validation in the implementation log. Record device model, OS/browser, viewport, scenario and result for real-device acceptance. Missing devices leave A In Progress; do not label it Implemented or infer acceptance from automated checks.

## Validation

- All five visible charts: 320/390/430px portrait, landscape and desktop; both themes; dense national scatter, full slate and full-season log; long names; retained releases without explosiveness; missing/zero/negative observations and unavailable states.
- Assert no page overflow, minimum touch targets and actual rendered essential text sizes; check labels do not collide and selected details are not clipped.
- Test nearest-point ambiguity/radius/ties, native scroll cancellation, keyboard selection and team-search keyboard behavior. Check keyboard-open results, Escape/focus return, drawer dismissal/navigation cleanup and scroll restoration on real iPhone Safari and Android Chrome.
- Verify every supported setting, existing URL behavior, hidden trajectory, gate behavior and unchanged export dimensions/content.
- Run web lint, typecheck, publication tests, build, UI tests, publication-gate tests, make contracts-check, strict MkDocs and git diff --check via project tooling.

## Handoff/amendments

Resume in a fresh Terra task using implement-plan with this exact path and explicit authorization. Implement A only. B requires recorded acceptance of A and separate owner approval. C remains deferred. No application files are changed by the Sol persistence session.

Mechanical amendments may proceed only when architecture, interfaces, scope and acceptance remain unchanged. Record their reason, previous approach, revised approach and impact; material conflicts return to Sol. Real-device evidence and publication decisions cannot be replaced by local fixture tests.

## Amendment 2026-10-23: phone scatter and compact header

- **Reason:** Mobile checks showed most of the first Stats and Ratings screen was header, and the 760px scatter hid most teams off screen.
- **Previous approach:** One national scatter geometry in a horizontally scrolling area at every width; chart chips in a grid; a full page header above the chart.
- **Revised approach:** Below 640px the scatter uses a phone portrait viewBox that follows the container width at 1:1 scale in a tall aspect, so the whole chart fits without scrolling. This reverses the earlier owner direction against a phone-specific scatter arrangement; the owner has since approved it. Desktop geometry, domains, averages and exports are unchanged. The chart chip grid is replaced by a pinned chart dropdown, the settings trigger and a summary line sit in a pinned bar, chart descriptions collapse into disclosures, and Ratings gets the same pinned search and Filters bar.
- **Impact:** Acceptance still requires the real-device evidence above. Follow-on shell work is tracked in [03-mobile-app-feel](../2026-10-23/03-mobile-app-feel.md).
