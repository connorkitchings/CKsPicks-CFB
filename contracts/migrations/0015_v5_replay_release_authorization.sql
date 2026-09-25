-- One reviewed retrospective release authorizes exactly one immutable V5
-- replay run. Only a database administrator may insert records. Pipeline and
-- web roles cannot create, replace, or delete approvals. Replay records never
-- satisfy prospective, readiness, or live authorization gates.
CREATE TABLE IF NOT EXISTS v5_replay_release_authorizations (
    authorization_id TEXT PRIMARY KEY,
    environment TEXT NOT NULL CHECK (environment IN ('preview', 'production')),
    season INTEGER NOT NULL,
    week INTEGER NOT NULL,
    prediction_run_id TEXT NOT NULL,
    model_id TEXT NOT NULL,
    inference_bundle_sha256 TEXT NOT NULL CHECK (length(inference_bundle_sha256) = 64),
    replay_manifest_uri TEXT NOT NULL,
    replay_manifest_sha256 TEXT NOT NULL CHECK (length(replay_manifest_sha256) = 64),
    verifier_uri TEXT NOT NULL,
    verifier_sha256 TEXT NOT NULL CHECK (length(verifier_sha256) = 64),
    serving_config_sha256 TEXT NOT NULL CHECK (length(serving_config_sha256) = 64),
    prediction_artifact_uri TEXT NOT NULL,
    prediction_artifact_sha256 TEXT NOT NULL CHECK (length(prediction_artifact_sha256) = 64),
    decision_ref TEXT NOT NULL CHECK (length(trim(decision_ref)) > 0),
    approved_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_v5_replay_release_authorization_run
        UNIQUE (environment, season, week, prediction_run_id)
);

REVOKE ALL ON v5_replay_release_authorizations FROM PUBLIC;
REVOKE ALL ON v5_replay_release_authorizations FROM cks_pipeline;
REVOKE ALL ON v5_replay_release_authorizations FROM cks_web;
GRANT SELECT ON v5_replay_release_authorizations TO cks_pipeline;
