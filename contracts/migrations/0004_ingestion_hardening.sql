-- Request-level capture lifecycle and reconciliation details.

ALTER TABLE catalog.source_captures
    ADD COLUMN IF NOT EXISTS response_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS object_sha TEXT,
    ADD COLUMN IF NOT EXISTS state TEXT NOT NULL DEFAULT 'registered';

UPDATE catalog.source_captures SET object_sha = content_sha WHERE object_sha IS NULL;
ALTER TABLE catalog.source_captures ALTER COLUMN object_sha SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'source_captures_state_check'
          AND conrelid = 'catalog.source_captures'::regclass
    ) THEN
        ALTER TABLE catalog.source_captures
            ADD CONSTRAINT source_captures_state_check
            CHECK (state IN ('staged', 'registered', 'quarantined', 'failed'));
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS catalog.source_reconciliations (
    reconciliation_id TEXT PRIMARY KEY,
    season INTEGER NOT NULL,
    game_id BIGINT NOT NULL,
    classification TEXT NOT NULL CHECK (
        classification IN (
            'exact_match', 'tolerated_difference', 'known_correction',
            'incomplete_source', 'blocking_conflict'
        )
    ),
    blocking BOOLEAN NOT NULL,
    source_dataset_versions JSONB NOT NULL DEFAULT '[]'::jsonb
        CHECK (jsonb_typeof(source_dataset_versions) = 'array'),
    details JSONB NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(details) = 'object'),
    reconciled_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (season, game_id, reconciliation_id)
);

CREATE INDEX IF NOT EXISTS idx_source_reconciliations_scope
    ON catalog.source_reconciliations (season, game_id, blocking);

CREATE TABLE IF NOT EXISTS catalog.dataset_capture_dependencies (
    child_version_id TEXT NOT NULL
        REFERENCES catalog.dataset_versions(version_id) ON DELETE RESTRICT,
    capture_id TEXT NOT NULL
        REFERENCES catalog.source_captures(capture_id) ON DELETE RESTRICT,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    PRIMARY KEY (child_version_id, capture_id),
    UNIQUE (child_version_id, ordinal)
);

CREATE INDEX IF NOT EXISTS idx_dataset_capture_dependencies_capture
    ON catalog.dataset_capture_dependencies (capture_id);

GRANT SELECT, INSERT, UPDATE ON catalog.source_reconciliations TO cks_pipeline;
GRANT SELECT, INSERT, UPDATE ON catalog.dataset_capture_dependencies TO cks_pipeline;
GRANT ALL PRIVILEGES ON catalog.source_reconciliations TO cks_migrator;
GRANT ALL PRIVILEGES ON catalog.dataset_capture_dependencies TO cks_migrator;
