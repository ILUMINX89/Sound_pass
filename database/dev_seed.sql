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
(2, 'El Campín',      'Bogotá', 'Cra. 30 #57-60', 36000),
(3, 'Estadio Atanasio Girardot', 'Medellín', NULL, 45000),
(4, 'Estadio Pascual Guerrero', 'Cali', NULL, 35000),
(5, 'Estadio Metropolitano', 'Barranquilla', NULL, 46000);

SELECT setval('venues_id_seq', (SELECT MAX(id) FROM venues));

-- ------------------------------------------------------------
-- concerts
-- ------------------------------------------------------------
INSERT INTO concerts (id, artist, tour_name, genre, venue_id, event_date, event_time, description, image_url) VALUES
(1, 'The Weeknd',       'After Hours Tour',      'Pop',        1, '2027-06-15', '20:00', 'Una noche inolvidable con los mayores éxitos de The Weeknd.', '/images/weeknd.jpg'),
(2, 'Imagine Dragons',  'LOOM World Tour',       'Rock',       2, '2027-06-22', '20:00', 'Imagine Dragons regresa a Colombia con su gira mundial LOOM.', '/images/imagine-dragons.jpg'),
(3, 'Dua Lipa',         'Radical Optimism Tour', 'Pop',        1, '2027-07-05', '20:00', 'Dua Lipa presenta su álbum Radical Optimism en vivo.', '/images/dua-lipa.jpg'),
(4, 'Karol G', 'Gira Colombia 2027', 'Reguetón', 3, '2027-03-12', '20:00', 'Karol G llega con una producción de escenario nunca antes vista en el país.', NULL),
(5, 'Feid', 'Ferxxo en vivo 2027', 'Reguetón', 3, '2027-04-03', '20:00', 'Feid presenta en vivo los mayores éxitos de su carrera.', NULL),
(6, 'Blessd', 'Blessd en concierto 2027', 'Reguetón', 1, '2027-04-17', '20:00', 'Blessd hace vibrar al público con lo mejor del nuevo reguetón colombiano.', NULL),
(7, 'Ryan Castro', 'Ryan Castro en vivo 2027', 'Reguetón', 3, '2027-05-08', '20:00', 'Ryan Castro trae toda la energía de Medellín a una noche de perreo y buena música.', NULL),
(8, 'Junior H', 'Sad Boyz Tour Colombia 2027', 'Regional mexicano', 2, '2027-05-22', '20:00', 'Junior H canta en vivo sus corridos y baladas más queridos.', NULL),
(9, 'Taylor Swift', 'The Eras Tour Colombia', 'Pop', 2, '2027-06-05', '19:30', 'Taylor Swift recorre todas sus eras en un espectáculo de más de tres horas.', NULL),
(10, 'Yeison Jiménez', 'Gira Popular 2027', 'Popular', 5, '2027-06-26', '20:00', 'Yeison Jiménez canta sus éxitos de música popular colombiana en una noche para corear.', NULL),
(11, 'Duki', 'Ameri Tour Colombia 2027', 'Trap', 1, '2027-07-17', '20:00', 'Duki llega con su show de trap más potente y sus temas más sonados.', NULL),
(12, 'W Sound', 'W Sound Fest 2027', 'Urbano', 4, '2027-08-07', '18:00', 'Una noche con los artistas del sello W Sound y lo mejor de la música urbana.', NULL),
(13, 'Pirlo', 'Pirlo en concierto 2027', 'Urbano', 1, '2027-08-28', '20:00', 'Pirlo presenta en vivo sus temas más populares en un show cercano y cargado de energía.', NULL),
(14, 'Peso Pluma', 'Éxodo Tour Colombia 2027', 'Regional mexicano', 3, '2027-09-18', '20:00', 'Peso Pluma lleva los corridos tumbados a Colombia con un espectáculo único.', NULL),
(15, 'Rauw Alejandro', 'Rauw Alejandro Live 2027', 'Reguetón', 5, '2027-10-09', '20:00', 'Rauw Alejandro combina reguetón, baile y electrónica en un show de otro nivel.', NULL),
(16, 'Grupo Frontera', 'Gira Frontera 2027', 'Regional mexicano', 4, '2027-11-06', '20:00', 'Grupo Frontera trae su música norteña para bailar toda la noche.', NULL);

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
(9, 3, 'VIP',          230000, 3000),

(10, 4, 'General', 180000, 1200),
(11, 4, 'Preferencial', 320000, 40),
(12, 4, 'VIP', 950000, 0),
(13, 5, 'General', 160000, 9000),
(14, 5, 'Preferencial', 260000, 40),
(15, 5, 'VIP', 520000, 2000),
(16, 6, 'General', 130000, 5000),
(17, 6, 'Preferencial', 190000, 3500),
(18, 6, 'VIP', 320000, 1500),
(19, 7, 'General', 140000, 12000),
(20, 7, 'Preferencial', 220000, 6000),
(21, 7, 'VIP', 400000, 2500),
(22, 8, 'General', 150000, 13000),
(23, 8, 'Preferencial', 230000, 8000),
(24, 8, 'VIP', 420000, 3000),
(25, 9, 'General', 420000, 0),
(26, 9, 'Preferencial', 780000, 0),
(27, 9, 'VIP', 1800000, 0),
(28, 10, 'General', 120000, 15000),
(29, 10, 'Preferencial', 190000, 9000),
(30, 10, 'VIP', 350000, 3500),
(31, 11, 'General', 170000, 6000),
(32, 11, 'Preferencial', 250000, 4000),
(33, 11, 'VIP', 480000, 1500),
(34, 12, 'General', 110000, 10000),
(35, 12, 'Preferencial', 170000, 6000),
(36, 12, 'VIP', 300000, 2500),
(37, 13, 'General', 120000, 4500),
(38, 13, 'Preferencial', 180000, 3000),
(39, 13, 'VIP', 300000, 1500),
(40, 14, 'General', 230000, 70),
(41, 14, 'Preferencial', 380000, 20),
(42, 14, 'VIP', 900000, 0),
(43, 15, 'General', 200000, 14000),
(44, 15, 'Preferencial', 330000, 9000),
(45, 15, 'VIP', 650000, 4000),
(46, 16, 'General', 140000, 11000),
(47, 16, 'Preferencial', 210000, 7000),
(48, 16, 'VIP', 380000, 3000);

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
