# Contract B: Button-driven live chart inspector

- **Status:** Draft
- **Created:** 2026-10-21
- **Planner:** Sol
- **Approval source:** Design requested in the owner's three-contract plan; execution remains separately gated on A acceptance and owner approval of this exact contract.
- **Implementation log:** Pending; create a separate implementation log when authorized.
- **Commit policy:** Separate planning commit; independent B implementation/release decision. Owner executes Git operations.

## Goal and acceptance

Add a live SVG inspector after [Contract A](03-mobile-charts-a-page.md) is accepted. It supplies button-driven geometric magnification and native scrolling with shared chart configuration. Complete means shared settings, focus/scroll restoration, unique identifiers and exports are verified, with real iPhone Safari/Android Chrome checks at 4x and performance evidence for a dense national scatter. B must not start merely because A code or automated tests pass.

## Baseline and constraints

Planning baseline: dev at c892b669, followed by accepted A implementation. Reconcile the actual A result before editing. Preserve data calculations, aggregation, national domains, exports, publication gates and hidden trajectory. No custom pinch, history interception, charting library, Fullscreen API, pipeline, database or release-cache work. [Contract C](05-mobile-charts-c-evaluation.md) evaluates gestures/history only after device evidence from B.

## Ordered changes

### 1. Shared-state ownership and rendering interface

Introduce a context provider scoped to persistent ChartsView. Hoist only the state needed for sharing; keep transforms/aggregation unchanged. Expose resolved plot props and separate rendering from data loading. Mount a second plot inside a native modal dialog, not a second complete ChartsView; the page remains mounted and inert while the dialog is open.

| State | Authority/persistence |
| --- | --- |
| Chart kind, season, week/window, side | Existing route/server inputs; authoritative. |
| Highlighted team | Existing team URL parameter. |
| Conference and per-chart metric | Shared client context; preserve existing navigation/default/capability behavior. |
| Selected team/game detail | Shared client context; clear when absent from the new dataset. |
| Inspector open, internal settings pane, zoom | Inspector-local UI state; no URL/history entries. |

Every instance-specific DOM/SVG identifier/reference uses a unique useId prefix, including any clipPath, defs, accessible-label and form-control references. Do not hoist football calculations or duplicate server loading. Both plot instances and settings consume the same resolved state.

### 2. Modal, settings and magnification

Offer Expand at every screen size. The native modal has an accessible name, focus containment, Escape/Close dismissal and focus restoration. Reuse A's viewport/keyboard-aware sizing and background scroll locking/restoration. Keep title/context, Close, Settings, export actions, zoom controls and selected-item details outside scaled content. Settings is an internal pane within this modal, not a nested modal; configuration applies to the page and inspector and survives dismissal.

Render SVG at explicit scaled layout dimensions inside overflow:auto. Zoom buttons change dimensions; native scrolling provides panning and momentum. Use touch-action: pan-x pan-y pinch-zoom. Native pinch remains browser/page zoom and is not chart-only pinch magnification. No custom pointer-drag panning, CSS transform scaling or will-change:transform.

Provide Zoom in/out, Fit, current percentage and directional pan buttons, with keyboard equivalents and 44px touch targets. Scale is clamped from 1x Fit to 4x Fit. Fit contains the complete scatter; long row charts fit the width and scroll vertically. Zoom-about-center preserves the viewport center subject to scroll bounds. Compute fit, zoom bounds, center preservation and scroll clamping in a pure tested module.

Compensate typography for base scale only; inspector zoom enlarges text with the chart. Preserve the chart's row/bar layout captured at opening. Device rotation recomputes Fit without changing that layout. Reset magnification for dataset, metric, side or population changes; highlight-only changes preserve it.

Configuration navigation shows explicit loading/error/empty content, never old data under new labels. Browser Back keeps normal navigation behavior; navigation/unmount fully restores modal and body state. Do not add browser-history entries.

### 3. Exports and acceptance evidence

Exports use the current resolved settings and existing export layout, independent of viewport scroll position or magnification. Document device testing and performance traces. Native scrolling must not trigger React renders on each frame. Missing device evidence leaves B In Progress and C deferred.

## Validation

- Pure fit/zoom-limit/scroll-clamp/center-preservation tests, including rotation, long row charts and tiny viewports.
- Unique IDs and correct DOM/SVG references with page, inspector, settings and temporary export content mounted.
- All supported settings before opening, while expanded and after closing; preserve team/default selection and capability restrictions.
- Focus, Escape/Close, normal Back navigation cleanup, keyboard pan/zoom, safe areas, keyboard-open settings, scroll restoration and no page overflow.
- Dense scatter/full slate/full-season log, both themes, negative/zero/missing observations, loading/error/empty states and unchanged exports.
- On real iPhone Safari and Android Chrome inspect text crispness at 4x and record device/browser and a performance trace while scrolling a dense national scatter. Report frame timing and React commits; investigate recurring scroll-related scripting/commits rather than claiming device usability from emulation.
- Web lint/typecheck/publication tests/build/UI tests/publication-gate tests, make contracts-check, strict MkDocs and git diff --check.

## Handoff/amendments

Terra starts only after A's device acceptance is recorded and the owner separately approves B or explicitly authorizes this exact path. Reconcile the implemented A interfaces first. Record mechanical amendments with reason/old/new/impact; material changes return to Sol. C is not included in B authorization.
