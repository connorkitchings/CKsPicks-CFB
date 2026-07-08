# Contracts

Single source of truth for shared contracts between the Python pipeline and the Next.js web app.

## Files

| File | Purpose |
|---|---|
| `schema.sql` | Canonical database schema (Postgres) |
| `schema.ts` | Drizzle ORM types (must match `schema.sql`) |
| `teams.py` | Python `TEAM_LOGO_MAP` for team name normalization |
| `teams.ts` | TypeScript `TEAM_LOGO_MAP` (must match `teams.py`) |
| `validation.py` | Cross-validation script to ensure all copies stay in sync |

## Usage

### Validate sync

```bash
uv run python contracts/validation.py
```

Or via Makefile:

```bash
make contracts-check
```

### Import in Python scripts

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "contracts"))
from teams import TEAM_LOGO_MAP
```

### Web app

The web app has local copies in `web/src/lib/` (required for TypeScript module resolution).
The validation script ensures these stay in sync with `contracts/`.

## Editing Rules

1. **Always edit files in `contracts/` first** -- they are canonical.
2. Run `make contracts-check` after any edit.
3. If the web app local copies (`web/src/lib/schema.ts`, `web/src/lib/teams.ts`) differ, copy from `contracts/` to sync them.
