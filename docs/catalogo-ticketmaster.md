# Catalogo Ticketmaster: operacion y alcance

La rama de trabajo conserva el asistente de la historia #71. No se ha asignado un numero de historia al catalogo ni se ha publicado en GitHub.

## Alcance solicitado y fuentes

La primera comprobacion real de Colombia devolvio HTTP 200, page.totalElements=0 y muestra vacia. Despues, el usuario pidio conciertos en cualquier pais, solo de cantantes de Estados Unidos, Mexico, Colombia, Argentina y Puerto Rico, incluyendo Bad Bunny. Esta configuracion local usa TICKETMASTER_SCOPE=artist_origin y TICKETMASTER_ARTIST_ORIGINS=US,MX,CO,AR,PR. Se conserva countryCode=CO en el modo country; en artist_origin se omite countryCode del evento deliberadamente.

Ticketmaster Discovery determina los eventos, artistas embebidos y fechas. Wikidata verifica personas vivas con ocupacion de cantante, rapero o cantautor y ciudadania en los paises seleccionados. Puerto Rico se verifica mediante la declaracion de origen/ciudadania Puerto Rico en Wikidata, sin confundirlo con el lugar donde ocurre un concierto. No se deduce nacionalidad del idioma, nombre, foto ni pais del recinto.

Para enfocar nombres conocidos se seleccionan, por origen, hasta 15 personas con mas sitelinks de Wikidata y un minimo de 20. Es un criterio editorial configurable, no una medicion de fama ni una lista exhaustiva. No hay una lista de artistas escrita a mano. Identidades ambiguas y actos musicales de origen no verificado se omiten; todos los actos musicales publicados deben superar el filtro. Esto puede omitir festivales y conciertos con teloneros no incluidos. Bad Bunny queda sujeto a verificacion y a que Ticketmaster tenga fechas futuras reales; no se inventan fechas para mostrarlo.

Solo se aceptan etiquetas de nombres verificadas, no aliases libres que puedan confundir un grupo con un solista. El registro se consulta en lotes, se conserva 24 horas en memoria en el proceso periodico y deja procedencia por concierto en artist_provenance. Si Wikidata falla, el ciclo completo falla sin publicar resultados parciales. El modo global consulta eventos por nombres verificados y contrasta las atracciones embebidas exactas y sus nombres verificados. No hace lookup de atracciones por cada fila.

## Arranque Docker y migracion

Conservar el archivo .env privado. DATABASE_URL debe apuntar a db:5432 dentro de Compose y coincidir con las credenciales del volumen existente. Cambiar POSTGRES_PASSWORD en Compose no cambia la contrasena de una base ya inicializada.

Antes de migrar, generar respaldo con pg_dump en formato custom desde el servicio db. En PowerShell usar subprocess con salida binaria a archivo; evitar redireccion binaria por versiones antiguas de PowerShell. En Linux:

```sh
mkdir -p backups
docker compose --env-file backend/.env exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > backups/soundpass-before-catalog.dump
docker compose --env-file backend/.env up -d db
docker compose --env-file backend/.env run --rm --no-deps migrate
docker compose --env-file backend/.env up -d --build
```

En desarrollo anadir `-f docker-compose.yml -f docker-compose.local.yml` a cada comando Compose. Este override ofrece frontend en http://localhost:5500 y usa el proxy existente. PostgreSQL no necesita un puerto del host. No usar down -v ni TRUNCATE.

La migracion 002_ticketmaster_catalog.sql es aditiva, transaccional y repetible sobre el esquema nuevo. Marca filas previas legacy/inactive con defaults, sin borrar usuarios, conciertos, ordenes, items ni boletos emitidos. Aumenta la longitud de nombres de artistas y eventos y admite hora nula. El servicio migrate ejecuta las migraciones antes de API e importador; el workflow copia el directorio y comprueba su ejecucion antes de reconstruir. El schema.sql es para instalaciones nuevas; no se ejecuta sobre volumen existente. dev_seed.sql es carga opcional de desarrollo; seed.sql normal no agrega demos.

Verificar conteos de users, orders, order_items e issued_tickets antes y despues; comprobar historial con JWT y PDF de una orden local. La prueba PostgreSQL dedicada verifica nueva instalacion y esquema legacy con ordenes, repeticion de migracion e IDs de importacion estables.

## Sincronizacion y diagnostico

