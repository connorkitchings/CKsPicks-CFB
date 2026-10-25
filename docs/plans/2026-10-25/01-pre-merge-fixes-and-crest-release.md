# Contract: Pre-merge fixes and Crest release completion

- **Status:** Implemented and integrated on `dev`; the owner accepted the regenerated wordmark lettering. Production deployment pending (release pull request #9 not yet merged).
- **Created:** 2026-10-25
- **Approval source:** Owner supplied the bundle definition in the 2026-10-25 session.
- **Implementation log:** `session_logs/2026-10-25/03-pre-merge-bundle.md`
- **Commit policy:** The bundle was committed to `dev` as separate commits on the owner's instruction; merging `dev` into `main` stays with the owner. Release pull request #9 carries the bundle.
- **Related:** [Site reorganization](../2026-10-21/01-site-reorganization-and-performance.md), [Mobile app-feel](../2026-10-23/03-mobile-app-feel.md), [Crest wordmark decision](../../decisions/2026-10-25-crest-wordmark.md).

## Goal and scope

Deliver six review fixes and the wordmark font-source cleanup as one bundle on top of `dev` at `2f16a808`, then publish `dev` to `main`. Production data, migrations, model releases and publication settings are unchanged. This is a web deploy only.

## Deliverables

1. **Release-scoped degraded caching.** The fallback cache behind `cachedOrTolerant` is keyed by environment, season, release ID and chart set for prediction games, market games and the biggest-edges record. Reuse stays within one identity for 30 seconds. With no active release nothing is remembered across requests. Required-data errors propagate.
2. **Share image invalidation.** A prepared share image is kept with its content identity, filename, title, dimensions, background and theme, and is reused only while all still match. An obsolete asynchronous render cannot restore it.
3. **Share cancellation.** `AbortError` on the first share or the retry is a cancellation: no download and no failure message. Genuine retry failures still fall back to a download.
4. **Environment defaults.** Optional assignments in `.env.example` and `web/.env.example` are commented out so copying either file keeps code defaults. Required credential placeholders stay active and marked required. No runtime default changed.
5. **Setup command.** `uv sync --group dev` replaces `uv sync --extra dev`.
6. **Historical audit evidence.** The deleted V4 YAML is restored byte for byte from the reviewed `main` revision to `conf/research/data_first_football_v1/historical/v4_2026.yaml`, and the audit root pins its checksum. The retired operational path stays absent.
7. **Wordmark font sources.** "CFB" is regenerated from Arimo Bold (SIL Open Font License) and "CREST" from Bitstream Charter Bold (explicit licence in the CTAN `charter` package). Provenance, licences and a reproducible generator are retained under `design/crest-wordmarks/`.
8. **Export lifecycle (follow-up from an independent review).** An export that is still rendering when its component unmounts, because the user switched chart type or left the page, can no longer download, share or finish a clipboard write.

## Acceptance

- Cache regressions cover activation, rollback, environment isolation, same-release reuse, expiry and rejected fallback reads.
- Browser share tests cover gesture failure, successful retry, changed content, cancellation and genuine failure, and confirm cancellation never downloads.
- Environment-example tests parse the files and check actual defaults without reading credentials or fetching provider data.
- The restored file matches the pinned checksum and the audit root resolves locally; no cloud audit was run.
- A delayed-render navigation test confirms an unmounted export produces no download, share call or saved clipboard image, with a control that still shares when the user stays.
- The wordmark is verified in both themes at 1440, 1280, 390 and 320 pixels, including theme switching, accessible name, home navigation, keyboard focus and clipping.
- `make check`, the fixture browser suite, a final code review and `git diff --check` pass.
- The development-tool dependency advisory (`esbuild` through `drizzle-kit`, non-blocking in CI) is recorded separately and not silenced by a forced downgrade.

## Deployment (pending)

After the owner merges `dev` into `main` and Vercel reports Ready: verify HTTP 200 for Games, Ratings, Graphs, Model, Method, one matchup, one team page and `/api/health`; verify HTTP 307 with preserved query parameters for the legacy Results, Performance, Methodology, Charts and matchup-index URLs; confirm health reports the expected active release; inspect desktop and phone screenshots; then record the merge commit, deployment and readback evidence in [Current Status](../../status.md). Rollback is a revert of the merge commit or Vercel's deployment rollback; no data rollback belongs to this bundle.
