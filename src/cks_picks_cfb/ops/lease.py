"""Database-side fencing for writes issued by a leased pipeline run."""

from __future__ import annotations

import os
from typing import Any


def assert_active_pipeline_lease(cursor: Any) -> None:
    """Reject a stale state-machine subprocess before it mutates web data.

    Direct operator commands intentionally remain supported: fencing is required
    only when the state machine supplied *either* lease environment variable.
    Supplying one without the other is always a configuration error.
    """

    run_id = os.getenv("CFB_PIPELINE_RUN_ID")
    epoch = os.getenv("CFB_PIPELINE_LEASE_EPOCH")
    if run_id is None and epoch is None:
        return
    if not run_id or epoch is None:
        raise RuntimeError("Pipeline lease context is incomplete")
    try:
        lease_epoch = int(epoch)
    except ValueError as exc:
        raise RuntimeError("Pipeline lease epoch is invalid") from exc

    cursor.execute(
        "SELECT 1 FROM ops.pipeline_runs WHERE pipeline_run_id = %s "
        "AND lease_epoch = %s AND lease_expires_at >= NOW()",
        (run_id, lease_epoch),
    )
    if cursor.fetchone() is None:
        raise RuntimeError("Pipeline lease is stale; refusing database write")
