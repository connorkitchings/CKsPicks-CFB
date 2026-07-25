# Session: CI and Readiness Integration

## TL;DR
- **Worked On:** Added continuous integration for the Python pipeline, shared contracts, and Next.js web app.
- **Completed:** Added a two-job GitHub Actions workflow, verified a clean web build without environment secrets, and corrected the root ignore rule so required web library modules are tracked.
- **Blockers:** Nx plugin workers cannot start in the local sandbox; the underlying web commands pass directly and CI disables the Nx daemon.
- **Next:** Review and merge the readiness PR, then run the 2026 preseason refresh when provider data is available in mid-August.

## Changes Made
- `.github/workflows/ci.yml`: Added Python 3.12 and Node 22 CI jobs for pull requests and pushes to `main`.
- `.gitignore`: Narrowly unignored `web/src/lib/`, which the generic Python `lib/` rule had excluded.
- `web/src/lib/`: Added the existing database, query, schema, and team contract modules to version control so clean checkouts can build.

## Testing
- [x] CI workflow YAML parses successfully
- [x] `uv run ruff format --check .`
- [x] `uv run ruff check .`
- [x] `PYTHONPATH=src:. uv run pytest tests/ -q` - 196 passed
- [x] `uv run python contracts/validation.py`
- [x] `npm run lint`
- [x] Clean-checkout `npm run build` without `.env` or `DATABASE_URL`
- [x] Clean-checkout `npm run typecheck`
- [x] `make preflight YEAR=2026 WEEK=1` - R2 and Neon passed
- [x] Live GitHub Actions web job; Python tests use a non-secret placeholder API key required by ingester constructors

## Notes for Next Session
CI intentionally requires no R2, Neon, CFBD, or database secrets. Production preflight remains a separate live operational check. Keep modeling paused until the weekly path is validated with real 2026 season data.

**tags:** ["ci", "github-actions", "2026-season", "web", "contracts"]
