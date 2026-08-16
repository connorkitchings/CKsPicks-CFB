"""Fail-closed runtime targeting for pipeline commands."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

RuntimeEnvironment = Literal["preview", "production"]


@dataclass(frozen=True)
class RuntimeTarget:
    """The database and artifact namespace selected for one operation."""

    environment: RuntimeEnvironment
    database_url: str


def resolve_runtime_target(environment: str) -> RuntimeTarget:
    """Resolve one explicit environment without Preview-to-production fallback."""
    if environment not in {"preview", "production"}:
        raise ValueError("environment must be preview or production")
    variable = "PREVIEW_DATABASE_URL" if environment == "preview" else "DATABASE_URL"
    database_url = os.getenv(variable)
    if not database_url:
        raise RuntimeError(f"{variable} is required for {environment} operations")
    if environment == "preview":
        production_url = os.getenv("DATABASE_URL")
        if production_url and database_url == production_url:
            raise RuntimeError("PREVIEW_DATABASE_URL must differ from DATABASE_URL")
    return RuntimeTarget(environment=environment, database_url=database_url)


def require_explicit_environment(value: str | None) -> RuntimeEnvironment:
    """Validate CLI environment input; mutating commands have no implicit default."""
    if value not in {"preview", "production"}:
        raise ValueError("--environment must be preview or production")
    return value
