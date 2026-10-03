# Session: Enable matchup pages full-time across the site

## TL;DR
- **Worked On:** Promoted Matchup breakdown pages (`/matchup`, `/matchup/[gameId]`, and the `Matchup →` card button) to be a full-time, permanent public feature of the site without requiring external Vercel environment variable configuration.
- **Outcome:**
  - `isMatchupEnabled` in `web/src/lib/matchup-gate.ts` updated to enable matchups by default across production, local development, and CI (`env.CFB_MATCHUP_ENABLED !== "0"`).
  - Maintained an explicit opt-out killswitch (`CFB_MATCHUP_ENABLED=0`) for emergency use.
  - Updated unit tests in `web/src/lib/matchup-gate.test.ts`.
  - Updated `web/README.md` and `AGENTS.md` to reflect that matchups are a full-time site feature.
- **Approval / Status:** User approved.
- **Blockers:** None.
- **Next:** User merges `dev` to `main` and pushes to deploy live to Vercel.

## Context and Decisions
- User explicitly requested: "Can we remove vercel's capability to have them and just control them here? I'm ready for them to be full time features on the site".
- Matchups were previously gated by `CFB_MATCHUP_ENABLED=1` in production to prevent premature exposure during early development.
- The feature is now mature and ready for full-time publication.
- Setting the gate to `env.CFB_MATCHUP_ENABLED !== "0"` gives direct repository control without Vercel configuration while preserving an emergency killswitch.

## Files Modified
- `web/src/lib/matchup-gate.ts`
- `web/src/lib/matchup-gate.test.ts`
- `web/README.md`
- `AGENTS.md`

## Validation
- [x] `npm --prefix web run typecheck` — passed (0 errors)
- [x] `npm --prefix web run lint` — passed (0 warnings/errors)
- [x] `npm --prefix web run test:publication` — passed (110/110)
- [x] `npm --prefix web run build` — passed (all routes compiled in 1.1s, `/matchup` and `/matchup/[gameId]` active)
- [x] `git diff --check` — passed (clean)

## Handoff Notes
- **Proposed commit message:**
  ```
  feat(web): enable matchup breakdown pages full-time by default

  - Enable /matchup and /matchup/[gameId] across production and dev
  - Keep CFB_MATCHUP_ENABLED=0 as emergency killswitch
  - Update matchup-gate unit tests and documentation
  ```

**tags:** ["web", "matchups", "feature-flags", "production"]
