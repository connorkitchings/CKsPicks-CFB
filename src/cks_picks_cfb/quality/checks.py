"""Check result types, severity policy and the check registry.

A check inspects one stage's inputs and returns an :class:`Outcome`. The registry
stamps the check id, stage and severity on it, so a check cannot mislabel itself.
A check that raises is recorded as a failed result at its own severity: a crashing
check never passes silently.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Sequence

STAGES = ("ingest", "silver", "gold", "publish")
BLOCK, WARN, INFO = "block", "warn", "info"
SEVERITIES = (BLOCK, WARN, INFO)
_ID = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)*$")


@dataclass(frozen=True)
class Outcome:
    """What a check function returns."""

    passed: bool
    observed: Any = None
    expected: Any = None
    detail: str = ""
    scope: Mapping[str, Any] = field(default_factory=dict)
    skipped: bool = False


def skipped(reason: str) -> Outcome:
    """A check whose input was not supplied: neither passed nor failed, never blocks."""
    return Outcome(passed=False, detail=f"skipped: {reason}", skipped=True)


@dataclass(frozen=True)
class CheckResult:
    check_id: str
    stage: str
    severity: str
    passed: bool
    observed: Any
    expected: Any
    detail: str
    scope: Mapping[str, Any]
    skipped: bool = False

    def to_record(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "stage": self.stage,
            "severity": self.severity,
            "passed": self.passed,
            "observed": self.observed,
            "expected": self.expected,
            "detail": self.detail,
            "scope": dict(self.scope),
            "skipped": self.skipped,
        }


@dataclass(frozen=True)
class CheckSpec:
    check_id: str
    stage: str
    severity: str
    description: str
    fn: Callable[[Mapping[str, Any]], Outcome | Sequence[Outcome]]


REGISTRY: dict[str, CheckSpec] = {}


def register_check(
    check_id: str, *, stage: str, severity: str, description: str
) -> Callable[[Callable], Callable]:
    """Register a check. Ids are unique, dotted snake_case and stage-valid."""
    if not _ID.match(check_id):
        raise ValueError(f"invalid check id: {check_id!r}")
    if stage not in STAGES:
        raise ValueError(f"unknown stage {stage!r}; expected one of {STAGES}")
    if severity not in SEVERITIES:
        raise ValueError(f"unknown severity {severity!r}; expected one of {SEVERITIES}")
    if not description.strip():
        raise ValueError(f"check {check_id} needs a description")

    def decorate(fn: Callable) -> Callable:
        if check_id in REGISTRY:
            raise ValueError(f"duplicate check id: {check_id}")
        REGISTRY[check_id] = CheckSpec(check_id, stage, severity, description, fn)
        return fn

    return decorate


def registry_problems() -> list[str]:
    """Return integrity problems in the registry (used by CI)."""
    problems = []
    for spec in REGISTRY.values():
        if spec.stage not in STAGES or spec.severity not in SEVERITIES:
            problems.append(f"{spec.check_id}: invalid stage or severity")
        if not spec.description.strip():
            problems.append(f"{spec.check_id}: missing description")
        if not callable(spec.fn):
            problems.append(f"{spec.check_id}: not callable")
    return problems


@dataclass(frozen=True)
class QualityRun:
    stage: str
    results: tuple[CheckResult, ...]

    @property
    def failures(self) -> tuple[CheckResult, ...]:
        return tuple(r for r in self.results if not r.passed and not r.skipped)

    @property
    def blocked(self) -> bool:
        return any(r.severity == BLOCK for r in self.failures)


def _result(spec: CheckSpec, outcome: Outcome) -> CheckResult:
    return CheckResult(
        spec.check_id,
        spec.stage,
        spec.severity,
        bool(outcome.passed),
        outcome.observed,
        outcome.expected,
        outcome.detail,
        dict(outcome.scope),
        bool(outcome.skipped),
    )


def run_stage(
    stage: str,
    context: Mapping[str, Any],
    *,
    registry: Mapping[str, CheckSpec] | None = None,
) -> QualityRun:
    """Run every registered check for ``stage`` in check-id order."""
    if stage not in STAGES:
        raise ValueError(f"unknown stage {stage!r}; expected one of {STAGES}")
    specs = sorted(
        (
            s
            for s in (registry if registry is not None else REGISTRY).values()
            if s.stage == stage
        ),
        key=lambda s: s.check_id,
    )
    results: list[CheckResult] = []
    for spec in specs:
        try:
            produced = spec.fn(context)
        except Exception as exc:  # a crashing check is a failed check
            results.append(
                _result(
                    spec,
                    Outcome(False, detail=f"check raised {type(exc).__name__}: {exc}"),
                )
            )
            continue
        outcomes = [produced] if isinstance(produced, Outcome) else list(produced)
        results.extend(_result(spec, o) for o in outcomes)
    return QualityRun(stage, tuple(results))
