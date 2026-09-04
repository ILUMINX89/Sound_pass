# Gestión de Conciertos en la Nube

Plataforma web para la compra y gestión de boletos de conciertos. El proyecto está compuesto por una base de datos PostgreSQL, una API backend en FastAPI y una interfaz frontend, pensada para desplegarse en la nube mediante Docker.

## Estado actual del proyecto

El desarrollo va avanzado en backend y base de datos. El frontend existe como maqueta funcional (HTML/CSS/JS) con datos de ejemplo, y **todavía no está conectado a la API real**.

| Componente | Estado |
|---|---|
| Base de datos (schema + seed) |  Completo |
| API backend (FastAPI) |  Endpoints principales implementados |
| Autenticación (JWT) |  Registro, login, usuario actual |
| Frontend (HTML/CSS/JS) |  Maqueta con datos estáticos, sin integrar con la API |
| Despliegue (Docker Compose) |  DB + API dockerizados, falta servicio de frontend |

## Estructura del repositorio

```
Gestion_conciertos_nube/
├── backend/
│   ├── src/
│   │   ├── main.py          # Punto de entrada de la app FastAPI
│   │   ├── config.py        # Configuración vía variables de entorno
│   │   ├── database.py      # Conexión a PostgreSQL (SQLAlchemy)
│   │   ├── models.py        # Modelos ORM (users, venues, concerts, ticket_types, orders, order_items)
│   │   ├── schemas.py       # Esquemas Pydantic (request/response)
│   │   ├── security.py      # Hash de contraseñas y JWT
│   │   └── routers/
│   │       ├── auth.py      # /auth (registro, login, /me)
│   │       ├── concerts.py  # /concerts (listado y detalle)
│   │       └── orders.py    # /orders (compra, historial, cancelación)
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
├── database/
│   ├── schema.sql           # Definición de tablas, relaciones y constraints
│   └── seed.sql             # Datos de ejemplo (usuarios, venues, conciertos, boletos)
├── frontend/
│   ├── index.html           # Pantallas: home, listado, detalle, checkout, éxito, mis boletos, cancelación
│   ├── script.js            # Lógica de navegación e interacción (con datos mock por ahora)
│   └── style.css
└── docker-compose.yml       # Orquesta la base de datos y la API
```

## Funcionalidades implementadas

### Base de datos
- Tablas: `users`, `venues`, `concerts`, `ticket_types`, `orders`, `order_items`.
- Relaciones con llaves foráneas, restricciones (`CHECK`) de estado de orden, método de pago, precios y cantidades no negativas.
- Índices sobre fecha/género de concierto y sobre usuario/estado de orden.
- Datos semilla (`seed.sql`) con usuarios, recintos, conciertos y tipos de boleto de ejemplo.

### API backend (FastAPI)
- **Autenticación** (`/auth`):
  - `POST /auth/register` — creación de cuenta.
  - `POST /auth/login` — inicio de sesión con JWT.
  - `GET /auth/me` — datos del usuario autenticado.
- **Conciertos** (`/concerts`):
  - `GET /concerts` — listado con filtros por ciudad y género, y ordenamiento por fecha o precio.
  - `GET /concerts/{id}` — detalle de un concierto, incluyendo recinto y tipos de boleto.
- **Órdenes** (`/orders`):
  - `POST /orders` — creación de una compra (valida disponibilidad, calcula subtotal + tarifa de servicio, descuenta inventario).
  - `GET /orders/me` — historial de compras del usuario (filtrable por estado).
  - `GET /orders/{id}` — detalle de una orden puntual.
  - `POST /orders/{id}/cancel` — cancelación de una orden, con devolución de boletos al inventario.
- `GET /health` — endpoint de verificación de estado del servicio.

### Frontend (maqueta)
- Pantallas construidas en HTML/CSS/JS: inicio, listado de conciertos, detalle, checkout, confirmación de compra, "mis boletos" y cancelación.
- Actualmente usa datos de ejemplo definidos directamente en `script.js`; **falta conectar las llamadas a la API del backend** (login/registro, listado real de conciertos, creación y cancelación de órdenes).

### Infraestructura
- `docker-compose.yml` levanta la base de datos PostgreSQL (con `schema.sql` y `seed.sql` cargados automáticamente) y la API en un contenedor `api`.
- `Dockerfile` del backend basado en `python:3.12-slim`.
- Configuración de la API vía variables de entorno (`.env.example`): cadena de conexión, clave secreta JWT, tiempo de expiración del token y orígenes permitidos (CORS).

## Cómo ejecutar el proyecto

### Con Docker Compose (backend + base de datos)
```bash
docker compose up --build
```
Esto levanta:
- PostgreSQL en `localhost:5432`
- API en `http://localhost:8000` (documentación interactiva en `http://localhost:8000/docs`)

### Frontend
Por ahora el frontend es estático y puede abrirse directamente (`frontend/index.html`) o servirse con cualquier servidor estático, ya que aún no consume la API.

### Backend en local sin Docker
```bash
cd backend
pip install -r requirements.txt
cp .env.example .env   # ajustar valores si es necesario
uvicorn src.main:app --reload
```

## Pendiente / próximos pasos
- Conectar el frontend a la API (autenticación, listado dinámico de conciertos, flujo de compra y cancelación reales).
- Agregar el frontend como servicio dentro de `docker-compose.yml`.
- Migraciones con Alembic (la dependencia ya está incluida en `requirements.txt`, falta configurarla y generar la primera migración).
- Pruebas automatizadas para la API.
- Manejo de roles (por ejemplo, administración de conciertos y recintos).

## Stack tecnológico
- **Backend:** FastAPI, SQLAlchemy 2.0, Pydantic v2, PostgreSQL (psycopg2), JWT (python-jose), bcrypt/passlib.
- **Frontend:** HTML, CSS y JavaScript vanilla.
- **Infraestructura:** Docker y Docker Compose.
