# Seguridad de API — issue #68

## Configuración preparada

`APP_ENV=local` conserva `/docs`, `/redoc` y `/openapi.json`. `staging` y
`production` desactivan las tres rutas y debug. Se rechazan claves JWT vacías,
de ejemplo, cortas o repetitivas; generar una con `openssl rand -hex 32`.
La comprobación no mide entropía: DevOps debe generar el secreto aleatoriamente.
`DATABASE_URL` debe configurarse y `ALLOWED_ORIGINS` queda vacío para mismo origen,
o contiene orígenes HTTPS explícitos para acceso cruzado.

Compose versionado usa nginx en el host, API en `127.0.0.1:8000` y PostgreSQL
solo en la red de Compose. Conserva `pgdata` y los montajes de inicialización.
`deploy/env.example` documenta variables ficticias. Configura `backend/.env` directamente en la VM y mantenlo fuera de la raíz pública. PostgreSQL existente
no cambia su contraseña al cambiar POSTGRES_PASSWORD: coordinar la credencial
real y DATABASE_URL sin reinicializar ni borrar el volumen. La URL debe usar el
servicio `db` y codificar los caracteres reservados de usuario/password.

En local, añadir explícitamente `-f docker-compose.local.yml` al Compose base
para acceder a PostgreSQL en `127.0.0.1:5433`; APP_ENV será local. Se requieren
las variables del Compose base también para este perfil. No ejecutar contenedores
ni despliegues durante esta sesión. No usar `docker compose down -v`.

## nginx y publicación

`deploy/nginx.conf.example` es una plantilla pendiente de adaptar y validar con
DevOps; no está instalada. Usa certificado válido, HTTP→HTTPS y
`location /api/` con `proxy_pass http://127.0.0.1:8000/`, eliminando `/api`.
Documentación devuelve 404 también en nginx, sin fallback a HTML.

Recursos según referencias actuales en HTML/CSS/JS: `index.html`, `style.css`,
`script.js`.
Las fuentes de Google, imágenes y Spotify son recursos externos; el único URL CSS
local adicional es una imagen data URI. No hay build que genere mapas. El workflow
copia exclusivamente esos tres archivos a la raíz web y nginx solo permite esas
rutas. Archivos antiguos de esa raíz deben inventariarse y retirarse tras respaldo;
la lista de nginx impide servirlos. `.env`, backend, Git y mapas quedan fuera.
`.dockerignore` evita incluir secretos y el entorno virtual en el contexto de build.

El workflow conserva el trigger `production` y exige la variable del environment
GitHub `PUBLIC_HTTPS_URL`, por ejemplo `https://soundpass.example.invalid`.
DevOps debe confirmar y configurar el host real antes de ejecutar CD. El health
check valida TLS (sin `-k`) y consulta `/api/health` por HTTPS.

## Autenticación y revisión del navegador

El helper común y la descarga PDF envían Bearer y comparten la base `/api`.
El PDF valida el tipo de contenido y revoca la URL del blob. Se conserva el escape
`esc` y el uso de `textContent` para texto no confiable.
Los scripts y las solicitudes seguirán siendo visibles en DevTools. No hay secretos
backend en la lista de recursos del navegador. El token sigue en localStorage:
no cambia el contrato ni se introduce autenticación por cookies.

Pedidos y PDF reutilizan `get_current_user` y filtran por propietario. Se conserva
404 para recursos ajenos. JWT exige firma HS256, exp y sub válidos, usuario existente
y un id compatible con el entero de PostgreSQL. No se registran tokens; se retiraron
cuerpos de error y excepciones externas de los logs de Spotify. Debug está apagado,
por lo que errores inesperados no entregan una traza al cliente.

## Validación pendiente antes de desplegar

- Confirmar rama desplegada, Compose efectivo (incluidos overrides), proyecto/volumen
  existente y nginx real. Un override antiguo puede volver a publicar puertos.
- Confirmar APP_ENV, SECRET_KEY, DATABASE_URL, ALLOWED_ORIGINS y credenciales de DB,
  Spotify y Ticketmaster mediante canal privado. Rotar secretos reales compartidos;
  rotar JWT invalida sesiones. Mantener las integraciones en backend.
- Revisar Docker y reglas IPv4/IPv6 tanto del host como de la nube: solo nginx
  público (80 redirección, 443 HTTPS); SSH limitado según política de DevOps.
- Validar `docker compose --env-file backend/.env config --quiet` con el entorno efectivo y `nginx -t`
  con certificado real. Si nginx resulta estar en Docker, usar servicio `api:8000`
  en red interna sin publicar el puerto; esta plantilla es para nginx en host.
- Respaldar configuración/BD, acordar reversión a imagen y configuración previas
  conservando `pgdata`. No ejecutar schema/seed manualmente sobre datos existentes.
- Probar `/api/docs`, `/api/redoc`, `/api/openapi.json` → 404 y health → 200.
- En navegador de preproducción, con cuentas sintéticas: registro, login, catálogo,
  compra, historial, cancelación y PDF; verificar rutas relativas, HTTPS y recursos
  públicos sin secretos/mapas. Verificar denegación cruzada sin cambiar el pedido.

Las pruebas automatizadas usan SQLite en memoria. No prueban locks/concurrencia de
PostgreSQL, TLS, firewall, proxy nginx real ni interacción visual del navegador.

## Escritura del catálogo

Los routers de conciertos y recintos incluyen flujos documentados de creación,
edición y eliminación. Se conserva su comportamiento: bloquearlos en el perfil
público ampliaría el alcance del #68 y eliminaría esos flujos. La autorización
administrativa del catálogo queda pendiente de una historia con roles definidos.
GET sigue disponible sin iniciar sesión.

## Evidencia local

La validación se realiza sobre una exportación aislada del índice, sin módulos,
configuración ni pruebas del asistente y sin `.env` local. Las pruebas usan SQLite
en memoria y verifican registro/login, catálogo, compra e historial de dos cuentas,
cancelación propia, PDF, 404 cruzados sin cambios de estado y rechazo de JWT
inválidos. También verifican claves y documentación por perfil.
Resultado: **5 pruebas de seguridad correctas** sobre el índice exportado con
`git checkout-index`, usando Python 3.12 y un entorno virtual nuevo instalado
únicamente desde `backend/requirements.txt`. Importación de FastAPI sin asistente
y `pip check` correctos; `git diff --cached --check` sin errores. YAML de Compose
y workflows válido; comprobados estáticamente los puertos y recursos publicados.
Las nueve pruebas anteriores mezclaban cinco de seguridad y cuatro del asistente;
esta batería excluye el bloqueo del catálogo y añade validación de BD/CORS.
Se añadieron casos JWT con exp nulo/lista/objeto: ahora devuelven 401 en vez de 500.

CI instala `backend/requirements.txt`, incluido httpx para TestClient, y ejecuta
la misma batería. Estas comprobaciones no sustituyen TLS, firewall ni PostgreSQL.

Compose, nginx y build Docker quedan pendientes de validación nativa con DevOps;
no se levantan contenedores ni se despliega durante esta sesión.

Referencias consultadas: [URLs de documentación de FastAPI](https://fastapi.tiangolo.com/tutorial/metadata/#docs-urls)
y [publicación de puertos de Docker](https://docs.docker.com/engine/network/port-publishing/).
