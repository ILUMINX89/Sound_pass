-- 003: preferencias de recomendacion por usuario (K-means al registrarse)
-- Seguro de repetir. Las cuentas existentes no necesitan fila: sin fila equivale a "sin responder".
BEGIN;

CREATE TABLE IF NOT EXISTS user_preferences (
    user_id             INTEGER      PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    status              VARCHAR(10)  NOT NULL CHECK (status IN ('answered', 'skipped')),
    genres              JSONB        NOT NULL DEFAULT '[]'::jsonb,
    artist_ids          JSONB        NOT NULL DEFAULT '[]'::jsonb,
    scale_danceability  SMALLINT     CHECK (scale_danceability BETWEEN 1 AND 5),
    scale_energy        SMALLINT     CHECK (scale_energy BETWEEN 1 AND 5),
    scale_acousticness  SMALLINT     CHECK (scale_acousticness BETWEEN 1 AND 5),
    scale_mood          SMALLINT     CHECK (scale_mood BETWEEN 1 AND 5),
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT ck_user_preferences_scales_together CHECK (
        (scale_danceability IS NULL AND scale_energy IS NULL
            AND scale_acousticness IS NULL AND scale_mood IS NULL)
        OR (scale_danceability IS NOT NULL AND scale_energy IS NOT NULL
            AND scale_acousticness IS NOT NULL AND scale_mood IS NOT NULL)
    )
);

COMMIT;
