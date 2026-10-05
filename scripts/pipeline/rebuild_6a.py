"""Stage 6A rebuild CLI: preflight, build, verify, publish (Preview only)."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT))  # legacy baseline stage imports scripts.*

from cks_picks_cfb.data.storage.base import StorageSettings  # noqa: E402
from cks_picks_cfb.rebuild.errors import RebuildError  # noqa: E402
from cks_picks_cfb.rebuild.orchestrator import Orchestrator  # noqa: E402
from cks_picks_cfb.rebuild.plan import RebuildPlan  # noqa: E402
from cks_picks_cfb.rebuild.stages import get_stages  # noqa: E402
from cks_picks_cfb.rebuild.targets import (  # noqa: E402
    GuardedStore,
    R2ObjectStore,
)


class LocalStagingStore:
    """Filesystem create-once staging under artifacts/rebuild/<run_id>/."""

    def __init__(self, root: Path):
        self.root = root
        self.identity = f"local:{root}"

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if self.root.resolve() not in path.parents:
            raise ValueError(f"staging key escapes root: {key}")
        return path

    def exists(self, key: str) -> bool:
        return self._path(key).exists()

    def read(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def discard_prefix(self, prefix: str) -> None:
        import shutil

        target = self._path(prefix.rstrip("/"))
        if target.is_dir():
            shutil.rmtree(target)

    def put_if_absent(self, key: str, data: bytes) -> bool:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with path.open("xb") as handle:
                handle.write(data)
            return True
        except FileExistsError:
            return False


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=REPO_ROOT, text=True).strip()


def _preview_store() -> R2ObjectStore:
    settings = StorageSettings.from_env(environment="preview")
    if settings.backend != "r2" or not all(
        (settings.bucket, settings.account_id, settings.access_key, settings.secret_key)
    ):
        raise RebuildError("6A requires CFB_STORAGE_BACKEND=r2 with CFB_R2_PREVIEW_*")
    return R2ObjectStore(
        bucket=settings.bucket,
        account_id=settings.account_id,
        access_key=settings.access_key,
        secret_key=settings.secret_key,
        endpoint=settings.endpoint,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "operation", choices=["preflight", "build", "verify", "publish"]
    )
    parser.add_argument("--plan", default="conf/rebuild/6a_v1.yaml")
    parser.add_argument("--expected-code-sha", required=True)
    parser.add_argument("--stage", action="append")
    args = parser.parse_args(argv)

    head = _git("rev-parse", "HEAD")
    if head != args.expected_code_sha:
        raise RebuildError("--expected-code-sha must equal committed HEAD")
    clean = not _git("status", "--porcelain")
    plan_path = REPO_ROOT / args.plan
    raw = yaml.safe_load(plan_path.read_text())
    remote = _preview_store()
    # The plan names the verified bucket identity; fill it only if the file left it
    # null and the operator confirmed it by passing the same value through the plan.
    if not raw.get("storage_identity"):
        raise RebuildError(
            f"plan storage_identity is unset; verified Preview identity is {remote.identity}"
        )
    plan = RebuildPlan.from_dict(raw)
    guard = GuardedStore(
        remote,
        run_id=plan.run_id,
        expected_identity=plan.storage_identity,
        run_namespace=plan.namespace,
    )
    staging = LocalStagingStore(REPO_ROOT / "artifacts" / "rebuild" / plan.run_id)
    orchestrator = Orchestrator(
        plan,
        get_stages(plan),
        staging=staging,
        code_sha=head,
        repo_root=REPO_ROOT,
        read_remote=remote.read,
    )
    config_sha = hashlib.sha256(plan_path.read_bytes()).hexdigest()
    if args.operation == "preflight":
        record = orchestrator.preflight(
            repo_root=REPO_ROOT,
            config_sha=config_sha,
            worktree_clean=clean,
            guard=guard,
            read_remote=remote.read,
        )
        print(json.dumps({"preflight_sha": record["manifest_sha256"]}))
    elif args.operation == "build":
        print(json.dumps(orchestrator.build(args.stage)))
    elif args.operation == "verify":
        verdict = orchestrator.verify(args.stage)
        print(
            json.dumps({"passed": verdict["passed"], "sha": verdict["manifest_sha256"]})
        )
        return 0 if verdict["passed"] else 1
    else:
        result = orchestrator.publish(guard)
        print(json.dumps(vars(result)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
