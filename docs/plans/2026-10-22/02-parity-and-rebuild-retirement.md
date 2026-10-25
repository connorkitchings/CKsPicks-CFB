# Serving-parity check and `rebuild/` retirement

- **Status:** Implemented
- **Created:** 2026-10-22
- **Approval source:** Owner accepted both items in chat on 2026-10-22.
- **Implementation log:** session_logs/2026-10-22/03-parity-and-rebuild-retirement.md

## Goal

Prove that pruned `dev` still produces the served V5 projections, then remove the 6A/6B `src/cks_picks_cfb/rebuild/` package that consolidation kept only for four scripts.

## Part A: serving parity (read-only)

Run `run_season.py prepare` into the scratchpad with the active release's manifests (through week 7, next week 8, as-of `2026-10-20T14:39:00Z`, `--environment preview`). Replace only provenance identities (release ID, code commit, predictions SHA, publication payload SHA and its 12-character prefix), then require byte-identical payloads, equal per-table row counts and unchanged rating and measurement identities. On a mismatch, stop and do not start Part B.

## Part B: retire `rebuild/`

Delete the package, the four scripts that imported it, the modules and tests left without importers, and the unread `conf/rebuild` files. Move the pinned bridge fixture to `tests/fixtures/v5_bridge_b2_w5_v1.json` byte-identically. Keep the `rebuild/6a|6b` R2 prefixes and manifest URIs, and research modules that still have callers. No change under the prepare path, so Part A's result holds for the post-retirement tree.

## Gate

Ruff, full pytest with coverage of at least 60%, `make contracts-check`, `make quality-check`, `mkdocs build --strict`, a zero-hit `rg` for deleted names, and `git diff HEAD --check`.
