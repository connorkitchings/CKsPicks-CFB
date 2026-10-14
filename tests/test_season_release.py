"""Behavioral tests for invisible staging and atomic all-view activation/rollback."""

import copy
import hashlib
import json
import re

import pytest

from cks_picks_cfb.season import release as r


def encoded(doc):
    return json.dumps(doc, sort_keys=True).encode()


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
        self.policy = (
            "a" * 64,
            "season_workflow_v1",
            "c" * 64,
            True,
            "owner-installed",
        )
        self.columns = {}

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
        elif "information_schema.columns" in query:
            base = values[0].removeprefix("season_release_")
            self.results = [
                (key, "jsonb" if isinstance(value, (dict, list)) else "text")
                for key, value in self.columns[base].items()
            ]
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
        base = re.search(r'INTO "season_release_(\w+)"', query.as_string())[1]
        for value in values:
            row = dict(
                zip(
                    self.columns[base],
                    (getattr(v, "obj", v) for v in value[1:]),
                    strict=True,
                )
            )
            self.projections.setdefault((value[0], base), []).append(row)

    def fetchone(self):
        return self.results[0] if self.results else None

    def fetchall(self):
        return self.results

    def commit(self):
        self.commits += 1


@pytest.fixture
def prepared():
    projections = {base: [] for base in r.PROJECTION_KEYS}
    projections.update(
        {
            "games": [{"game_id": 1, "season": 2026, "week": 0}],
            "game_results": [{"game_id": 1, "home_points": 10, "away_points": 7}],
            "predictions": [{"run_id": "week0", "game_id": 1}],
            "site_week_selections": [{"season": 2026, "week": 0, "run_id": "week0"}],
            "v5_rating_snapshots": [{"snapshot_id": "rating", "season": 2026}],
            "system_stats": [{"season": 2026}],
        }
    )
    raw = encoded(projections)
    manifest = {
        "schema_version": "season_run_v1",
        "release_id": "candidate",
        "season": 2026,
        "active_week": 0,
        "model_manifest_sha256": "a" * 64,
        "revision_manifest_sha256": "b" * 64,
        "workflow_version": "season_workflow_v1",
        "grading_policy_sha256": "c" * 64,
        "code_sha": "d" * 40,
        "config_sha": "e" * 64,
        "verification_uri": "verify.json",
        "output_refs": {
            "serving_projections": {
                "uri": "projections.json",
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        },
    }
    verification = {
        "state": "passed",
        "identity": {key: manifest[key] for key in r.IDENTITY_FIELDS},
        "checks": {"complete": True},
        "output_refs": manifest["output_refs"],
    }
    verification_raw = encoded(verification)
    manifest["verification_sha256"] = hashlib.sha256(verification_raw).hexdigest()
    return manifest, verification_raw, raw, projections


def stage(db, prepared, label="candidate"):
    manifest, verification, projections, rows = prepared
    manifest = {**manifest, "release_id": label}
    db.columns = {
        base: row[0] if row else {key: None for key in keys}
        for base, keys in r.PROJECTION_KEYS.items()
        for row in [rows[base]]
    }
    return r.stage_release(
        db,
        manifest_raw=encoded(manifest),
        run_manifest_uri="run.json",
        verification_raw=verification,
        projection_raw=projections,
        environment=db.environment,
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


def test_staging_invisible_and_identical_retry_writes_no_rows(prepared):
    db = Database()
    release_id = stage(db, prepared)
    assert db.rows[release_id]["status"] == "staged"
    before = copy.deepcopy(db.projections)
    assert stage(db, prepared) == release_id
    assert db.projections == before
    assert not db.history
    assert db.commits == 0


def test_activation_readback_and_owner_rollback_restore_all_views(prepared):
    db = Database()
    old = stage(db, prepared, "old")
    activate(db, old)
    original = copy.deepcopy(
        {base: rows for (rid, base), rows in db.projections.items() if rid == old}
    )
    new = stage(db, prepared, "new")
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
def test_activation_refuses_without_changing_pointer(prepared, fault):
    db = Database()
    candidate = stage(db, prepared)
    if fault == "prior":
        kwargs = {"expected_previous_release_id": "other"}
    else:
        kwargs = {"expected_previous_release_id": None}
    if fault == "environment":
        db.rows[candidate]["environment"] = "production"
    elif fault == "policy":
        db.policy = (*db.policy[:3], False, db.policy[-1])
    elif fault == "readback":
        db.projections[(candidate, "games")][0]["game_id"] = 999
    elif fault == "role":
        db.role = "cks_prod_pipeline"
    with pytest.raises(ValueError):
        r.activate_release(
            db, environment="preview", season=2026, release_id=candidate, **kwargs
        )
    assert db.rows[candidate]["status"] == "staged"
    assert not db.history


def test_production_requires_matching_independent_preview_rehearsal(prepared):
    prod = Database("production")
    candidate = stage(prod, prepared)
    with pytest.raises(r.SeasonReleaseError, match="Preview rehearsal"):
        activate(prod, candidate)
    preview = Database()
    preview_id = stage(preview, prepared)
    activate(preview, preview_id)
    preview.read_only = True
    assert activate(prod, candidate, preview_conn=preview)["release_id"] == candidate


def test_production_refuses_preview_with_different_view_content(prepared):
    prod, preview = Database("production"), Database()
    candidate = stage(prod, prepared)
    preview_id = stage(preview, prepared)
    activate(preview, preview_id)
    preview.read_only = True
    preview.projections[(preview_id, "game_results")][0]["home_points"] = 999
    with pytest.raises(r.SeasonReleaseError, match="readback"):
        activate(prod, candidate, preview_conn=preview)
    assert prod.rows[candidate]["status"] == "staged"


@pytest.mark.parametrize("authorized,owner", [(False, True), (True, False)])
def test_rollback_requires_owner_approval_and_privilege(prepared, authorized, owner):
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


@pytest.mark.parametrize(
    "fault",
    [
        "verification_hash",
        "projection_hash",
        "verification_identity",
        "failed_check",
        "missing_projection",
        "duplicate",
        "foreign_scope",
        "missing_predictions",
        "missing_final",
    ],
)
def test_stage_refuses_unverified_or_incomplete_candidate(prepared, fault):
    manifest, verifyraw, raw, projections = copy.deepcopy(prepared)
    db = Database()
    if fault == "verification_hash":
        verifyraw += b"\n"
    elif fault == "projection_hash":
        raw += b"\n"
    elif fault in {"verification_identity", "failed_check"}:
        verification = json.loads(verifyraw)
        if fault == "verification_identity":
            verification["identity"]["code_sha"] = "changed"
        else:
            verification["checks"]["complete"] = False
        verifyraw = encoded(verification)
        manifest["verification_sha256"] = hashlib.sha256(verifyraw).hexdigest()
    else:
        if fault == "missing_projection":
            projections.pop("market_quotes")
        elif fault == "duplicate":
            projections["games"].append(copy.deepcopy(projections["games"][0]))
        elif fault == "foreign_scope":
            projections["games"][0]["season"] = 2025
        elif fault == "missing_predictions":
            projections["predictions"] = []
        else:
            projections["game_results"][0]["home_points"] = None
        raw = encoded(projections)
        manifest["output_refs"]["serving_projections"]["sha256"] = hashlib.sha256(
            raw
        ).hexdigest()
        verification = json.loads(verifyraw)
        verification["output_refs"] = manifest["output_refs"]
        verifyraw = encoded(verification)
        manifest["verification_sha256"] = hashlib.sha256(verifyraw).hexdigest()
    with pytest.raises(r.SeasonReleaseError):
        r.stage_release(
            db,
            manifest_raw=encoded(manifest),
            run_manifest_uri="run.json",
            verification_raw=verifyraw,
            projection_raw=raw,
            environment="preview",
        )
    assert not db.rows


def test_timestamp_normalization_and_environment_metadata_are_stable():
    first = [{"cutoff_utc": "2026-10-14T01:00:00Z", "environment": "preview"}]
    second = [{"cutoff_utc": "2026-10-13T21:00:00-04:00", "environment": "production"}]
    assert r.projection_check(first) == r.projection_check(second)
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


def test_autocommit_cannot_partially_stage_or_activate(prepared):
    db = Database()
    db.autocommit = True
    with pytest.raises(r.SeasonReleaseError, match="transaction"):
        stage(db, prepared)
    with pytest.raises(r.SeasonReleaseError, match="transaction"):
        activate(db, "candidate")
    assert not db.rows and not db.history
