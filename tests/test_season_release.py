"""Behavioral tests for invisible staging and atomic all-view activation/rollback.

Candidates are sealed by ``tests.season_candidates`` and pass the REAL
``verification.derive_checks`` / ``validate_report``; only the database is faked.
"""

import copy
import json
import re

import pytest

from cks_picks_cfb.season import release as r
from cks_picks_cfb.season.manifest import canonical, sha
from cks_picks_cfb.season.projection_common import CHART_TABLES as CHART_V1_TABLES
from cks_picks_cfb.season.projection_common import (
    PROJECTION_SETS,
    recognized_projection_set,
)
from tests.season_candidates import (
    POLICY,
    candidate,
    manifest_uri,
    payload_for,
    seal,
)
from tests.test_season_verification import REVISION_RAW


class Database:
    def __init__(self, environment="preview", owner=False):
        self.environment = environment
        self.owner = owner
        self.role = (
            "cks_preview_migrator"
            if owner
            else f"cks_{'prod' if environment == 'production' else 'preview'}_pipeline"
        )
        self.rows = {}
        self.projections = {}
        self.history = []
        self.results = []
        self.statements = []
        self.read_only = False
        self.commits = 0
        self.policy = (*POLICY.values(), True, "owner-installed")
        self.columns = {}
        self.run_columns = {}
        self.registry = {}

    def cursor(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def execute(self, query, values=()):
        query = query if isinstance(query, str) else query.as_string()
        self.statements.append(query)
        self.results = []
        if "has_table_privilege" in query:
            self.results = [(self.role, self.role, self.owner)]
        elif query == "SELECT session_user, current_user":
            self.results = [(self.role, self.role)]
        elif "pg_advisory" in query:
            pass
        elif "table_name = 'prediction_runs'" in query:
            self.results = list(self.run_columns.items())
        elif "FROM prediction_runs WHERE run_id" in query:
            row = self.registry.get(values[0])
            self.results = [tuple(row[k] for k in self.run_columns)] if row else []
        elif query.startswith("INSERT INTO prediction_runs"):
            row = dict(zip(self.run_columns, values, strict=True))
            self.registry[row["run_id"]] = {
                k: getattr(value, "obj", value) for k, value in row.items()
            }
        elif "information_schema.columns" in query:
            base = values[0].removeprefix("season_release_")
            server = ["release_id"] + (
                ["environment"] if base == "matchup_data_publications" else []
            )
            self.results = [(key, "text") for key in server] + [
                (key, "jsonb" if isinstance(value, (dict, list)) else "text")
                for key, value in self.columns[base].items()
            ]
        elif query == "SET CONSTRAINTS ALL IMMEDIATE":
            pass
        elif "environment IS DISTINCT FROM" in query:
            base = re.search(r'FROM "season_release_(\w+)"', query)[1]
            rows = self.projections.get((values[0], base), [])
            self.results = [(sum(row["environment"] != values[1] for row in rows),)]
        elif "current_setting('default_transaction_read_only')" in query:
            self.results = [("on", "on") if self.read_only else ("off", "off")]
        elif query.startswith("SELECT activate_season_release"):
            release_id, previous, digest = values
            row = self.rows[release_id]
            if previous:
                self.rows[previous]["status"] = "superseded"
            row["status"] = "active"
            self.history.append(
                (row["environment"], row["season"], previous, release_id)
                + ("activate", self.policy[-1], digest)
            )
            self.results = [(previous,)]
        elif query.startswith("INSERT INTO season_release_history"):
            self.history.append(values)
        elif query.startswith("INSERT INTO season_releases") or query.startswith(
            'INSERT INTO "season_releases"'
        ):
            self.rows[values[0]] = {
                **dict(
                    zip(
                        r.RELEASE_COLUMNS,
                        (getattr(v, "obj", v) for v in values),
                        strict=True,
                    )
                ),
                "status": "staged",
            }
        elif query.startswith("UPDATE season_releases SET status = 'rolled_back'"):
            self.rows[values[0]]["status"] = "rolled_back"
        elif query.startswith("UPDATE season_releases SET status = 'active'"):
            self.rows[values[0]]["status"] = "active"
        elif query.startswith(
            "SELECT release_id FROM season_releases WHERE release_id"
        ):
            if values[0] in self.rows:
                self.results = [(values[0],)]
        elif "FROM season_releases" in query and "status = 'active'" in query:
            self.results = [
                (key,)
                for key, row in self.rows.items()
                if row["environment"] == values[0]
                and row["season"] == values[1]
                and row["status"] == "active"
            ]
        elif "FROM season_release_policies" in query:
            self.results = [self.policy]
        elif query.startswith("SELECT projection_checks"):
            self.results = [(self.rows[values[0]]["projection_checks"],)]
        elif query.startswith("SELECT readback_sha256"):
            self.results = [
                (h[-1],)
                for h in self.history
                if h[3] == values[0] and h[4] == "activate"
            ]
        elif query.startswith(
            "SELECT release_id FROM season_releases WHERE environment = 'preview'"
        ):
            fields = (
                "season",
                "model_manifest_sha256",
                "revision_manifest_sha256",
                "workflow_version",
                "grading_policy_sha256",
                "code_sha",
                "config_sha",
                "active_week",
            )
            self.results = [
                (key,)
                for key, row in self.rows.items()
                if row["environment"] == "preview"
                and tuple(row[f] for f in fields) == values
            ]
        elif "FROM season_releases WHERE release_id" in query:
            row = self.rows.get(values[0])
            self.results = (
                [tuple(row[k] for k in (*r.RELEASE_COLUMNS, "status"))] if row else []
            )
        elif match := re.search(r'FROM "season_release_(\w+)"', query):
            base = match[1]
            self.results = [
                tuple(row[k] for k in self.columns[base])
                for row in self.projections.get((values[0], base), [])
            ]
        else:
            raise AssertionError(query)

    def executemany(self, query, values):
        match = re.search(
            r'INTO "season_release_(\w+)" \((.*?)\) VALUES', query.as_string()
        )
        base, names = match[1], re.findall(r'"(\w+)"', match[2])
        for value in values:
            row = dict(
                zip(names, (getattr(item, "obj", item) for item in value), strict=True)
            )
            release_id = row.pop("release_id")
            self.projections.setdefault((release_id, base), []).append(row)

    def fetchone(self):
        return self.results[0] if self.results else None

    def fetchall(self):
        return self.results

    def commit(self):
        self.commits += 1


def _types(row: dict) -> dict:
    return {
        k: "jsonb" if isinstance(v, (dict, list)) else "text" for k, v in row.items()
    }


def schema_for(db, payload):
    """Teach the fake database the 0025 columns of ``payload``'s tables."""
    db.columns = {
        base: _types(rows[0]) if rows else {key: "text" for key in keys}
        for base, keys in r.PROJECTION_KEYS.items()
        for rows in [payload[base]]
    }
    db.run_columns = _types(payload["prediction_runs"][0])


def stage(db, label="candidate", sealed=None):
    sealed = sealed or candidate(label)
    schema_for(db, json.loads(sealed["projection_raw"]))
    return r.stage_release(
        db,
        run_manifest_uri=manifest_uri(sealed),
        environment=db.environment,
        **sealed,
    )


def activate(db, release_id, previous=None, **kwargs):
    return r.activate_release(
        db,
        environment=db.environment,
        season=2026,
        release_id=release_id,
        expected_previous_release_id=previous,
        **kwargs,
    )


def test_staging_invisible_and_identical_retry_writes_no_rows():
    db = Database()
    release_id = stage(db)
    assert db.rows[release_id]["status"] == "staged"
    assert len(db.registry) == 3  # weeks 0..active_week registered once
    before = copy.deepcopy((db.projections, db.registry))
    assert stage(db) == release_id
    assert (db.projections, db.registry) == before
    assert not db.history
    assert db.commits == 0


def test_staged_release_records_logical_uris_only():
    db = Database()
    sealed = candidate("candidate")
    release_id = stage(db, sealed=sealed)
    manifest = json.loads(sealed["manifest_raw"])
    row = db.rows[release_id]
    assert row["run_manifest_uri"] == manifest["run_manifest_logical_uri"]
    assert row["verification_uri"] == manifest["verification_logical_uri"]
    assert not any(
        row[k].startswith("/") for k in ("run_manifest_uri", "verification_uri")
    )


def test_activation_readback_and_owner_rollback_restore_all_views():
    db = Database()
    old = stage(db, "old")
    activate(db, old)
    original = copy.deepcopy(
        {base: rows for (rid, base), rows in db.projections.items() if rid == old}
    )
    new = stage(db, "new")
    receipt = activate(db, new, old)
    assert receipt["prior_release_id"] == old
    assert db.rows[old]["status"] == "superseded"
    db.owner = True
    db.role = "cks_preview_migrator"
    rolled = r.rollback_release(
        db,
        environment="preview",
        season=2026,
        release_id=old,
        expected_previous_release_id=new,
        owner_authorized=True,
        decision_ref="owner rollback",
    )
    assert rolled["action"] == "rollback"
    assert db.rows[new]["status"] == "rolled_back"
    assert db.rows[old]["status"] == "active"
    assert {
        base: rows for (rid, base), rows in db.projections.items() if rid == old
    } == original
    assert len(db.history) == 3
    assert db.commits == 0


@pytest.mark.parametrize(
    "fault", ["prior", "environment", "policy", "readback", "role"]
)
def test_activation_refuses_without_changing_pointer(fault):
    db = Database()
    staged = stage(db)
    if fault == "prior":
        kwargs = {"expected_previous_release_id": "other"}
    else:
        kwargs = {"expected_previous_release_id": None}
    if fault == "environment":
        db.rows[staged]["environment"] = "production"
    elif fault == "policy":
        db.policy = (*db.policy[:3], False, db.policy[-1])
    elif fault == "readback":
        db.projections[(staged, "games")][0]["game_id"] = 999
    elif fault == "role":
        db.role = "cks_prod_pipeline"
    with pytest.raises(ValueError):
        r.activate_release(
            db, environment="preview", season=2026, release_id=staged, **kwargs
        )
    assert db.rows[staged]["status"] == "staged"
    assert not db.history


def test_production_requires_matching_independent_preview_rehearsal():
    prod = Database("production")
    staged = stage(prod)
    with pytest.raises(r.SeasonReleaseError, match="Preview rehearsal"):
        activate(prod, staged)
    preview = Database()
    preview_id = stage(preview)
    activate(preview, preview_id)
    preview.read_only = True
    assert activate(prod, staged, preview_conn=preview)["release_id"] == staged


def test_production_refuses_preview_with_different_view_content():
    prod, preview = Database("production"), Database()
    staged = stage(prod)
    preview_id = stage(preview)
    activate(preview, preview_id)
    preview.read_only = True
    preview.projections[(preview_id, "game_results")][0]["home_points"] = 999
    with pytest.raises(r.SeasonReleaseError, match="readback"):
        activate(prod, staged, preview_conn=preview)
    assert prod.rows[staged]["status"] == "staged"


@pytest.mark.parametrize("authorized,owner", [(False, True), (True, False)])
def test_rollback_requires_owner_approval_and_privilege(authorized, owner):
    db = Database(owner=owner)
    with pytest.raises(r.SeasonReleaseError, match="owner"):
        r.rollback_release(
            db,
            environment="preview",
            season=2026,
            release_id="old",
            expected_previous_release_id="new",
            owner_authorized=authorized,
            decision_ref="decision",
        )
    assert not db.history


def _fail_check(report):
    report["checks"]["paired_predictions"]["passed"] = False


def _edit_manifest(sealed, **changes):
    manifest = json.loads(sealed["manifest_raw"])
    for key, value in changes.items():
        if value is None:
            manifest.pop(key)
        else:
            manifest[key] = value
    sealed["manifest_raw"] = canonical(manifest)


PAYLOAD_FAULTS = {
    "duplicate": lambda p: p["games"].append(copy.deepcopy(p["games"][0])),
    "foreign_scope": lambda p: p["games"][0].update(season=2025),
    "prediction_outside_schedule": lambda p: p["predictions"].append(
        {**p["predictions"][0], "game_id": 99}
    ),
    "environment_key": lambda p: p["games"][0].update(environment="preview"),
    "release_id_key": lambda p: p["system_stats"][0].update(release_id="preview-x"),
    "missing_final": lambda p: p["game_results"][0].update(home_points=None),
    # Passes the scope check; only the re-derived verification refuses it.
    "wrong_grade": lambda p: p["prediction_grades"][0].update(result="loss"),
}


@pytest.mark.parametrize(
    "fault",
    [
        "verification_hash",
        "projection_hash",
        "verification_schema",
        "failed_check",
        "local_run_manifest_uri",
        "missing_logical_uri",
        "missing_identities",
        "identity_differs",
        "missing_projection",
        *PAYLOAD_FAULTS,
    ],
)
def test_stage_refuses_unverified_or_incomplete_candidate(fault):
    sealed = candidate("candidate")
    uri = manifest_uri(sealed)
    if fault == "verification_hash":
        sealed["verification_raw"] += b"\n"
    elif fault == "projection_hash":
        sealed["projection_raw"] += b"\n"
    elif fault == "verification_schema":
        sealed = candidate(
            edit_report=lambda doc: doc.update(schema_version="season_verification_v1")
        )
    elif fault == "failed_check":
        sealed = candidate(edit_report=_fail_check)
    elif fault == "local_run_manifest_uri":
        uri = "/Users/me/prepared/run-manifest.json"
    elif fault == "missing_logical_uri":
        _edit_manifest(sealed, verification_logical_uri=None)
    elif fault == "missing_identities":
        _edit_manifest(sealed, identities=None)
    elif fault == "identity_differs":
        _edit_manifest(sealed, code_sha="b" * 40)
    elif fault == "missing_projection":
        payload = payload_for("candidate")
        payload.pop("market_quotes")
        sealed = seal("candidate", payload, reported_payload=payload_for("candidate"))
    else:
        sealed = candidate(edit_payload=PAYLOAD_FAULTS[fault])
    db = Database()
    schema_for(db, payload_for("candidate"))
    with pytest.raises(r.SeasonReleaseError):
        r.stage_release(
            db,
            run_manifest_uri=uri,
            environment="preview",
            **sealed,
        )
    assert not db.rows and not db.registry


def test_full_schedule_stages_games_without_predictions():
    def later_game(payload):
        game = next(g for g in payload["games"] if g["week"] == 3)
        payload["games"].append({**game, "game_id": 6, "week": 4})

    db = Database()
    release_id = stage(db, sealed=candidate("candidate", edit_payload=later_game))

    games = db.projections[(release_id, "games")]
    assert len(games) == 6 and sum(g["predicted_spread"] is None for g in games) == 2


def _candidate_args(label="candidate"):
    sealed = candidate(label)
    return (
        json.loads(sealed["manifest_raw"]),
        json.loads(sealed["verification_raw"]),
        json.loads(sealed["projection_raw"]),
    )


def test_validate_candidate_passes_with_real_rederived_report():
    manifest, report, payload = _candidate_args()

    r.validate_candidate(manifest, report, payload, revision_raw=REVISION_RAW)


def _stale_report_for_changed_payload(manifest, report, payload):
    """A report honestly derived for one payload, presented with another."""
    payload["prediction_market_selections"][0]["price"] = -105.0


@pytest.mark.parametrize(
    "forgery",
    ["derived-failure", "extra-check", "missing-check", "bare-boolean", "observed"],
)
def test_validate_candidate_refuses_forged_checks(forgery):
    manifest, report, payload = _candidate_args()
    if forgery == "derived-failure":
        _stale_report_for_changed_payload(manifest, report, payload)
    elif forgery == "extra-check":
        report["checks"]["self_declared"] = {
            "passed": True,
            "observed": {},
            "source": "prepare",
        }
    elif forgery == "missing-check":
        report["checks"].pop("market_links")
    elif forgery == "bare-boolean":
        report["checks"]["market_links"] = True
    else:
        report["checks"]["market_links"]["observed"]["quotes"] = 99

    with pytest.raises(r.SeasonReleaseError, match="check"):
        r.validate_candidate(manifest, report, payload, revision_raw=REVISION_RAW)


@pytest.mark.parametrize("field", ["projection_checks", "row_counts"])
def test_validate_candidate_refuses_report_for_other_payload(field):
    manifest, report, payload = _candidate_args()
    report[field]["games"] = {"rows": 9, "sha256": "0" * 64} if field[0] == "p" else 9

    with pytest.raises(r.SeasonReleaseError, match="differ from payload"):
        r.validate_candidate(manifest, report, payload, revision_raw=REVISION_RAW)


def test_validate_candidate_binds_report_to_the_run_manifest():
    manifest, report, payload = _candidate_args()
    other, _, _ = _candidate_args("other")

    with pytest.raises(r.SeasonReleaseError, match="identity differs from manifest"):
        r.validate_candidate(
            {**other, "output_refs": manifest["output_refs"]},
            report,
            payload,
            revision_raw=REVISION_RAW,
        )


def test_validate_candidate_wraps_verification_rejection():
    manifest, report, payload = _candidate_args()

    def reject(doc, *, projections, manifest):
        raise ValueError("row counts differ")

    with pytest.raises(r.SeasonReleaseError, match="row counts differ"):
        r.validate_candidate(
            manifest, report, payload, revision_raw=REVISION_RAW, validate=reject
        )


def test_timestamp_normalization_and_server_columns_are_excluded():
    first = [
        {
            "cutoff_utc": "2026-10-14T01:00:00Z",
            "environment": "preview",
            "release_id": "preview-r1",
        }
    ]
    second = [
        {
            "cutoff_utc": "2026-10-13T21:00:00-04:00",
            "environment": "production",
            "release_id": "production-r1",
        }
    ]
    payload = [{"cutoff_utc": "2026-10-14T01:00:00Z"}]
    assert r.projection_check(first) == r.projection_check(second)
    assert r.projection_check(first) == r.projection_check(payload)
    with pytest.raises(r.SeasonReleaseError, match="naive"):
        r.projection_check([{"cutoff_utc": "2026-10-14T01:00:00"}])


def test_full_row_digest_handles_postgres_numeric_and_timestamp_adaptation():
    from datetime import datetime, timezone
    from decimal import Decimal

    expected = [
        {"as_of_cutoff": "2026-10-14T01:00:00Z", "value": 2, "profit_units": "1.0000"}
    ]
    stored = [
        {
            "as_of_cutoff": datetime(2026, 10, 14, 1, tzinfo=timezone.utc),
            "value": 2.0,
            "profit_units": Decimal("1.0000"),
        }
    ]
    assert r.projection_check(expected) == r.projection_check(stored)
    with pytest.raises(r.SeasonReleaseError, match="nonfinite"):
        r.projection_check([{"value": float("nan")}])


def test_additive_schema_projects_all_legacy_columns_and_has_one_active_pointer():
    from pathlib import Path

    from contracts.validation import extract_sql_table_columns

    root = Path(__file__).resolve().parents[1]
    tables = extract_sql_table_columns(root / "contracts/schema.sql")
    for base in r.PROJECTION_KEYS:
        expected = tables[base] | {"release_id"}
        if base == "game_results":
            expected.add("source_dataset_version_id")
        assert tables["season_release_" + base] == expected
    sql = (root / "contracts/migrations/0025_season_releases.sql").read_text()
    assert "ON season_releases (environment, season) WHERE status = 'active'" in sql
    assert (
        "REVOKE ALL ON season_release_policies FROM PUBLIC, cks_pipeline, cks_web"
        in sql
    )
    assert "GRANT UPDATE" not in sql
    assert "SECURITY DEFINER SET search_path = pg_catalog, public" in sql
    assert (
        "GRANT EXECUTE ON FUNCTION activate_season_release(TEXT, TEXT, TEXT) TO cks_pipeline;"
        in sql
    )
    assert "pipeline may not roll back releases" in sql
    assert "CREATE TABLE IF NOT EXISTS season_release_pointer" not in sql


def test_registered_run_collision_preserves_existing_row():
    class RegistryCursor:
        def execute(self, query, params=()):
            self.query = query if isinstance(query, str) else query.as_string()

        def fetchall(self):
            return [
                (k, "text")
                for k in ("run_id", "season", "state", "frozen_at", "artifact_sha256")
            ]

        def fetchone(self):
            return ("week0", 2026, "scored", None, "a" * 64)

    cursor = RegistryCursor()
    row = {
        "run_id": "week0",
        "season": 2026,
        "state": "published",
        "frozen_at": None,
        "artifact_sha256": "a" * 64,
    }
    r._register_runs(cursor, [row], 2026)
    assert cursor.query.startswith("SELECT")
    with pytest.raises(r.SeasonReleaseError, match="collision"):
        r._register_runs(cursor, [{**row, "artifact_sha256": "b" * 64}], 2026)
    with pytest.raises(r.SeasonReleaseError, match="freeze"):
        r._register_runs(cursor, [{**row, "frozen_at": "2026-10-14T00:00:00Z"}], 2026)


def test_autocommit_cannot_partially_stage_or_activate():
    db = Database()
    db.autocommit = True
    with pytest.raises(r.SeasonReleaseError, match="transaction"):
        stage(db)
    with pytest.raises(r.SeasonReleaseError, match="transaction"):
        activate(db, "candidate")
    assert not db.rows and not db.history


def _prepared_run(tmp_path):
    """A manifest whose output refs and verification live on disk."""
    files = {
        "serving_projections": b'{"games":[]}',
        "ratings": b"ratings",
        "verification": b'{"schema_version":"season_verification_v2"}',
    }
    for name, raw in files.items():
        (tmp_path / name).write_bytes(raw)
    refs = {
        name: {"uri": str(tmp_path / name), "sha256": sha(raw), "rows": 1}
        for name, raw in files.items()
        if name != "verification"
    }
    manifest = {
        "output_refs": refs,
        "verification_uri": str(tmp_path / "verification"),
        "verification_sha256": sha(files["verification"]),
    }
    return manifest, files


def test_release_reads_payload_from_manifest_ref_after_rehashing_outputs(tmp_path):
    from scripts.pipeline.run_season import _sealed_candidate

    manifest, files = _prepared_run(tmp_path)
    pinned = manifest["output_refs"]["serving_projections"]["sha256"]

    assert _sealed_candidate(manifest, pinned) == (
        files["serving_projections"],
        files["verification"],
    )


@pytest.mark.parametrize("fault", ["pin", "other-output", "payload", "verification"])
def test_release_refuses_unpinned_or_changed_prepared_outputs(tmp_path, fault):
    from scripts.pipeline.run_season import _sealed_candidate

    manifest, _ = _prepared_run(tmp_path)
    pinned = manifest["output_refs"]["serving_projections"]["sha256"]
    if fault == "pin":
        pinned = "0" * 64
    elif fault == "other-output":
        (tmp_path / "ratings").write_bytes(b"changed")
    elif fault == "payload":
        (tmp_path / "serving_projections").write_bytes(b"{}")
    else:
        (tmp_path / "verification").write_bytes(b"{}")

    with pytest.raises(ValueError, match="checksum"):
        _sealed_candidate(manifest, pinned)


# ---------------------------------------------------------------- projection sets


def retained_release(db, label, projection_set):
    """Turn a staged charts_v2 release into a retained one of an older set."""
    release_id = stage(db, label)
    dropped = set(PROJECTION_SETS["charts_v2"]) - set(PROJECTION_SETS[projection_set])
    for table in dropped:
        db.projections.pop((release_id, table), None)
        del db.rows[release_id]["projection_checks"][table]
    return release_id


def retained_core_release(db, label="core"):
    """A retained core_v1 release (18 tables)."""
    return retained_release(db, label, "core_v1")


def test_staging_requires_charts_v2_and_records_its_checks():
    db = Database()
    release_id = stage(db)
    checks = db.rows[release_id]["projection_checks"]
    assert set(checks) == set(PROJECTION_SETS["charts_v2"])
    assert recognized_projection_set(checks) == "charts_v2"
    assert db.projections[(release_id, "team_game_yardage")]
    with db.cursor() as cur:
        assert r._readback(cur, release_id, checks, "preview") == checks
    assert activate(db, release_id)["release_id"] == release_id


def test_charts_v1_set_is_frozen_and_charts_v2_only_adds_yardage():
    v1, v2 = PROJECTION_SETS["charts_v1"], PROJECTION_SETS["charts_v2"]
    assert v1 == (*PROJECTION_SETS["core_v1"], *CHART_V1_TABLES)
    assert v2 == (*v1, "team_game_yardage")


def test_retained_charts_v1_release_reads_back_activates_and_rolls_back():
    db = Database()
    old = retained_release(db, "old-charts", "charts_v1")
    checks = db.rows[old]["projection_checks"]
    assert recognized_projection_set(checks) == "charts_v1"
    with db.cursor() as cur:
        assert r._readback(cur, old, checks, "preview") == checks
    activate(db, old)
    new = stage(db, "new")
    activate(db, new, old)
    db.owner = True
    db.role = "cks_preview_migrator"
    receipt = r.rollback_release(
        db,
        environment="preview",
        season=2026,
        release_id=old,
        expected_previous_release_id=new,
        owner_authorized=True,
        decision_ref="owner rollback",
    )
    assert receipt["action"] == "rollback"
    assert db.rows[old]["status"] == "active"
    assert not any(
        base == "team_game_yardage" for rid, base in db.projections if rid == old
    )


def test_retained_core_v1_release_reads_back_and_activates_by_its_recorded_set():
    db = Database()
    release_id = retained_core_release(db)
    checks = db.rows[release_id]["projection_checks"]
    assert recognized_projection_set(checks) == "core_v1"
    with db.cursor() as cur:
        assert r._readback(cur, release_id, checks, "preview") == checks
    assert activate(db, release_id)["release_id"] == release_id


def test_retained_core_v1_release_survives_owner_rollback():
    db = Database()
    old = retained_core_release(db, "old")
    activate(db, old)
    new = stage(db, "new")
    activate(db, new, old)
    db.owner = True
    db.role = "cks_preview_migrator"
    receipt = r.rollback_release(
        db,
        environment="preview",
        season=2026,
        release_id=old,
        expected_previous_release_id=new,
        owner_authorized=True,
        decision_ref="owner rollback",
    )
    assert receipt["action"] == "rollback"
    assert db.rows[old]["status"] == "active"


def test_readback_compares_only_the_recorded_set_and_detects_drift_in_it():
    db = Database()
    release_id = retained_core_release(db)
    checks = db.rows[release_id]["projection_checks"]
    db.projections[(release_id, "games")][0]["game_id"] = 999
    with db.cursor() as cur, pytest.raises(r.SeasonReleaseError, match="differs"):
        r._readback(cur, release_id, checks, "preview")


@pytest.mark.parametrize("drop", ["games", "team_adjusted_epa"])
def test_partial_and_unknown_recorded_sets_fail_readback(drop):
    db = Database()
    release_id = stage(db)
    checks = dict(db.rows[release_id]["projection_checks"])
    del checks[drop]
    with db.cursor() as cur, pytest.raises(r.SeasonReleaseError, match="required"):
        r._readback(cur, release_id, checks, "preview")
    checks = {**db.rows[release_id]["projection_checks"], "extra_table": {}}
    with db.cursor() as cur, pytest.raises(r.SeasonReleaseError, match="required"):
        r._readback(cur, release_id, checks, "preview")


@pytest.mark.parametrize("projection_set", ["core_v1", "charts_v1"])
def test_older_set_candidates_are_refused_at_staging(projection_set):
    db = Database()
    full = payload_for("old-candidate")
    kept = {"prediction_runs", *PROJECTION_SETS[projection_set]}
    older = {k: v for k, v in full.items() if k in kept}
    sealed = seal("old-candidate", older, reported_payload=full)
    schema_for(db, full)
    with pytest.raises(r.SeasonReleaseError, match=f"{projection_set} candidates"):
        r.stage_release(
            db,
            run_manifest_uri=manifest_uri(sealed),
            environment="preview",
            **sealed,
        )
    assert not db.rows and not db.projections


def test_partial_set_candidates_are_refused_at_staging():
    db = Database()
    full = payload_for("partial")
    partial = {k: v for k, v in full.items() if k != "team_adjusted_epa"}
    sealed = seal("partial", partial, reported_payload=full)
    schema_for(db, full)
    with pytest.raises(r.SeasonReleaseError, match="complete fixed"):
        r.stage_release(
            db, run_manifest_uri=manifest_uri(sealed), environment="preview", **sealed
        )


def test_candidate_without_the_chart_reconciliation_check_is_refused():
    def drop_check(report):
        del report["checks"]["team_chart_reconciliation"]

    db = Database()
    sealed = candidate("no-chart-check", edit_report=drop_check)
    with pytest.raises(r.SeasonReleaseError, match="checks missing"):
        stage(db, sealed=sealed)


def test_candidate_with_a_failed_chart_check_is_refused():
    def fail(payload):
        payload["team_game_stats"].pop()

    db = Database()
    sealed = candidate("bad-chart", edit_payload=fail)
    with pytest.raises(ValueError):
        stage(db, sealed=sealed)
