# Decision Log

This document records the architectural decisions made for the `cfb_model` project.

- **[YYYY-MM-DD]** - Initial project setup and tooling choices (e.g., `uv`, `prefect`).
- **[2025-08-10]** - Pivot storage backend from Supabase Postgres to local Parquet with
  per-partition manifests and validation utilities. See [LOG:2025-08-10].
- **[2025-08-10]** - Standardize Python baseline to 3.12+ and adopt `uv` for environment and
  tooling. See [LOG:2025-08-10].
