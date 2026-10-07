# Session: Track 1 Production promotion planning

## TL;DR
- **Worked On:** Investigated the Window 1 Production promotion and the broader `dev` to `main` deployment selected by the user.
- **Outcome:** Persisted an approved decision-complete contract. The Window 1 code and venue pin are already ancestors of `main`; the chosen full promotion includes 7A/7B web read paths. Added a plan to pin both Silver games and venues inputs.
- **Plan Contract:** [Track 1 Production venues and full `dev` promotion](../../docs/plans/2026-10-07/01-track1-production-promotion.md)
- **Approval / Status:** User approved by explicitly requesting implementation of the exact Track 1 plan. Plan commit remains user-run; implementation belongs in a fresh task after that commit.
- **Blockers:** The current host lacks the restricted Production pipeline Keychain item, so live Production venue dry-run and current database evidence must be recaptured on an authorized operator host.
- **Next:** User commits the plan; a fresh implementation task adds and tests the games-version pin, captures release evidence, and prepares the two separately authorized Production actions.

## Context and Decisions
- Worktree was clean on branch `dev`, HEAD `8f3c9b62098ccb6fedf43ac24b45a3efe06377fb`; local `main` was `562319aaf0510d840d60806e11c4802ea0c80049`, 49 commits behind at planning capture. Recheck refs before release.
- User chose full `dev` promotion, including the Stage 7A/7B web changes. Window 1 code and pinned venue publisher are already in `main` history.
- User chose to pin both Silver inputs. `--games-version` will be added compatibly; the venues version remains `b569d242e8c4c53b416bfe14` pending live coverage verification.
- Production venue publication and `main` promotion each need separate authorization after a reviewable packet. User runs Git operations.
- The recent Stage 7B records report Production migrations 0023/0024 and the Week 5 attestation are present, but the Track 1 task must recapture them and the actual web-role grants.

## Work Completed
- Reviewed the repository plan-session workflow, Contract 04 Window 1 release gates, current Stage 7A/7B status, venue publisher, test coverage, Vercel deployment configuration, current branch history, and prior Window 1/Stage 7B logs.
- Confirmed `.vercelignore` restricts deployment upload to `web/`; Vercel Git docs describe Preview deployment for pull requests and Production deployment on configured production-branch changes.
- Attempted the restricted Production venue dry-run. The wrapper failed closed because Keychain item `ckspicks-cfb/production/pipeline-url` is unavailable on this host. No remote write occurred.
- Persisted the plan and added it to `docs/plans/index.md`.

## Files Modified
- `docs/plans/2026-10-07/01-track1-production-promotion.md` — Approved release contract.
- `docs/plans/index.md` — Added the active Track 1 contract.
- `session_logs/2026-10-07/01-track1-production-promotion-planning.md` — Planning evidence and handoff.

## Validation
- [x] `git diff --check`
- [x] `.venv/bin/python -m mkdocs build --quiet` (passed). `uv run mkdocs build --quiet` could not access the host uv cache in this sandbox; the repository venv entry point ran the same build successfully.

## Amendments and Blockers
- No scope amendment. Live Production release evidence remains to be recaptured on the authorized operator host.

## Handoff Notes
- **Resume at:** User-run plan commit, then a fresh implementation task for the exact approved contract.
- **Watch out for:** Do not use prior 271-game coverage as current Week 6 evidence. Do not authorize the venue data write and the `main` push as one combined operation.

**tags:** ["release", "window1", "production", "plan"]
