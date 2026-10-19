# Mobile web experience

- **Status:** Implemented
- **Completed:** 2026-10-19
- **Created:** 2026-10-18
- **Planner:** Sol
- **Approval source:** Owner approved the proposed mobile web experience plan in this chat on 2026-10-18 with “Proceed.”
- **Implementation log:** `session_logs/2026-10-18/08-mobile-web-implementation.md`
- **Commit policy:** Separate planning commit, followed by user-controlled implementation commits

## Goal and acceptance

Give each page a clear mobile purpose while retaining the site's visual identity: Picks and Results support fast slate scanning; Ratings supports team/category comparison; Matchups supports game research; Performance explains records before exposing audit detail. Desktop presentation may change where the shared design benefits, as explicitly selected by the owner.

Include the four main tabs, matchup picker, matchup details, loading states and error states. Exclude Charts content/design and currently unlinked team-history pages.

Completion requires the ordered changes and validation below, with a rendered visual checkpoint after each implementation stage. At 390 × 844, the default populated fixture Picks and Results pages must show their first complete game card above bottom navigation with optional summaries collapsed. No content may overflow the viewport at supported widths or become obscured by navigation.

## Baseline and constraints

- Inspected clean `dev` at `b57fabe9`. Planning is isolated in the managed `mobile-web-plan` worktree. Begin implementation from a worktree containing this approved contract and recheck intervening changes.
- Read `AGENTS.md`, `docs/status.md`, `.codex/QUICKSTART.md`, `.agent/CONTEXT.md`, the planning workflow and recent October 16–18 session logs. Live release/week authority remains exclusively in `docs/status.md`.
- The existing local server rendered market-only content during review. Prediction-mode visual findings came from the public site, cross-checked against current source; do not treat local/public data differences as a model or release defect.
- At 390 px, the public Picks page's first full game card began approximately 819 px down. Records, Best Bets and controls occupied the initial viewport. Results had a similar hierarchy issue.
- On Ratings, choosing offense changes order but leaves overall rating as the largest value. Picks and Results duplicate toolbar behavior. Several matchup actions measured 26–32 px tall.
- At 640 px, the loaded public matchup page expanded to 739 px and pushed the home team off-screen. The current source retains the fixed-width forecast panel associated with this overflow.
- UI planning required no database connection or lake access. Environment files are present and the configured storage backend is `r2`; no credentials were printed. Any later real-data read must verify the intended environment independently.
- Keep existing dependencies, data contracts, serving queries, calculations, publication gates, missing-data meanings and fixed share-image content. No database migration, model change, publication change, release activation or deployment is authorized.
- Preserve the brand, palette and general visual language. Avoid global color/token changes that inadvertently redesign Charts.

## Ordered changes

### 1. Shared foundation

- Standardize repeated search fields, segmented controls, week navigation, disclosures and page headings with small shared components. Share behavior only where it is common; do not build a general configuration-driven page/card framework.
- Share the Picks/Results toolbar and card structure while retaining distinct prediction and grading content.
- Retain bottom navigation below the existing `sm` breakpoint and top navigation on larger screens. Match content clearance to actual bar height plus device safe areas; verify four-item and five-item navigation without changing Charts visibility.
- Use at least 44 px touch targets, visible keyboard focus, readable contrast and reduced-motion support. Primary content is at least 14 px; supporting metadata is at least 12 px. Normal text must meet WCAG AA contrast.
- Maintain semantic headings, labels, selected states and accessible disclosure controls. Ensure skip navigation and focus remain usable on included routes.
- Validate shared components before applying them to the remaining stages.

### 2. Picks and Results

