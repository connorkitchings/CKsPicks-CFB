"""Fail-closed baseline derivation and independent comparison verification."""

from __future__ import annotations

import copy
import json
from types import SimpleNamespace

import pandas as pd
import pytest

from cks_picks_cfb.rebuild import comparison_baseline as b
from cks_picks_cfb.rebuild import published_comparison as pc
from cks_picks_cfb.rebuild.errors import GateError
from scripts.pipeline import capture_task4_w6_comparison_baseline as cli


def components():
    old = [
        {"component_id": f"old{i}", "season": 2026, "as_of_week": 6} for i in range(508)
    ]
    extra = [
        {"component_id": f"new{i}", "season": 2026, "as_of_week": 7} for i in range(276)
    ]
    return old, extra


def test_derive_keeps_all_week6_components_and_is_order_independent():
    old, extra = components()
    expected = sorted(row["component_id"] for row in extra)
    assert b.derive_component_ids(old, list(reversed(old + extra)), 7) == expected


@pytest.mark.parametrize(
    "fault", ["missing", "count", "scope", "duplicate", "week6", "season"]
)
def test_derive_refuses_unapproved_population(fault):
    old, extra = components()
    built = old + extra
    if fault == "missing":
        built = built[1:]
    elif fault == "count":
        built = built[:-1]
    elif fault == "scope":
        built[-1] = {**built[-1], "as_of_week": 8}
    elif fault == "duplicate":
        built.append(built[-1])
    elif fault == "week6":
        old = old[:-1]
    else:
        built[-1] = {**built[-1], "season": 2025}
    with pytest.raises(b.BaselineError):
        b.derive_component_ids(old, built, 7)


def test_check_additions_refuses_duplicate_primary_keys():
    old, extra = components()
    with pytest.raises(b.BaselineError, match="duplicate"):
        b.check_additions(
            "components", old, old + extra + extra[:1], ["component_id"], None
        )


@pytest.fixture
def captured(tmp_path):
    old, extra = components()
    source = tmp_path / "ids.json"
    source.write_text(json.dumps(sorted(row["component_id"] for row in extra)))
    lock = {
        "extends": {
            "added_post_week": 6,
            "newly_final_game_ids": list(range(58)),
            "previous_extension": {
                "added_post_week": 5,
                "newly_final_game_ids": list(range(100, 156)),
            },
        }
    }
    lock_raw = json.dumps(lock).encode()
    doc = {
        "schema_version": b.SCHEMA,
        "environment": "preview",
        "season": 2026,
        "tables": {
            table: [
                {
                    "season": "2026",
                    "week": "6",
                    "provenance": "run",
                    "rows": 508 if table == "team_rating_components" else 1,
                    "sha256": "a" * 64,
                }
            ]
            for table in b.WEEK_COLUMN
        },
        "publications": {
            run: [{column: "value" for column in b.PUBLICATION_COLUMNS}]
            for run in b.RATING_RUNS
        },
        "expected_additions": {
            "team_rating_components": b.component_declaration(source),
            "team_game_measurements": b.measurement_declaration(
                lock, b.hashlib.sha256(lock_raw).hexdigest()
            ),
        },
    }
    return doc, lock_raw, source


def test_valid_baseline_rechecks_declaration_source_bytes(captured):
    doc, lock_raw, source = captured
    assert b.validate_baseline(json.dumps(doc).encode(), lock_raw) == doc
    source.write_text(source.read_text() + "\n")
    with pytest.raises(b.BaselineError, match="source bytes changed"):
        b.validate_baseline(json.dumps(doc).encode(), lock_raw)


@pytest.mark.parametrize(
    "fault", ["schema", "groups", "hash", "declaration", "publication", "week6"]
)
def test_invalid_baseline_refuses(captured, fault):
    doc, lock_raw, _ = captured
    if fault == "schema":
        doc["schema_version"] = "other"
    elif fault == "groups":
        doc["tables"]["team_rating_components"].clear()
    elif fault == "hash":
        doc["tables"]["team_rating_components"][0]["sha256"] = "invalid"
    elif fault == "declaration":
        doc["expected_additions"]["team_game_measurements"]["values"][-1] = 999
    elif fault == "publication":
        doc["publications"][b.RATING_RUNS[0]] = []
    else:
        doc["tables"]["team_rating_components"][0]["rows"] = 507
    with pytest.raises(b.BaselineError):
        b.validate_baseline(json.dumps(doc).encode(), lock_raw)


