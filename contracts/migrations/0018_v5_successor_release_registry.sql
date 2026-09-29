-- Preserve the original V5 pair while admitting separately approved successors.
-- A release authorization still binds one exact immutable prediction run.
CREATE TABLE IF NOT EXISTS v5_model_bundle_approvals (
    approval_id TEXT PRIMARY KEY,
    model_id TEXT NOT NULL,
    inference_bundle_sha256 TEXT NOT NULL CHECK (length(inference_bundle_sha256) = 64),
    first_live_season INTEGER NOT NULL,
    first_live_week INTEGER NOT NULL,
    decision_ref TEXT NOT NULL CHECK (length(trim(decision_ref)) > 0),
    approved_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_v5_model_bundle_approval UNIQUE (model_id, inference_bundle_sha256)
);

INSERT INTO v5_model_bundle_approvals (
    approval_id, model_id, inference_bundle_sha256,
    first_live_season, first_live_week, decision_ref, approved_at
)
SELECT 'legacy-v5-' || inference_bundle_sha256, model_id, inference_bundle_sha256,
       first_live_season, first_live_week, decision_ref, approved_at
FROM v5_release_policy WHERE id = 1
ON CONFLICT (approval_id) DO NOTHING;

CREATE TABLE IF NOT EXISTS v5_intended_update_release_authorizations (
    authorization_id TEXT PRIMARY KEY,
    environment TEXT NOT NULL CHECK (environment IN ('preview', 'production')),
    season INTEGER NOT NULL,
    week INTEGER NOT NULL,
    prediction_run_id TEXT NOT NULL,
    evidence_class TEXT NOT NULL CHECK (evidence_class IN ('replay', 'pending', 'live')),
    model_id TEXT NOT NULL,
    inference_bundle_sha256 TEXT NOT NULL CHECK (length(inference_bundle_sha256) = 64),
    rating_manifest_sha256 TEXT NOT NULL CHECK (length(rating_manifest_sha256) = 64),
    forecast_manifest_uri TEXT NOT NULL,
    forecast_manifest_sha256 TEXT NOT NULL CHECK (length(forecast_manifest_sha256) = 64),
    serving_manifest_uri TEXT NOT NULL,
    serving_manifest_sha256 TEXT NOT NULL CHECK (length(serving_manifest_sha256) = 64),
    verifier_uri TEXT NOT NULL,
    verifier_sha256 TEXT NOT NULL CHECK (length(verifier_sha256) = 64),
    prediction_artifact_uri TEXT NOT NULL,
    prediction_artifact_sha256 TEXT NOT NULL CHECK (length(prediction_artifact_sha256) = 64),
    decision_ref TEXT NOT NULL CHECK (length(trim(decision_ref)) > 0),
    approved_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_v5_intended_update_authorization_run
        UNIQUE (environment, season, week, prediction_run_id)
);

REVOKE ALL ON v5_model_bundle_approvals FROM PUBLIC;
REVOKE ALL ON v5_model_bundle_approvals FROM cks_pipeline;
REVOKE ALL ON v5_model_bundle_approvals FROM cks_web;
GRANT SELECT ON v5_model_bundle_approvals TO cks_pipeline;
REVOKE ALL ON v5_intended_update_release_authorizations FROM PUBLIC;
REVOKE ALL ON v5_intended_update_release_authorizations FROM cks_pipeline;
REVOKE ALL ON v5_intended_update_release_authorizations FROM cks_web;
GRANT SELECT ON v5_intended_update_release_authorizations TO cks_pipeline;
