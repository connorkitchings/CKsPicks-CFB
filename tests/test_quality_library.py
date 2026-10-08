"""Quality library: registration, severity policy, determinism, immutability."""

from __future__ import annotations

import json

import pytest

from cks_picks_cfb.quality import checks as q
from cks_picks_cfb.quality.__main__ import main as cli_main
from cks_picks_cfb.quality.receipt import (
    build_receipt,
    receipt_relative_path,
    write_receipt_local,
    write_receipt_storage,
)


@pytest.fixture
def registry(monkeypatch):
    monkeypatch.setattr(q, "REGISTRY", {})
    return q.REGISTRY


def _run(stage="silver", ctx=None):
    return q.run_stage(stage, ctx or {}, registry=q.REGISTRY)


def test_register_rejects_bad_ids_stages_severities_and_duplicates(registry):
    with pytest.raises(ValueError, match="invalid check id"):
        q.register_check("Bad Id", stage="silver", severity=q.BLOCK, description="x")
    with pytest.raises(ValueError, match="unknown stage"):
        q.register_check("a.b", stage="bronze", severity=q.BLOCK, description="x")
    with pytest.raises(ValueError, match="unknown severity"):
        q.register_check("a.b", stage="silver", severity="fatal", description="x")
    with pytest.raises(ValueError, match="needs a description"):
        q.register_check("a.b", stage="silver", severity=q.BLOCK, description=" ")

    @q.register_check("a.b", stage="silver", severity=q.BLOCK, description="ok")
    def first(ctx):
        return q.Outcome(True)

    with pytest.raises(ValueError, match="duplicate"):
        q.register_check("a.b", stage="silver", severity=q.WARN, description="again")(
            first
        )


def test_only_failed_block_checks_block_a_run(registry):
    @q.register_check("s.warn_fail", stage="silver", severity=q.WARN, description="w")
    def warn(ctx):
        return q.Outcome(False, observed=1, expected=0)

    @q.register_check("s.block_pass", stage="silver", severity=q.BLOCK, description="b")
    def ok(ctx):
        return q.Outcome(True)

    run = _run()
    assert not run.blocked and len(run.failures) == 1

    @q.register_check("s.block_fail", stage="silver", severity=q.BLOCK, description="b")
    def bad(ctx):
        return q.Outcome(False, detail="boom")

    assert _run().blocked


def test_a_crashing_check_is_a_failed_check_at_its_severity(registry):
    @q.register_check("s.crash", stage="silver", severity=q.BLOCK, description="c")
    def crash(ctx):
        raise KeyError("missing column")

    run = _run()
    assert run.blocked
    assert "KeyError" in run.results[0].detail


def test_checks_run_only_for_their_stage_and_can_emit_many_results(registry):
    @q.register_check("i.rows", stage="ingest", severity=q.BLOCK, description="rows")
    def rows(ctx):
        return [q.Outcome(True, scope={"week": w}) for w in (1, 2)]

    assert _run("silver").results == ()
    assert [r.scope["week"] for r in _run("ingest").results] == [1, 2]


def test_receipt_is_deterministic_and_content_addressed(registry):
    @q.register_check("s.a", stage="silver", severity=q.WARN, description="a")
    def a(ctx):
        return q.Outcome(True, observed=3, expected=3)

    kwargs = dict(identity={"year": 2026}, code_sha="abc", inputs={"games": "v1"})
    r1 = build_receipt(_run(), **kwargs)
    r2 = build_receipt(_run(), **kwargs)
    assert r1 == r2 and len(r1["receipt_id"]) == 64
    assert (
        build_receipt(_run(), **{**kwargs, "code_sha": "def"})["receipt_id"]
        != r1["receipt_id"]
    )
    assert r1["summary"]["by_severity"] == {
        "warn": {"passed": 1, "failed": 0, "skipped": 0}
    }


def test_local_writer_is_idempotent_and_refuses_collisions(registry, tmp_path):
    receipt = build_receipt(_run(), identity={}, code_sha="abc")
    path = write_receipt_local(receipt, tmp_path)
    assert path.read_bytes() == write_receipt_local(receipt, tmp_path).read_bytes()
    path.write_bytes(b"tampered")
    with pytest.raises(FileExistsError, match="collision"):
        write_receipt_local(receipt, tmp_path)


def test_storage_writer_is_idempotent_and_refuses_collisions(registry):
    class Store:
        def __init__(self):
            self.blobs = {}

        def exists(self, uri):
            return uri in self.blobs

        def read_bytes(self, uri):
            return self.blobs[uri]

        def write_bytes(self, payload, uri):
            self.blobs[uri] = payload

    store = Store()
    receipt = build_receipt(_run(), identity={}, code_sha="abc")
    uri = write_receipt_storage(receipt, store)
    assert uri == receipt_relative_path(receipt)
    assert write_receipt_storage(receipt, store) == uri
    store.blobs[uri] = b"other"
    with pytest.raises(FileExistsError):
        write_receipt_storage(receipt, store)


def test_registry_problems_flags_a_broken_entry(registry):
    registry["x.y"] = q.CheckSpec("x.y", "silver", "loud", "", lambda ctx: None)
    assert len(q.registry_problems()) == 2


def test_cli_exit_codes_and_receipt(registry, tmp_path, capsys, monkeypatch):
    @q.register_check("s.fail", stage="silver", severity=q.BLOCK, description="f")
    def fail(ctx):
        return q.Outcome(False)

    monkeypatch.setattr("cks_picks_cfb.quality.__main__.REGISTRY", q.REGISTRY)
    monkeypatch.setattr(
        "cks_picks_cfb.quality.__main__.run_stage",
        lambda stage, ctx, **kwargs: q.run_stage(
            stage, ctx, registry=q.REGISTRY, **kwargs
        ),
    )
    assert cli_main(["--stage", "silver", "--output", str(tmp_path)]) == 1
    out = json.loads(capsys.readouterr().out)
    assert (
        out["blocked"] is True
        and (tmp_path / out["receipt"].split(str(tmp_path) + "/")[-1]).exists()
    )
    assert cli_main(["--stage", "gold", "--output", str(tmp_path)]) == 0
    assert cli_main(["--verify-registry"]) == 0
    with pytest.raises(SystemExit) as exc:
        cli_main([])
    assert exc.value.code == 2


def test_a_skipped_check_neither_fails_nor_blocks_and_is_counted(registry):
    @q.register_check("s.skip", stage="silver", severity=q.BLOCK, description="s")
    def skip(ctx):
        return q.skipped("no frame supplied")

    run = _run()
    assert not run.blocked and run.failures == ()
    receipt = build_receipt(run, identity={}, code_sha="abc")
    assert receipt["summary"]["skipped"] == 1 and receipt["summary"]["failed"] == 0
    assert receipt["checks"][0]["skipped"] is True


def test_receipt_write_requires_matching_readback(registry):
    class CorruptStore:
        def exists(self, uri):
            return False

        def write_bytes(self, payload, uri):
            pass

        def read_bytes(self, uri):
            return b"corrupted"

    receipt = build_receipt(_run(), identity={}, code_sha="abc")
    with pytest.raises(IOError, match="readback differs"):
        write_receipt_storage(receipt, CorruptStore())
