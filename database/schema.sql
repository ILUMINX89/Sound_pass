-- ============================================================
-- SoundPass — schema.sql
-- PostgreSQL database schema
-- ============================================================

DROP TABLE IF EXISTS order_items CASCADE;
DROP TABLE IF EXISTS orders CASCADE;
DROP TABLE IF EXISTS ticket_types CASCADE;
DROP TABLE IF EXISTS concerts CASCADE;
DROP TABLE IF EXISTS venues CASCADE;
DROP TABLE IF EXISTS users CASCADE;

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
