-- Resumable request-level evidence for Preview-only historical play capture.
CREATE TABLE IF NOT EXISTS catalog.source_request_attempts (
    ingestion_run_id TEXT NOT NULL REFERENCES catalog.ingestion_runs(ingestion_run_id) ON DELETE RESTRICT,
    request_sha TEXT NOT NULL CHECK (length(request_sha) = 64),
    attempt INTEGER NOT NULL CHECK (attempt > 0),
    state TEXT NOT NULL CHECK (state IN ('running', 'succeeded', 'failed')),
    capture_id TEXT REFERENCES catalog.source_captures(capture_id) ON DELETE RESTRICT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    error_category TEXT,
    error_detail TEXT,
    PRIMARY KEY (ingestion_run_id, request_sha, attempt)
);
CREATE INDEX IF NOT EXISTS idx_source_request_attempts_run_state
    ON catalog.source_request_attempts (ingestion_run_id, state);
