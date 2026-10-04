"""Rebuild orchestration errors; every guard fails closed with one of these."""

from __future__ import annotations


class RebuildError(RuntimeError):
    """Base class for rebuild harness failures."""


class PlanError(RebuildError):
    """The rebuild plan is invalid, incomplete or inconsistent with its inputs."""


class InputPinError(RebuildError):
    """An input is unpinned, unverified, implicit, scratch-sourced or stale."""


class TargetError(RebuildError):
    """The storage or database target is not the verified Preview target."""


class ImmutableCollisionError(RebuildError):
    """An immutable object already exists with different bytes."""


class GateError(RebuildError):
    """A stage, verification or publication prerequisite failed."""