```sh
docker compose --env-file backend/.env run --rm --no-deps api python -m src.probe_ticketmaster
docker compose --env-file backend/.env run --rm --no-deps api python -m src.sync_ticketmaster --once
docker compose --env-file backend/.env logs --tail=100 catalog-sync
curl http://localhost:5500/api/concerts/catalog-status
curl 'http://localhost:5500/api/concerts?sort=date'
```

El probe comprueba el modo por pais CO incluso cuando el catalogo publico esta configurado por origen global. Imprime unicamente estado HTTP, total y muestra publica. El importador periodico inicia un ciclo al arrancar y repite cada 1800 segundos; un fallo no termina el proceso. La ausencia de clave no bloquea cuenta ni historial.

Se descargan y validan todas las paginas antes de escribir. Las ventanas que superan 1000 filas se dividen y se deduplican IDs. Cambios de metadatos, paginas incompletas, errores 429/red, formatos invalidos o presupuestos agotados abortan el ciclo completo. El importador es serial, espera entre solicitudes, tiene como maximo un reintento ante 429 y respeta Retry-After hasta 30 segundos; una espera mayor aborta el ciclo. El modo global limita el conjunto a 100 solicitudes Discovery y 600 segundos de recorrido por ciclo. Los reintentos de red publicos de Wikidata estan acotados. Un bloqueo de sesion PostgreSQL exclusivo serializa procesos y se mantiene fuera de la transaccion de escritura durante la descarga.

Cancelados o eventos presentes pero inelegibles se retiran al completar el ciclo; ausencias requieren dos recorridos completos consecutivos del mismo alcance y ventana. Para horas desconocidas solo se aplica ausencia cuando toda la fecha local esta cubierta. Una fecha pasada se excluye al consultar aunque el importador no funcione. last_success_at se guarda tambien cuando el feed valido esta vacio. catalog-status diferencia unavailable, updated y stale (mas de dos intervalos desde el ultimo exito).

## Variables privadas para VM

TICKETMASTER_API_KEY; TICKETMASTER_SCOPE=artist_origin; TICKETMASTER_ARTIST_ORIGINS=US,MX,CO,AR,PR; TICKETMASTER_ARTISTS_PER_ORIGIN=15; TICKETMASTER_ARTIST_MIN_SITELINKS=20; TICKETMASTER_COUNTRY_CODE=CO; TICKETMASTER_WINDOW_DAYS=365; TICKETMASTER_SYNC_INTERVAL_SECONDS=1800. Conservar OLLAMA_BASE_URL privado, OLLAMA_MODEL=qwen2.5:1.5b y OLLAMA_TIMEOUT_SECONDS=55. La VM requiere conectividad privada a Ollama y HTTPS hacia Ticketmaster y Wikidata.

Kubernetes no se ha desplegado ni validado contra un cluster durante este cambio. Antes de aplicar k8s/, respaldar su PostgreSQL y ejecutar las migraciones SQL desde un cliente psql autorizado con ON_ERROR_STOP=1. No iniciar el Deployment API ni catalog-sync hasta verificar columnas y catalog_sync. Las variables van por ConfigMap y los valores privados por secret.yaml; hay una sola replica del importador y el bloqueo PostgreSQL tambien cubre ejecuciones manuales y multiples replicas.

## Restauracion

Detener API e importador antes de restaurar. Verificar el respaldo con pg_restore --list. Restaurar primero en una base nueva con pg_restore --exit-on-error --no-owner y las credenciales privadas, comprobar conteos, historial y PDFs, y apuntar DATABASE_URL a esa base validada. Conservar el volumen anterior para volver atras. No restaurar destructivamente sobre la base de trabajo sin un procedimiento aprobado. El rollback de codigo no requiere borrar las columnas aditivas.

## Pruebas Docker

Ejecutar unittest discover -s tests -v dentro de la imagen del backend con backend/tests montado en /app/tests. Usar APP_ENV=test y no fijar DATABASE_URL durante las pruebas de configuracion, ya que comprueban el valor por defecto. Para migracion real, montar database en /fixtures y configurar CATALOG_TEST_DATABASE_URL a una base desechable llamada catalog_test. Esa prueba elimina solamente los schemas catalog_legacy_test y catalog_new_test dentro de catalog_test. Nunca usar la base de usuarios como destino de pruebas.

Los fixtures son aislados; no se cargan en el catalogo publico. La validacion real y sus limitaciones quedan registradas en la entrega local.
