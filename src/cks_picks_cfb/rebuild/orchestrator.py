"""Stage DAG orchestrator: preflight, build, verify and Preview publication."""

from __future__ import annotations

import contextlib
import json
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from cks_picks_cfb.data.data_first_phase2d import (
    sha256,
    signed_payload,
    verify_signed_payload,
)
from cks_picks_cfb.rebuild.errors import GateError, ImmutableCollisionError
from cks_picks_cfb.rebuild.inputs import no_implicit_latest, resolve_all
from cks_picks_cfb.rebuild.plan import (
    RebuildPlan,
    StagePlan,
    build_preflight_record,
    verify_preflight_record,
)
from cks_picks_cfb.rebuild.targets import GuardedStore, ObjectStore, sha256_bytes

Artifacts = Iterable[tuple[str, bytes]]


@dataclass
class StageContext:
    """What a stage may see: its verified pins and its parents' manifest hashes."""

    plan: RebuildPlan
    stage: StagePlan
    inputs: Mapping[str, str]
    parents: Mapping[str, str]
    read_artifact: Callable[[str, str], bytes]
    code_sha: str = ""
    read_input: Callable[[str], bytes] = lambda name: (_ for _ in ()).throw(
        GateError(f"no input reader for {name}")
    )


@dataclass
class StageOutput:
    artifacts: Artifacts
    metrics: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Stage:
    plan: StagePlan
    build: Callable[[StageContext], StageOutput]
    verify: Callable[[StageContext], list[str]]


@dataclass
class PublishResult:
    root_key: str
    root_sha: str
    objects: int
    writes: int
    registered: bool


def _canonical_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