def report_context(captured):
    doc, lock_raw, _ = captured
    raw = json.dumps(doc).encode()
    tables = {
        table: {
            "rows_built": 2,
            "rows_published": 1,
            "unexplained": 0,
            "differences_by_bucket": {},
        }
        for table in [*b.WEEK_COLUMN, "team_season_stats"]
    }
    tables["team_rating_components"]["rows_published"] = 508
    tables["team_rating_components"]["rows_built"] = 784
    tables["team_game_measurements"]["rows_built"] = 115
    report = {
        "tables": tables,
        "kickoff_evidence": {"expected_cutoff_cells": 0},
        "control_baseline_history": {
            "matches_published": True,
            "team_rating_components": {"rows_published": 508},
        },
        "baseline_enforcement": {
            "baseline_sha256": b.hashlib.sha256(raw).hexdigest(),
            "fingerprints_passed": True,
            "capture": doc,
            "populations": {
                table: {
                    "passed": True,
                    "declaration": declaration,
                    "published_rows": tables[table]["rows_published"],
                    "built_rows": tables[table]["rows_built"],
                    "added_rows": tables[table]["rows_built"]
                    - tables[table]["rows_published"],
                }
                for table, declaration in doc["expected_additions"].items()
            },
        },
    }
    context = SimpleNamespace(
        stage=SimpleNamespace(name="published_comparison"),
        plan=SimpleNamespace(run_id="test"),
        read_input={
            "comparison_baseline": raw,
            "source_lock_2026": lock_raw,
        }.__getitem__,
        read_artifact=lambda *_: json.dumps(report).encode(),
    )
    return doc, report, context


def mock_snapshot(monkeypatch, doc):
    from cks_picks_cfb.data import runtime

    monkeypatch.setattr(
        runtime,
        "resolve_runtime_target",
        lambda _: SimpleNamespace(database_url="pipeline-url"),
    )
    calls = []

    def read(url):
        calls.append(url)
        return doc, {}

    monkeypatch.setattr(b, "read_snapshot", read)
    return calls


def test_verify_independently_recaptures_fingerprints(captured, monkeypatch):
    doc, _, context = report_context(captured)
    calls = mock_snapshot(monkeypatch, doc)
    assert pc.verify(context) == []
    assert calls == ["pipeline-url"]


@pytest.mark.parametrize(
    "fault",
    ["absent", "hash", "failed", "population", "current_table", "current_publication"],
)
def test_verify_refuses_missing_evidence_and_fresh_drift(captured, monkeypatch, fault):
    doc, report, context = report_context(captured)
    current = copy.deepcopy(doc)
    mock_snapshot(monkeypatch, current)
    if fault == "absent":
        report.pop("baseline_enforcement")
    elif fault == "hash":
        report["baseline_enforcement"]["baseline_sha256"] = "b" * 64
    elif fault == "failed":
        report["baseline_enforcement"]["fingerprints_passed"] = False
    elif fault == "population":
        report["baseline_enforcement"]["populations"].pop("team_rating_components")
    elif fault == "current_table":
        current["tables"]["team_rating_components"][0]["sha256"] = "c" * 64
    else:
        current["publications"][b.RATING_RUNS[0]][0]["code_sha"] = "different"
    assert pc.verify(context)


def test_cli_uses_pipeline_url_and_never_migrator_fallback(monkeypatch, tmp_path):
    monkeypatch.delenv("PREVIEW_DATABASE_URL", raising=False)
    monkeypatch.setenv("DATABASE_URL", "migrator-url")
    called = []
    monkeypatch.setattr(
        cli, "derive_from_plan", lambda path, url: called.append(url) or ["new"]
    )
    args = [
        "--derive-component-additions",
        "--plan",
        "plan.yaml",
        "--out",
        str(tmp_path / "ids.json"),
    ]
    assert cli.main(args) == 2
    assert called == []
    monkeypatch.setenv("PREVIEW_DATABASE_URL", "pipeline-url")
    assert cli.main(args) == 0
    assert called == ["pipeline-url"]
    assert cli.main(args) == 3  # exclusive create


