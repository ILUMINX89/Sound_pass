-- ============================================================
-- SoundPass — schema.sql
-- PostgreSQL database schema
-- ============================================================


-- ------------------------------------------------------------
-- users
-- ------------------------------------------------------------
CREATE TABLE users (
    id              SERIAL PRIMARY KEY,
    full_name       VARCHAR(150)        NOT NULL,
    email           VARCHAR(150)        NOT NULL UNIQUE,
    password_hash   VARCHAR(255)        NOT NULL,
    created_at      TIMESTAMPTZ         NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------
-- venues
-- ------------------------------------------------------------
CREATE TABLE venues (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(150)        NOT NULL,
    city            VARCHAR(100)        NOT NULL,
    address         VARCHAR(255),
    capacity        INTEGER
);

-- ------------------------------------------------------------
-- concerts
-- ------------------------------------------------------------
CREATE TABLE concerts (
    id              SERIAL PRIMARY KEY,
    artist          VARCHAR(150)        NOT NULL,
    tour_name       VARCHAR(200)        NOT NULL,
    genre           VARCHAR(50)         NOT NULL,
    venue_id        INTEGER             NOT NULL REFERENCES venues(id) ON DELETE RESTRICT,
    event_date      DATE                NOT NULL,
    event_time      TIME                NOT NULL,
    description     TEXT,
    image_url       VARCHAR(500),
    created_at      TIMESTAMPTZ         NOT NULL DEFAULT now()
);

CREATE INDEX idx_concerts_event_date ON concerts(event_date);
CREATE INDEX idx_concerts_genre      ON concerts(genre);

-- ------------------------------------------------------------
-- ticket_types  (General / Preferencial / VIP, per concert)
-- ------------------------------------------------------------
CREATE TABLE ticket_types (
    id                  SERIAL PRIMARY KEY,
    concert_id          INTEGER         NOT NULL REFERENCES concerts(id) ON DELETE CASCADE,
    name                VARCHAR(50)     NOT NULL,
    price               NUMERIC(12,2)   NOT NULL CHECK (price >= 0),
    quantity_available  INTEGER         NOT NULL CHECK (quantity_available >= 0),
    UNIQUE (concert_id, name)
);

-- ------------------------------------------------------------
-- orders  (one order = one concert purchase / checkout)
-- ------------------------------------------------------------
CREATE TABLE orders (
    id              SERIAL PRIMARY KEY,
    order_code      VARCHAR(20)         NOT NULL UNIQUE,      -- e.g. SP-458792
    user_id         INTEGER             NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    concert_id      INTEGER             NOT NULL REFERENCES concerts(id) ON DELETE RESTRICT,
    status          VARCHAR(20)         NOT NULL DEFAULT 'confirmed'
                        CHECK (status IN ('confirmed', 'cancelled')),
    payment_method  VARCHAR(30)         NOT NULL
                        CHECK (payment_method IN ('card', 'pse', 'nequi')),
    subtotal        NUMERIC(12,2)       NOT NULL,
    service_fee     NUMERIC(12,2)       NOT NULL DEFAULT 0,
    total           NUMERIC(12,2)       NOT NULL,
    created_at      TIMESTAMPTZ         NOT NULL DEFAULT now(),
    cancelled_at    TIMESTAMPTZ
);

CREATE INDEX idx_orders_user_id ON orders(user_id);
CREATE INDEX idx_orders_status  ON orders(status);

-- ------------------------------------------------------------
-- order_items  (line items: which ticket type + quantity)
-- ------------------------------------------------------------
CREATE TABLE order_items (
    id              SERIAL PRIMARY KEY,
    order_id        INTEGER             NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    ticket_type_id  INTEGER             NOT NULL REFERENCES ticket_types(id) ON DELETE RESTRICT,
    quantity        INTEGER             NOT NULL CHECK (quantity > 0),
    unit_price      NUMERIC(12,2)       NOT NULL
);

CREATE INDEX idx_order_items_order_id ON order_items(order_id);

-- Boletas individuales con identificador persistente.
CREATE TABLE IF NOT EXISTS issued_tickets (
    id SERIAL PRIMARY KEY,
    order_item_id INTEGER NOT NULL
        REFERENCES order_items(id) ON DELETE CASCADE,
    sequence_number INTEGER NOT NULL,
    public_code VARCHAR(64) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_issued_tickets_public_code
        UNIQUE (public_code),

    CONSTRAINT uq_issued_tickets_item_sequence
        UNIQUE (order_item_id, sequence_number),

    CONSTRAINT ck_issued_tickets_sequence_positive
        CHECK (sequence_number > 0)
);
BEGIN;
SELECT pg_advisory_xact_lock(7294101);
ALTER TABLE venues ADD COLUMN IF NOT EXISTS external_id VARCHAR(255) UNIQUE;
ALTER TABLE concerts ALTER COLUMN artist TYPE TEXT;
ALTER TABLE concerts ALTER COLUMN tour_name TYPE TEXT;
ALTER TABLE concerts ALTER COLUMN event_time DROP NOT NULL;
ALTER TABLE concerts ADD COLUMN IF NOT EXISTS source VARCHAR(30) NOT NULL DEFAULT 'legacy';
ALTER TABLE concerts ADD COLUMN IF NOT EXISTS external_id VARCHAR(255) UNIQUE;
ALTER TABLE concerts ADD COLUMN IF NOT EXISTS starts_at TIMESTAMPTZ;
ALTER TABLE concerts ADD COLUMN IF NOT EXISTS timezone VARCHAR(100);
ALTER TABLE concerts ADD COLUMN IF NOT EXISTS catalog_status VARCHAR(30) NOT NULL DEFAULT 'inactive';
ALTER TABLE concerts ADD COLUMN IF NOT EXISTS official_url TEXT;
ALTER TABLE concerts ADD COLUMN IF NOT EXISTS provider_price NUMERIC(18,2);
ALTER TABLE concerts ADD COLUMN IF NOT EXISTS currency VARCHAR(3);
ALTER TABLE concerts ADD COLUMN IF NOT EXISTS country_code VARCHAR(2);
ALTER TABLE concerts ADD COLUMN IF NOT EXISTS synced_at TIMESTAMPTZ;
ALTER TABLE concerts ADD COLUMN IF NOT EXISTS missing_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE concerts ADD COLUMN IF NOT EXISTS catalog_scope VARCHAR(64) NOT NULL DEFAULT 'CO';
ALTER TABLE concerts ADD COLUMN IF NOT EXISTS artist_provenance TEXT;
CREATE INDEX IF NOT EXISTS idx_catalog_visibility ON concerts(source,country_code,catalog_status,event_date);
CREATE TABLE IF NOT EXISTS catalog_sync (
 country_code VARCHAR(2) PRIMARY KEY, last_success_at TIMESTAMPTZ,
 window_start TIMESTAMPTZ, window_end TIMESTAMPTZ, event_count INTEGER NOT NULL DEFAULT 0
);
ALTER TABLE catalog_sync ALTER COLUMN country_code TYPE VARCHAR(64);
COMMIT;
