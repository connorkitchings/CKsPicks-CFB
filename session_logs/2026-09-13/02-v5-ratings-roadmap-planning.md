# Session: V5 Ratings Roadmap Review and Approved Contract Package

## TL;DR

- **Worked On:** Start Session and Plan Session review of the ratings transformation, documentation authority, expanded history, and remaining implementation sequence.
- **Outcome:** Approved common roadmap and seven bounded contracts saved. No canonical documentation, tests, model code, production state, or cloud data changed in this persistence step.
- **Plan Contract:** `docs/plans/2026-09-13/v5-ratings-successor-roadmap-and-contracts.md`
- **Approval / Status:** User approved the proposed package with “Implement the proposed plan.” on 2026-09-13 after switching out of Plan Mode. Common contract and contracts 00–06 are Approved; none of the implementation phases has been executed here.
- **Blockers:** None for plan persistence. Computational phases have explicit unmet predecessor gates; possession measurement certification is not yet performed.
- **Next:** User-controlled plan commit, then a fresh Terra task for `docs/plans/2026-09-13/00-v5-documentation-and-methodology-alignment.md`.

## Context and decisions

Reviewed AGENTS, local Start/Plan Session skills, Quickstart, architecture context,
September 11 and 13 session records, current roadmaps, methodology, measurement
and evaluation guidance, contract lifecycle, held Phase 4A–6 contracts, and
relevant observation/state/replay/authority-test code. Branch `main`, initial
HEAD `ca2adee`, clean worktree. `.env` safely verified: backend r2 and source,
Preview, and generic R2 credential sets present; no values printed and no cloud
data I/O performed. No September 12 session folder existed.

Repository evidence records Repair v2 verified, Phase 3 v2 certified September 11,
and possession methodology specified and documented. README, documentation home,
onboarding, historical roadmap and evaluation retain stale pending-work claims.
Existing authority tests pass despite that drift. Week 2 closure makes the
separate V4 feature-v5 scoring task resumable after fresh ref/outcome verification.

The user selected an evidence-led review and all phase contracts now, bridge-first
forecasting, separate feature-v5 diagnostic closure, the human-facing name “V5
ratings successor,” a full-history versus latest-five fitting-window comparison,
and possession arithmetic as an optional later challenger.

The approved package corrects global 2015–2019 constant fitting across 2018/2019
validation, the simplified credibility equation's missing prior-variance term,
and incomplete scoring accounting. It retains the two possession definitions and
60-candidate grid. It separates code completion, data certification, downstream
eligibility, and prospective evidence. The V4 feature-v5 absolute win-rate
threshold is preserved but cannot establish causality without paired prediction
and error evidence.

Public primary references consulted: CFBD's methodology overview (output scales,
version comparability and missingness) and Forecasting: Principles and Practice
(rolling-origin earlier-only fitting). Links are in the common contract.

## Work completed

- Saved the approved roadmap/common execution rules and methodology amendments.
- Saved contracts 00 documentation, 01 independent diagnostic, 02 measurement,
  03 ratings, 04 forecasting/windows, 05 readiness/tooling, and 06 evidence/review.
- Recorded concrete entry/exit gates, interfaces, artifacts, validation, failure
  behavior, amendment process, and the separate Terra handoff for each phase.
- Preserved the approved persistence-only scope: existing authority-page/test
  updates are tasks of contract 00, not edits made by the planning task.

## Files modified

- `docs/plans/2026-09-13/v5-ratings-successor-roadmap-and-contracts.md` — new approved common contract and phase queue.
- `docs/plans/2026-09-13/00-v5-documentation-and-methodology-alignment.md` — new documentation/test implementation contract.
- `docs/plans/2026-09-13/01-v4-feature-v5-diagnostic-closure.md` — new bounded diagnostic closure contract.
- `docs/plans/2026-09-13/02-v5-possession-measurement-certification.md` — new certification contract.
- `docs/plans/2026-09-13/03-v5-possession-rating-estimation.md` — new rating tournament contract.
- `docs/plans/2026-09-13/04-v5-forecast-bridge-and-fitting-window.md` — new forecast/window/calibration contract.
- `docs/plans/2026-09-13/05-v5-prospective-readiness-and-shadow-tooling.md` — new readiness/tooling contract.
- `docs/plans/2026-09-13/06-v5-prospective-evidence-and-recommendation.md` — new collection/review contract.
- `session_logs/2026-09-13/02-v5-ratings-roadmap-planning.md` — this log.

## Validation

- [x] Planning baseline: `uv run pytest -q -W error tests/test_data_first_documentation_authority.py` — 5 passed.
- [x] Planning baseline: strict MkDocs build to a temporary output directory.
- [x] Persistence: metadata, complete 00–06 queue, and local Markdown links validated for all eight Approved documents.
- [x] Persistence: `uv run mkdocs build --strict --quiet --site-dir /private/tmp/ckspicks-v5-contract-docs-20260913` — passed.
- [x] Persistence: `.venv/bin/python -m pytest -q -W error tests/test_data_first_documentation_authority.py` — 5 passed. The `uv run` test invocation could not access the global uv cache (`sdists-v9/.git`, permission denied); direct use of the existing project virtual environment ran the same tests successfully without changing dependencies.
- [x] Persistence: `git diff --check` and explicit added-file trailing-whitespace/newline checks — passed. Added files are untracked until the user stages them, so the explicit check supplements Git's tracked diff check.

## Amendments and blockers

None for persistence. Contracts preserve future data-dependent failures as explicit
stop conditions rather than inventing successful manifests or running research
in the planning session. No files outside the new plan folder and this log were
intentionally edited. User performs Git operations manually.

Suggested separate commit: `docs(plans): approve V5 ratings roadmap and phase contracts`.

## Handoff notes

**Resume at:** Fresh Terra task, after the user-controlled plan checkpoint:

```text
Use the repository-local implement-plan skill and implement the approved contract at:

docs/plans/2026-09-13/00-v5-documentation-and-methodology-alignment.md

Treat it and its linked common contract as authoritative. Preserve its decisions,
run its validation, and stop for any material conflict. This request explicitly
authorizes implementation of that contract only.
```

**Watch out for:** This package is not a production model change. The roadmap and
other canonical pages remain stale until 00 is executed. Contract 01 is independent
of the ratings sequence. Approved downstream contracts still require verified
parents. No existing historical candidate evidence transfers into the new window.

**tags:** ["planning", "v5", "ratings", "possession", "data-first", "contracts", "documentation"]
