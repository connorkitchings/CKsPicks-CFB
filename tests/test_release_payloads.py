"""Release payload builders: structure, comparison, receipt and controller acceptance."""

from __future__ import annotations

import importlib.util
import math
from pathlib import Path

import pandas as pd
import pytest

from cks_picks_cfb.data.data_first_phase2d import signed_payload
from cks_picks_cfb.ops.v5_batch_selection_v2 import (
    V5BatchSelectionError,
    validate_v2_packet,
)
from cks_picks_cfb.rebuild import release_payloads as rp

_BASE = Path(__file__).resolve().parent / "test_v5_batch_selection_v2.py"
_spec = importlib.util.spec_from_file_location("_batch_v2_fixture", _BASE)
_base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_base)

OLD = {"byplay": "old-byplay", "games": "old-games"}
NEW = {"byplay": "new-byplay", "games": "new-games", "rebuild_root": "6a-root"}


def _frame(value=0.2, rank=3, **overrides):
    row = {
        "season": 2026,
        "as_of_week": 5,
        "team": "Alabama",
        "role": "offense",
        "metric": "ppa_per_play",
        "value": value,
        "n": 100,
        "games": 5,
        "rank": rank,
        "cohort_size": 130,
        **overrides,
    }
    return pd.DataFrame([row])


def test_stat_rows_use_controller_columns_honest_provenance_and_null_values():
    frame = pd.concat(
        [
            _frame(),
            _frame(team="Zeta", value=float("nan"), rank=float("nan"), cohort_size=130),
        ],
        ignore_index=True,
    )
    rows = rp.stat_rows(frame, NEW)
    assert [r["team"] for r in rows] == ["Alabama", "Zeta"]
    assert list(rows[0]) == list(rp.STAT_COLUMNS)
    assert rows[1]["value"] is None and rows[1]["rank"] is None
    assert isinstance(rows[0]["n"], int) and isinstance(rows[0]["rank"], int)
    assert rows[0]["source_versions"] == NEW
    assert rows[0]["source_versions"] is not NEW
    with pytest.raises(rp.PayloadError, match="source_versions"):
        rp.stat_rows(frame, {})


def test_structural_problems_catch_each_contract_violation():
    good = rp.stat_rows(_frame(), NEW)[0]
    assert rp.structural_problems([good]) == []
    assert "duplicate" in " ".join(rp.structural_problems([good, dict(good)]))
    assert "rank" in " ".join(rp.structural_problems([{**good, "rank": 131}]))
    assert "ranked row has no value" in " ".join(
        rp.structural_problems([{**good, "value": None}])
    )
    assert "non-finite" in " ".join(
        rp.structural_problems([{**good, "value": math.inf}])
    )
    assert "unknown role" in " ".join(rp.structural_problems([{**good, "role": "x"}]))
    assert "nonempty" in " ".join(
        rp.structural_problems([{**good, "source_versions": {}}])
    )


def test_compare_separates_value_rank_only_and_count_only_changes():
    base = rp.stat_rows(
        pd.concat(
            [
                _frame(team="A"),
                _frame(team="B"),
                _frame(team="C"),
                _frame(team="D"),
            ],
            ignore_index=True,
        ),
        OLD,
    )
    after = [dict(r, source_versions=NEW) for r in base]
    after[0]["value"] = 0.9
    after[1]["rank"] = 9
    after[2]["n"] = 7
    result = rp.compare_stats(base, after)
    assert result["same_key_set"] is True
    assert result["value_changed"] == {"ppa_per_play": 1}
    assert result["rank_only_changed"] == {"ppa_per_play": 1}
    assert result["count_only_changed"] == {"ppa_per_play": 1}
    assert result["provenance_changed_keys"] == 4
    dropped = rp.compare_stats(base, after[:3])
    assert dropped["same_key_set"] is False and dropped["only_before"] == 1


