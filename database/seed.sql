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

-- Administrador de DEMOSTRACIÓN (contraseña demo123, igual que los otros usuarios del seed).
-- Solo para desarrollo: en un entorno real crea la cuenta con otra contraseña y promuévela con la migración 002.
INSERT INTO users (id, full_name, email, password_hash, role) VALUES
(3, 'Admin SoundPass', 'admin@soundpass.example', '$2b$12$Als6Jvg1BSKnhAWzYGtDI.zBCPytBQe4Z1N1te5.iHEY1dVNkJzYW', 'admin');
 
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