def test_build_refuses_live_table_or_publication_drift_before_payload(
    captured, monkeypatch
):
    import psycopg

    from cks_picks_cfb.data import runtime
    from cks_picks_cfb.rebuild import targets

    doc, lock_raw, _ = captured
    monkeypatch.setattr(pc, "lock_scope", lambda _: {})
    monkeypatch.setattr(pc, "table_additions", lambda *_: {})
    monkeypatch.setattr(pc, "published_rating_runs", lambda _: {})
    monkeypatch.setattr(
        runtime,
        "resolve_runtime_target",
        lambda _: SimpleNamespace(database_url="pipeline"),
    )
    monkeypatch.setattr(targets, "assert_preview_database", lambda _: None)

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def cursor(self):
            return self

    monkeypatch.setattr(psycopg, "connect", lambda _: Connection())
    called = []
    monkeypatch.setattr(pc, "reconstruct_frames", lambda *_: called.append(True))
    context = SimpleNamespace(
        plan=SimpleNamespace(policies={}),
        read_input={
            "source_lock_2026": lock_raw,
            "comparison_baseline": json.dumps(doc).encode(),
            pc.KICKOFF_EVIDENCE_INPUT: b"{}",
        }.__getitem__,
    )
    for table_drift in (True, False):
        current = copy.deepcopy(doc)
        if table_drift:
            current["tables"]["team_rating_components"][0]["sha256"] = "b" * 64
        else:
            current["publications"][b.RATING_RUNS[0]][0]["code_sha"] = "changed"
        monkeypatch.setattr(b, "capture", lambda _: (current, {}))
        with pytest.raises(GateError, match="baseline drift"):
            pc.build(context)
    assert called == []


def test_build_enforces_actual_declared_additions(captured, monkeypatch):
    import psycopg

    from cks_picks_cfb.data import runtime
    from cks_picks_cfb.rebuild import targets

    doc, lock_raw, _ = captured
    old, extra = components()
    # A new key in the correct week still fails unless its exact ID was declared.
    extra[-1]["component_id"] = "undeclared"
    games = [
        {
            "season": 2026,
            "game_id": game,
            "team": "A",
            "unit_role": "offense",
            "measurement_id": "ppp",
        }
        for game in doc["expected_additions"]["team_game_measurements"]["values"]
    ]
    old_game = {**games[0], "game_id": 999}
    published = {
        "team_rating_components": pd.DataFrame(old),
        "team_game_measurements": pd.DataFrame([old_game]),
        "team_possession_stats": pd.DataFrame(),
        "team_possession_adjusted": pd.DataFrame(),
        "team_season_stats": pd.DataFrame(),
    }
    rebuilt = {
        **published,
        "team_rating_components": pd.DataFrame(old + extra),
        "team_game_measurements": pd.DataFrame([old_game, *games]),
    }
    monkeypatch.setattr(pc, "lock_scope", lambda _: {})
    monkeypatch.setattr(pc, "table_additions", lambda *_: {})
    monkeypatch.setattr(pc, "published_rating_runs", lambda _: {})
    monkeypatch.setattr(pc, "check_published_runs", lambda *_: None)
    monkeypatch.setattr(
        runtime,
        "resolve_runtime_target",
        lambda _: SimpleNamespace(database_url="pipeline"),
    )
    monkeypatch.setattr(targets, "assert_preview_database", lambda _: None)

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def cursor(self):
            return self

        def execute(self, *_):
            pass

        def fetchall(self):
            return []

    monkeypatch.setattr(psycopg, "connect", lambda _: Connection())
    monkeypatch.setattr(b, "capture", lambda _: (doc, {}))
    monkeypatch.setattr(pc, "fetch_table", lambda cur, table, *args: published[table])
    run = SimpleNamespace(storage=None, frame=lambda _: pd.DataFrame())
    monkeypatch.setattr(
        pc, "reconstruct_frames", lambda *_: (rebuilt, None, run, {}, set())
    )
    context = SimpleNamespace(
        plan=SimpleNamespace(policies={}),
        read_input={
            "source_lock_2026": lock_raw,
            "comparison_baseline": json.dumps(doc).encode(),
            pc.KICKOFF_EVIDENCE_INPUT: b"{}",
            "silver_2026_parents": b"{}",
        }.__getitem__,
    )
    with pytest.raises(GateError, match="outside the declaration"):
        pc.build(context)


