# Decisions

This section documents key architectural and product decisions for the project. Use the template to
add new decisions and keep the log current.

- Decision Template: `docs/decisions/decision_template.md`
- Decision Log: `docs/decisions/decision_log.md`

Link decisions from other docs using the Vibe Coding System syntax:

- `[PRD-decision:YYYY-MM-DD]` — references a dated decision entry
- `[LOG:YYYY-MM-DD]` — references a session log

Latest highlights:

- 2025-09-05: Ruff lint policy updated — notebooks excluded; E501 ignored to reduce noise.
- 2025-09-05: Deep validation thresholds adopted for box score vs team_game comparison (plays/ypp/sr).
- 2025-08-14: Storage format standardized to CSV for both raw and processed datasets for easier
  inspection and portability. Partitioning scheme: `data/<raw|processed>/<entity>/<year>/<week>/<game_id>`
  for plays-derived entities as applicable, and `data/<raw|processed>/<entity>/<year>` for others.
- 2025-08-12: Training window set to 2014–2024 (excluding 2020); opponent adjustment method
  finalized (additive, 4 iterations, league-mean centering, 3/2/1 recency); feature catalog
  updated accordingly.
