-- v2 immutable dataset identity, executable schemas, and durable pipeline leases.

ALTER TABLE catalog.schema_versions
    ADD COLUMN IF NOT EXISTS schema_sha TEXT;

ALTER TABLE catalog.dataset_versions
    ADD COLUMN IF NOT EXISTS identity_version TEXT NOT NULL DEFAULT 'v1',
    ADD COLUMN IF NOT EXISTS schema_sha TEXT;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'dataset_versions_identity_version_check'
          AND conrelid = 'catalog.dataset_versions'::regclass
    ) THEN
        ALTER TABLE catalog.dataset_versions
            ADD CONSTRAINT dataset_versions_identity_version_check
            CHECK (identity_version IN ('v1', 'dataset_identity_v2'));
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_dataset_versions_schema
    ON catalog.dataset_versions (dataset, schema_version, schema_sha);

ALTER TABLE ops.pipeline_runs
    ADD COLUMN IF NOT EXISTS definition_json JSONB,
    ADD COLUMN IF NOT EXISTS definition_sha TEXT,
    ADD COLUMN IF NOT EXISTS lease_owner TEXT,
    ADD COLUMN IF NOT EXISTS lease_epoch BIGINT NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS lease_expires_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS heartbeat_at TIMESTAMPTZ;

ALTER TABLE ops.pipeline_steps
    ADD COLUMN IF NOT EXISTS definition_sha TEXT,
    ADD COLUMN IF NOT EXISTS lease_epoch BIGINT;

CREATE INDEX IF NOT EXISTS idx_pipeline_runs_lease
    ON ops.pipeline_runs (environment, season, week, lease_expires_at);

GRANT SELECT, INSERT, UPDATE ON catalog.schema_versions TO cks_pipeline;
GRANT ALL PRIVILEGES ON catalog.schema_versions TO cks_migrator;
