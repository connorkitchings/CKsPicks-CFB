"""Rebuild plan and signed preflight record."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from cks_picks_cfb.data.data_first_phase2d import (
    sha256,
    signed_payload,
    verify_signed_payload,
)
from cks_picks_cfb.rebuild.errors import PlanError

HISTORICAL_SEASONS = (2015, 2016, 2017, 2018, 2019, 2021, 2022, 2023, 2024, 2025)
FORBIDDEN_SEASONS = (2020,)
LIVE_SEASON = 2026
DEFAULT_NAMESPACE = "rebuild/6a/"
RUN_NAMESPACES = ("rebuild/6a/", "rebuild/6b/")
INPUT_KINDS = ("git_file", "r2_object", "stage_output")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_SCRATCH_MARKERS = ("scratch", "cache", "/tmp/", "latest", "tmp/")
_SCRATCH_PREFIXES = ("artifacts/", "data/", "/")


@dataclass(frozen=True)
class InputPin:
    """One explicit, hash-bound input."""

    name: str
    uri: str
    sha256: str
    kind: str
    captured_at: str | None = None

    def validate(self) -> None:
        if not self.name or not self.uri:
            raise PlanError("input pin requires name and uri")
        if self.kind not in INPUT_KINDS:
            raise PlanError(f"input {self.name}: unknown kind {self.kind!r}")
        if not _HEX64.match(self.sha256 or ""):
            raise PlanError(f"input {self.name}: sha256 must be 64 lowercase hex")
        lowered = self.uri.lower()
        if any(marker in lowered for marker in _SCRATCH_MARKERS):
            raise PlanError(
                f"input {self.name}: scratch/implicit-latest uri {self.uri}"
            )
        if self.kind == "git_file" and lowered.startswith(_SCRATCH_PREFIXES):
            raise PlanError(f"input {self.name}: untracked scratch path {self.uri}")
        if self.captured_at is not None:
            datetime.fromisoformat(self.captured_at.replace("Z", "+00:00"))


@dataclass(frozen=True)
class StagePlan:
    """Declared stage: which pins it consumes and which keys it will write."""

    name: str
    inputs: tuple[str, ...] = ()
    parents: tuple[str, ...] = ()
    outputs: tuple[str, ...] = ()
    legacy_allowed: bool = False


@dataclass(frozen=True)
class RebuildPlan:
    run_id: str
    storage_identity: str
    seasons: tuple[int, ...]
    inputs: tuple[InputPin, ...]
    stages: tuple[StagePlan, ...]
    registry_checksum: str
    decisions: Mapping[str, str] = field(default_factory=dict)
    policies: Mapping[str, Any] = field(default_factory=dict)
    cutoff_2026: str | None = None
    database_name: str | None = None
    namespace: str = DEFAULT_NAMESPACE

    def validate(self) -> None:
        if not re.match(r"^[A-Za-z0-9][A-Za-z0-9._-]*$", self.run_id or ""):
            raise PlanError("run_id must be a single safe path segment")
        if not self.storage_identity:
            raise PlanError("plan must name the expected storage identity")
        if self.namespace not in RUN_NAMESPACES:
            raise PlanError(f"namespace must be one of {RUN_NAMESPACES}")
        if not self.seasons or any(s in FORBIDDEN_SEASONS for s in self.seasons):
            raise PlanError("2020 is excluded at every boundary")
        if set(self.seasons) != set(HISTORICAL_SEASONS):
            raise PlanError("plan seasons must be exactly 2015-2019 and 2021-2025")
        if not _HEX64.match(self.registry_checksum or ""):
            raise PlanError("registry_checksum must be 64 lowercase hex")
        names = [pin.name for pin in self.inputs]
        if len(set(names)) != len(names):
            raise PlanError("duplicate input names")
        for pin in self.inputs:
            pin.validate()
        for name, digest in self.decisions.items():
            if not _HEX64.match(digest):
                raise PlanError(f"decision {name}: sha256 must be 64 lowercase hex")
        stage_names = [stage.name for stage in self.stages]
        if len(set(stage_names)) != len(stage_names):
            raise PlanError("duplicate stage names")
        known = set(names)
        for index, stage in enumerate(self.stages):
            if missing := set(stage.inputs) - known:
                raise PlanError(
                    f"stage {stage.name}: unpinned inputs {sorted(missing)}"
                )
            earlier = set(stage_names[:index])
            if bad := set(stage.parents) - earlier:
                raise PlanError(f"stage {stage.name}: parents must precede it: {bad}")
        if self.cutoff_2026 is not None:
            cutoff = datetime.fromisoformat(self.cutoff_2026.replace("Z", "+00:00"))
            if cutoff.tzinfo is None or cutoff.utcoffset().total_seconds() != 0:
                raise PlanError("cutoff_2026 must be an exact UTC timestamp")

    def run_prefix(self) -> str:
        return f"{self.namespace}{self.run_id}/"

    def as_dict(self) -> dict[str, Any]:
        value = self._base_dict()
        if self.namespace != DEFAULT_NAMESPACE:
            # Omitted for the default so signed 6A plans keep their exact hash.
            value["namespace"] = self.namespace
        return value

    def _base_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "storage_identity": self.storage_identity,
            "database_name": self.database_name,
            "seasons": list(self.seasons),
            "forbidden_seasons": list(FORBIDDEN_SEASONS),
            "inputs": [vars(pin).copy() for pin in self.inputs],
            "stages": [
                {
                    "name": s.name,
                    "inputs": list(s.inputs),
                    "parents": list(s.parents),
                    "outputs": list(s.outputs),
                    "legacy_allowed": s.legacy_allowed,
                }
                for s in self.stages
            ],
            "registry_checksum": self.registry_checksum,
            "decisions": dict(self.decisions),
            "policies": dict(self.policies),
            "cutoff_2026": self.cutoff_2026,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "RebuildPlan":
        try:
            plan = cls(
                run_id=value["run_id"],
                storage_identity=value["storage_identity"],
                database_name=value.get("database_name"),
                seasons=tuple(int(s) for s in value["seasons"]),
                inputs=tuple(InputPin(**pin) for pin in value["inputs"]),
                stages=tuple(
                    StagePlan(
                        name=s["name"],
                        inputs=tuple(s.get("inputs", ())),
                        parents=tuple(s.get("parents", ())),
                        outputs=tuple(s.get("outputs", ())),
                        legacy_allowed=bool(s.get("legacy_allowed", False)),
                    )
                    for s in value["stages"]
                ),
                registry_checksum=value["registry_checksum"],
                decisions=dict(value.get("decisions", {})),
                policies=dict(value.get("policies", {})),
                cutoff_2026=value.get("cutoff_2026"),
                namespace=value.get("namespace", DEFAULT_NAMESPACE),
            )
        except (KeyError, TypeError) as error:
            raise PlanError(f"malformed plan: {error!r}") from error
        plan.validate()
        return plan

    def plan_sha(self) -> str:
        return sha256(self.as_dict())


def build_preflight_record(
    plan: RebuildPlan,
    *,
    code_sha: str,
    config_sha: str,
    worktree_clean: bool,
    resolved_inputs: Mapping[str, str],
    write_scope: Sequence[str],
) -> dict[str, Any]:
    """Create the signed preflight record binding plan, code and verified inputs."""
    plan.validate()
    if not worktree_clean:
        raise PlanError("preflight requires a clean committed worktree")
    if not re.match(r"^[0-9a-f]{40}$", code_sha or ""):
        raise PlanError("code_sha must be a 40-hex commit")
    expected = {pin.name: pin.sha256 for pin in plan.inputs}
    if dict(resolved_inputs) != expected:
        raise PlanError("resolved input hashes differ from the plan pins")
    return signed_payload(
        {
            "kind": "rebuild_preflight_v1",
            "plan": plan.as_dict(),
            "plan_sha": plan.plan_sha(),
            "code_sha": code_sha,
            "config_sha": config_sha,
            "resolved_inputs": dict(resolved_inputs),
            "write_scope": sorted(write_scope),
        }
    )


def verify_preflight_record(
    record: Mapping[str, Any], plan: RebuildPlan, *, code_sha: str
) -> None:
    verify_signed_payload(record, label="preflight record")
    if record.get("kind") != "rebuild_preflight_v1":
        raise PlanError("not a preflight record")
    if record.get("plan_sha") != plan.plan_sha():
        raise PlanError("preflight record was made for a different plan")
    if record.get("code_sha") != code_sha:
        raise PlanError("preflight record was made for different code")
