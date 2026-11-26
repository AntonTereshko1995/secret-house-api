-- Migration 008: add user_id to promocode for personal (single-use review reward) codes
-- Idempotent: safe to re-run on every startup.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'promocode' AND column_name = 'user_id'
    ) THEN
        ALTER TABLE promocode ADD COLUMN user_id INTEGER NULL REFERENCES "user"(id);
    END IF;
END
$$;