def test_derive_checks_all_other_stage_pins_without_creating_staging(
    monkeypatch, tmp_path
):
    import psycopg

    from cks_picks_cfb.rebuild import common, inputs, targets
    from cks_picks_cfb.rebuild.plan import RebuildPlan

    plan_path = cli.REPO_ROOT / "conf/rebuild/6a_task4_w6_v2.yaml"
    plan = RebuildPlan.from_dict(__import__("yaml").safe_load(plan_path.read_text()))
    old, extra = components()
    remote_pins = {p.uri: p for p in plan.inputs if p.kind == "r2_object"}
    remote = {uri: json.dumps({"uri": uri}).encode() for uri in remote_pins}
    checked = []
    monkeypatch.setattr(
        common,
        "preview_storage",
        lambda _: SimpleNamespace(read_bytes=remote.__getitem__),
    )

    def resolve(pin, **kwargs):
        checked.append(pin.name)
        assert pin.name != "comparison_baseline"
        if pin.kind == "r2_object":
            object.__setattr__(
                pin, "sha256", b.hashlib.sha256(remote[pin.uri]).hexdigest()
            )

    monkeypatch.setattr(inputs, "resolve_input", resolve)
    monkeypatch.setattr(targets, "assert_preview_database", lambda _: None)
    rollback = []

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def cursor(self):
            return self

        def rollback(self):
            rollback.append(True)

    conn = Connection()
    monkeypatch.setattr(psycopg, "connect", lambda url: conn)
    monkeypatch.setattr(b, "capture", lambda _: ({}, {"team_rating_components": old}))

    def reconstruct(context, cur):
        with pytest.raises(b.BaselineError, match="staged artifacts"):
            context.read_artifact("stage", "file")
        assert set(context.read_input.__self__) == set(checked)
        return (
            {"team_rating_components": pd.DataFrame(old + extra)},
            None,
            None,
            {},
            None,
        )

    monkeypatch.setattr(pc, "reconstruct_frames", reconstruct)
    monkeypatch.setattr(pc, "lock_scope", lambda _: {})
    monkeypatch.setattr(
        pc,
        "table_additions",
        lambda *_: {"team_rating_components": {"first_as_of_week": 7}},
    )
    assert len(cli.derive_from_plan(plan_path, "pipeline")) == 276
    stage = next(s for s in plan.stages if s.name == "published_comparison")
    assert set(checked) == set(stage.inputs) - {"comparison_baseline"}
    assert conn.read_only is True
    assert conn.isolation_level == psycopg.IsolationLevel.REPEATABLE_READ
    assert rollback == [True]


def test_read_snapshot_refuses_a_migrator_identity(monkeypatch):
    import psycopg

    from cks_picks_cfb.rebuild.errors import TargetError

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def cursor(self):
            return self

        def execute(self, *_):
            pass

        def fetchone(self):
            return ("cks_preview_migrator", "cks_preview_migrator", "neondb")

    monkeypatch.setattr(psycopg, "connect", lambda _: Connection())
    with pytest.raises(TargetError, match="cks_preview_pipeline"):
        b.read_snapshot("migrator")


def test_verify_refuses_self_consistent_but_wrong_component_addition_count(
    captured, monkeypatch
):
    doc, report, context = report_context(captured)
    mock_snapshot(monkeypatch, doc)
    report["tables"]["team_rating_components"]["rows_built"] -= 1
    evidence = report["baseline_enforcement"]["populations"]["team_rating_components"]
    evidence["built_rows"] -= 1
    evidence["added_rows"] -= 1
    assert "team_rating_components: population enforcement invalid" in pc.verify(
        context
    )


def test_baseline_refuses_duplicate_fingerprint_groups(captured):
    doc, lock_raw, _ = captured
    groups = doc["tables"]["team_possession_stats"]
    groups.append(copy.deepcopy(groups[0]))
    with pytest.raises(b.BaselineError, match="duplicate baseline fingerprint"):
        b.validate_baseline(json.dumps(doc).encode(), lock_raw)


def test_verify_refuses_duplicate_groups_in_recorded_capture(captured, monkeypatch):
    doc, report, context = report_context(captured)
    mock_snapshot(monkeypatch, doc)
    recorded = copy.deepcopy(doc)
    correct = recorded["tables"]["team_rating_components"][0]
    corrupted = {**correct, "sha256": "b" * 64}
    recorded["tables"]["team_rating_components"] = [corrupted, correct]
    report["baseline_enforcement"]["capture"] = recorded
    assert any(
        "duplicate fingerprint group" in problem for problem in pc.verify(context)
    )


def test_diff_captures_refuses_duplicate_groups_on_either_side(captured):
    doc, _, _ = captured
    corrupt = copy.deepcopy(doc)
    groups = corrupt["tables"]["team_possession_stats"]
    groups.insert(0, {**groups[0], "sha256": "b" * 64})
    for before, after in ((doc, corrupt), (corrupt, doc)):
        with pytest.raises(b.BaselineError, match="duplicate fingerprint group"):
            b.diff_captures(before, after)
