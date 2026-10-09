"""6A-bridged matchup publication: loader, verifier, scoped writes."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
import psycopg
import pytest
from test_matchup_data import (
    ALIAS,
    CUTOFFS,
    GAME_NAMES,
    _roles_fixture,
    game_rows,
    team_stats,
)
from test_publish_matchup_data import MemoryStorage, parquet, sha

from cks_picks_cfb.data import matchup_data as md
from cks_picks_cfb.data import matchup_publish as mp
from cks_picks_cfb.data.data_first_phase2d import signed_payload
from cks_picks_cfb.db.migrations import apply_migrations
from cks_picks_cfb.ratings.possession_intended_update import CANDIDATE_ID

GAMES = {"Alpha", "Beta", "Hawai'i"}
SIX_A_RUN_ID = "6a-test-r1"
BRIDGE_RUN_ID = "btest-run"


def raw_observations() -> pd.DataFrame:
    return pd.DataFrame(
        game_rows(
            1,
            0,
            "Alpha",
            "Hawai_i",
            team_stats(10, 30, 8.0, 60),
            team_stats(12, 12, -2.0, 70, nonoff=7),
        )
        + game_rows(
            2,
            1,
            "Beta",
            "Alpha",
            team_stats(11, 22, 4.0, 66),
            team_stats(10, 40, 9.0, 55, ppp_missing=True),
        )
        + game_rows(
            3,
            2,
            "Hawai_i",
            "Beta",
            team_stats(9, 18, 1.0, 50),
            team_stats(11, 33, 6.0, 64),
        )
    )


def make_bridge_store():
    """Signed w6live-style rating set + signed 6A root with raw states."""
    raw_obs = raw_observations()
    name_map = md.resolve_game_names(
        set(raw_obs.team) | set(raw_obs.opponent), GAME_NAMES, ALIAS
    )
    prepared = md.prepare_observations(raw_obs, name_map)
    priors, pregame, current = _roles_fixture(prepared)
    store = MemoryStorage()
    base = "art/bintended"
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
    states_key = f"rebuild/6a/{SIX_A_RUN_ID}/states_2026/observations.parquet"
    obs_raw = parquet(raw_obs)
    store.put(states_key, obs_raw)
    root = signed_payload(
        {
            "kind": "rebuild_root_v1",
            "run_id": SIX_A_RUN_ID,
            "objects": {states_key: sha(obs_raw)},
        }
    )
    root_raw = json.dumps(root).encode()
    root_uri = f"rebuild/6a/{SIX_A_RUN_ID}/root-manifest.json"
    store.put(root_uri, root_raw)
    root_sha = sha(root_raw)
    rating = signed_payload(
        {
            "schema_version": mp.INTENDED_UPDATE_SCHEMA,
            "state": "frozen",
            "candidate_id": CANDIDATE_ID,
            "identity": {"run_id": BRIDGE_RUN_ID},
            "parents": {"measurement_manifest_sha256": root_sha},
            "output_refs": refs,
            "post_week_cutoffs": {
                str(k - 1): v.isoformat() for k, v in CUTOFFS.items()
            },
        }
    )
    rating_raw = json.dumps(rating).encode()
    rating_uri = f"{base}/rating-manifest.json"
    store.put(rating_uri, rating_raw)
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
    return store, rating_uri, root_sha


def bridge_built():
    store, rating_uri, root_sha = make_bridge_store()
    art = mp.load_6a_bridged_artifacts(store, rating_uri, SIX_A_RUN_ID, root_sha, 2026)
    built = mp.build_payload(art, season=2026, game_names=GAMES, alias_map=ALIAS)
    return store, art, built


def test_bridge_loader_accepts_a_verified_set():
    store, rating_uri, root_sha = make_bridge_store()
    art = mp.load_6a_bridged_artifacts(store, rating_uri, SIX_A_RUN_ID, root_sha, 2026)
    assert art.lineage == "intended_update" and art.run_id == BRIDGE_RUN_ID
    assert art.candidate_id == CANDIDATE_ID
    assert art.rating_sha256 == sha(store.read_bytes(rating_uri))
    assert art.measurement_sha256 == root_sha
    assert art.measurement_uri == f"rebuild/6a/{SIX_A_RUN_ID}/root-manifest.json"
    assert art.observations_version_id == f"6a:{SIX_A_RUN_ID}"
    assert art.observations_records_sha == sha(
        store.read_bytes(f"rebuild/6a/{SIX_A_RUN_ID}/states_2026/observations.parquet")
    )
    assert len(art.observations) == 96 and len(art.current_roles) == 2
    assert sorted(art.post_week_cutoffs) == [0, 1, 2]


def test_bridge_build_matches_default_path_gate_for_gate(monkeypatch):
    """On equivalent inputs the bridge build behaves exactly like the default
    loader path (the fixture's known quirks reproduce on both; real-data
    consistency is proven by the Preview dry run, where every gate passes)."""
    from test_publish_matchup_data import make_store

    served_store, served_rating_uri, served_measurement_uri = make_store(monkeypatch)
    served = mp.load_intended_update_artifacts(
        served_store, served_rating_uri, served_measurement_uri, 2026
    )
    served_built = mp.build_payload(
        served, season=2026, game_names=GAMES, alias_map=ALIAS
    )
    _, _, bridged_built = bridge_built()
    served_gates = {g.name: g.ok for g in mp.run_static_gates(served_built, GAMES)}
    bridged_gates = {g.name: g.ok for g in mp.run_static_gates(bridged_built, GAMES)}
    assert served_gates == bridged_gates
    assert bridged_gates["game log is row-for-row with possession_observation"]
    assert bridged_built.payload.row_counts() == served_built.payload.row_counts()


def test_bridge_rejects_a_changed_root():
    store, rating_uri, root_sha = make_bridge_store()
    root_uri = f"rebuild/6a/{SIX_A_RUN_ID}/root-manifest.json"
    root = json.loads(store.read_bytes(root_uri))
    root["objects"]["extra"] = "x"
    store.put(root_uri, json.dumps(signed_payload(root)).encode())
    with pytest.raises(mp.PublishError, match="6A root manifest .* changed"):
        mp.load_6a_bridged_artifacts(store, rating_uri, SIX_A_RUN_ID, root_sha, 2026)


def _repin_root(store, root_uri, mutate):
    """Edit the 6A root and pin the new bytes, so checks past the sha pin run."""
    root = json.loads(store.read_bytes(root_uri))
    mutate(root)
    raw = json.dumps(signed_payload(root)).encode()
    store.put(root_uri, raw)
    return sha(raw)


def test_bridge_rejects_an_unsigned_root():
    store, rating_uri, _ = make_bridge_store()
    root_uri = f"rebuild/6a/{SIX_A_RUN_ID}/root-manifest.json"
    root = json.loads(store.read_bytes(root_uri))
    root.pop("manifest_sha256", None)  # unsigned content
    raw = json.dumps(root).encode()
    store.put(root_uri, raw)
    # Pin the unsigned bytes so the flow reaches the signature check.
    _repoint_rating(store, rating_uri, sha(raw))
    with pytest.raises(Exception, match="checksum mismatch"):
        mp.load_6a_bridged_artifacts(store, rating_uri, SIX_A_RUN_ID, sha(raw), 2026)


def _repoint_rating(store, rating_uri, new_parent_sha):
    """Point the rating parent at a re-pinned root (re-signing rating + verifier)."""
    rating = json.loads(store.read_bytes(rating_uri))
    rating["parents"]["measurement_manifest_sha256"] = new_parent_sha
    rating_raw = json.dumps(signed_payload(rating)).encode()
    store.put(rating_uri, rating_raw)
    verifier = signed_payload(
        {
            "schema_version": mp.INTENDED_UPDATE_VERIFIER_SCHEMA,
            "state": "verified",
            "rating_manifest_raw_sha256": sha(rating_raw),
        }
    )
    store.put(
        "art/bintended/verification/verifier-manifest.json",
        json.dumps(verifier).encode(),
    )


def test_bridge_rejects_a_wrong_kind_or_run_id():
    store, rating_uri, _ = make_bridge_store()
    root_uri = f"rebuild/6a/{SIX_A_RUN_ID}/root-manifest.json"
    new_sha = _repin_root(
        store, root_uri, lambda root: root.update(kind="something_else_v1")
    )
    _repoint_rating(store, rating_uri, new_sha)
    with pytest.raises(mp.PublishError, match="not the published 6A root"):
        mp.load_6a_bridged_artifacts(store, rating_uri, SIX_A_RUN_ID, new_sha, 2026)


def test_bridge_rejects_a_mismatched_parent():
    store, rating_uri, root_sha = make_bridge_store()
    _repoint_rating(store, rating_uri, "0" * 64)
    with pytest.raises(mp.PublishError, match="not the pinned 6A root"):
        mp.load_6a_bridged_artifacts(store, rating_uri, SIX_A_RUN_ID, root_sha, 2026)


def test_bridge_rejects_tampered_observations():
    store, rating_uri, root_sha = make_bridge_store()
    key = f"rebuild/6a/{SIX_A_RUN_ID}/states_2026/observations.parquet"
    store.put(key, b"changed bytes")
    with pytest.raises(mp.PublishError, match="published 6A object changed"):
        mp.load_6a_bridged_artifacts(store, rating_uri, SIX_A_RUN_ID, root_sha, 2026)


def test_bridge_rejects_a_missing_states_key():
    store, rating_uri, _ = make_bridge_store()
    root_uri = f"rebuild/6a/{SIX_A_RUN_ID}/root-manifest.json"
    new_sha = _repin_root(store, root_uri, lambda root: root.update(objects={}))
    # Point the rating parent at the re-pinned root so the flow reaches the objects map.
    _repoint_rating(store, rating_uri, new_sha)
    with pytest.raises(mp.PublishError, match="is not in the published 6A root"):
        mp.load_6a_bridged_artifacts(store, rating_uri, SIX_A_RUN_ID, new_sha, 2026)


def test_prepare_run_flag_validation():
    store, rating_uri, root_sha = make_bridge_store()
    base = dict(
        season=2026,
        lineage="intended_update",
        rating_manifest_uri=rating_uri,
        measurement_manifest_uri=None,
        weeks=None,
        alias_map=ALIAS,
    )
    with pytest.raises(mp.PublishError, match="required together"):
        mp.prepare_run(store, None, six_a_run_id=SIX_A_RUN_ID, **base)
    with pytest.raises(mp.PublishError, match="required together"):
        mp.prepare_run(store, None, six_a_root_sha256=root_sha, **base)
    with pytest.raises(mp.PublishError, match="measurement manifest URI is required"):
        mp.prepare_run(store, None, **base)


def test_verifier_manifest_signs_and_asserts():
    store, art, built = bridge_built()
    payload_sha = md.payload_sha256(built.payload.records())
    gates = [mp.GateResult("static-a", True), mp.GateResult("db-a", True, "fine")]
    manifest = mp.build_bridge_verifier_manifest(
        art, built, payload_sha, gates, gates, "abc"
    )
    uri = mp.bridge_verifier_uri("art/bintended/rating-manifest.json")
    assert uri == "art/bintended/verification/bridge-verifier-manifest.json"
    store.put(uri, json.dumps(manifest).encode())
    checked = mp.assert_bridge_verifier(
        store, uri, art.rating_sha256, art.measurement_sha256, payload_sha
    )
    assert checked["payload_sha256"] == payload_sha
    with pytest.raises(mp.PublishError, match="differs from this build"):
        mp.assert_bridge_verifier(
            store, uri, art.rating_sha256, art.measurement_sha256, "0" * 64
        )
    with pytest.raises(mp.PublishError, match="different rating manifest"):
        mp.assert_bridge_verifier(
            store, uri, "f" * 64, art.measurement_sha256, payload_sha
        )
    with pytest.raises(mp.PublishError, match="different 6A root"):
        mp.assert_bridge_verifier(store, uri, art.rating_sha256, "e" * 64, payload_sha)
    with pytest.raises(mp.PublishError, match="missing"):
        mp.assert_bridge_verifier(
            store,
            "art/nope.json",
            art.rating_sha256,
            art.measurement_sha256,
            payload_sha,
        )


def test_verifier_builder_refuses_failed_gates():
    _, art, built = bridge_built()
    payload_sha = md.payload_sha256(built.payload.records())
    gates = mp.run_static_gates(built, GAMES)
    bad = [mp.GateResult("boom", False, "nope")]
    with pytest.raises(mp.PublishError, match="gates failed"):
        mp.build_bridge_verifier_manifest(art, built, payload_sha, bad, gates, "abc")


TEST_URL = os.getenv("TEST_DATABASE_URL")
needs_db = pytest.mark.skipif(not TEST_URL, reason="requires disposable PostgreSQL")


def fresh_db():
    with psycopg.connect(TEST_URL, autocommit=True) as conn, conn.cursor() as cur:
        for schema in ("ops", "catalog", "public"):
            cur.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
        cur.execute("CREATE SCHEMA public")
    apply_migrations(TEST_URL, Path("contracts/migrations"))


def log_rows(cur):
    cur.execute(
        "SELECT game_id, team, unit_role, measurement_id, measurement_manifest_sha256, "
        "raw_value FROM team_game_measurements ORDER BY 1, 2, 3, 4"
    )
    return cur.fetchall()


@needs_db
def test_scoped_write_preserves_other_lineage_rows(monkeypatch):
    from test_publish_matchup_data import built_from_store, project_snapshots

    fresh_db()
    art, built = built_from_store(monkeypatch)
    full_sha = md.payload_sha256(built.payload.records())
    _, bart, bbuilt = bridge_built()
    bridge_sha = md.payload_sha256(bbuilt.payload.records())
    with psycopg.connect(TEST_URL) as conn, conn.cursor() as cur:
        project_snapshots(cur, built)
        project_snapshots(cur, bbuilt)
        mp.write_payload(
            cur,
            built,
            art,
            season=2026,
            environment="preview",
            code_sha="t",
            payload_sha=full_sha,
        )
        before = log_rows(cur)
        assert len(before) == len(built.payload.frames["team_game_measurements"])
        # Scoped bridged write: only game 1's log rows are restamped.
        counts = mp.write_payload(
            cur,
            bbuilt,
            bart,
            season=2026,
            environment="preview",
            code_sha="t",
            payload_sha=bridge_sha,
            log_game_ids={1},
        )
        scoped = bbuilt.payload.frames["team_game_measurements"]
        assert counts["team_game_measurements"] == len(
            scoped[scoped["game_id"].astype(int).eq(1)]
        )
        after = log_rows(cur)
        assert [r for r in before if r[0] != 1] == [r for r in after if r[0] != 1]
        cur.execute(
            "SELECT DISTINCT measurement_manifest_sha256 FROM team_game_measurements "
            "WHERE game_id = 1"
        )
        assert cur.fetchall() == [(bart.measurement_sha256,)]
        cur.execute(
            "SELECT DISTINCT measurement_manifest_sha256 FROM team_game_measurements "
            "WHERE game_id != 1"
        )
        assert cur.fetchall() == [(art.measurement_sha256,)]
