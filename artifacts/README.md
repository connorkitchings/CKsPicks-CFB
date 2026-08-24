# Local Artifacts

Repository-local `artifacts/` content is for development, research, temporary
reports, and compatible local tooling. It is not the durable production source
of truth and must not act as a mutable production-model registry.

Production datasets and model/prediction artifacts use immutable Cloudflare R2
lineage; Neon holds derived serving and workflow state. See the
[data platform](../docs/architecture/data_platform_2026.md) and
[production runbook](../docs/ops/production_runbook.md).
