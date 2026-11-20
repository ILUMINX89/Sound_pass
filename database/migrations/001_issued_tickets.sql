BEGIN;

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

COMMIT;
