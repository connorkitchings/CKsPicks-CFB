# Session: Renaming Project to CKsPicks-CFB

## TL;DR

- **Worked On:** Renaming the project from `cfb_model` to `CKsPicks-CFB` and restructuring the codebase.
- **Completed:**
  - moved source code to `src/cks_picks_cfb` package structure.
  - Updated configuration files (`pyproject.toml`, `mkdocs.yml`, `Makefile`).
  - Updated imports across all source files, checks, and scripts.
  - Updated `README.md` with new project name and instructions.
- **Blockers:** None.
- **Next:** Verify any external scripts or CI/CD pipelines not in this repo.

## Changes Made

- **Configuration:** Updated `pyproject.toml`, `mkdocs.yml`, `Makefile` to reflect new project name and path.
- **Source Code:** Moved `src/*` to `src/cks_picks_cfb/*`.
- **Imports:** Updated all `from src.` and `import src` to `from cks_picks_cfb.` and `import cks_picks_cfb`.
- **Documentation:** Updated `README.md` with new project name and install steps.

## Testing

- [x] Health checks pass (formatting, linting)
- [x] Tests pass (81 passed)
- [x] Documentation updated

## Technical Details

- The package name is now `cks_picks_cfb`.
- `get_repo_root` in `config/__init__.py` was updated to `parents[3]` to account for the deeper directory structure.
- `hydra` config path in `train.py` was updated to `../../conf`.

## Notes for Next Session

- Resume at: Verifying any external integrations or starting next feature work.
- Remember: All imports now start with `cks_picks_cfb`.
- Watch out for: Any personal scripts that might still reference `src`.

**tags:** ["refactoring", "renaming", "structure"]
