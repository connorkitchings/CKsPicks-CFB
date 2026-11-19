# Session: V6 methodology research survey

## TL;DR

- **Worked On:** Six-track web research pass on rating systems, rating architectures, totals modeling, sportsbook practice, evaluation statistics and point-in-time input feasibility, written up as one survey.
- **Outcome:** New `docs/research/v6-methodology-survey-2026-11.md` with ranked recommendations, each carrying a policy label and a feasibility rating, plus a gap map to Operational V5 gaps. Evidence is mostly secondary or non-CFB; the survey says so per claim.
- **Plan Contract:** `N/A (fast path)` — documentation only, no code, model, config or production change.
- **Approval / Status:** Owner-requested research plan for this session; docs-only on local `dev`, committed locally, not pushed.
- **Blockers:** None. Several primary pages (SP+/FEI methodology, Sagarin, Massey, PredictionTracker, KenPom) could not be fetched.
- **Next:** Owner decisions listed in section 8 of the survey (L3 policy question, 90% vs 95% interval, 2026 as confirmation season, totals diagnostic as first post-2026-12-13 contract).

**tags:** ["research", "v6", "methodology", "docs-only"]

## Context and Decisions

- V5 is frozen for the 2026 record; model research starts after the 2026-12-13 final close, so this work is documentation only.
- All V5 figures use Operational V5 from the baseline audit (13.7151 margin MAE, 13.3709 total MAE, predicted-total SD 1.57 vs 16.90, neutral-site margin bias -2.69 on 126 games, stage-0 bias +7.51). The backlog's older -4.32 neutral-site figure includes postseason games and was not used.
- Market views are labelled L2 or L3 per Amendment 5; none is recommended as an input.

## Work Completed

- Ran six parallel research agents; synthesized by theme and flagged thin evidence (three of the six had LOW or LOW-MEDIUM confidence).
- Wrote the survey, added it to the research nav and linked it from backlog section B.

## Files Modified

- `docs/research/v6-methodology-survey-2026-11.md` — new survey
- `mkdocs.yml` — nav entry next to the V6 architecture design page
- `docs/planning/offseason-2027-backlog.md` — one-line link in section B
- `session_logs/2026-11-19/01-v6-methodology-research.md` — this log

## Validation

- [x] `uv run mkdocs build --strict`
- [x] `git diff --check`
- [x] `git status` shows only the four files above; `docs/status.md` unchanged

## Amendments and Blockers

- Confirmed gap: `ratings_lab/evaluation.py` `paired_comparison` returns 90% intervals; protocol adoption thresholds use 95% (Amendment 2 unapplied). Not changed here.

## Handoff Notes

- **Resume at:** Session complete; next step is the owner decisions in survey section 8.
- **Watch out for:** The survey's power table and sigma estimates are the survey's own arithmetic (game-level iid assumption). CFBD point-in-time verdicts are unverified until checked against the live API.
