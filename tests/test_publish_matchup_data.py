"""Matchup data publish path: artifact verification, gates, stale keys, conflicts, writes."""

from __future__ import annotations

import io
import json
import os
from pathlib import Path

import pandas as pd
import psycopg
import pytest
from test_matchup_data import (
    ALIAS,
    CUTOFFS,
    _roles_fixture,
    world,
)

from cks_picks_cfb.data import matchup_data as md
from cks_picks_cfb.data import matchup_publish as mp
from cks_picks_cfb.data.data_first_phase2d import signed_payload
from cks_picks_cfb.db.migrations import apply_migrations
from cks_picks_cfb.ratings.possession_intended_update import CANDIDATE_ID

GAMES = {"Alpha", "Beta", "Hawai'i"}


class MemoryStorage:
    def __init__(self):
        self.objects: dict[str, bytes] = {}

    def put(self, path, data: bytes):
        self.objects[path] = data

    def read_bytes(self, path):
        return self.objects[path]


def parquet(frame: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    frame.to_parquet(buffer)
    return buffer.getvalue()


def sha(raw: bytes) -> str:
    return mp._sha(raw)


def make_store(monkeypatch, *, tamper=None):
    """A tiny but fully signed artifact set mirroring the real layout."""
    prepared, _ = world()
    observations = prepared[list(mp.md._OBS_REQUIRED)].copy()
    observations["kickoff_utc"] = observations["kickoff_utc"].astype(str)
    priors, pregame, current = _roles_fixture(prepared)
    store = MemoryStorage()
    base = "art/intended"
    refs = {}
    for name, frame in (
        ("priors", priors),
        ("pregame_roles", pregame),
        ("current_roles", current),
    ):
        raw = parquet(frame)
        store.put(f"{base}/{name}.parquet", raw)
        refs[name] = {
            "uri": f"{base}/{name}.parquet",
            "raw_sha256": sha(raw),
            "rows": len(frame),
        }
    measurement = signed_payload(
        {
            "schema_version": "data_first_possession_measurement_manifest_v1",
            "output_refs": {
                "observations": {
                    "artifact_kind": "partitioned_dataset_v1",
                    "dataset": "possession_observation",
                    "version_id": "v-obs",
                    "schema_version": "data_first_possession_observation_v1",
                    "content_sha": "c" * 64,
                    "records_sha": "d" * 64,
                    "uri": "lake/obs/partitioned-manifest.json",
                    "row_count": len(observations),
                    "partition_keys": ["season"],
                }
            },
        }
    )
    measurement_raw = json.dumps(measurement).encode()
    store.put("art/measurement-manifest.json", measurement_raw)
    rating = signed_payload(
        {
            "schema_version": mp.INTENDED_UPDATE_SCHEMA,
            "state": "frozen",
            "candidate_id": CANDIDATE_ID,
            "identity": {"run_id": "run"},
            "parents": {"measurement_manifest_sha256": sha(measurement_raw)},
            "output_refs": refs,
            "post_week_cutoffs": {
                str(k - 1): v.isoformat() for k, v in CUTOFFS.items()
            },
        }
    )
    rating_raw = json.dumps(rating).encode()
    store.put(f"{base}/rating-manifest.json", rating_raw)
    verifier = signed_payload(
        {
            "schema_version": mp.INTENDED_UPDATE_VERIFIER_SCHEMA,
            "state": "verified",
            "rating_manifest_raw_sha256": sha(rating_raw),
        }
    )
    store.put(
        f"{base}/verification/verifier-manifest.json", json.dumps(verifier).encode()
    )
    monkeypatch.setattr(
        mp, "iter_partitioned_dataset", lambda storage, ref: iter([observations])
    )
    if tamper:
        tamper(store, rating, measurement, verifier)
    return store, f"{base}/rating-manifest.json", "art/measurement-manifest.json"


def test_loader_accepts_a_fully_verified_artifact_set(monkeypatch):
    store, rating_uri, measurement_uri = make_store(monkeypatch)
    art = mp.load_intended_update_artifacts(store, rating_uri, measurement_uri, 2026)
    assert art.lineage == "intended_update" and art.run_id == "run"
    assert len(art.observations) == 96 and len(art.current_roles) == 2
    assert sorted(art.post_week_cutoffs) == [0, 1, 2]
    assert art.rating_sha256 == sha(store.read_bytes(rating_uri))


def test_loader_rejects_a_wrong_measurement_parent(monkeypatch):
    store, rating_uri, measurement_uri = make_store(monkeypatch)
    other = signed_payload({"schema_version": "x", "output_refs": {"observations": {}}})
    store.put(measurement_uri, json.dumps(other).encode())
    with pytest.raises(mp.PublishError, match="not the rating manifest's parent"):
        mp.load_intended_update_artifacts(store, rating_uri, measurement_uri, 2026)


def test_loader_rejects_unverified_or_mismatched_verifier(monkeypatch):
    for change in ({"state": "pending"}, {"rating_manifest_raw_sha256": "0" * 64}):
        store, rating_uri, measurement_uri = make_store(monkeypatch)
        path = rating_uri.rsplit("/", 1)[0] + "/verification/verifier-manifest.json"
        verifier = json.loads(store.read_bytes(path))
        verifier.update(change)
        store.put(path, json.dumps(signed_payload(verifier)).encode())
        with pytest.raises(mp.PublishError, match="independent verifier"):
            mp.load_intended_update_artifacts(store, rating_uri, measurement_uri, 2026)


def test_loader_rejects_wrong_schema_unfrozen_and_tampered_children(monkeypatch):
    store, rating_uri, measurement_uri = make_store(monkeypatch)
    rating = json.loads(store.read_bytes(rating_uri))
    rating["state"] = "draft"
    store.put(rating_uri, json.dumps(signed_payload(rating)).encode())
    with pytest.raises(mp.PublishError, match="reviewed intended-update"):
        mp.load_intended_update_artifacts(store, rating_uri, measurement_uri, 2026)

    store, rating_uri, measurement_uri = make_store(monkeypatch)
    store.put("art/intended/current_roles.parquet", b"changed bytes")
    with pytest.raises(mp.PublishError, match="current_roles checksum changed"):
        mp.load_intended_update_artifacts(store, rating_uri, measurement_uri, 2026)


def test_loader_rejects_an_unsigned_manifest(monkeypatch):
    store, rating_uri, measurement_uri = make_store(monkeypatch)
    rating = json.loads(store.read_bytes(rating_uri))
    rating["state"] = "frozen "  # edited after signing
    store.put(rating_uri, json.dumps(rating).encode())
    with pytest.raises(Exception, match="checksum mismatch"):
        mp.load_intended_update_artifacts(store, rating_uri, measurement_uri, 2026)


def built_from_store(monkeypatch):
    store, rating_uri, measurement_uri = make_store(monkeypatch)
    art = mp.load_intended_update_artifacts(store, rating_uri, measurement_uri, 2026)
    built = mp.build_payload(art, season=2026, game_names=GAMES, alias_map=ALIAS)
    return art, built


def test_build_payload_covers_all_tables_and_is_deterministic(monkeypatch):
    art, built = built_from_store(monkeypatch)
    counts = built.payload.row_counts()
    assert (
        counts["team_game_measurements"] == 96 and counts["team_rating_components"] == 4
    )
    assert built.weeks == [0, 1, 2, 3]
    first = md.payload_sha256(built.payload.records())
    _, again = built_from_store(monkeypatch)
    assert md.payload_sha256(again.payload.records()) == first
    only = mp.build_payload(
        art, season=2026, game_names=GAMES, alias_map=ALIAS, weeks=[2]
    )
    assert sorted(only.as_of_cutoffs) == [2]
    assert set(only.payload.frames["team_possession_stats"].as_of_week) == {2}
    assert set(only.payload.frames["team_rating_components"].as_of_week) == {2}


def test_static_gates_flag_a_broken_decomposition(monkeypatch):
    _, built = built_from_store(monkeypatch)
    comps = built.payload.frames["team_rating_components"]
    broken = comps.copy()
    broken.loc[broken["snapshot_class"].eq("current").idxmax(), "rating_mean"] += 0.5
    built.payload.frames["team_rating_components"] = broken
    gates = {g.name: g for g in mp.run_static_gates(built, GAMES)}
    assert not gates["rating = prior + evidence; weights and precision reconcile"].ok
    assert gates["game log is row-for-row with possession_observation"].ok


def test_parse_weeks():
    assert mp.parse_weeks(None) is None
    assert mp.parse_weeks("0-2,5") == [0, 1, 2, 5]
    with pytest.raises(mp.PublishError):
        mp.parse_weeks("5-1")


TEST_URL = os.getenv("TEST_DATABASE_URL")
needs_db = pytest.mark.skipif(not TEST_URL, reason="requires disposable PostgreSQL")


def fresh_db():
    with psycopg.connect(TEST_URL, autocommit=True) as conn, conn.cursor() as cur:
        for schema in ("ops", "catalog", "public"):
            cur.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
        cur.execute("CREATE SCHEMA public")
    apply_migrations(TEST_URL, Path("contracts/migrations"))


def project_snapshots(cur, built, *, shift=0.0):
    """Insert the v5 snapshot rows the components reference."""
    comps = built.payload.frames["team_rating_components"]
    for sid, group in comps.groupby("v5_snapshot_id"):
        off = group[group.unit_role == "offense"]
        dfn = group[group.unit_role == "defense"]
        o = off.iloc[0] if len(off) else None
        d = dfn.iloc[0] if len(dfn) else None
        any_row = group.iloc[0]
        cur.execute(
            "INSERT INTO v5_rating_snapshots (snapshot_id, source_run_id, source_manifest_sha256, "
            "team, season, week, game_id, snapshot_class, cutoff_utc, offense_rating, offense_variance, "
            "defense_rating, defense_variance, overall_rating, overall_variance) VALUES "
            "(%s, 'run', %s, %s, 2026, %s, %s, %s, %s, %s, %s, %s, %s, 0, 0) ON CONFLICT DO NOTHING",
            (
                sid,
                any_row.source_manifest_sha256,
                any_row.rating_team,
                int(any_row.as_of_week),
                None if pd.isna(any_row.game_id) else int(any_row.game_id),
                "pregame" if any_row.snapshot_class != "current" else "current",
                any_row.cutoff_utc.to_pydatetime(),
                (o.rating_mean + shift) if o is not None else 0.0,
                o.rating_variance if o is not None else 1.0,
                d.rating_mean if d is not None else 0.0,
                d.rating_variance if d is not None else 1.0,
            ),
        )


@needs_db
def test_db_gates_write_verify_idempotency_stale_and_conflicts(monkeypatch):
    fresh_db()
    art, built = built_from_store(monkeypatch)
    payload_sha = md.payload_sha256(built.payload.records())
    with psycopg.connect(TEST_URL) as conn, conn.cursor() as cur:
        # Ratings not projected yet: the FK-forcing gate fails, with a count.
        monkeypatch.setattr(
            mp, "selected_rating_source", lambda c, s: art.rating_sha256
        )
        gates = {g.name: g for g in mp.run_db_gates(cur, built, art, 2026)}
        assert gates["rating manifest is the site's selected source"].ok
        assert not gates["every component's v5 snapshot is projected"].ok
        project_snapshots(cur, built)
        gates = {g.name: g for g in mp.run_db_gates(cur, built, art, 2026)}
        assert gates["every component's v5 snapshot is projected"].ok
        assert gates["component rating/variance equal v5_rating_snapshots"].ok
        # A different selected source is a failed binding gate.
        monkeypatch.setattr(mp, "selected_rating_source", lambda c, s: "f" * 64)
        assert not mp.run_db_gates(cur, built, art, 2026)[0].ok
        assert mp.missing_tables(cur) == []

        # Nothing exists yet, so nothing is stale or conflicting; dry-run steps wrote nothing.
        assert mp.stale_keys(cur, built, 2026) == {}
        assert (
            mp.check_component_conflicts(
                cur, built.payload.frames["team_rating_components"]
            )
            == []
        )
        cur.execute("SELECT count(*) FROM team_game_measurements")
        assert cur.fetchone() == (0,)

        counts = mp.write_payload(
            cur,
            built,
            art,
            season=2026,
            environment="preview",
            code_sha="abc",
            payload_sha=payload_sha,
        )
        assert counts == built.payload.row_counts()
        assert mp.compare_db_to_payload(cur, built, 2026) == []
        cur.execute("SELECT payload_sha256, as_of_weeks FROM matchup_data_publications")
        assert cur.fetchall() == [(payload_sha, built.weeks)]

        # Re-running is a no-op: same rows, still verified, one receipt.
        mp.write_payload(
            cur,
            built,
            art,
            season=2026,
            environment="preview",
            code_sha="abc",
            payload_sha=payload_sha,
        )
        assert mp.compare_db_to_payload(cur, built, 2026) == []
        cur.execute("SELECT count(*) FROM matchup_data_publications")
        assert cur.fetchone() == (1,)

        # A smaller payload would leave rows behind (the pipeline role cannot DELETE).
        smaller = mp.build_payload(
            art, season=2026, game_names=GAMES, alias_map=ALIAS, weeks=[2]
        )
        stale = mp.stale_keys(cur, smaller, 2026)

        assert set(stale) <= {
            "team_possession_stats",
            "team_possession_adjusted",
            "team_game_measurements",
        }
        # Same scope, one fewer row: the removed key is reported stale.
        trimmed = mp.build_payload(art, season=2026, game_names=GAMES, alias_map=ALIAS)
        trimmed.payload.frames["team_possession_stats"] = trimmed.payload.frames[
            "team_possession_stats"
        ].iloc[1:]
        assert len(mp.stale_keys(cur, trimmed, 2026)["team_possession_stats"]) == 1

        # An existing component that differs from the payload is a conflict.
        cur.execute(
            "UPDATE team_rating_components SET rating_mean = rating_mean + 1 WHERE component_id = (SELECT min(component_id) FROM team_rating_components)"
        )
        assert (
            len(
                mp.check_component_conflicts(
                    cur, built.payload.frames["team_rating_components"]
                )
            )
            == 1
        )
        assert mp.compare_db_to_payload(cur, built, 2026) != []
