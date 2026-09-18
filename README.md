# SoundPass — Plataforma de venta de boletos para conciertos

Aplicación web full-stack desplegada de extremo a extremo en Microsoft Azure.
Actividad integradora de la asignatura **Desarrollo de aplicaciones en la nube**,
Fundación Universitaria Los Libertadores.

**Aplicación en producción:** http://68.155.151.9

---

## Tabla de contenido

- [Descripción del proyecto](#descripción-del-proyecto)
- [Integrantes](#integrantes)
- [Stack tecnológico](#stack-tecnológico)
- [Arquitectura del sistema](#arquitectura-del-sistema)
- [Modelo de datos](#modelo-de-datos)
- [API REST](#api-rest)
- [Instalación local](#instalación-local)
- [Despliegue en Azure](#despliegue-en-azure)
- [Credenciales de prueba](#credenciales-de-prueba)
- [Problemas encontrados y soluciones](#problemas-encontrados-y-soluciones)
- [Capturas de pantalla](#capturas-de-pantalla)
- [Estructura del repositorio](#estructura-del-repositorio)

---

## Descripción del proyecto

**Dominio elegido:** sistema de eventos y venta de boletos.

SoundPass permite consultar un catálogo de conciertos, filtrarlo por ciudad y
género, registrarse como usuario, comprar boletos de distintas categorías y
consultar o cancelar las órdenes propias.

El enunciado pedía un CRUD completo sobre al menos dos entidades relacionadas.
El modelo final tiene **seis tablas** organizadas en dos cadenas de relación:

- **Catálogo:** un recinto (`venues`) aloja muchos conciertos (`concerts`), y
  cada concierto ofrece varios tipos de boleta (`ticket_types`) con su precio y
  disponibilidad.
- **Compra:** un usuario (`users`) genera órdenes (`orders`), y cada orden
  agrupa sus ítems (`order_items`) con la cantidad comprada.

La base viene poblada con 13 conciertos de prueba en ocho ciudades de Colombia.

---

## Integrantes

- Sergio Arias
- Esteban Parra
- Camilo Montenegro

---

## Stack tecnológico

| Capa | Tecnología |
|---|---|
| Backend | FastAPI 0.115 + SQLAlchemy 2.0 (Python 3.12) |
| Base de datos | PostgreSQL 16 |
| Frontend | HTML, CSS y JavaScript sin framework |
| Autenticación | JWT (python-jose) + bcrypt vía passlib |
| Contenedores | Docker + Docker Compose |
| Servidor web | nginx (archivos estáticos y proxy inverso) |
| Nube | Microsoft Azure — Máquina Virtual Ubuntu 24.04 |

**Servicios cloud implementados:** Azure Virtual Machines, Network Security
Group (reglas de entrada) y disco administrado. Todos los componentes viven en
el mismo proveedor, como exige el enunciado.

---

## Arquitectura del sistema

```
                    ┌──────────────────────────────────────────────────────┐
                    │        Azure · Máquina Virtual Ubuntu 24.04          │
                    │                  68.155.151.9                        │
   Navegador        │                                                      │
   ──────────►  :80 │  ┌──────────┐    ┌───────────────┐   ┌─────────────┐ │
                    │  │  nginx   │───►│   FastAPI     │──►│ PostgreSQL  │ │
                    │  │          │    │ contenedor    │   │ contenedor  │ │
                    │  │ /  → web │    │    :8000      │   │    :5432    │ │
                    │  │ /api → ↗ │    └───────────────┘   └─────────────┘ │
                    │  └──────────┘        red interna de Docker           │
                    └──────────────────────────────────────────────────────┘
```

Decisiones de diseño relevantes:

1. **Máquina virtual con Docker** en lugar de servicios administrados, para que
   el entorno local y el de producción sean idénticos: el mismo
   `docker-compose.yml` corre en ambos.
2. **nginx como proxy inverso.** El frontend y la API se sirven desde el mismo
   origen (`http://68.155.151.9` y `http://68.155.151.9/api`), de modo que el
   navegador nunca cruza orígenes y el problema de CORS desaparece en vez de
   administrarse.
3. **Configuración por variables de entorno.** Ninguna credencial está en el
   código: la cadena de conexión, la clave de firma JWT y los orígenes
   permitidos se inyectan como variables.
4. **Superficie mínima expuesta.** Solo el puerto 80 está abierto al exterior.
   La API (8000) y la base de datos (5432) solo son alcanzables desde la red
   interna de Docker.

---

## Modelo de datos

Diagrama entidad-relación: [`database/diagram.png`](database/diagram.png)
Esquema completo: [`database/schema.sql`](database/schema.sql)
Datos de prueba: [`database/seed.sql`](database/seed.sql)

| Tabla | Descripción | Relaciones |
|---|---|---|
| `users` | Cuentas registradas | 1:N con `orders` |
| `venues` | Recintos: nombre, ciudad, dirección, aforo | 1:N con `concerts` |
| `concerts` | Artista, gira, género, fecha y hora | N:1 con `venues`, 1:N con `ticket_types` |
| `ticket_types` | Categoría de boleta, precio, disponibilidad | N:1 con `concerts` |
| `orders` | Orden de compra con código, estado y total | N:1 con `users`, 1:N con `order_items` |
| `order_items` | Ítems de la orden con cantidad y precio unitario | N:1 con `orders` y `ticket_types` |

---

## API REST

Documentación interactiva generada por FastAPI: `/docs` (Swagger UI).
Documentación detallada: [`docs/api-documentation.md`](docs/api-documentation.md)

### Autenticación

| Método | Ruta | Descripción |
|---|---|---|
| POST | `/auth/register` | Crea una cuenta. Devuelve 201 |
| POST | `/auth/login` | Devuelve el token JWT |
| GET | `/auth/me` | Datos del usuario autenticado |

### Conciertos

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/concerts` | Lista conciertos futuros. Filtros: `city`, `genre`, `sort` |
| GET | `/concerts/{id}` | Detalle con recinto y tipos de boleta |
| POST | `/concerts` | Crea un concierto. Devuelve 201 |
| PUT | `/concerts/{id}` | Actualiza un concierto |
| DELETE | `/concerts/{id}` | Elimina un concierto. Devuelve 204 |
| GET | `/concerts/{id}/ticket_types` | Relación entre entidades |

El parámetro `sort` acepta `date`, `price_asc` o `price_desc`.

### Recintos

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/venues` | Lista todos los recintos |
| POST | `/venues` | Crea un recinto. Devuelve 201 |
| DELETE | `/venues/{id}` | Elimina un recinto. Devuelve 204 |

### Órdenes (requieren token)

| Método | Ruta | Descripción |
|---|---|---|
| POST | `/orders` | Crea una orden con sus ítems. Devuelve 201 |
| GET | `/orders/me` | Órdenes del usuario autenticado |
| GET | `/orders/{id}` | Detalle de una orden propia |
| POST | `/orders/{id}/cancel` | Cancela una orden |

### Utilidad

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/health` | Verificación de estado del servicio |

### Ejemplo de uso

```bash
# Registro
curl -X POST http://68.155.151.9/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"full_name":"Ana Gómez","email":"ana@ejemplo.com","password":"clave123"}'

# Ingreso
curl -X POST http://68.155.151.9/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"ana@ejemplo.com","password":"clave123"}'

# Compra (reemplazar <TOKEN> por el access_token recibido)
curl -X POST http://68.155.151.9/api/orders \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"concert_id":4,"payment_method":"card","items":[{"ticket_type_id":1,"quantity":2}]}'
```

### Códigos de estado

| Código | Significado |
|---|---|
| 200 / 201 / 204 | Operación exitosa |
| 400 | Tipo de boleta inválido para ese concierto |
| 401 | Falta el token o es inválido |
| 404 | El recurso no existe |
| 409 | No hay disponibilidad suficiente |
| 422 | El cuerpo de la petición no pasó la validación |

Los errores se devuelven como `{"detail": "mensaje"}`.

---

## Instalación local

**Requisitos:** Docker y Docker Compose.

```bash
git clone https://github.com/[usuario]/Gestion_conciertos_nube.git
cd Gestion_conciertos_nube
docker compose up -d --build
```

Docker ejecuta `schema.sql` y `seed.sql` automáticamente la primera vez que
arranca el contenedor de PostgreSQL, así que la base queda poblada sin pasos
adicionales.

- API: http://127.0.0.1:8000
- Documentación: http://127.0.0.1:8000/docs
- Frontend: abrir `frontend/index.html` con Live Server (puerto 5500), o
  servirlo con `python3 -m http.server 5500` desde la carpeta `frontend/`.

En local, `frontend/script.js` debe apuntar a `http://127.0.0.1:8000`.

### Variables de entorno

Copiar `backend/.env.example` a `backend/.env` y ajustar:

| Variable | Descripción |
|---|---|
| `DATABASE_URL` | Cadena de conexión SQLAlchemy a PostgreSQL |
| `SECRET_KEY` | Clave de firma de los tokens JWT |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Vigencia del token (por defecto 1440) |
| `ALLOWED_ORIGINS` | Orígenes permitidos por CORS, separados por coma |

---

## Despliegue en Azure

### 1. Máquina virtual

Se creó una VM Ubuntu 24.04 en Azure con IP pública estática. En el Network
Security Group se habilitaron dos reglas de entrada:

| Puerto | Uso |
|---|---|
| 22 | Administración por SSH |
| 80 | Tráfico HTTP público |

El puerto 5432 (PostgreSQL) y el 8000 (API) **no se exponen**.

### 2. Aplicación

```bash
ssh soundpass@68.155.151.9

git clone https://github.com/[usuario]/Gestion_conciertos_nube.git
cd Gestion_conciertos_nube
```

Se crea un archivo `docker-compose.override.yml` (no versionado) con las
credenciales reales del servidor:

```yaml
services:
  api:
    build: ./backend
    container_name: soundpass-api
    restart: unless-stopped
    environment:
      DATABASE_URL: postgresql+psycopg2://soundpass_user:<CLAVE>@db:5432/soundpass
      SECRET_KEY: <CLAVE_JWT>
      ALLOWED_ORIGINS: http://68.155.151.9
    ports:
      - "8000:8000"
    depends_on:
      db:
        condition: service_healthy
```

Y se levanta todo:

```bash
sudo docker compose up -d --build
sudo docker compose ps
curl http://127.0.0.1:8000/health
```

### 3. Servidor web

```bash
sudo apt update && sudo apt install -y nginx
sudo mkdir -p /var/www/soundpass
sudo cp frontend/* /var/www/soundpass/
```

Configuración en `/etc/nginx/sites-available/soundpass`:

```nginx
server {
    listen 80;
    server_name 68.155.151.9;

    root /var/www/soundpass;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000/;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

```bash
sudo ln -sf /etc/nginx/sites-available/soundpass /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
```

En el servidor, la primera línea de `script.js` queda como
`const API_URL = "/api";` para que todo salga del mismo origen.

### 4. Verificación

```bash
curl -I http://127.0.0.1/            # 200 OK, text/html
curl http://127.0.0.1/api/concerts   # JSON con los conciertos
```

### Disponibilidad

Los contenedores usan `restart: unless-stopped` y nginx corre como servicio del
sistema, de modo que la aplicación vuelve sola si la máquina se reinicia.

---

## Credenciales de prueba

Puede registrarse una cuenta nueva desde la aplicación, o usar:

| Correo | Contraseña |
|---|---|
| [completar si hay usuario semilla] | [completar] |

Las contraseñas se almacenan con hash bcrypt; nunca en texto plano.

---

## Problemas encontrados y soluciones

**El frontend cargaba pero ninguna petición respondía.**
El frontend y la API se servían en puertos distintos, así que el navegador los
trataba como orígenes separados y bloqueaba las peticiones por política de CORS.
En vez de mantener una lista de orígenes permitidos, se puso nginx al frente
como proxy inverso: ahora todo sale del mismo origen y el problema desaparece.

**La página respondía dentro de la VM pero no desde internet.**
`curl http://127.0.0.1` funcionaba, pero el navegador no llegaba. La causa era
el Network Security Group de Azure, que filtra el tráfico antes de que alcance
el sistema operativo. Abrir el puerto en el servidor no basta: hay que agregar
también la regla de entrada en Azure.

**La API no levantaba junto a la base de datos.**
El `docker-compose.yml` del servidor solo declaraba el servicio de PostgreSQL.
Se agregó el servicio `api` mediante un archivo de override, con
`depends_on: condition: service_healthy` para que espere a que la base pase su
healthcheck antes de arrancar.

**Credenciales de ejemplo iguales a las de producción.**
El `.env.example` del repositorio traía credenciales de muestra que coincidían
con las del despliegue. Se generó una contraseña aleatoria directamente en el
servidor, almacenada solo en el archivo de override, que no se versiona.

---

## Capturas de pantalla

Disponibles en [`docs/screenshots/`](docs/screenshots/):

- Catálogo de conciertos con filtros aplicados
- Detalle de un concierto con sus tipos de boleta
- Formulario de registro e ingreso
- Proceso de compra y confirmación de la orden
- Vista de "Mis tickets"
- Documentación Swagger en `/docs`
- Recursos desplegados en el portal de Azure
- Consulta a PostgreSQL mostrando una orden recién creada

---

## Estructura del repositorio

```
Gestion_conciertos_nube/
├── README.md
├── docker-compose.yml
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── .env.example
│   └── src/
│       ├── main.py             # Aplicación FastAPI y CORS
│       ├── config.py           # Configuración por variables de entorno
│       ├── database.py         # Motor y sesiones de SQLAlchemy
│       ├── models.py           # Modelos ORM
│       ├── schemas.py          # Esquemas Pydantic
│       ├── security.py         # Hash de contraseñas y JWT
│       └── routers/
│           ├── auth.py
│           ├── concerts.py
│           ├── venues.py
│           └── orders.py
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── script.js
├── database/
│   ├── schema.sql
│   ├── seed.sql
│   └── diagram.png
├── docs/
│   ├── api-documentation.md
│   ├── deployment-guide.md
│   └── screenshots/
└── video/
    └── sustentacion.mp4
```

---

## Seguridad

- Contraseñas almacenadas con hash bcrypt.
- Sesiones mediante token JWT firmado, con expiración configurable.
- Las rutas de compra y consulta de órdenes rechazan peticiones sin token.
- Ninguna credencial en el repositorio: todo por variables de entorno.
- Validación de entradas con Pydantic antes de tocar la base.
- Consultas a través del ORM, sin construir SQL concatenando cadenas.
- Un solo puerto público; base de datos y API aisladas en la red interna.

**Pendiente:** HTTPS. La aplicación se sirve por HTTP porque no se cuenta con un
dominio propio. Con un dominio, el certificado se resolvería con Let's Encrypt y
certbot sobre el mismo nginx.
