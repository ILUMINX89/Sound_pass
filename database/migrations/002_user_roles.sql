-- 002: roles de usuario (customer / admin)
-- Seguro de repetir: no falla si la columna ya existe. Las cuentas existentes quedan como 'customer'.
BEGIN;

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS role VARCHAR(20) NOT NULL DEFAULT 'customer';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'ck_users_role'
    ) THEN
        ALTER TABLE users
            ADD CONSTRAINT ck_users_role CHECK (role IN ('customer', 'admin'));
    END IF;
END $$;

COMMIT;

-- Para convertir UNA cuenta existente en administrador (cambia el correo y ejecútalo a mano):
-- UPDATE users SET role = 'admin' WHERE email = 'correo.del.admin@ejemplo.com';