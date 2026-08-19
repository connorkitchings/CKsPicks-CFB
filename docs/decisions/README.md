# Decisions

This section documents key architectural and product decisions for the project. Use the template to
add new decisions and keep the log current.

- Decision Template: `docs/decisions/decision_template.md`
- Decision Log: `docs/decisions/decision_log.md`

Link decisions from other docs using the Vibe Coding System syntax:

- `[PRD-decision:YYYY-MM-DD]` — references a dated decision entry
- `[LOG:YYYY-MM-DD]` — references a session log

Latest highlights:

- 2026-08-18: V4 bundle `week0-2026-v4-strict-20260818-r2` selected as the 2026
  launch model; `prior_only_fallback` posture (no further CFBD talent rechecks).
- 2026-08-18: Production deployed — Neon production branch + shared immutable
  R2 bucket + Vercel in fail-closed `market` publication mode.
- 2026-08-17: V4 strict vs. reconstructed point-in-time feature references split.
- 2026-08-16: Games 1–3 prediction-only promotion basis
  (`selection_basis=predictive_results_only`).
- 2026-08-09: Untimestamped historical lines quarantined as
  `legacy_market_references`; canonical Week 0 policy adopted.
