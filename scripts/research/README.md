# Data-First Research Commands

New executable commands for the data-first football forecasting program live
in this directory.

- Put reusable measurements, ratings, forecasting, and evaluation logic in
  `src/cks_picks_cfb/`.
- Put executable research orchestration in `scripts/research/`.
- Keep exploratory notebooks and one-off analyses in `research/`.
- Keep supported production workflows in `scripts/pipeline/`.

Production modules and commands must not import from `scripts/research/` or
`research/`. Research commands may call reusable library code through explicit
interfaces, but they cannot publish, freeze, close, migrate, deploy, or otherwise
activate production state.

Existing rating and successor scripts remain at their current paths as named
benchmark compatibility entry points. New program commands must use the
`artifacts/research/data-first-football-v1/` artifact namespace and the
`conf/research/data_first_football_v1/` configuration root.
