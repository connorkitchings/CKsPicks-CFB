"""Stage 6A publication to Preview: plan (default) or apply, with optional catalog.

Dry run (default) verifies the signed verify record, the write allow-list and what already
exists remotely, and writes nothing. ``--apply`` copies the verified staged objects to the
Preview R2 bucket create-once, reads every object back, writes the root manifest last, and
with ``--register-catalog`` registers the datasets in ONE Preview catalog transaction.
``--prove-idempotence`` then repeats the publication and requires zero new writes.

    uv run python scripts/pipeline/publish_6a.py --expected-code-sha $(git rev-parse HEAD)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT))

from cks_picks_cfb.rebuild import catalog_publish  # noqa: E402
from cks_picks_cfb.rebuild.errors import GateError  # noqa: E402
from cks_picks_cfb.rebuild.orchestrator import Orchestrator  # noqa: E402
from cks_picks_cfb.rebuild.plan import RebuildPlan  # noqa: E402
from cks_picks_cfb.rebuild.stages import get_stages  # noqa: E402
from cks_picks_cfb.rebuild.targets import (  # noqa: E402
    GuardedStore,
    assert_preview_database,
)
from scripts.pipeline.rebuild_6a import (  # noqa: E402
    LocalStagingStore,
    _git,
    _preview_store,
)


def _build_sha(plan_path: Path, run_id: str) -> str:
    record = json.loads(
        (REPO_ROOT / "artifacts" / "rebuild" / run_id / "preflight.json").read_text()
    )
    return str(record["code_sha"])


def _orchestrator(args) -> tuple[Orchestrator, GuardedStore, RebuildPlan, object, str]:
    head = _git("rev-parse", "HEAD")
    if head != args.expected_code_sha:
        raise GateError("--expected-code-sha must equal committed HEAD")
    if _git("status", "--porcelain"):
        raise GateError("publication requires a clean committed worktree")
    plan_path = REPO_ROOT / args.plan
    plan = RebuildPlan.from_dict(yaml.safe_load(plan_path.read_text()))
    build_sha = _build_sha(plan_path, plan.run_id)
    # Publication is a pure copy of verified bytes: the publisher commit must descend from
    # the build commit; the plan itself is checked against the signed preflight record.
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", build_sha, head], cwd=REPO_ROOT
    )
    if ancestor.returncode != 0:
        raise GateError("the publisher commit does not descend from the build commit")
    remote = _preview_store()
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
        code_sha=build_sha,
        repo_root=REPO_ROOT,
        read_remote=remote.read,
    )
    return orchestrator, guard, plan, staging, head


def plan_publication(orchestrator: Orchestrator, guard: GuardedStore, staging) -> dict:
    """Everything a publication would do, with no write."""
    record = orchestrator._preflight()
    if not staging.exists(orchestrator.VERIFY):
        raise GateError("no verify record: run the full verify first")
    verdict = json.loads(staging.read(orchestrator.VERIFY))
    if not verdict["passed"] or verdict.get("partial"):
        raise GateError("the verify record did not pass in full")
    if verdict["preflight_sha"] != record["manifest_sha256"]:
        raise GateError("the verify record belongs to another preflight")
    total_bytes, namespaces, existing, mismatched = 0, Counter(), 0, 0
    published: dict[str, str] = {}
    owner: dict[str, str] = {}
    for name in orchestrator.order:
        manifest = orchestrator._load_manifest(name)
        if (
            manifest is None
            or manifest["manifest_sha256"] != verdict["stages"][name]["manifest_sha"]
        ):
            raise GateError(f"stage {name} changed after verification")
        for key, digest in manifest["artifacts"].items():
            guard.check_key(key)
            data = staging.read(orchestrator._artifact_key(name, key))
            if hashlib.sha256(data).hexdigest() != digest:
                raise GateError(f"staged bytes changed after verification: {key}")
            total_bytes += len(data)
            namespaces["/".join(key.split("/")[:2])] += 1
            published[key] = digest
            owner[key] = name
            if guard.exists(key):
                existing += 1
                if hashlib.sha256(guard.read(key)).hexdigest() != digest:
                    mismatched += 1
    if mismatched:
        raise GateError(
            f"{mismatched} existing remote objects differ from the staged bytes"
        )
    entries = catalog_publish.collect_entries(
        published,
        lambda key: staging.read(orchestrator._artifact_key(owner[key], key)),
    )
    return {
        "objects": len(published),
        "bytes": total_bytes,
        "namespaces": dict(sorted(namespaces.items())),
        "already_present_identical": existing,
        "catalog_entries": Counter(f"{e.kind}:{e.tier}:{e.dataset}" for e in entries),
        "catalog_write_scope_ok": catalog_publish.write_scope_ok(),
        "verify_sha": verdict["manifest_sha256"],
    }


def _registrar(guard: GuardedStore, results: list):
    from cks_picks_cfb.data.runtime import resolve_runtime_target
    from cks_picks_cfb.data.schema_contracts import schema_for

    conn_url = resolve_runtime_target("preview").database_url

    def register(root: dict) -> None:
        entries = catalog_publish.collect_entries(root["objects"], guard.read)
        results.append(
            catalog_publish.register_entries(
                conn_url,
                entries,
                schema_lookup=schema_for,
                before_write=lambda cur: assert_preview_database(cur),
            )
        )

    return register


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", default="conf/rebuild/6a_v1.yaml")
    parser.add_argument("--expected-code-sha", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--register-catalog", action="store_true")
    parser.add_argument("--prove-idempotence", action="store_true")
    args = parser.parse_args(argv)
    if (args.register_catalog or args.prove_idempotence) and not args.apply:
        raise GateError("--register-catalog and --prove-idempotence require --apply")
    orchestrator, guard, plan, staging, publisher = _orchestrator(args)
    summary = plan_publication(orchestrator, guard, staging)
    if not args.apply:
        print(json.dumps({"mode": "dry-run", **summary}, indent=2, default=dict))
        return 0
    catalog_results: list[dict] = []
    registrar = _registrar(guard, catalog_results) if args.register_catalog else None
    first = orchestrator.publish(guard, registrar=registrar, publisher_sha=publisher)
    report = {
        "mode": "apply",
        "plan": summary,
        "publish": vars(first),
        "catalog": catalog_results[:],
    }
    if args.prove_idempotence:
        second = orchestrator.publish(
            guard, registrar=registrar, publisher_sha=publisher
        )
        report["retry"] = vars(second)
        report["retry_catalog"] = catalog_results[1:]
        if second.writes != 0 or second.root_sha != first.root_sha:
            raise GateError("the identical retry wrote objects or changed the root")
        if registrar and any(sum(item.values()) for item in catalog_results[1:]):
            raise GateError("the identical retry wrote catalog rows")
    print(json.dumps(report, indent=2, default=dict))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
