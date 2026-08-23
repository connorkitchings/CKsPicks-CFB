"""Small, dependency-free contracts shared by operation components."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Callable


class StepState(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True)
class OperationContext:
    command: str
    environment: str
    season: int
    week: int | None
    as_of: str | None
    pipeline_run_id: str
    prediction_run_id: str | None = None
    lease_epoch: int | None = None

    @property
    def lock_key(self) -> str:
        return f"cks:{self.environment}:{self.season}:{self.week or 0}"


StepAction = Callable[[OperationContext], Sequence[Mapping[str, Any]] | None]
