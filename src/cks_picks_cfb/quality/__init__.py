"""Data-quality checks, receipts and the ``python -m cks_picks_cfb.quality`` CLI."""

from cks_picks_cfb.quality.checks import (
    BLOCK,
    INFO,
    REGISTRY,
    STAGES,
    WARN,
    CheckResult,
    Outcome,
    QualityRun,
    register_check,
    registry_problems,
    run_stage,
    skipped,
)
from cks_picks_cfb.quality.receipt import (
    build_receipt,
    write_receipt_local,
    write_receipt_storage,
)

__all__ = [
    "BLOCK",
    "INFO",
    "REGISTRY",
    "STAGES",
    "WARN",
    "CheckResult",
    "Outcome",
    "QualityRun",
    "build_receipt",
    "register_check",
    "registry_problems",
    "run_stage",
    "skipped",
    "write_receipt_local",
    "write_receipt_storage",
]

# Importing the stage modules registers their checks.
from cks_picks_cfb.quality import ingest as _ingest  # noqa: E402,F401
from cks_picks_cfb.quality import publish as _publish  # noqa: E402,F401
from cks_picks_cfb.quality import silver as _silver  # noqa: E402,F401
