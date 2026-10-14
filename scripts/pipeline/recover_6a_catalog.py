"""Recover the Preview catalog registration of an already-published 6A run (catalog only).

The Week 6 6A root was published without its catalog registration (and with no publisher
commit recorded). The root is create-once, so it is not republished: this command reads the
published root, checks its signature and every object it registers against the root's
hashes, and registers the same entries ``publish_6a.py --register-catalog`` would have, with
the same ``catalog_publish`` code, in ONE Preview transaction. It writes no R2 object and no
serving table.

Dry run (default) verifies everything and reports what would be registered. ``--apply``
registers, reads every version back on a separate read-only connection, proves an identical
retry writes zero rows and that the root's bytes are unchanged, and leaves a local recovery
record that keeps the root's missing publisher commit on file.

    uv run python scripts/pipeline/recover_6a_catalog.py \\
        --root-uri rebuild/6a/6a-rebuild-w6-20261012-r2/root-manifest.json \\
        --root-sha256 9d218543eec7eda149bbb5ba446b5f73f33b8ae107d5a7da20bdbe00f8d007c3 \\
        --expected-code-sha <the root's build commit> --expected-versions 49 [--apply]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT))

from cks_picks_cfb.data.data_first_phase2d import verify_signed_payload  # noqa: E402
from cks_picks_cfb.rebuild import catalog_publish  # noqa: E402
from cks_picks_cfb.rebuild.errors import GateError  # noqa: E402
from cks_picks_cfb.rebuild.plan import RebuildPlan  # noqa: E402
from cks_picks_cfb.rebuild.targets import assert_preview_database  # noqa: E402

ROOT_URI = re.compile(r"rebuild/6a/(?P<run>[^/]+)/root-manifest\.json")


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def open_root(
    read: Callable[[str], bytes], root_uri: str, root_sha256: str, code_sha: str
) -> dict[str, Any]:
    """The published root at exactly this URI and raw hash, signed, of this build commit."""
    match = ROOT_URI.fullmatch(root_uri)
    if match is None:
        raise GateError(f"{root_uri} is not a 6A root manifest key")
    raw = read(root_uri)
    if _sha(raw) != root_sha256:
        raise GateError(f"{root_uri} is not the root pinned by --root-sha256")
    root = json.loads(raw)
    verify_signed_payload(root, label="published root manifest")
    if root.get("kind") != "rebuild_root_v1" or root.get("run_id") != match["run"]:
        raise GateError(f"{root_uri} is not the published root of {match['run']}")
    if root.get("code_sha") != code_sha:
        raise GateError(
            f"root build commit {root.get('code_sha')} != --expected-code-sha {code_sha}"
        )
    return root


def collect(
    root: dict[str, Any], read: Callable[[str], bytes], expected_versions: int
) -> list[catalog_publish.Entry]:
    """The catalog entries of the root, every byte they rest on checked against the root."""
    objects = root["objects"]

    def checked(key: str) -> bytes:
        data = read(key)
        if _sha(data) != objects[key]:
            raise GateError(f"published object changed: {key}")
        return data

    entries = catalog_publish.collect_entries(objects, checked)
    for entry in entries:
        if entry.kind == "plain" and objects.get(entry.uri) != entry.content_sha:
            raise GateError(f"{entry.version_id}: data is not the root's {entry.uri}")
    if len(entries) != expected_versions:
        raise GateError(
            f"the root registers {len(entries)} dataset versions, not {expected_versions}"
        )
    return entries


VERSION_COLUMNS = (
    "version_id",
    "dataset",
    "tier",
    "schema_version",
    "content_sha",
    "uri",
    "manifest_uri",
    "row_count",
)


def _identity(entry: catalog_publish.Entry) -> tuple:
    return tuple(str(getattr(entry, c)) for c in VERSION_COLUMNS)


def catalog_state(cur, entries: Sequence[catalog_publish.Entry]) -> dict[str, Any]:
    """What the catalog already holds for these entries, and every reason not to write.

    An existing version that differs from its entry is a conflict; a parent outside this
    batch must already be registered. Either refuses the recovery.
    """
    ids = [e.version_id for e in entries]
    cur.execute(
        f"SELECT {', '.join(VERSION_COLUMNS)} FROM catalog.dataset_versions "  # noqa: S608
        "WHERE version_id = ANY(%s)",
        (ids,),
    )
    existing = {row[0]: tuple(map(str, row)) for row in cur.fetchall()}
    conflicts = sorted(
        e.version_id
        for e in entries
        if e.version_id in existing and existing[e.version_id] != _identity(e)
    )
    external = sorted({p for e in entries for p in e.parents} - set(ids))
    found: set[str] = set()
    if external:
        cur.execute(
            "SELECT version_id FROM catalog.dataset_versions WHERE version_id = ANY(%s)",
            (external,),
        )
        found = {row[0] for row in cur.fetchall()}
    missing = sorted(set(external) - found)
    if conflicts:
        raise GateError(f"existing catalog versions conflict: {conflicts}")
    if missing:
        raise GateError(f"parents missing from the catalog: {missing}")
    return {
        "versions_expected": len(ids),
        "already_registered": len(existing),
        "to_register": len(ids) - len(existing),
        "external_parents": len(external),
    }


def readback(cur, entries: Sequence[catalog_publish.Entry]) -> dict[str, Any]:
    """Every version, edge, capture and quality result present and as recorded."""
    ids = [e.version_id for e in entries]
    cur.execute(
        f"SELECT {', '.join(VERSION_COLUMNS)} FROM catalog.dataset_versions "  # noqa: S608
        "WHERE version_id = ANY(%s)",
        (ids,),
    )
    rows = {row[0]: tuple(map(str, row)) for row in cur.fetchall()}
    counts = {}
    for name, table, column in (
        ("dependencies", "dataset_dependencies", "child_version_id"),
        ("captures", "dataset_capture_dependencies", "child_version_id"),
        ("quality", "quality_results", "version_id"),
    ):
        cur.execute(
            f"SELECT count(*) FROM catalog.{table} WHERE {column} = ANY(%s)",  # noqa: S608
            (ids,),
        )
        counts[name] = int(cur.fetchone()[0])
    expected = {
        "dependencies": sum(len(set(e.parents)) for e in entries),
        "captures": sum(len(set(e.captures)) for e in entries),
        "quality": sum(len(e.validation) for e in entries),
    }
    mismatched = sorted(
        e.version_id for e in entries if rows.get(e.version_id) != _identity(e)
    )
    return {
        "versions_expected": len(ids),
        "versions_present": len(rows),
        "versions_mismatched": mismatched,
        "counts": counts,
        "counts_expected": expected,
        "complete": not mismatched and counts == expected,
    }


def recover(
    *,
    read: Callable[[str], bytes],
    storage_identity: str,
    plan: RebuildPlan,
    root_uri: str,
    root_sha256: str,
    code_sha: str,
    expected_versions: int,
    connect: Callable[[str], Any],
    conn_url: str,
    schema_lookup: Callable[[str, str], Any],
    apply: bool,
) -> dict[str, Any]:
    """Verify, then (with ``apply``) register, read back and prove the retry is empty."""
    if storage_identity != plan.storage_identity:
        raise GateError(
            f"storage {storage_identity!r} is not the plan's {plan.storage_identity!r}"
        )
    if root_uri != f"{plan.run_prefix()}root-manifest.json":
        raise GateError(f"{root_uri} is not the root of plan run {plan.run_id}")
    root = open_root(read, root_uri, root_sha256, code_sha)
    entries = collect(root, read, expected_versions)

    def check(cur) -> dict[str, Any]:
        assert_preview_database(cur)
        return catalog_state(cur, entries)

    with connect(conn_url) as conn:
        conn.read_only = True
        with conn.cursor() as cur:
            state = check(cur)
    report: dict[str, Any] = {
        "mode": "apply" if apply else "dry-run",
        "root": {
            "uri": root_uri,
            "raw_sha256": root_sha256,
            "code_sha": root["code_sha"],
            "publisher_code_sha": root.get("publisher_code_sha"),
        },
        "catalog_write_scope_ok": catalog_publish.write_scope_ok(),
        "catalog_before": state,
    }
    if not apply:
        return report

    def register() -> dict[str, int]:
        return catalog_publish.register_entries(
            conn_url,
            entries,
            schema_lookup=schema_lookup,
            before_write=check,  # re-checked inside the writing transaction
            connect=connect,
        )

    report["written"] = register()
    with connect(conn_url) as conn:
        conn.read_only = True
        with conn.cursor() as cur:
            assert_preview_database(cur)
            report["readback"] = readback(cur, entries)
    if not report["readback"]["complete"]:
        raise GateError(f"catalog readback is incomplete: {report['readback']}")
    report["retry_written"] = register()
    if any(report["retry_written"].values()):
        raise GateError("the identical retry wrote catalog rows")
    if _sha(read(root_uri)) != root_sha256:
        raise GateError("the published root's bytes changed")
    report["root_bytes_unchanged"] = True
    return report


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=REPO_ROOT, text=True).strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", default="conf/rebuild/6a_w6_v1.yaml")
    parser.add_argument("--root-uri", required=True)
    parser.add_argument("--root-sha256", required=True)
    parser.add_argument("--expected-code-sha", required=True)
    parser.add_argument("--expected-versions", type=int, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)

    from cks_picks_cfb.data.runtime import resolve_runtime_target
    from cks_picks_cfb.data.schema_contracts import schema_for
    from scripts.pipeline.rebuild_6a import _preview_store

    if _git("status", "--porcelain"):
        raise GateError("recovery requires a clean committed worktree")
    import psycopg

    plan = RebuildPlan.from_dict(yaml.safe_load((REPO_ROOT / args.plan).read_text()))
    store = _preview_store()
    report = recover(
        read=store.read,
        storage_identity=store.identity,
        plan=plan,
        root_uri=args.root_uri,
        root_sha256=args.root_sha256,
        code_sha=args.expected_code_sha,
        expected_versions=args.expected_versions,
        connect=psycopg.connect,
        conn_url=resolve_runtime_target("preview").database_url,
        schema_lookup=schema_for,
        apply=args.apply,
    )
    report["recovery_code_sha"] = _git("rev-parse", "HEAD")
    if args.apply:
        report["limitation"] = (
            "the root was published by rebuild_6a.py publish: publisher_code_sha is null "
            "and the root is create-once, so it stays as published; only its catalog "
            "registration was recovered, by the commit above"
        )
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        record = REPO_ROOT / "artifacts" / "rebuild" / plan.run_id
        record.mkdir(parents=True, exist_ok=True)
        with (record / f"catalog-recovery.{stamp}.json").open("x") as handle:
            json.dump(report, handle, indent=2, sort_keys=True, default=str)
    print(json.dumps(report, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
