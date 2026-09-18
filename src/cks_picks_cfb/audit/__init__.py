"""Shared contracts for the V5-10 historical-foundation audit.

This package is deliberately independent of every producer computation: it
imports only generic storage readers, schema contracts, and signing utilities.
Expected manifest schemas, dataset roles, and pinned identities are restated
here (rather than imported from producer-mixed modules) so the audit harness
cannot mirror a producer defect into agreement.
"""

from __future__ import annotations

AUDIT_CONFIG_SCHEMA = "data_first_historical_audit_config_v1"
AUDIT_IDENTITY_SCHEMA = "data_first_historical_audit_identity_v1"
AUDIT_MANIFEST_SCHEMA = "data_first_historical_audit_manifest_v1"
AUDIT_EVIDENCE_SCHEMA = "data_first_historical_audit_evidence_v1"

AUDIT_OUTPUT_ROOT = (
    "artifacts/research/data-first-football-v1/audits/historical-foundation-v1/runs"
)

ELIGIBLE_SEASONS = (2015, 2016, 2017, 2018, 2019, 2021, 2022, 2023, 2024, 2025)
FORBIDDEN_SEASONS = (2020,)
# Seasons that must never appear in any audit evidence, including nested refs.
REJECTED_SEASONS = (2020, 2026)

SEVERITIES = ("blocker", "major", "minor", "info")
DISPOSITIONS = (
    "eligible_for_next_contract",
    "historical_evidence_only",
    "prohibited_until_closed",
)
# Provisional severity used only in local 10a preflight evidence; 10b assigns
# a final severity from SEVERITIES to every finding.
PROVISIONAL_SEVERITY = "unassigned"

# Expected parent stages in dependency order, with manifest schema, state, and
# output dataset roles restated from (not imported from) producer contracts.
PARENT_STAGES = (
    {
        "stage": "repair",
        "manifest_schema": "data_first_repair_manifest_v2",
        "state": "repaired_reconstructed_only",
        "output_datasets": (
            ("population", "repair_population", "data_first_repair_population_v2"),
            ("auxiliary", "repair_auxiliary", "data_first_repair_auxiliary_v2"),
            ("coverage", "repair_coverage", "data_first_repair_coverage_v2"),
            ("issues", "repair_issue", "data_first_repair_issue_v2"),
            (
                "capture_plan",
                "repair_capture_plan",
                "data_first_repair_capture_plan_v2",
            ),
        ),
    },
    {
        "stage": "measurements",
        "manifest_schema": "data_first_possession_measurement_manifest_v1",
        "state": None,  # R6 producer manifest carries no lifecycle state field.
        "output_datasets": (
            (
                "population",
                "possession_population",
                "data_first_possession_population_v1",
            ),
            ("possessions", "possession_ledger", "data_first_possession_possession_v1"),
            (
                "scoring_events",
                "possession_scoring_event",
                "data_first_possession_scoring_event_v1",
            ),
            (
                "observations",
                "possession_observation",
                "data_first_possession_observation_v1",
            ),
            ("snapshots", "possession_snapshot", "data_first_possession_snapshot_v1"),
            (
                "adjusted_history",
                "possession_adjusted_history",
                "data_first_possession_adjusted_history_v1",
            ),
            ("terminal", "possession_terminal", "data_first_possession_terminal_v1"),
            ("coverage", "possession_coverage", "data_first_possession_coverage_v1"),
        ),
    },
    {
        "stage": "ratings",
        "manifest_schema": "data_first_possession_retained_rating_v1",
        "state": "frozen",
        "output_datasets": (
            (
                "rating_registry",
                "possession_rating_registry",
                "data_first_possession_rating_registry_v1",
            ),
            (
                "priors",
                "possession_rating_prior",
                "data_first_possession_rating_prior_v1",
            ),
            (
                "noise_fits",
                "possession_rating_noise_fit",
                "data_first_possession_rating_noise_fit_v1",
            ),
            (
                "rating_states",
                "possession_rating_state",
                "data_first_possession_rating_state_v1",
            ),
            (
                "team_states",
                "possession_team_state",
                "data_first_possession_team_state_v1",
            ),
            (
                "bridge_predictions",
                "possession_rating_bridge_prediction",
                "data_first_possession_rating_bridge_prediction_v1",
            ),
            (
                "attribution",
                "possession_rating_attribution",
                "data_first_possession_rating_attribution_v1",
            ),
        ),
    },
    {
        "stage": "forecasts",
        "manifest_schema": "data_first_forecast_manifest_v1",
        "state": "frozen",
        "output_datasets": (
            (
                "forecast_registry",
                "forecast_registry",
                "data_first_forecast_registry_v1",
            ),
            ("forecast_model", "forecast_model", "data_first_forecast_model_v1"),
            (
                "forecast_prediction",
                "forecast_prediction",
                "data_first_forecast_prediction_v1",
            ),
            (
                "forecast_calibration",
                "forecast_calibration",
                "data_first_forecast_calibration_v1",
            ),
            (
                "window_comparison",
                "window_comparison",
                "data_first_window_comparison_v1",
            ),
            (
                "forecast_selection",
                "forecast_selection",
                "data_first_forecast_selection_v1",
            ),
        ),
    },
)

# Sealed population counts restated for cross-manifest agreement checks.
SEALED_REPAIR_POPULATION = {
    "scheduled_games": 8936,
    "forecast_eligible_games": 8935,
    "measurement_usable_games": 8903,
    "measurement_missing_games": 33,
}

# Confirmed structural conditions seeded into the preflight findings set. Their
# existence is established; Contract 10 determines scope, severity,
# disposition, and closure criteria.
SEEDED_FINDINGS = (
    {
        "finding_id": "audit-structural-001",
        "title": "Repair v2 verification imports producer computation",
        "description": (
            "scripts/research/verify_data_first_repair_v2.py imports and calls "
            "producer compute_repair from scripts/research/run_data_first_repair_v2.py, "
            "so Repair v2 does not meet the independent-reconstruction standard."
        ),
        "affected_stages": ("repair",),
    },
    {
        "finding_id": "audit-structural-002",
        "title": "Forecast verification does not reconstruct stored outputs",
        "description": (
            "src/cks_picks_cfb/forecast/forecast_verification.py validates manifest "
            "metadata and reference labels but never reads or reconstructs the stored "
            "forecast outputs, offsets, bridge fits, calibration, or selection."
        ),
        "affected_stages": ("forecasts",),
    },
)