class Orchestrator:
    """Runs one signed plan against a staging store; publishes only verified output."""

    PREFLIGHT = "preflight.json"
    VERIFY = "verify.json"

    def __init__(
        self,
        plan: RebuildPlan,
        stages: Iterable[Stage],
        *,
        staging: ObjectStore,
        code_sha: str,
        repo_root: Path | None = None,
        read_remote: Callable[[str], bytes] | None = None,
    ):
        plan.validate()
        self.repo_root = repo_root
        self.read_remote = read_remote
        self.plan = plan
        self.stages = {stage.plan.name: stage for stage in stages}
        planned = [stage.name for stage in plan.stages]
        if set(self.stages) != set(planned):
            raise GateError("implemented stages differ from the plan")
        self.order = planned
        self.staging = staging
        self.code_sha = code_sha

    # ---- helpers ---------------------------------------------------------
    def _put(self, key: str, data: bytes) -> str:
        """Create-once in staging; identical retries pass, conflicts fail."""
        if not self.staging.put_if_absent(key, data):
            if sha256_bytes(self.staging.read(key)) != sha256_bytes(data):
                raise ImmutableCollisionError(f"staging collision: {key}")
        return sha256_bytes(data)

    def _json(self, key: str) -> dict[str, Any]:
        return json.loads(self.staging.read(key))

    def _manifest_key(self, stage: str) -> str:
        return f"stages/{stage}/manifest.json"

    def _artifact_key(self, stage: str, key: str) -> str:
        return f"stages/{stage}/artifacts/{key}"

    def _load_manifest(self, stage: str) -> dict[str, Any] | None:
        key = self._manifest_key(stage)
        if not self.staging.exists(key):
            return None
        manifest = self._json(key)
        verify_signed_payload(manifest, label=f"stage manifest {stage}")
        return manifest

    def _read_input(self, stage: Stage, inputs: Mapping[str, str]):
        pins = {pin.name: pin for pin in self.plan.inputs}

        def read(name: str) -> bytes:
            if name not in stage.plan.inputs:
                raise GateError(f"stage {stage.plan.name} did not declare input {name}")
            pin = pins[name]
            if pin.kind == "git_file" and self.repo_root is not None:
                data = (self.repo_root / pin.uri).read_bytes()
            elif pin.kind == "r2_object" and self.read_remote is not None:
                data = self.read_remote(pin.uri)
            else:
                raise GateError(f"input {name} cannot be read here")
            if sha256_bytes(data) != inputs[name]:
                raise GateError(f"input {name} changed after preflight")
            return data

        return read

    def _context(self, stage: Stage, inputs: Mapping[str, str]) -> StageContext:
        parents: dict[str, str] = {}
        for parent in stage.plan.parents:
            manifest = self._load_manifest(parent)
            if manifest is None:
                raise GateError(f"stage {stage.plan.name}: parent {parent} not built")
            parents[parent] = manifest["manifest_sha256"]
        return StageContext(
            plan=self.plan,
            stage=stage.plan,
            inputs=inputs,
            parents=parents,
            read_artifact=lambda s, k: self.staging.read(self._artifact_key(s, k)),
            read_input=self._read_input(stage, inputs),
            code_sha=self.code_sha,
        )

    def _check_declared(self, stage: StagePlan, key: str) -> None:
        if stage.outputs and not key.startswith(tuple(stage.outputs)):
            raise GateError(f"stage {stage.name}: undeclared output {key}")

    # ---- operations ------------------------------------------------------
    def preflight(
        self,
        *,
        repo_root: Path,
        config_sha: str,
        worktree_clean: bool,
        guard: GuardedStore,
        read_remote: Callable[[str], bytes] | None = None,
        is_tracked: Callable[[str, Path], bool] | None = None,
    ) -> dict[str, Any]:
        """Verify target and pins, then record the full intended scope. No data writes."""
        if guard.identity != self.plan.storage_identity:
            raise GateError("storage identity differs from the plan")
        kwargs: dict[str, Any] = {"repo_root": repo_root, "read_remote": read_remote}
        if is_tracked is not None:
            kwargs["is_tracked"] = is_tracked
        resolved = resolve_all(self.plan, **kwargs)
        scope = [prefix for prefix in guard.namespaces]
        record = build_preflight_record(
            self.plan,
            code_sha=self.code_sha,
            config_sha=config_sha,
            worktree_clean=worktree_clean,
            resolved_inputs=resolved,
            write_scope=scope,
        )
        self._put(self.PREFLIGHT, _canonical_bytes(record))
        return record

    def _preflight(self) -> dict[str, Any]:
        if not self.staging.exists(self.PREFLIGHT):
            raise GateError("no preflight record; run preflight first")
        record = self._json(self.PREFLIGHT)
        verify_preflight_record(record, self.plan, code_sha=self.code_sha)
        return record

    def build(self, only: Iterable[str] | None = None) -> dict[str, str]:
        """Build stages in order; resume only against identical verified parents."""
        record = self._preflight()
        wanted = set(only) if only is not None else set(self.order)
        built: dict[str, str] = {}
        for name in self.order:
            stage = self.stages[name]
            existing = self._load_manifest(name)
            if existing is None and name not in wanted:
                continue
            context = self._context(stage, record["resolved_inputs"])
            if existing is None and hasattr(self.staging, "discard_prefix"):
                # A stage without a manifest was never consumable; drop partial leftovers
                # of a failed attempt so a retry cannot collide with them.
                self.staging.discard_prefix(f"stages/{name}/")
            if existing is not None:
                if existing["preflight_sha"] != record["manifest_sha256"] or existing[
                    "parents"
                ] != dict(context.parents):
                    raise GateError(f"stage {name}: conflicting inputs for built stage")
                built[name] = existing["manifest_sha256"]
                continue
            guard = (
                contextlib.nullcontext()
                if stage.plan.legacy_allowed
                else no_implicit_latest()
            )
            with guard:
                output = stage.build(context)
                artifacts: dict[str, str] = {}
                for key, data in output.artifacts:
                    self._check_declared(stage.plan, key)
                    artifacts[key] = self._put(self._artifact_key(name, key), data)
            manifest = signed_payload(
                {
                    "kind": "rebuild_stage_v1",
                    "stage": name,
                    "preflight_sha": record["manifest_sha256"],
                    "code_sha": self.code_sha,
                    "parents": dict(context.parents),
                    "artifacts": artifacts,
                    "metrics": dict(output.metrics),
                }
            )
            self._put(self._manifest_key(name), _canonical_bytes(manifest))
            built[name] = manifest["manifest_sha256"]
        return built

    def verify(self, only: Iterable[str] | None = None) -> dict[str, Any]:
        """Re-hash staged bytes and run each stage's independent verifier.

        A partial verify (``only``) reports those stages but is never persisted, so
        it can never satisfy publication; only a full verify writes the record.
        """
        record = self._preflight()
        wanted = set(only) if only is not None else set(self.order)
        results: dict[str, Any] = {}
        passed = True
        for name in self.order:
            if name not in wanted:
                continue
            manifest = self._load_manifest(name)
            if manifest is None:
                results[name] = {"manifest_sha": None, "problems": ["stage not built"]}
                passed = False
                continue
            problems: list[str] = []
            for key, digest in manifest["artifacts"].items():
                data = self.staging.read(self._artifact_key(name, key))
                if sha256_bytes(data) != digest:
                    problems.append(f"artifact hash mismatch: {key}")
            stage = self.stages[name]
            context = self._context(stage, record["resolved_inputs"])
            problems.extend(stage.verify(context))
            results[name] = {
                "manifest_sha": manifest["manifest_sha256"],
                "problems": problems,
            }
            passed = passed and not problems
        verdict = signed_payload(
            {
                "kind": "rebuild_verify_v1",
                "preflight_sha": record["manifest_sha256"],
                "code_sha": self.code_sha,
                "stages": results,
                "passed": passed,
                "partial": only is not None,
            }
        )
        if only is None:
            self._put(self.VERIFY, _canonical_bytes(verdict))
        return verdict

    def publish(
        self,
        guard: GuardedStore,
        *,
        registrar: Callable[[dict[str, Any]], None] | None = None,
        publisher_sha: str | None = None,
    ) -> PublishResult:
        """Publish verified output create-once, read back, then root, then catalog.

        Publication copies already-verified bytes, so the stage identity stays the build
        commit (``code_sha``); ``publisher_sha`` records the later commit of the tooling
        that performed the copy.
        """
        record = self._preflight()
        if not self.staging.exists(self.VERIFY):
            raise GateError("publish requires a verify record")
        verdict = self._json(self.VERIFY)
        verify_signed_payload(verdict, label="verify record")
        if (
            not verdict["passed"]
            or verdict.get("partial")
            or verdict["preflight_sha"] != record["manifest_sha256"]
        ):
            raise GateError("publish refused: verification did not pass")
        if guard.identity != self.plan.storage_identity:
            raise GateError("storage identity differs from the plan")
        before = guard.ledger.writes
        stage_manifests: dict[str, str] = {}
        published: dict[str, str] = {}
        for name in self.order:
            manifest = self._load_manifest(name)
            if manifest is None or (
                manifest["manifest_sha256"] != verdict["stages"][name]["manifest_sha"]
            ):
                raise GateError(f"stage {name} changed after verification")
            stage_manifests[name] = manifest["manifest_sha256"]
            for key, digest in manifest["artifacts"].items():
                data = self.staging.read(self._artifact_key(name, key))
                if sha256_bytes(data) != digest:
                    raise GateError(f"staged bytes changed after verification: {key}")
                guard.create_once(key, data)
                published[key] = digest
        for key, digest in published.items():
            if sha256_bytes(guard.read(key)) != digest:
                raise GateError(f"readback hash mismatch: {key}")
        root = signed_payload(
            {
                "kind": "rebuild_root_v1",
                "run_id": self.plan.run_id,
                "preflight_sha": record["manifest_sha256"],
                "verify_sha": verdict["manifest_sha256"],
                "code_sha": self.code_sha,
                "publisher_code_sha": publisher_sha,
                "stages": stage_manifests,
                "objects": published,
            }
        )
        root_key = f"rebuild/6a/{self.plan.run_id}/root-manifest.json"
        guard.create_once(root_key, _canonical_bytes(root))
        if registrar is not None:
            registrar(root)
        return PublishResult(
            root_key=root_key,
            root_sha=root["manifest_sha256"],
            objects=len(published),
            writes=guard.ledger.writes - before,
            registered=registrar is not None,
        )


def stage_hash(value: Mapping[str, Any]) -> str:
    return sha256(value)
