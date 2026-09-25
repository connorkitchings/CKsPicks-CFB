-- Migration 0016: Append-only prediction_market_selections table and
-- market_quote_id on prediction_grades.
--
-- prediction_market_selections records the exact target-level best-quote
-- selection for every prediction run/game/target combination.  Each row is
-- immutable: (run_id, game_id, target) is the primary key and duplicates fail.
-- The selected quote must belong to the same game (enforced by trigger below).
-- No existing migration, grade, or prediction row is modified.
--
-- prediction_grades gains a nullable market_quote_id column so that new
-- best-quote grades carry the exact quote used for settlement.  Legacy grades
-- without the column remain readable and valid.

-- ---------------------------------------------------------------------------
-- prediction_market_selections
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS prediction_market_selections (
    run_id          TEXT NOT NULL REFERENCES prediction_runs(run_id) ON DELETE RESTRICT,
    game_id         BIGINT NOT NULL REFERENCES games(game_id) ON DELETE RESTRICT,
    target          TEXT NOT NULL CHECK (target IN ('spread', 'total')),
    snapshot_id     TEXT NOT NULL REFERENCES market_snapshots(snapshot_id) ON DELETE RESTRICT,
    quote_id        TEXT NOT NULL REFERENCES market_quotes(quote_id) ON DELETE RESTRICT,
    side            TEXT NOT NULL CHECK (side IN ('home', 'away', 'over', 'under')),
    point           DOUBLE PRECISION NOT NULL,
    price           DOUBLE PRECISION NOT NULL,
    edge            DOUBLE PRECISION NOT NULL CHECK (edge >= 0),
    policy_version  TEXT NOT NULL CHECK (length(trim(policy_version)) > 0),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (run_id, game_id, target)
);

-- The selected quote must cover the same game as the prediction.  We enforce
-- this with a check against market_quotes.game_id via a trigger rather than
-- a stored generated column (Neon Postgres supports BEFORE triggers).
CREATE OR REPLACE FUNCTION trg_pms_quote_game_match()
RETURNS TRIGGER AS $$
DECLARE
    quote_game_id BIGINT;
BEGIN
    SELECT mq.game_id INTO quote_game_id
    FROM market_quotes mq
    WHERE mq.quote_id = NEW.quote_id;

    IF quote_game_id IS DISTINCT FROM NEW.game_id THEN
        RAISE EXCEPTION
            'prediction_market_selections: quote_id % belongs to game_id % but selection is for game_id %',
            NEW.quote_id, quote_game_id, NEW.game_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS pms_quote_game_match ON prediction_market_selections;
CREATE TRIGGER pms_quote_game_match
    BEFORE INSERT ON prediction_market_selections
    FOR EACH ROW
    EXECUTE FUNCTION trg_pms_quote_game_match();

CREATE INDEX IF NOT EXISTS idx_pms_run_id
    ON prediction_market_selections (run_id);

CREATE INDEX IF NOT EXISTS idx_pms_game_id
    ON prediction_market_selections (game_id);

-- ---------------------------------------------------------------------------
-- prediction_grades: add nullable market_quote_id for new best-quote grades
-- ---------------------------------------------------------------------------

ALTER TABLE prediction_grades
    ADD COLUMN IF NOT EXISTS market_quote_id TEXT
        REFERENCES market_quotes(quote_id) ON DELETE RESTRICT;

-- ---------------------------------------------------------------------------
-- Grants
-- ---------------------------------------------------------------------------

GRANT SELECT ON prediction_market_selections TO cks_web;
GRANT SELECT, INSERT, UPDATE ON prediction_market_selections TO cks_pipeline;
