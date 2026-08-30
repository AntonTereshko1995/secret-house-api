-- Migration 002: add public_id UUID to booking table
-- Run once against the production database before deploying the updated API.
-- Safe to run multiple times (IF NOT EXISTS guard via DO block).

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'booking' AND column_name = 'public_id'
    ) THEN
        ALTER TABLE booking ADD COLUMN public_id UUID NOT NULL DEFAULT gen_random_uuid();
        CREATE UNIQUE INDEX booking_public_id_idx ON booking (public_id);
    END IF;
END
$$;
