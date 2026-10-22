# Contract C: Evaluate chart gestures and history

- **Status:** Deferred
- **Created:** 2026-10-21
- **Planner:** Sol
- **Approval source:** Owner requested this deferred evaluation contract; no authorization for gesture/history implementation.
- **Implementation log:** Pending evaluation evidence after B device testing.
- **Commit policy:** Separate planning commit; any resulting implementation requires a new owner-approved amendment. Git operations remain owner-controlled.

## Goal and acceptance

After [Contract B](04-mobile-charts-b-inspector.md) is tested on real iPhone Safari and Android Chrome, determine whether button zoom and native scrolling adequately support inspection. This is an evaluation contract, not a code implementation contract. A valid outcome is that no custom pinch or history work is needed.

## Baseline and constraints

Depends on accepted [Contract A](03-mobile-charts-a-page.md) and B's device evidence. Preserve SVG, native browser zoom, accessible button alternatives, exports, all existing publication boundaries and hidden trajectory. Do not implement custom pinch, focal-point zoom, history interception or new state/URL contracts under C alone. Native page pinch does not prove custom chart pinch works.

## Ordered evaluation

1. Record device model, OS/browser, tested dataset/configuration, task and observed result for reading national scatters, following a season log, changing settings and closing inspection.
2. Determine whether buttons plus native scrolling suffice. Record specific unmet tasks and user evidence rather than assuming gestures are necessary.
3. If chart-only pinch is justified, propose a separately approved amendment with pointer cancellation, scrolling/browser-zoom conflicts, per-chart gesture scope, accessible alternatives and pure tested clamp/fit/zoom-about-point mathematics. Specify requestAnimationFrame updates rather than React state for every movement. Validate scope for scatters and long row charts; do not disable scrolling globally.
4. If Back-to-dismiss is justified, propose a separately approved amendment: one inspector-owned entry, no drawer entries; explicit Close uses history.back only while that entry is owned/current. Specify Next.js route changes, settings persistence, forward/back behavior and scroll restoration before implementing.
5. Record accept/no-change/defer decisions and remaining evidence gaps. No code follows automatically from evaluation approval.

## Validation

Require real-device observations from both platforms. Any gesture proposal also requires pure zoom-math tests, real-device text crispness at 4x and performance evidence for panning a dense national scatter. Do not claim Playwright WebKit emulation verifies native pinch. Documentation persistence runs strict MkDocs and git diff --check; any later implementation amendment defines its own complete regression gates.

## Handoff/amendments

Remain Deferred until B has device evidence and the owner requests evaluation. A or B approval does not approve C implementation. Any resulting code needs a new decision-complete amendment and separate exact-path authorization; retain user-controlled Git and release decisions.
