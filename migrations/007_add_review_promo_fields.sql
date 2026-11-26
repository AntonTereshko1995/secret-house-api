-- Migration 007: add is_single_use to promocode, reward_promo_code to booking
-- Idempotent: safe to re-run on every startup.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'promocode' AND column_name = 'is_single_use'
    ) THEN
        ALTER TABLE promocode ADD COLUMN is_single_use BOOLEAN NOT NULL DEFAULT FALSE;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'booking' AND column_name = 'reward_promo_code'
    ) THEN
        ALTER TABLE booking ADD COLUMN reward_promo_code VARCHAR(50);
    END IF;
END
$$;
