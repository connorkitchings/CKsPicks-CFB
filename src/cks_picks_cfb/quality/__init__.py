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
    "write_receipt_local",
    "write_receipt_storage",
]
