-- Migration 005: add combined sauna+bathtub pricing columns + global setting
-- Idempotent: safe to run on every startup.

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'tariff_pricing' AND column_name = 'combined_sauna_bath_tub_price'
    ) THEN
        ALTER TABLE tariff_pricing
            ADD COLUMN combined_sauna_bath_tub_price FLOAT NOT NULL DEFAULT 0;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'tariff_pricing' AND column_name = 'sale_combined_sauna_bath_tub_price'
    ) THEN
        ALTER TABLE tariff_pricing
            ADD COLUMN sale_combined_sauna_bath_tub_price FLOAT NOT NULL DEFAULT 0;
    END IF;

    INSERT INTO pricing_settings (key, value)
        VALUES ('is_sauna_bath_tub_combo_active', 'false')
        ON CONFLICT (key) DO NOTHING;
END
$$;
