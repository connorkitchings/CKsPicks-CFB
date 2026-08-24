# Session: History Purge + Nx Task Runner

## TL;DR
- **Worked On:** Purge ~180M of binary bloat from git history; add Nx 20 for cached cross-stack task orchestration
- **Completed:** `.git` shrunk 206M → 9.3M (95.5%); Nx installed with `pipeline` + `web` projects, all targets verified cached
- **Blockers:** None
- **Next:** Season still pending CFBD data (rosters/coaches/recruiting); re-run ingestion mid-August

---

## What Was Done

### Phase 1–4: Git History Purge
The repo's `.git` was 206M but only 32M of files were tracked — the rest was dead binary weight in history.

**Root cause:** Legacy PyMC trace files (`.nc`, ~30M each × 6), historical model binaries (`.joblib`), and MLflow artifacts committed in early development and never purged.

**Process:**
1. Installed `git-filter-repo` via Homebrew
2. Backed up to `/tmp/ckspicks-backup-20260708-102736.bundle` (204M)
3. Untracked 273 MLflow files under `artifacts/mlruns/` + tightened `.gitignore` (global `*.nc`, `*.joblib`, `*.pkl` ignores)
4. Ran `git filter-repo --strip-blobs-bigger-than 1M` — stripped every blob >1M from all 122 commits in 0.33s
5. Reclaimed space: `git reflog expire --expire=now --all && git gc --prune=now --aggressive`
6. Re-added `origin` remote (filter-repo removes it as safety), force-pushed

**Result:** `.git` 206M → 9.3M. Zero blobs >1M remain. All 1,259 source files intact. All commits preserved (new SHAs from rewrite).

### Phase 5: Nx Task Runner Setup
Added Nx 20 at the repo root for cached task orchestration across both stacks.

**New files:**
- `package.json` (root) — nx devDependency, no npm workspaces (web/ keeps its own package-lock.json)
- `nx.json` — targetDefaults (build, lint cached), namedInputs, cache in `.nx/`
- `project.json` (root) — `pipeline` project: `test`, `lint`, `format` targets wrapping `uv run` commands with Python-scoped cache inputs
- `web/project.json` — `build`, `dev`, `start`, `lint`, `typecheck` targets wrapping `npm run` with Next.js-aware outputs (`{projectRoot}/.next`)

**Bug fixed during setup:** `conftest.py` uses `os.environ.setdefault("CFB_STORAGE_BACKEND", "local")` which is too weak — `.env`'s `CFB_STORAGE_BACKEND='r2'` leaked through when run via Nx, causing 5 `test_external_ratings` tests to fail (ingester couldn't find mock CSVs on R2 backend). Fixed by setting `env: {"CFB_STORAGE_BACKEND": "local"}` explicitly in the pipeline test target.

**Verified:**
- `npx nx run pipeline:test` — 187 passed, cached on re-run
- `npx nx run web:build` — builds, cached on re-run
- `npx nx run-many -t lint typecheck test build` — all pass, 5/5 served from cache on second run

**Design decisions:**
- No npm workspaces — avoids disrupting web/'s existing dependency management
- No `@nxlv/python` plugin — `uv` already handles Python; Nx wraps commands via `nx:run-commands`
- Makefile stays as source of truth for multi-step workflows (`make weekly`); Nx wraps individual tasks with caching

---

## Changes Made
- `.gitignore` — added `*.nc`, `*.joblib`, `*.pkl`, `*.pickle`, `*.h5`, `*.pt`, `*.safetensors`, `.nx/`, `node_modules/`; simplified `artifacts/mlruns/` pattern
- `package.json` (NEW, root) — nx 20.8.4 devDependency
- `package-lock.json` (NEW, root)
- `nx.json` (NEW) — caching config
- `project.json` (NEW, root) — pipeline project (Python tasks)
- `web/project.json` (NEW) — web project (Next.js tasks)
- `.codex/QUICKSTART.md` — added Nx section with target reference table and usage examples
- `AGENTS.md` — added Nx to architecture table, updated commands reference
- **Git history rewritten** (122 commits, all SHAs changed, force-pushed to origin)

## Testing
- [x] `uv run ruff format .` — 102 files unchanged
- [x] `uv run ruff check .` — all passed
- [x] `uv run pytest -q` — 187 passed
- [x] `npx nx run-many -t lint typecheck test build` — all pass, caching verified
- [x] `npx nx run web:build` — Next.js build succeeds
- [x] Git history: 0 blobs >1M, all source files intact

## Notes for Next Session

**Resume at:**
- Re-run 2026 ingestion mid-August when CFBD publishes rosters/coaches/recruiting:
  ```bash
  make ingest-season YEAR=2026 ENTITIES=rosters,coaches,recruiting,rankings
  ```
- Refresh games for TV time updates closer to Week 1:
  ```bash
  make ingest-season YEAR=2026 ENTITIES=games
  ```

**Context:**
- Backup bundle at `/tmp/ckspicks-backup-20260708-102736.bundle` (safe to delete after confirming everything works)
- The `test_external_ratings` flaky test bug is environmental, not code — conftest.py's `setdefault` is intentionally weak to allow cloud integration tests to override. The Nx `project.json` works around this with explicit env. If running pytest directly and seeing failures, check `CFB_STORAGE_BACKEND` in the shell env.
- Any other local clones of this repo must be re-cloned (history was rewritten, all SHAs changed)

**Watch out for:**
- `git filter-repo` removed the `origin` remote; it was re-added manually to `https://github.com/connorkitchings/CKsPicks-CFB.git`
- The Nx cache (`.nx/`) is gitignored and machine-local; CI would need Nx Cloud for shared caching

**tags:** ["git", "history-rewrite", "nx", "task-runner", "caching", "performance", "repo-cleanup"]
