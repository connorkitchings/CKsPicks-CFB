# Session: Stratum review-findings remediation

## TL;DR

- **Worked On:** Fixing the contract gaps and medium/low findings from the review of the unreleased Stratum redesign, in five phases.
- **Outcome:** Implemented and validated on `connorkitchings/stratum-review-fixes` (based on `origin/dev` `b8250246` plus the local-only `dev` commit `b854196f`, cherry-picked). Not pushed.
- **Plan Contract:** [Site redesign and analytical usability](../../docs/plans/2026-11-15/site-redesign-and-analytical-usability.md), remediation amendment.
- **Blockers:** None.
- **Next:** Owner moves local `dev` to the branch tip with `git reset --keep` (a fast-forward is impossible because the cherry-pick changed the SHA). No push.

**tags:** ["web", "accessibility", "validation"]

## Decisions

- Rebasing `dev` in the main checkout was not possible from the isolated session, so the work branch was built from `origin/dev` with `b854196f` cherry-picked. Local `dev` needs a fast-forward.
- Team page reads `?season=` only in UI-test mode to keep its `revalidate = 300` static behavior; production uses the publication season.
- Model scatter keeps keyboard focus by drawing a non-interactive overlay for the selected point instead of reordering the DOM.
- Axe dev dependency added with owner approval.

## Commits

`9ff51409` Phase 1, `c08c91c5` Phase 3, `21682240` Phase 4, `4a9fbf06` Phase 2, `350ec5df` Phase 5, `7c74d99b` axe, `3b8114cd` code-review fixes.

## Validation

`make check` pass; `make web-e2e` 483 passed / 10 skipped (baseline before the work was 446 / 10), both before and after the review fixes.

- Sweep (320/390/820/1280px, both themes): 0 overflow, 0 console errors; remaining sub-44px items are SVG chart marks and narrow inline links, covered by the touch-target spec.
- Probe: Model target follows the Record tab; Thursday TBD game sorts last; "t" ranks T teams first.
- Visual check of market, key factors, Graphs tab and team schedule: no defects. Key-factors team names truncate at 390px (not fixed).
- Code review at `high`: 10 findings, 9 fixed, 1 skipped (alias redirect keeps no `?season=`, to stay static). The sweep and probe ran before the review fixes; the e2e suite ran after.

## Owner decisions

Team page stays ISR; `?season=` honored in UI-test mode only; Preview check of Week 12 TBD ordering skipped; CSP with nonce out of scope; local `dev` only, no push.

## Not done

CSP with nonce; Preview check of Week 12 TBD ordering; `getRatingAnalysisHistory` no-release guard is tested through an extracted helper, not through `v5.ts` itself.