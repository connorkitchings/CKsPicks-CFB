-- Require exact rating provenance on V5 prediction runs. Existing and future
-- V4 rollback runs remain valid without a rating manifest.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM prediction_runs
        WHERE model_id LIKE 'v5-%' AND rating_manifest_sha256 IS NULL
    ) THEN
        RAISE EXCEPTION
            'Migration 0017 blocked: V5 prediction_runs lack rating_manifest_sha256';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'prediction_runs'::regclass
          AND conname = 'chk_prediction_runs_rating_manifest_required'
    ) THEN
        ALTER TABLE prediction_runs
            ADD CONSTRAINT chk_prediction_runs_rating_manifest_required
            CHECK (
                model_id IS NULL OR model_id NOT LIKE 'v5-%'
                OR rating_manifest_sha256 IS NOT NULL
            );
    END IF;
END $$;
