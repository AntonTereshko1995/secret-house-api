-- Migration 001: add has_bath_tub column to booking table
-- Run once against the production database before deploying the updated API.
-- Safe to run multiple times (IF NOT EXISTS guard via DO block).

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'booking' AND column_name = 'has_bath_tub'
    ) THEN
        ALTER TABLE booking ADD COLUMN has_bath_tub BOOLEAN NOT NULL DEFAULT FALSE;
    END IF;
END
$$;