def test_receipt_is_failed_when_keys_differ_or_a_check_fails():
    base = rp.stat_rows(_frame(), OLD)
    after = rp.stat_rows(_frame(team="Other"), NEW)
    receipt = rp.verification_receipt(
        before_sha256="a" * 64,
        after_sha256="b" * 64,
        before_rows=base,
        after_rows=after,
        decision_ref="d",
        checks={},
    )
    assert receipt["state"] == "failed"
    ok_after = [dict(r, source_versions=NEW) for r in base]
    failed = rp.verification_receipt(
        before_sha256="a" * 64,
        after_sha256="b" * 64,
        before_rows=base,
        after_rows=ok_after,
        decision_ref="d",
        checks={"sample_recompute": {"passed": False}},
    )
    assert failed["state"] == "failed" and failed["failed_checks"] == [
        "sample_recompute"
    ]
    with pytest.raises(rp.PayloadError, match="decision"):
        rp.verification_receipt(
            before_sha256="a",
            after_sha256="b",
            before_rows=base,
            after_rows=ok_after,
            decision_ref=" ",
            checks={},
        )


def _controller_packet(*, strip_binding=False):
    """A packet whose stats payloads and receipt come from the new library."""
    packet, storage = _base._packet()
    before_rows = rp.stat_rows(_frame(value=0.2), OLD)
    after_rows = rp.stat_rows(_frame(value=0.25), NEW)
    refs = {}
    payloads = {}
    for name, rows, uri in (
        ("before", before_rows, "r2://stats/lib-before"),
        ("after", after_rows, "r2://stats/lib-after"),
    ):
        payload = rp.team_stats_payload(
            rows,
            environment="preview",
            season=2026,
            parents={"rebuild_root_sha256": "c" * 64},
            label=name,
        )
        raw, digest = rp.payload_bytes(payload)
        storage.objects[uri] = raw
        refs[name] = {"uri": uri, "sha256": digest}
        payloads[name] = payload
    receipt = rp.verification_receipt(
        before_sha256=refs["before"]["sha256"],
        after_sha256=refs["after"]["sha256"],
        before_rows=before_rows,
        after_rows=after_rows,
        decision_ref="decision-7a",
        checks={"structure": {"passed": True}},
    )
    if strip_binding:
        receipt = signed_payload(
            {
                k: v
                for k, v in receipt.items()
                if k not in ("manifest_sha256", "provenance_change")
            }
        )
    raw, digest = rp.payload_bytes(receipt)
    storage.objects["r2://stats/lib-verify"] = raw
    packet["team_stats_before"] = refs["before"]
    packet["team_stats_after"] = refs["after"]
    packet["team_stats_verifier"] = {"uri": "r2://stats/lib-verify", "sha256": digest}
    packet = signed_payload({k: v for k, v in packet.items() if k != "manifest_sha256"})
    return packet, storage, receipt


def test_library_payloads_and_receipt_pass_the_real_controller_validation():
    packet, storage, receipt = _controller_packet()
    assert receipt["state"] == "verified"
    assert receipt["provenance_change"]["keys_changed"] == 1
    result = validate_v2_packet(packet, environment="preview", storage=storage)
    after = result["payloads"]["team_stats_after"]["rows"][0]
    assert after["source_versions"] == NEW and after["value"] == 0.25


def test_controller_rejects_library_payloads_when_the_binding_is_missing():
    packet, storage, _ = _controller_packet(strip_binding=True)
    with pytest.raises(V5BatchSelectionError, match="without a matching verifier"):
        validate_v2_packet(packet, environment="preview", storage=storage)


def test_payload_refuses_invalid_rows_and_environments():
    rows = rp.stat_rows(_frame(), NEW)
    with pytest.raises(rp.PayloadError, match="environment"):
        rp.team_stats_payload(
            rows, environment="staging", season=2026, parents={}, label="x"
        )
    with pytest.raises(rp.PayloadError, match="rank"):
        rp.team_stats_payload(
            [dict(rows[0], rank=500)],
            environment="preview",
            season=2026,
            parents={},
            label="x",
        )


def test_change_gate_allows_only_the_nullable_ppa_family_to_change_value():
    from scripts.pipeline.verify_corrected_publication_payloads import change_gate

    before = rp.stat_rows(
        pd.concat(
            [
                _frame(team="A", metric="epa_pass"),
                _frame(team="A", metric="success_rate"),
            ],
            ignore_index=True,
        ),
        OLD,
    )
    allowed = [dict(r, source_versions=NEW) for r in before]
    allowed[0]["value"] = 0.9
    assert change_gate(before, allowed)["passed"] is True

    blocked = [dict(r, source_versions=NEW) for r in before]
    blocked[1]["value"] = 0.9
    result = change_gate(before, blocked)
    assert result["passed"] is False
    assert result["unexpected_value_changes"] == ["success_rate"]

    assert change_gate(before, allowed[:1])["passed"] is False
