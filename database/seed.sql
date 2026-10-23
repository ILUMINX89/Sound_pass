-- ============================================================
-- SoundPass — seed.sql
-- Sample data matching the product mockups
-- Run after schema.sql
-- ============================================================

-- ------------------------------------------------------------
-- users
-- password for every demo user is: demo123
-- ------------------------------------------------------------
INSERT INTO users (id, full_name, email, password_hash) VALUES
(1, 'Camila Torres', 'camila.torres@example.com', '$2b$12$Als6Jvg1BSKnhAWzYGtDI.zBCPytBQe4Z1N1te5.iHEY1dVNkJzYW'),
(2, 'Andrés Gómez',  'andres.gomez@example.com',  '$2b$12$Als6Jvg1BSKnhAWzYGtDI.zBCPytBQe4Z1N1te5.iHEY1dVNkJzYW');

SELECT setval('users_id_seq', (SELECT MAX(id) FROM users));

-- ------------------------------------------------------------
-- venues
-- ------------------------------------------------------------
INSERT INTO venues (id, name, city, address, capacity) VALUES
(1, 'Movistar Arena', 'Bogotá', 'Cl. 63 #47-33', 14000),
(2, 'El Campín',      'Bogotá', 'Cra. 30 #57-60', 36000);

SELECT setval('venues_id_seq', (SELECT MAX(id) FROM venues));

-- ------------------------------------------------------------
-- concerts
-- ------------------------------------------------------------
INSERT INTO concerts (id, artist, tour_name, genre, venue_id, event_date, event_time, description, image_url) VALUES
(1, 'The Weeknd',       'After Hours Tour',      'Pop',        1, '2027-06-15', '20:00', 'Una noche inolvidable con los mayores éxitos de The Weeknd.', '/images/weeknd.jpg'),
(2, 'Imagine Dragons',  'LOOM World Tour',       'Rock',       2, '2027-06-22', '20:00', 'Imagine Dragons regresa a Colombia con su gira mundial LOOM.', '/images/imagine-dragons.jpg'),
(3, 'Dua Lipa',         'Radical Optimism Tour', 'Pop',        1, '2027-07-05', '20:00', 'Dua Lipa presenta su álbum Radical Optimism en vivo.', '/images/dua-lipa.jpg');

SELECT setval('concerts_id_seq', (SELECT MAX(id) FROM concerts));

-- ------------------------------------------------------------
-- ticket_types
-- ------------------------------------------------------------
INSERT INTO ticket_types (id, concert_id, name, price, quantity_available) VALUES
(1, 1, 'General',      120000, 6000),
(2, 1, 'Preferencial', 180000, 5000),
(3, 1, 'VIP',          250000, 3000),

(4, 2, 'General',      150000, 15000),
(5, 2, 'Preferencial', 210000, 12000),
(6, 2, 'VIP',          290000, 9000),

(7, 3, 'General',      110000, 6000),
(8, 3, 'Preferencial', 165000, 5000),
(9, 3, 'VIP',          230000, 3000);

SELECT setval('ticket_types_id_seq', (SELECT MAX(id) FROM ticket_types));

-- ------------------------------------------------------------
-- orders  +  order_items
-- Order 1: confirmed — 2x Preferencial, The Weeknd
-- Order 2: confirmed — 1x General, Imagine Dragons
-- ------------------------------------------------------------
INSERT INTO orders (id, order_code, user_id, concert_id, status, payment_method, subtotal, service_fee, total, created_at) VALUES
(1, 'SP-458792', 1, 1, 'confirmed', 'card', 360000, 12000, 372000, '2025-05-10 10:24:00-05'),
(2, 'SP-459103', 1, 2, 'confirmed', 'card', 150000, 6000,  156000, '2025-04-28 15:02:00-05');

SELECT setval('orders_id_seq', (SELECT MAX(id) FROM orders));

INSERT INTO order_items (id, order_id, ticket_type_id, quantity, unit_price) VALUES
(1, 1, 2, 2, 180000),   -- 2x Preferencial — The Weeknd
(2, 2, 4, 1, 150000);   -- 1x General — Imagine Dragons

SELECT setval('order_items_id_seq', (SELECT MAX(id) FROM order_items));
