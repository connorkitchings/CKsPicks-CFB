"""Pinned input resolution, legacy-parent denylist and implicit-latest guard."""

from __future__ import annotations

import contextlib
import subprocess
from collections.abc import Callable, Iterator, Mapping
from pathlib import Path
from typing import Any

from cks_picks_cfb.rebuild.errors import InputPinError
from cks_picks_cfb.rebuild.plan import InputPin, RebuildPlan, StagePlan
from cks_picks_cfb.rebuild.targets import sha256_bytes

#: Legacy parents the corrected chain must never consume (baseline stages excepted).
LEGACY_PARENT_TOKENS = (
    "repair-v2-20260909T1417Z",
    "possession-v1-measurements-20260921-r9",
    "possession-v1-ratings-20260921-11d59ee-r9cert",
    "forecast-v1-20260921-5afd577-11c",
    "fc26a3d03416e688dc437ad863653dfac7df6faad51b478a7b94f466c0d870c3",
    # The served 2026 chain (pre-6A lineage): reproduction and comparison stages only.
    "intended-update/2026-runs/20260929",
    "intended-update/2026-serving/2026w",
    "e80ae3473d88d0c458325c19343e7dae6447924d9abad29b15089bc19cacd26b",
    "30c4f1eb0ef5b3c1e30b2a877b4553923c3b5ff68832eea0282e37e625b13531",
)


def reject_legacy_parents(plan: RebuildPlan) -> None:
    """Fail if a non-legacy stage consumes a pin that names a stale legacy parent."""
    pins = {pin.name: pin for pin in plan.inputs}
    for stage in plan.stages:
        if stage.legacy_allowed:
            continue
        for name in stage.inputs:
            pin = pins[name]
            haystack = f"{pin.name} {pin.uri} {pin.sha256}"
            for token in LEGACY_PARENT_TOKENS:
                if token in haystack:
                    raise InputPinError(
                        f"stage {stage.name} consumes legacy parent via input "
                        f"{name} ({token})"
                    )


def git_tracked(path: str, repo_root: Path) -> bool:
    result = subprocess.run(
        ["git", "ls-files", "--error-unmatch", "--", path],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def resolve_input(
    pin: InputPin,
    *,
    repo_root: Path,
    read_remote: Callable[[str], bytes] | None = None,
    stage_outputs: Mapping[str, str] | None = None,
    is_tracked: Callable[[str, Path], bool] = git_tracked,
) -> str:
    """Return the verified sha256 of ``pin`` or raise; no input is trusted unhashed."""
    pin.validate()
    if pin.kind == "git_file":
        if not is_tracked(pin.uri, repo_root):
            raise InputPinError(f"input {pin.name}: {pin.uri} is not git-tracked")
        actual = sha256_bytes((repo_root / pin.uri).read_bytes())
    elif pin.kind == "r2_object":
        if read_remote is None:
            raise InputPinError(f"input {pin.name}: no remote reader supplied")
        actual = sha256_bytes(read_remote(pin.uri))
    else:
        known = (stage_outputs or {}).get(pin.uri)
        if known is None:
            raise InputPinError(f"input {pin.name}: stage output {pin.uri} not built")
        actual = known
    if actual != pin.sha256:
        raise InputPinError(
            f"input {pin.name}: hash mismatch (expected {pin.sha256}, got {actual})"
        )
    return actual


def resolve_all(plan: RebuildPlan, **kwargs: Any) -> dict[str, str]:
    """Resolve every non-stage-output pin; used by preflight."""
    reject_legacy_parents(plan)
    return {
        pin.name: resolve_input(pin, **kwargs)
        for pin in plan.inputs
        if pin.kind != "stage_output"
    }


@contextlib.contextmanager
def no_implicit_latest() -> Iterator[None]:
    """Make catalog 'latest version' selection raise while a stage builds."""
    from cks_picks_cfb.data import catalog

    names = ("dataset_ref_as_of", "dataset_ref_for_partition_as_of")
    originals = {
        name: getattr(catalog, name) for name in names if hasattr(catalog, name)
    }

    def refuse(*_args: Any, **_kwargs: Any) -> None:
        raise InputPinError("implicit latest dataset selection is forbidden in 6A")

    for name in originals:
        setattr(catalog, name, refuse)
    try:
        yield
    finally:
        for name, original in originals.items():
            setattr(catalog, name, original)


def stage_pins(plan: RebuildPlan, stage: StagePlan) -> dict[str, InputPin]:
    pins = {pin.name: pin for pin in plan.inputs}
    return {name: pins[name] for name in stage.inputs}
