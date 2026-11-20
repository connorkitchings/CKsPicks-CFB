# JP+ site review: decisions and adoption record

- **Date:** 2026-11-17
- **Scope:** Design, functionality and content of <https://www.jpplusratings.com/>. Methods are deferred to a later discussion.
- **Evidence:** All eight JP+ sections inspected at 1440 px (desktop) and 400 px (phone) on 2026-11-17, compared with Stratum Production on Week 12.
- **Contract:** [JP+ review adoptions](../plans/2026-11-17/jpplus-review-adoptions.md)
- **Session log:** `session_logs/2026-11-17/03-jpplus-site-review.md`

## Owner decisions

- **Adopt (display-only, existing release data):** weekly movers panel, projected score, record by size of the model-vs-market difference, and "How to read the ratings" plus "How Stratum differs from other models" on `/model/method`.
- **Rating scale** (points per game versus rating units): deferred to the later methods discussion.
- **Output:** this record and one implementation contract, implemented later in a fresh task.

## Review findings

| JP+ feature | Verdict |
| --- | --- |
| Home "What changed this week": top 5 rating risers and fallers (ranked by rating points, not rank, with a note why), plus expected wins, playoff % and title % movers | **Adopt** rating movers only; the other three need a season simulation (deferred) |
| Projected score on every game (for example Houston 40.8, W. Virginia 26.3) | **Adopt** |
| Three record populations (all predictions, all 5+ disagreements, selections) and MAE versus open and close | **Adopt** as mutually exclusive difference bands; Stratum already shows MAE versus market |
| About page: "How to read the ratings" and comparison with SP+, FPI, Sagarin/Massey | **Adopt** on `/model/method` |
| Ratings in points versus average; Off − Def + ST reconcile | **Deferred** (methods discussion) |
| Futures, season win projections, playoff and conference odds, playoff stakes, projected bracket | **Deferred**: needs a season simulator (model work, offseason backlog candidate) |
| Team "Outlook" page with generated résumé narrative; résumé Best/Worst result columns | **Deferred**: `season_release_team_resume` has no per-game contribution; needs pipeline and migration |
| Full Board Open / Current / Edge versus current, CLV page | **Deferred**: tied to near-kickoff capture (on a branch) and methods |
| Season/week archive back to 2022 | **Deferred** |
| Inline expandable team row with trajectory and previous/next team | **Not now**; team pages cover it |
| Hype tagline, persistent "60.4% ATS backtest" banner | **Reject**: Stratum's honest live record (49.7% / 46.8%) is a differentiator |
| Picks with EV, "playable through", sizing multipliers, signal flags | **Reject**: betting policy keeps Stratum display-only |
| Six hover-only dropdown menus (clicks did nothing in testing); game rows that open nothing | **Reject**; Stratum's four tabs and matchup pages are stronger |