- Order phone content as page/week context, compact record, collapsed Best Bets or Highlights, search/sort controls, then games.
- Keep spread and total records visible. Results emphasizes the selected week, with season context available through disclosure.
- Preserve every existing highlight and its game anchor when expanded. Expandable summaries are optional presentation; required publication/timing notices remain visible.
- Default phones to compact cards. Keep the desktop grid/list choice; omit that choice from the phone toolbar. A desktop view selection must not force a dense desktop row layout on a phone.
- Cards show both teams, kickoff or final scores, spread and total picks, model values, edges and applicable grades.
- Put extended forecast wording, line source, location and grading explanations in a labeled details disclosure. Preserve their original meaning and availability.
- Keep a dedicated Matchup link with a generous touch target. Let important team names and picks wrap instead of truncating them. Preserve away/home order and missing-line/no-lean distinctions.
- Preserve existing sort, search, week and season behavior, market-only restrictions and highlight anchors.
- Inspect representative populated cards at phone and desktop widths before continuing.

### 3. Ratings

- Promote the selected category's value when sorting Overall, Offense or Defense; label it explicitly and keep the remaining values secondary.
- Give sort controls an accessible selected state. Keep national ranking calculated before filtering.
- Replace the phone's scrolling period strip with a labeled period selector. Retain the wider-screen timeline.
- Preserve active search and sort when changing periods, using the existing rating route parameters rather than introducing a new API.
- Keep uncertainty and methodology accessible. Inspect all three selected-category states, period changes and long team names.

### 4. Matchups

- Place both teams together in a compact comparison header, with records and final scores where applicable.
- Put Forecast & Lines below the team header, using available width instead of a fixed-width center panel. This arrangement also eliminates the 640 px overflow.
- Below 1024 px, show one unit comparison at a time with selectors labeled “[Team] offense.” Default to away offense.
- Use three comparison columns on phones: offense value/rank, metric, defense value/rank. Keep all existing metrics, section groupings, rank/tie meanings and missing-value behavior.
- At 1024 px and above, retain both unit comparisons side by side.
- Apply shared week controls and compact game entries to the matchup picker.
- Preserve share-image content and export behavior, numerical formatting, availability notices, publication gates and existing navigation destinations.
- Inspect upcoming and completed games, both unit selections, and unavailable-stats states before continuing.

### 5. Performance and shared states

- Lead with separate spread and total records and win rates. Keep forecast diagnostics in an expandable section labeled as season-wide.
- Follow with weekly records and their Results links.
- Make the audit collapsed by default. Opening it exposes a week selector defaulting to the latest graded week; game disclosures reveal forecasts, captured lines, grades and provenance.
- Keep the existing target filter consistent across weekly records and audit entries. Preserve the existing season-summary calculation semantics.
- Preserve access to every graded game without rendering the full expanded audit in the default page flow. Filtering to another target must not silently select a different audit week; an empty selected-week result receives an explicit empty state.
- Align loading placeholders with the revised page hierarchy. Keep retry and unavailable states readable and usable, with user-facing copy rather than infrastructure implementation details.
- Inspect the complete core journeys on phones and desktop.

### Interfaces and compatibility

There are no new public data APIs, database schemas, projection types or serving queries. Component props may change internally to share controls, compact summaries and disclosures. Existing URLs, week/season selection, rating period/search/sort parameters, game anchors, publication modes and share-image data remain compatible. New unit/audit/disclosure state is presentation state; this contract does not require new route parameters.

## Validation

