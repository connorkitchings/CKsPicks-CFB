-- Additive compatibility migration for canonical upcoming-game route labels.
-- Historic prediction rows retain their completed-game labels.
ALTER TABLE predictions
    DROP CONSTRAINT IF EXISTS predictions_regime_check;

ALTER TABLE predictions
    ADD CONSTRAINT predictions_regime_check
    CHECK (
        regime IN (
            'preseason', 'one_game', 'two_games', 'three_games',
            'game_1', 'game_2', 'game_3', 'established'
        )
    );
