-- Additive compatibility migration for the fourth upcoming-game route.
-- Historic rows retain their stored legacy/canonical labels.
ALTER TABLE predictions
    DROP CONSTRAINT IF EXISTS predictions_regime_check;

ALTER TABLE predictions
    ADD CONSTRAINT predictions_regime_check
    CHECK (
        regime IN (
            'preseason', 'one_game', 'two_games', 'three_games',
            'game_1', 'game_2', 'game_3', 'game_4', 'established'
        )
    );
