-- Migration 004: add tariff_pricing and pricing_settings tables
-- Idempotent: safe to run on every startup.

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'tariff_pricing'
    ) THEN
        CREATE TABLE tariff_pricing (
            id SERIAL PRIMARY KEY,
            tariff_id VARCHAR(50) NOT NULL,
            price FLOAT NOT NULL DEFAULT 0,
            sauna_price FLOAT NOT NULL DEFAULT 0,
            bath_tub_price FLOAT NOT NULL DEFAULT 0,
            secret_room_price FLOAT NOT NULL DEFAULT 0,
            extra_bedroom_price FLOAT NOT NULL DEFAULT 0,
            extra_hour_price FLOAT NOT NULL DEFAULT 0,
            extra_people_price FLOAT NOT NULL DEFAULT 0,
            photoshoot_price FLOAT NOT NULL DEFAULT 0,
            multi_day_prices JSONB NOT NULL DEFAULT '{}',
            sale_price FLOAT NOT NULL DEFAULT 0,
            sale_sauna_price FLOAT NOT NULL DEFAULT 0,
            sale_bath_tub_price FLOAT NOT NULL DEFAULT 0,
            sale_secret_room_price FLOAT NOT NULL DEFAULT 0,
            sale_extra_bedroom_price FLOAT NOT NULL DEFAULT 0,
            sale_extra_hour_price FLOAT NOT NULL DEFAULT 0,
            sale_extra_people_price FLOAT NOT NULL DEFAULT 0,
            sale_photoshoot_price FLOAT NOT NULL DEFAULT 0,
            sale_multi_day_prices JSONB NOT NULL DEFAULT '{}',
            updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
            UNIQUE(tariff_id)
        );
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'pricing_settings'
    ) THEN
        CREATE TABLE pricing_settings (
            key VARCHAR(100) PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        );
    END IF;

    INSERT INTO pricing_settings (key, value)
        VALUES ('is_sale_active', 'false'), ('transfer_price', '300')
        ON CONFLICT (key) DO NOTHING;
END
$$;
