from __future__ import annotations

import json

import pytest

from cks_picks_cfb.data.data_first_phase2c import (
    CHECKPOINT_SCHEMA,
    DEVELOPMENT_SEASONS,
    OUTPUT_DATASETS,
    Phase2cError,
    build_run_identity,
    checkpoint_payload,
    omission_reasons,
    parse_manifest,
    ref_set_payload,
    require_exact_regular_lineage,
    require_expected_dry_run,
    require_identical_identity,
)


def _identity() -> dict:
    return build_run_identity(
        run_id="2026-09-06T1200Z-phase2c-expanded-silver-v1",
        environment="preview",
        as_of="2026-09-06T12:00:00+00:00",
        code_sha="a" * 40,
        configuration={"input": "sealed"},
        input_manifests=[{"uri": "manifest.json", "raw_sha256": "b" * 64}],
    )


def _r1_source_set() -> dict:
    return {
        "entries": [
            {
                "season": season,
                "entity": entity,
                "capture_ids": [f"{season}-{entity}"],
            }
            for season in DEVELOPMENT_SEASONS
            for entity in ("games", "plays", "game_stats", "teams")
        ]
    }


def _entry(season: int) -> dict:
    return {
        "season": season,
        "outputs": {
            dataset: {
                "dataset": dataset,
                "version_id": f"{season}-{dataset}",
                "schema_version": "v1",
                "content_sha": "a" * 64,
                "uri": f"lake/{season}/{dataset}",
            }
            for dataset in OUTPUT_DATASETS
        },
    }


def test_manifest_hashes_raw_bytes_and_rejects_bad_state():
    raw = json.dumps({"state": "complete", "value": 1}).encode()
    manifest, evidence = parse_manifest(
        uri="sealed.json", raw_bytes=raw, allowed_states={"complete"}, label="test"
    )
    assert manifest["value"] == 1
    assert evidence["raw_sha256"]
    with pytest.raises(Phase2cError, match="allowed state"):
        parse_manifest(
            uri="sealed.json",
            raw_bytes=json.dumps({"state": "running"}).encode(),
            allowed_states={"complete"},
            label="test",
        )


def test_regular_phase1_captures_must_equal_r1_per_season_and_entity():
    regular = {
        entity: {season: [f"{season}-{entity}"] for season in DEVELOPMENT_SEASONS}
        for entity in ("games", "plays", "game_stats", "teams")
    }
    require_exact_regular_lineage(_r1_source_set(), regular)
    regular["games"][2015] = ["wrong"]
    with pytest.raises(Phase2cError, match="mismatch"):
        require_exact_regular_lineage(_r1_source_set(), regular)


def test_identity_is_immutable_and_preview_only():
    identity = _identity()
    require_identical_identity(identity, dict(identity))
    changed = dict(identity) | {"as_of": "2026-09-07T00:00:00+00:00"}
    with pytest.raises(Phase2cError, match="collision"):
        require_identical_identity(identity, changed)
    with pytest.raises(Phase2cError, match="Preview"):
        build_run_identity(
            run_id="run-phase2c-expanded-silver-v1",
            environment="production",
            as_of="2026-09-06T12:00:00+00:00",
            code_sha="a" * 40,
            configuration={},
            input_manifests=[],
        )


def test_checkpoint_requires_exactly_eight_outputs_and_is_bound_to_identity():
    checkpoint = checkpoint_payload(identity=_identity(), entry=_entry(2015))
    assert checkpoint["schema_version"] == CHECKPOINT_SCHEMA
    assert checkpoint["identity_sha256"] == _identity()["identity_sha256"]
    bad = _entry(2015)
    bad["outputs"].pop("plays")
    with pytest.raises(Phase2cError, match="eight outputs"):
        checkpoint_payload(identity=_identity(), entry=bad)


def test_ref_set_requires_all_permitted_seasons_and_complete_outputs():
    entries = [_entry(season) for season in DEVELOPMENT_SEASONS]
    payload = ref_set_payload(identity=_identity(), entries=entries, state="complete")
    assert payload["manifest_sha256"]
    with pytest.raises(Phase2cError, match="every permitted season"):
        ref_set_payload(identity=_identity(), entries=entries[:-1], state="complete")


def test_omissions_allow_only_declared_regular_plays_and_block_postseason_detail():
    result = omission_reasons(
        missing_plays=[1],
        missing_stats=[2],
        declared_regular_plays=[1],
        postseason_game_ids=[3],
    )
    assert result["plays"] == [{"game_id": 1, "reason": "provider_response_omission"}]
    with pytest.raises(Phase2cError, match="postseason"):
        omission_reasons(
            missing_plays=[3],
            missing_stats=[],
            declared_regular_plays=[3],
            postseason_game_ids=[3],
        )


def test_dry_run_requires_the_approved_ten_season_corpus_counts():
    entries = []
    for index, season in enumerate(DEVELOPMENT_SEASONS):
        final = index == len(DEVELOPMENT_SEASONS) - 1
        entries.append(
            {
                "season": season,
                "row_counts": {
                    "fbs_involved_games": 899 if final else 893,
                    "game_outcomes": 899 if final else 893,
                },
                "season_type": {
                    "regular": 853 if final else 852,
                    "postseason": 46 if final else 41,
                },
                "population": {
                    "fbs_fbs": 781 if final else 779,
                    "fbs_fcs": 118 if final else 114,
                },
                "reconciliation": {"blocking": 0},
            }
        )
    require_expected_dry_run(entries)
    entries[-1]["population"]["fbs_fcs"] = 117
    with pytest.raises(Phase2cError, match="corpus counts"):
        require_expected_dry_run(entries)