- Inspect widths 320, 360, 390, 430, 640, 768, 1024 and 1280 px, including both sides of any changed breakpoint. Include the existing 639/640 and unit-panel 1023/1024 transitions.
- Verify light/dark themes, touch and keyboard interaction, browser zoom, reduced motion and bottom-navigation/safe-area clearance. Check horizontal overflow after content loads, not only while skeletons display.
- Cover long names, missing lines, no lean, pushes, ungraded games, empty searches, unavailable stats, loading and retry states.
- Extend fixtures to include teams whose overall/offense/defense order differs, multiple periods and enough games/weeks to exercise card scanning and audit navigation.
- Test disclosures, selected states, unit switching, correct metric emphasis, period/filter preservation, desktop-view-to-phone resizing and unchanged displayed numbers.
- Verify every audit game remains reachable by its week and applicable target. Verify target changes, empty audit weeks and latest-week default.
- Keep publication/matchup restrictions and disabled/enabled Charts navigation regression coverage. Do not change chart content or numerical tests to accommodate unrelated failures.
- Run `npm --prefix web run lint`, `npm --prefix web run typecheck`, `npm --prefix web run test:publication`, `npm --prefix web run build`, affected browser suites and the Charts publication-gate suite. Run the core mobile journeys in Chromium and WebKit. Use a clean implementation worktree and independent server so existing development servers and their `.next` outputs are not disturbed.
- Capture and visually inspect before/after screenshots at representative phone and desktop widths after each stage. These checkpoints verify this contract; a material design departure returns for review.
- Perform the repository code-review workflow after implementation and resolve actionable findings.
- Run `git diff --check` and `uv run mkdocs build --quiet` for documentation changes, keeping generated output outside tracked files. Record exact results and any pre-existing failures in the implementation log.
- Definition of done: all included journeys meet the acceptance criteria, all required checks pass, screenshots have been inspected and behavior/documentation/session-log changes are complete. Do not claim real-device Safari testing from WebKit automation alone.

## Handoff/amendments

Owner approved this scope in chat on 2026-10-18. The planning task saves only this contract, its index entry and its planning log. Product implementation belongs in a fresh Terra task using the repository-local `implement-plan` skill and this exact path.

The planning log is `session_logs/2026-10-18/07-mobile-web-planning.md`. Allocate the implementation log's current date and next unused number when starting. Recommend a separate planning commit; the owner executes all commits, merges and pushes. Production or Preview deployment/activation requires separate authorization.

A mechanical amendment may proceed only if architecture, interfaces, scope and acceptance remain unchanged. Record its reason, prior approach, revised approach and impact in this section and the implementation log. Material changes or conflicts return to Sol for owner review.

Copy-ready implementation prompt:

```text
Use the repository-local implement-plan skill and implement the approved contract at:

docs/plans/2026-10-18/04-mobile-web-experience.md

Treat it as authoritative. Preserve its architectural decisions, run its validation,
and stop for any material conflict. This request explicitly authorizes implementation.
Work in an isolated worktree that contains the approved contract.
```


## Implementation completion — 2026-10-19

Implemented in the isolated `mobile-web-plan` worktree from `b57fabe9`, following the owner's explicit exact-path implementation authorization. The implementation log records the staged visual checkpoints, focused corrections and final verification: `session_logs/2026-10-18/08-mobile-web-implementation.md`.

Mechanical amendments preserved architecture, interfaces, scope and acceptance:

- Global skip navigation required focus targets on excluded routes; added only main IDs and tab indices to Charts, methodology and team history. Their content/design remains unchanged.
- Browser verification exposed early search input before hydration and browser-dependent date punctuation. Shared search controls now wait for hydration before accepting input, and market timestamps assemble explicit timezone-aware date parts consistently.
- A simulated 34 px home-indicator area exposed insufficient first-card clearance on Results. The visible week record heading and Season context disclosure now share a row, with expanded context spanning the full width. No text or targets were reduced. First-card bottoms are approximately 724 px on Picks and 744 px on Results, above navigation at 753 px in both browser engines.
- Six source-shape assertions in `ratings.test.ts` were mechanically updated for wrapping, card extraction and accessible wording. Numerical assertions and calculations remain unchanged.

Final validation passed: lint, typecheck, 245 unit/publication tests (1 existing skip), 123 Chromium tests (23 existing skips), 79 WebKit tests (8 existing hidden-chart skips), Charts-enabled and Charts-disabled fixture production builds, 12 Charts gate tests, documentation build and diff whitespace checks. A loaded-content matrix covered 120 route/width/theme combinations with no page errors or horizontal overflow. Keyboard, reduced motion, 2× browser zoom, disclosures and safe-area checks passed. Three independent behavior, design and security reviews found no actionable issues. WebKit automation does not constitute physical iPhone/Safari testing.

All definition-of-done items are complete. No data access, deployment, staging, commit or push occurred. Owner-controlled planning and implementation commits remain the next step.
