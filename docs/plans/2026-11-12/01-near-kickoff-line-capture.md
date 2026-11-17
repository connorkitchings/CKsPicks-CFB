# Near-kickoff line capture (analysis-only closing-line evidence)

- **Status:** In Progress. Approved 2026-11-12 and implemented on branch `worktree-connorkitchings-offseason-prep-contracts` (uncommitted); the dry run and the confirmed Preview capture check (Validation) and the `dev` to `main` release plus the repository variable (change 4) remain.
- **Created:** 2026-11-12
- **Planner:** Sol
- **Approval source:** Owner decisions recorded 2026-11-12: (1) credit budget accepted (the account has a 500-credit monthly allowance, 496 remaining on 2026-11-12; this plan needs about 24, ceiling 50); (2) cloud automation (a GitHub workflow), not manual or local cron; (3) near-kickoff lines are kept separate from early-week lines, so the two can be compared later (line-value analysis). Owner approved implementation on 2026-11-12 ("yes, go ahead with contract 1").
- **Implementation log:** `session_logs/2026-11-12/01-near-kickoff-capture-impl.md`
- **Commit policy:** Commit on `dev` with implementation; one pull request into `dev`. A `dev` to `main` release is required before a GitHub-scheduled workflow can run, so a manual capture (one command) covers any Saturday that comes before the release; the owner does not want manual capture as the routine.

## Goal and acceptance

The weekly captures are early-week fetches, so the official record has no true closing line ([record methodology](../../modeling/record_methodology.md), "no true closing line exists"). Lines close at kickoff and can only be captured while games are being played. Closing-line value (does the line move toward the model between the early-week capture and kickoff?) is a market-independent test of whether V5 carries signal, which a 49% against-the-spread record over about 560 games cannot give. It also feeds the market-comparison spoke of the site.

Acceptance:

1. From the Week 12 slate (Saturday 2026-11-21) through Week 15, a capture runs on Saturday morning (Eastern) and one midweek slot (Tuesday through Friday, only when the week has midweek games), stores the Odds API board, and is registered with a snapshot type that is distinguishable from the early-week captures.
2. Each capture is made before the earliest kickoff it is meant to describe, and records its capture timestamp.
3. The captures are **analysis only**: absent from every revision manifest, every `prepare` input, `market_snapshots`, `prediction_grades`, the public record and the site. `record_methodology.md` stays unchanged.
4. One dry run (no `--confirm`) and one confirmed capture on Preview storage pass the verification in the Validation section.

## Baseline and constraints

- Baseline: `dev` at `452899e9`. The existing script `scripts/data/fetch_odds_api_market_quotes.py` makes one live board request (about 2 credits, regions `us`, spreads and totals), matches events strictly to the week's Silver schedule, and registers an immutable Bronze capture under provider `the_odds_api`, entity `market_quotes`.
- **Contamination risk (the main design constraint):** the revision builders (`scripts/pipeline/build_season_revision.py`, `build_market_revision.py`, `build_week_market_snapshot.py`) include every registered 2026 Odds API capture registered before they run (weekly runbook, step 1b). A near-kickoff capture stored under the existing `market_quotes` entity would therefore flow into revision inputs and could replace the early-week line in the record. The owner decided the early-week and near-kickoff lines stay separate, so the snapshot type must be a different **entity** (preferred: `market_quotes_near_kickoff`), not a label inside the same entity, unless task 1 proves the builders filter by label. Task 1 fixes the exact name and mechanism.
- In scope: a small capture wrapper or a `--snapshot-type` option on the existing script, entity registration (`src/cks_picks_cfb/data/the_odds_api.py`, `data/schema_contracts.py`, catalog and lake registration as the entity requires), a scheduler, tests, a runbook section.
- Out of scope: any use of these lines as model input, grading, display or the record; changing how existing weekly captures are made; Production storage writes (captures go to Preview storage only until the owner decides otherwise); CFBD lines.
- Budget (approved): about 2 credits per call. Rough ceiling for Weeks 12 to 15: 4 weeks x (1 Saturday + up to 2 midweek) x 2 credits = 24 credits. Never use the historical-snapshot mode (20 credits each).
- Stop gates: if registering a new entity needs a schema migration or changes to verification rules, stop and return to Sol. If a capture would run after the earliest kickoff it targets, do not register it as "near-kickoff".

## Ordered changes

1. **Entity decision (read-only).** Read the three revision builders and `season/inputs.py` to confirm how captures are selected, then decide entity versus label. Output: a short finding in the implementation log. Acceptance: it states exactly which code paths would ingest the new snapshot type (target: none).
2. **Capture path.** Add the snapshot type and make the script write it when asked, defaulting to unchanged behavior for the existing weekly use. Acceptance: existing weekly capture tests pass without edits; a new test proves a near-kickoff capture is not returned by the revision builders' capture selection.
3. **Scheduling (GitHub workflow, owner decision).** `.github/workflows/near-kickoff-capture.yml`: Preview credentials only, modeled on `data-first-pregame-capture.yml`, behind a repository variable switch, a concurrency group distinct from the weekly update. Because GitHub scheduled runs are sometimes delayed or skipped, schedule each slot twice (a primary and a backup 60 to 90 minutes later, both before the earliest kickoff) and make the capture idempotent per slot, so a backup run skips when the primary succeeded. The workflow works out the week and the kickoff times from the stored schedule, skips outside Weeks 12 to 15, and skips when no game kicks off within the slot's window. Acceptance: it never overlaps the Sunday and Monday weekly-run windows, and a failed primary is followed by a successful backup in a test with a fake clock.
4. **Release gate.** Scheduled workflows run only from `main`, so after the `dev` to `main` release the owner sets the repository variable that enables the workflow. Until then run the same command by hand for any Saturday slate.
5. **Runbook and status.** Add a "Near-kickoff capture (analysis only)" section, including the first-release gate below, to `docs/ops/weekly_runbook.md` and one line to `docs/status.md`.

## Validation

- `make check`; the new tests; `git diff --check`; `uv run mkdocs build --strict`.
- Dry run: `PYTHONPATH=.:src uv run python scripts/data/fetch_odds_api_market_quotes.py --year 2026 --week <W> <snapshot-type option>` prints the estimate and makes no provider request.
- One confirmed capture on Preview storage (under the Preview wrapper, see the runbook): check the snapshot type, that the capture timestamp is before the earliest kickoff, and that the capture id is absent from the next revision manifest and from `prediction_grades`.
- Negative scenarios: unmatched events are logged and skipped; a week with no schedule rows stops with an error; a rerun produces a second immutable capture rather than overwriting.

## Handoff/amendments

Approval and resume gate: the owner approves the credit budget, the scheduler and the entity decision. Next action after approval: task 1. Mechanical amendments may proceed if architecture, interfaces, scope and acceptance are unchanged; anything else returns to Sol. Record each amendment (reason, previous approach, revised approach, impact) below.

Related: the [pre-registered research protocol](02-offseason-research-protocol.md), which names closing-line value as a monitoring analysis that uses this data.
