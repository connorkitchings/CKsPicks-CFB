"""Restricted pipeline database identity required before any V5 write."""

from __future__ import annotations

from typing import Any


class V5ReleaseError(ValueError):
    """The reviewed release does not authorize this exact immutable run."""


V5_PIPELINE_ROLE_BY_ENVIRONMENT = {
    "preview": "cks_preview_pipeline",
    "production": "cks_prod_pipeline",
}


def assert_v5_database_environment(cur: Any, environment: str) -> None:
    """Require the exact restricted pipeline login for this environment.

    Both the login identity (``session_user``) and the effective identity
    (``current_user``) must equal the branch-scoped pipeline role, so owner,
    migrator, web, wrong-branch, and ``SET ROLE`` sessions are all rejected
    before any V5 prediction or selection write.
    """
    expected = V5_PIPELINE_ROLE_BY_ENVIRONMENT.get(environment)
    if expected is None:
        raise V5ReleaseError("invalid V5 database environment")
    cur.execute("SELECT session_user, current_user")
    row = cur.fetchone()
    if not row or len(row) < 2:
        raise V5ReleaseError("V5 database identity is unreadable")
    session_role, effective_role = str(row[0]), str(row[1])
    if session_role != expected or effective_role != expected:
        raise V5ReleaseError(
            "V5 writes require the exact restricted pipeline role "
            f"{expected} for environment {environment}; got "
            f"session_user={session_role!r}, current_user={effective_role!r}"
        )
