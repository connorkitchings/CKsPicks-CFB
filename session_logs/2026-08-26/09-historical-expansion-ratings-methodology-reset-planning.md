# Session: Historical expansion and ratings methodology reset planning

## TL;DR

- **Worked On:** Reframed the rating-successor program after the simple
  carryover prior produced questionable preseason rankings.
- **Outcome:** Approved a two-track roadmap: R1–R4 research using 2015–2019
  and 2021–2025, and O1–O3 operations that preserve V4 plus candidate-v1 as a
  diagnostic baseline.
- **Plan Contract:**
  `docs/plans/2026-08-26/historical-expansion-ratings-methodology-reset.md`
- **Approval / Status:** User explicitly authorized implementation in Codex on
  2026-08-26; plan is `Approved` pending its required separate plan commit.
- **Blockers:** None for planning. Data coverage and source-semantic gates may
  stop R2–R4.

## Decisions

- Collect/model 2015–2019 and 2021–2025; exclude 2020 universally.
- Retain candidate v1 at `ac1fba1` as an isolated, non-blocking diagnostic
  lane while research proceeds.
- Treat 2019→2021 as a two-year-decay stress case, not a normal transition
  fitting observation.
- Use staged tournaments: offseason prior, within-season update, then
  structured predictor.
- Keep football-only inputs. Markets remain post-model evaluation only.
- Select through 2024 and evaluate 2025 once as a locked confirmation.
- Optimize early-season and full-season behavior jointly; neither slice may
  regress materially.

## Evidence Gathered

- The current code hard-codes 2021–2025 historical development; 2019 is
  currently prior-only and 2020 is forbidden.
- Historical source inventory contains 2019 games, 847 play objects, teams,
  venues, team-season, weather, and betting exports; 2015–2018 are absent.
- A read-only CFBD request returned 15,369 compatible 2015 Week 1 plays with
  all required rating-measurement fields.
- The project context confirms shared R2 credentials/bucket are intentional;
  immutable namespaces and Neon branches isolate environments.
- Historical preseason context may be reconstructed for research only until it
  passes explicit semantics, coverage, and 2026 authentic-capture gates.

## Handoff Notes

- **Resume at:** Commit this plan/log separately, mark the plan `In Progress`,
  then implement Task 1 before changing data or ratings code.
- **Watch out for:** Do not modify V4, use market inputs, write production
  data, or create a candidate-v2 prospective freeze from existing 2026 timing.

**tags:** ["ratings", "historical-data", "methodology", "planning"]
