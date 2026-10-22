# Session Logs

Session logs are chronological engineering evidence, not current architecture
authority. Start with repository onboarding and the documentation home, then
read logs only when their historical context is relevant.

## Active window

Active logs are the **current calendar month's**: `YYYY-MM-DD/` folders for
October 2026 sit directly under this directory. Logs from earlier months are
retained under `archive/daily/YYYY-MM-DD/` with the same folder names (August
and September 2026 are archived; earlier history is there too).

The monthly cutoff is a manual documentation-maintenance policy, not
automation: when a month closes, move its date folders with `git mv` and
rewrite references. Keep using `YYYY-MM-DD/NN-descriptive-slug.md` for new
session logs and retain `TEMPLATE.md` as the only active template.

See [the archive index](archive/README.md) for historical layout. Closed
implementation contracts referenced by archived logs live under
[`docs/archive/plans/`](../docs/archive/plans/index.md); open contracts are in
[`docs/plans/`](../docs/plans/index.md).
