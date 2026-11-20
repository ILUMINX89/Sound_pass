# Entrega local: catalogo y SoundPass AI

Rama: feature/sprint3-soundpass-ai, base b3d4c66, historia del asistente #71. Sin commit, push ni PR; GitHub no se modifico. No hay numero confirmado de historia de catalogo.

## Validacion realizada

- Docker reconstruido: API, importador periodico y frontend local en http://localhost:5500.
- 17 pruebas unittest aprobadas dentro de Docker, con PostgreSQL 16 aislado para migraciones, lock e importacion. JavaScript validado con node --check en node:22-alpine. Compose validado con config --quiet.
- Migracion 002 aplicada al volumen existente despues de respaldo custom en .local/soundpass-before-catalog-20261120-154857.dump. Se conservaron 2 usuarios, 2 ordenes, 2 items de orden y 16 conciertos legacy. El PDF de una compra historica respondio 200 con firma PDF.
- Cobertura CO real: HTTP 200, totalElements=0, muestra vacia. A solicitud posterior se habilito el alcance mundial por origen verificado US, MX, CO, AR, PR.
- Primer ciclo global completo: 268 eventos recibidos, 101 publicados, 167 omitidos. Una muestra de Bob Dylan coincidio en ID, fecha y titulo con Discovery. GET por el proxy devolvio 200; historial 200; detalle legacy publico 404; intento real de compra local de evento externo 409.
- Bad Bunny esta verificado en el registro real (bad_bunny_selected=True). La primera instantanea no contenia fechas suyas. No se agregaron fechas ni artistas ficticios.
- Ollama 0.24.0 real admite JSON estructurado. Modelo qwen2.5:1.5b. La pregunta de mayor a menor respondio 200 en 8.62 segundos despues de validar la direccion explicita; el primer artista coincidio con la consulta descendente compartida. Cercanos primero respondio 200 en 11.95 segundos y ayuda en 10.17 segundos. Sin JWT: 401.
- Hubo timeouts de 55 segundos e inversion de orden durante desarrollo: se redujo el esquema/generacion y se agrego validacion de direccion explicita con prueba. La ayuda usa instrucciones verificadas para evitar politicas inventadas por el modelo.

## Limites

La revision visual en navegador no se pudo ejecutar: computer-use fallo dos veces por native pipe de Windows no disponible. Se verificaron rutas autenticadas reales mediante el proxy, no una sesion visual. Kubernetes y VM no se desplegaron. Wikidata produjo errores 502/timeouts durante desarrollo; los ciclos fallidos conservaron la instantanea. El importador final queda activo y repite cada 1800 segundos. El ciclo final completo termino correctamente en 69.68 segundos: 60 cantantes verificados, Bad Bunny incluido en la seleccion, 239 eventos recibidos, 68 publicados y 171 omitidos. La web devuelve 89 eventos: 68 corresponden al ultimo feed y 21 de la instantanea anterior permanecen mientras se cumple la regla documentada de dos ausencias completas consecutivas. La seleccion por sitelinks y ciudadania es conservadora, no exhaustiva.

## Comandos principales ejecutados

```sh
docker compose -f docker-compose.yml -f docker-compose.local.yml build api catalog-sync
docker compose -f docker-compose.yml -f docker-compose.local.yml run --rm --no-deps migrate
docker compose -f docker-compose.yml -f docker-compose.local.yml up -d --no-deps api catalog-sync frontend
docker compose run --rm --no-deps api python -m src.probe_ticketmaster
docker compose run --rm --no-deps api python -m src.sync_ticketmaster --once
docker run --rm ... sound_pass-api python -m unittest discover -s tests -v
docker run --rm ... node:22-alpine node --check /frontend/script.js
```

Los puntos suspensivos corresponden a mounts de tests y database y a la URL de la base Docker desechable, no a credenciales de produccion. El procedimiento reproducible y las variables de VM estan en catalogo-ticketmaster.md. Se corrigio solo el DATABASE_URL privado local para coincidir con el usuario/contrasena ya validos de PostgreSQL; no se rotaron claves. Se conserva .env fuera de Git.

## Archivos modificados o nuevos

```text
 M .github/workflows/deploy.yml
 M .gitignore
 M README.md
 M backend/.env.example
 M backend/src/config.py
 M backend/src/models.py
 M backend/src/routers/assistant.py
 M backend/src/routers/concerts.py
 M backend/src/routers/orders.py
 M backend/src/schemas.py
 M backend/src/ticket_pdf.py
 M backend/src/ticketmaster.py
 M database/schema.sql
 M database/seed.sql
 M deploy/env.example
 M docker-compose.local.yml
 M docker-compose.yml
 M docs/ia.md
 M frontend/script.js
 M k8s/01-configmap.yaml
 M k8s/kustomization.yaml
 M k8s/secret.example.yaml
?? backend/src/artist_origins.py
?? backend/src/catalog.py
?? backend/src/probe_ticketmaster.py
?? backend/src/sync_ticketmaster.py
?? backend/tests/test_catalog.py
?? backend/tests/test_catalog_migrations.py
?? database/dev_seed.sql
?? database/migrations/002_ticketmaster_catalog.sql
?? docs/catalogo-ticketmaster.md
?? k8s/21-catalog-sync.yaml
```
