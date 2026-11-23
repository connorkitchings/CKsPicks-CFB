# Changelog

Stratum CFB follows [semantic versioning](https://semver.org/) for the website: a major version for a redesign, a minor version for a new feature, a patch for a fix. Weekly data releases do not change the version. The version lives in `web/package.json` (shown in the site footer and reported by `/api/health`); `pyproject.toml` carries the same number. Format: [Keep a Changelog](https://keepachangelog.com/).

## [2.0.0] - unreleased (date set on merge)

### Added
- Stratum redesign: new visual system, app bar and bottom navigation, light and dark themes that persist across navigation.
- Teams hub (`/teams`) with ratings, a résumé and schedule view, a Strength vs résumé plot, and a compact phone list.
- Team pages with next-game forecast, rating trend and game log.
- Graphs: sortable data tables, outlier break marks, a logo key, and Net success and Game log charts.
- Model page: season record trend and an error explorer; a Method page with contents navigation.
- Phone List layout and search on Games; charts measured to the phone width.
- A Stratum-branded 404 page; per-route page titles and share metadata.
- Site version in the footer and in `/api/health` (`appVersion`, `commit`).
- "Regular season complete" notice for the end-of-season state.
- Weekly automation: Monday catch-up for a missed close and a noon-Eastern dispatcher.
- Yards per play and opponent-adjusted yards per play on team stats and matchup pages (context only; not used in ratings or forecasts; shown after the next close-week release).

### Changed
- Matchup share images follow the page theme.
- Games model line names the favoured team with a positive margin.
- Small chart and interface text raised to at least 11px.

### Fixed
- Résumé ranks showed raw ratings on `?group=resume` links.
- Clipped and covered Net success break labels; unreadable team-page chart labels on desktop.
- Games search placeholder truncated at 320px.

## [1.0.0] - 2026-10-25

### Added
- Four-tab site: Games, Ratings, Graphs and Model, with matchup pages, on V5 forecasts against market lines.

### Follow-ups in the 1.x line (no version was tagged)
- Visualization suite (PR #13) and its repairs (PR #14, PR #15).
- Matchup layout, export placement and shared rank shading (PR #16).
- Stratum identity (PR #17).
- Rating breakdown on matchup pages (PR #29).
