-- Migration 006: partial unique index for guest_review.booking_id
-- The table itself is created by SQLAlchemy create_all (via GuestReviewBase).
-- This migration adds the partial unique index (not supported by create_all).
-- Wrapped in IF EXISTS check because migrations run BEFORE create_all on first deploy.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables WHERE table_name = 'guest_review'
    ) THEN
        CREATE UNIQUE INDEX IF NOT EXISTS uq_guest_review_booking_id
            ON guest_review(booking_id) WHERE booking_id IS NOT NULL;
    END IF;
END
$$;
