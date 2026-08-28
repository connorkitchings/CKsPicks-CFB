-- Existing Preview pipeline roles need access to the 0009 attempt ledger.
GRANT SELECT, INSERT, UPDATE ON catalog.source_request_attempts TO cks_pipeline;
GRANT ALL PRIVILEGES ON catalog.source_request_attempts TO cks_migrator;
