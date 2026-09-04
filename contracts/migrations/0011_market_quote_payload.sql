-- Price-payload parity for canonical market quotes (docs/plans/2026-09-03/market-line-retention.md).
-- Append-only: additive columns, no backfill, no constraint changes.
ALTER TABLE market_quotes ADD COLUMN IF NOT EXISTS home_spread_price DOUBLE PRECISION;
ALTER TABLE market_quotes ADD COLUMN IF NOT EXISTS away_spread_price DOUBLE PRECISION;
ALTER TABLE market_quotes ADD COLUMN IF NOT EXISTS over_price DOUBLE PRECISION;
ALTER TABLE market_quotes ADD COLUMN IF NOT EXISTS under_price DOUBLE PRECISION;
ALTER TABLE market_quotes ADD COLUMN IF NOT EXISTS quote_updated_at TIMESTAMPTZ;
ALTER TABLE market_quotes ADD COLUMN IF NOT EXISTS source_event_id TEXT;
