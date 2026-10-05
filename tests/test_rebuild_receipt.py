from __future__ import annotations

import json
from types import SimpleNamespace

from cks_picks_cfb.data.data_first_phase2d import signed_payload
from cks_picks_cfb.rebuild import receipt


def _receipt() -> dict:
    attribution = {
        name: {
            "team_states_changed": 1,
            "forecast_margin_changed": 2,
            "forecast_margin_mean_abs": 0.5,
            "forecast_margin_max_abs": 3.0,
        }
        for name in ("epa_only", "combined")
    }
    return signed_payload(
        {
            "identity": {
                "main_run_id": "r",
                "build_code_sha": "a" * 40,
                "publisher_code_sha": "b" * 40,
                "root_manifest": {"raw_sha256": "c" * 64},
            },
            "coverage": {
                "games": 3,
                "forecast_eligible": 2,
                "measurement_usable": 1,
                "admitted_ledger": {},
            },
            "attribution": {"headline_vs_baseline": attribution},
            "non_claims": list(receipt.NON_CLAIMS),
            "production_activation_authorized": False,
            "validation": {
                "step5_comparison": {"passed": True},
                "gold_contract_problems": 0,
                "attribution": {"epa_only_identity_gate": {"passed": True}},
                "published_comparison": {"control_matches_published": True},
            },
            "outputs": {
                "catalog": {
                    "versions_present": 1,
                    "versions_expected": 1,
                    "content_uri_row_mismatches": 0,
                }
            },
        }
    )


def test_markdown_is_deterministic_and_lists_every_non_claim():
    body = _receipt()
    first = receipt.render_markdown(body)
    assert first == receipt.render_markdown(json.loads(json.dumps(body)))
    for claim in receipt.NON_CLAIMS:
        assert claim in first
    assert "| epa_only | 1 | 2 | 0.5000 | 3.000 |" in first


def test_verify_flags_a_receipt_that_differs_from_fresh_derivation(monkeypatch):
    staged = _receipt()
    tampered = {**staged, "non_claims": staged["non_claims"][:-1]}
    ctx = SimpleNamespace(
        stage=SimpleNamespace(name="receipt"),
        plan=SimpleNamespace(run_id="6a-task4-r1"),
        read_artifact=lambda stage, key: json.dumps(tampered).encode(),
    )
    monkeypatch.setattr(receipt, "verify_signed_payload", lambda *a, **k: None)
    monkeypatch.setattr(receipt, "derive_receipt", lambda context: staged)
    problems = receipt.verify(ctx)
    assert any("fresh derivation" in p for p in problems)
    assert any("non-claims were altered" in p for p in problems)


def test_verify_passes_an_untampered_receipt(monkeypatch):
    staged = _receipt()
    ctx = SimpleNamespace(
        stage=SimpleNamespace(name="receipt"),
        plan=SimpleNamespace(run_id="6a-task4-r1"),
        read_artifact=lambda stage, key: json.dumps(staged).encode(),
    )
    monkeypatch.setattr(receipt, "verify_signed_payload", lambda *a, **k: None)
    monkeypatch.setattr(receipt, "derive_receipt", lambda context: staged)
    assert receipt.verify(ctx) == []
