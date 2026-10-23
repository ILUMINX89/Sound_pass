# SoundPass — Gestión colaborativa de conciertos y boletas

> Documentación revisada contra la rama `development` el 23 de octubre de 2026.

Plataforma web de venta de boletos para conciertos, desarrollada por un equipo de 3 personas con metodología ágil (Kanban en GitHub Projects), integración y despliegue continuos con GitHub Actions y despliegue en la nube de Microsoft Azure.

Actividad de la asignatura **Desarrollo de aplicaciones en la nube**, Fundación Universitaria Los Libertadores.

| | |
|---|---|
| **Aplicación en producción** | http://20.80.47.160 |
| **Tablero del proyecto** | https://github.com/users/ILUMINX89/projects/2 |
| **Repositorio** | https://github.com/ILUMINX89/Sound_pass |
| **Guía de contribución** | [CONTRIBUTING.md](CONTRIBUTING.md) |
| **Bitácora de errores** | [docs/bitacora.md](docs/bitacora.md) |

---

## Tabla de contenido

- [Equipo de Desarrollo](#equipo-de-desarrollo)
- [Descripción del Proyecto](#descripción-del-proyecto)
- [Arquitectura](#arquitectura)
- [Modelo entidad–relación](#modelo-entidadrelación)
- [Modelo vista–controlador del proyecto](#modelo-vistacontrolador-del-proyecto)
- [Metodología](#metodología)
- [Sprints e historias](#sprints-e-historias)
- [Automatización con GitHub Actions](#automatización-con-github-actions)
- [Métricas del proyecto](#métricas-del-proyecto)
- [Instalación y uso en Linux](#instalación-y-uso-en-linux)
- [Despliegue en Azure](#despliegue-en-azure)
- [API REST](#api-rest)
- [Lecciones Aprendidas](#lecciones-aprendidas)
- [Estructura del repositorio](#estructura-del-repositorio)
- [Enlaces Importantes](#enlaces-importantes)

---

## Equipo de Desarrollo

| Rol | Integrante | GitHub |
|---|---|---|
| **Product Owner** | Esteban Parra | [@ILUMINX89](https://github.com/ILUMINX89) |
| **Backend Developer** | Esteban Parra | [@ILUMINX89](https://github.com/ILUMINX89) |
| **Frontend Developer / QA** | Sergio Arias | [@Sergioa-aR](https://github.com/Sergioa-aR) |
| **DevOps Engineer** | Camilo Montenegro | [@imaakro](https://github.com/imaakro) |

### Responsabilidades de cada integrante

La distribución conserva los roles definidos en el README anterior y concreta sus responsabilidades según las funcionalidades y tareas documentadas en el proyecto.

| Integrante | Rol | Responsabilidades |
|---|---|---|
| **Esteban Parra — @ILUMINX89** | **Product Owner** | Definir el alcance funcional, organizar y priorizar las historias de usuario, coordinar las entregas y comprobar que los criterios de aceptación correspondan a las necesidades del proyecto. |
| **Esteban Parra — @ILUMINX89** | **Backend Developer** | Desarrollar y mantener la API FastAPI, los modelos y contratos de datos, la autenticación y las operaciones de conciertos y órdenes. Integrar Spotify, Wikipedia y Ticketmaster; implementar la emisión de boletas PDF con QR y sus migraciones. Documentar los endpoints e informar las variables y dependencias necesarias para desplegarlos. |
| **Sergio Arias — @Sergioa-aR** | **Frontend Developer / QA** | Desarrollar las pantallas en HTML, CSS y JavaScript, mantener el diseño responsive y conectar la interfaz con la API. Presentar el catálogo, los detalles de conciertos y órdenes, el reproductor, las biografías, los próximos eventos y la galería. Verificar navegación, formularios, estados de carga y error, y los flujos de compra y gestión de boletas; registrar los fallos encontrados. |
| **Camilo Montenegro — @imaakro** | **DevOps Engineer** | Mantener Docker y Docker Compose, la infraestructura de Azure, nginx y los workflows de CI/CD. Gestionar la configuración del despliegue y sus secretos, verificar la ejecución de los checks y la disponibilidad posterior al despliegue. Mantener las automatizaciones de GitHub Projects, las plantillas de issues, la revisión del formato de commits y la documentación del proceso de contribución. |

### Responsabilidades compartidas

- Registrar el trabajo mediante issues y mantener actualizados sus datos y evidencias en el tablero.
- Crear las ramas desde `development`, usar commits con el formato acordado y abrir PRs vinculados a su historia.
- Revisar los cambios de otro integrante en **Files changed**, dejar un comentario y aprobar cuando corresponda antes del merge. Ningún integrante debe mergear su propio PR.
- Comprobar los criterios de aceptación, documentar las validaciones realizadas y reportar los pendientes de integración o despliegue.
- Mantener las credenciales reales fuera del repositorio y coordinar los cambios de configuración que necesite la VM.

Los roles indican la responsabilidad principal de cada integrante; las contribuciones puntuales a otras capas quedan reflejadas en los issues y PRs. Por ejemplo, la conexión del botón de descarga al PDF fue aportada por Esteban en el PR #49.

---

## Descripción del Proyecto

**Dominio:** sistema de eventos y venta de boletos.

SoundPass permite consultar un catálogo de conciertos, filtrarlo por ciudad y género, registrarse como usuario, comprar boletos de distintas categorías y consultar o cancelar las órdenes propias.

### Funcionalidades actuales

- Catálogo, filtros, precios, disponibilidad y cuenta regresiva del concierto.
- Registro e inicio de sesión con JWT; consulta y cancelación de órdenes propias.
- Compra con cargo de servicio de $6.000 COP por entrada. Los métodos de pago son simulados; no hay una pasarela de cobro integrada en el backend.
- Reproductor oficial de Spotify y galería con ampliación de imágenes del artista.
- Biografía breve desde Wikipedia en español, con enlace a la fuente.
- Próximas presentaciones desde Ticketmaster, con fecha, hora local, ciudad y recinto; son informativas y no representan inventario de SoundPass.
- Descarga autenticada de un PDF con una página y un QR persistente por entrada.

Las secciones externas muestran estados de carga, ausencia de resultados y errores sin bloquear la compra. Spotify puede devolver una misma fotografía en varias resoluciones. El QR identifica la entrada; todavía no existe un sistema de validación de ingreso o de prevención de reingreso.

El modelo de datos tiene **siete tablas** organizadas en dos cadenas de relación:

- **Catálogo:** un recinto (`venues`) aloja muchos conciertos (`concerts`), y cada concierto ofrece varios tipos de boleta (`ticket_types`) con su precio y disponibilidad.
- **Compra:** un usuario (`users`) genera órdenes (`orders`), y cada orden agrupa sus ítems (`order_items`) con la cantidad comprada.

| Tabla | Descripción | Relaciones |
|---|---|---|
| `users` | Cuentas registradas | 1:N con `orders` |
| `venues` | Recintos: nombre, ciudad, dirección, aforo | 1:N con `concerts` |
| `concerts` | Artista, gira, género, fecha y hora | N:1 con `venues`, 1:N con `ticket_types` |
| `ticket_types` | Categoría de boleta, precio, disponibilidad | N:1 con `concerts` |
| `orders` | Orden de compra con código, estado y total | N:1 con `users`, 1:N con `order_items` |
| `order_items` | Ítems de la orden con cantidad y precio unitario | N:1 con `orders` y `ticket_types` |
| `issued_tickets` | Código persistente de cada entrada emitida | N:1 con `order_items`; código público y consecutivo únicos |

---

## Arquitectura

- **Frontend:** HTML, CSS y JavaScript sin framework, servido por nginx
- **Backend:** FastAPI 0.115 + SQLAlchemy 2.0 (Python 3.12), autenticación JWT y contraseñas con bcrypt
- **Base de datos:** PostgreSQL 16
- **Infraestructura:** Microsoft Azure, máquina virtual Ubuntu (el profesor confirmó que se puede usar cualquier nube)
- **CI/CD:** GitHub Actions
- **Containerización:** Docker y Docker Compose

El navegador consume el frontend estático y la API mediante nginx. El proxy transforma `/api/concerts` en `/concerts` para FastAPI. El backend consulta PostgreSQL y los proveedores externos.

| Componente | Responsabilidad |
|---|---|
| nginx | Servir el frontend y dirigir `/api/` al backend |
| FastAPI | Autenticación, catálogo, órdenes, integraciones y emisión de PDF |
| PostgreSQL | Persistencia de usuarios, catálogo, compras y códigos de boletas |
| Spotify / Wikipedia / Ticketmaster | Información complementaria del artista |
| GitHub Actions | Verificación de código, automatización del tablero y despliegue |

Decisiones de diseño:

1. **Máquina virtual con Docker** para que el entorno local y el de producción sean idénticos: el mismo `docker-compose.yml` corre en ambos.
2. **nginx como proxy inverso.** El frontend y la API salen del mismo origen (`/` y `/api`), así el navegador no cruza orígenes y no hay problemas de CORS.
3. **Ninguna credencial en el código.** Las claves del servidor se generan dentro de la VM en un `docker-compose.override.yml` que no se versiona, y las de GitHub Actions están en *Secrets*.
4. **Puertos según el entorno.** El Compose versionado publica 8000 y 5432 en el host. En la VM se deben restringir mediante firewall y configuración de red; el repositorio por sí solo no demuestra qué puertos son accesibles desde internet.

---


## Modelo entidad–relación

El siguiente diagrama representa las siete tablas de PostgreSQL definidas en `database/schema.sql`, la migración de boletas y sus correspondencias en `backend/src/models.py`.

```mermaid
erDiagram
    users ||--o{ orders : realiza
    venues ||--o{ concerts : aloja
    concerts ||--o{ ticket_types : ofrece
    concerts ||--o{ orders : recibe
    orders ||--o{ order_items : contiene
    ticket_types ||--o{ order_items : clasifica
    order_items ||--o{ issued_tickets : genera

    users {
        integer id PK
        varchar full_name
        varchar email UK
        varchar password_hash
        timestamptz created_at
    }
    venues {
        integer id PK
        varchar name
        varchar city
        varchar address
        integer capacity
    }
    concerts {
        integer id PK
        varchar artist
        varchar tour_name
        varchar genre
        integer venue_id FK
        date event_date
        time event_time
        text description
        varchar image_url
        timestamptz created_at
    }
    ticket_types {
        integer id PK
        integer concert_id FK
        varchar name
        numeric price
        integer quantity_available
    }
    orders {
        integer id PK
        varchar order_code UK
        integer user_id FK
        integer concert_id FK
        varchar status
        varchar payment_method
        numeric subtotal
        numeric service_fee
        numeric total
        timestamptz created_at
        timestamptz cancelled_at
    }
    order_items {
        integer id PK
        integer order_id FK
        integer ticket_type_id FK
        integer quantity
        numeric unit_price
    }
    issued_tickets {
        integer id PK
        integer order_item_id FK
        integer sequence_number
        varchar public_code UK
        timestamptz created_at
    }
```

**Notación:** `PK` identifica una clave primaria, `FK` una clave foránea y `UK` un valor único. `||--o{` significa que cada registro hijo pertenece a exactamente un padre y el padre puede tener cero o muchos hijos.

| Relación | Cardinalidad | Interpretación |
|---|---|---|
| Usuario → órdenes | 1:N | Cada orden pertenece a un usuario; una cuenta puede no tener compras |
| Recinto → conciertos | 1:N | Cada concierto se realiza en un recinto |
| Concierto → tipos de boleta | 1:N | Un concierto ofrece categorías con precio e inventario propios |
| Concierto → órdenes | 1:N | Cada orden corresponde a un único concierto |
| Orden → ítems | 1:N | Cada ítem pertenece a una orden y registra cantidad y precio unitario |
| Tipo de boleta → ítems | 1:N | Una categoría puede aparecer en varias compras |
| Ítem → boletas emitidas | 1:N | Cada entrada individual emitida pertenece a un ítem de compra |

El diagrama muestra la cardinalidad admitida por las claves foráneas. En el flujo de compra, la orden se crea con sus ítems; las boletas individuales se generan en la primera descarga del PDF. Por eso un ítem puede existir sin registros en `issued_tickets` hasta ese momento.

### Restricciones y reglas del modelo

- `users.email`, `orders.order_code` e `issued_tickets.public_code` son únicos.
- El esquema SQL impide repetir la combinación `(concert_id, name)` en `ticket_types`.
- `issued_tickets` impide repetir `(order_item_id, sequence_number)`, y el consecutivo debe ser mayor que cero.
- Las cantidades compradas deben ser positivas; el esquema SQL exige precios e inventario no negativos.
- Una orden tiene estado `confirmed` o `cancelled`, y admite los métodos `card`, `pse` y `nequi`.
- El backend comprueba que los tipos de boleta comprados pertenezcan al concierto de la orden. Las claves foráneas, por separado, no expresan esa regla entre tablas.
- `order_items.unit_price` conserva el precio unitario de la compra, mientras `ticket_types.price` representa el precio del catálogo.
- El artista se guarda como texto en `concerts.artist`; no existe una tabla independiente de artistas. Spotify, Wikipedia y Ticketmaster son proveedores externos, no entidades persistidas como tablas propias.

---

## Modelo vista–controlador del proyecto

SoundPass utiliza un **frontend separado que consume una API REST**. Sus responsabilidades pueden explicarse mediante Modelo–Vista–Controlador (MVC), con controladores HTTP en FastAPI y vistas renderizadas por JavaScript en el navegador. Es una correspondencia arquitectónica: el proyecto no utiliza un framework MVC con plantillas HTML renderizadas en el servidor.

### Correspondencia con los archivos actuales

| Capa o responsabilidad | Archivos | Función en SoundPass |
|---|---|---|
| Modelo | `backend/src/models.py` | Entidades SQLAlchemy, relaciones y restricciones del dominio |
| Persistencia del modelo | `backend/src/database.py`, `database/schema.sql`, `database/migrations/` | Sesiones, conexión y estructura PostgreSQL |
| Vista | `frontend/index.html`, `frontend/style.css` y funciones de renderizado de `frontend/script.js` | Pantallas, formularios, catálogo, órdenes y detalle del concierto |
| Controlador HTTP | `backend/src/routers/auth.py`, `concerts.py`, `venues.py`, `orders.py`, `tickets.py` | Recibir solicitudes, validar permisos, ejecutar operaciones y devolver JSON o PDF |
| Interacción de la vista | Eventos, estado y llamadas `fetch` en `frontend/script.js` | Responder a acciones del usuario, invocar la API y actualizar la pantalla |
| Contratos de entrada y salida | `backend/src/schemas.py` | Validar y serializar datos mediante Pydantic |
| Servicios auxiliares | `spotify.py`, `wikipedia.py`, `ticketmaster.py`, `ticket_pdf.py` | Consultar proveedores o generar documentos |
| Seguridad y composición | `security.py`, `config.py`, `main.py` | JWT, configuración, registro de routers y middleware |

`schemas.py` define contratos de la API y no sustituye las entidades persistentes de `models.py`. Actualmente los routers también contienen lógica de negocio y consultas SQLAlchemy; no existe una capa de servicios de negocio separada para todas las operaciones. Asimismo, `script.js` reúne interacción, estado y renderizado de la vista.

### Diagrama de responsabilidades

```mermaid
graph TD
    V["Vista: HTML, CSS y JavaScript"]
    C["Controladores: routers FastAPI"]
    M["Modelo: entidades SQLAlchemy"]
    D[(PostgreSQL)]
    S["Servicios: proveedores y PDF"]
    E["Spotify, Wikipedia y Ticketmaster"]

    V -->|"Solicitud HTTP y JWT cuando aplica"| C
    C -->|"JSON o archivo PDF"| V
    C -->|"Consultas y operaciones"| M
    M -->|"Persistencia mediante sesión"| D
    C -->|"Información externa o documento"| S
    S -->|"Consultas a proveedores"| E
```

El acceso del navegador pasa por nginx y el prefijo `/api` en el despliegue descrito. El proxy es infraestructura y no representa una capa MVC.

### Ejemplo: compra y descarga de boletas

1. **Vista:** el usuario selecciona concierto, categoría y cantidad; `script.js` envía `POST /orders` con el token.
2. **Controlador:** `routers/orders.py` obtiene al usuario autenticado, comprueba el concierto y el inventario, calcula importes y coordina la transacción.
3. **Modelo:** se guardan `orders` y `order_items`, y se actualiza la disponibilidad de `ticket_types`.
4. **Vista:** la respuesta JSON permite presentar la compra y habilitar su descarga.
5. **Controlador de descarga:** `routers/tickets.py` recibe `GET /orders/{order_id}/tickets/pdf`, comprueba propiedad y estado de la orden, y consulta o crea `issued_tickets`.
6. **Servicio y vista:** `ticket_pdf.py` construye el PDF; el controlador lo devuelve y `script.js` inicia la descarga del archivo.

Esta separación permite mantener la presentación en el frontend, las operaciones HTTP en los routers y los datos persistentes en el modelo, aunque algunas responsabilidades todavía compartan archivo.

---


## Metodología

Trabajamos con **Kanban** en GitHub Projects, simulando **3 sprints**:

| Sprint | Fechas | Enfoque |
|---|---|---|
| Sprint 1 | 13 al 15 de octubre | Configuración del proyecto, seguridad y backend |
| Sprint 2 | 16 al 18 de octubre | Frontend, integración continua y automatización |
| Sprint 3 | 19 al 22 de octubre | Despliegue, documentación y mejoras pedidas por el profesor |

**Tablero:** `Backlog → Ready → In Progress → Review → Done`

**Campos personalizados:** Sprint (1, 2, 3), Prioridad (Alta, Media, Baja), Estimación (1, 2, 3, 5, 8), Tipo (Feature, Bug, Documentation, DevOps) y Rol (Backend, Frontend, DevOps, QA, Documentación). El responsable es la persona asignada al issue.

**Ramas:**

```
main                      versión estable (rama por defecto)
├── production            lo que está desplegado; cada merge despliega la app
└── development           integración del sprint
     ├── feature/sprintN-<funcionalidad>
     └── fix/<error>
```

**Flujo de trabajo:** issue con la plantilla → rama `feature/` desde `development` → commits con formato `tipo: descripción` → PR hacia `development` con `Closes #N` → revisión de otro miembro → merge → release a `production` (despliegue automático) → `main`.

El paso a paso completo para cualquier miembro está en [CONTRIBUTING.md](CONTRIBUTING.md).

---

## Sprints e historias

Corte: **23 de octubre de 2026**. La siguiente tabla distingue el estado del issue de la evidencia de integración. Un PR mergeado no demuestra por sí solo que la funcionalidad se haya probado en la VM.

| Issue | Historia o tarea | Autor del issue | Estado del issue | Evidencia |
|---|---|---|---|---|
| [#3](https://github.com/ILUMINX89/Sound_pass/issues/3) | Proteger credenciales del repositorio | @imaakro | Cerrado | [PR #1](https://github.com/ILUMINX89/Sound_pass/pull/1) mergeado |
| [#4](https://github.com/ILUMINX89/Sound_pass/issues/4) | Integración continua con GitHub Actions | @imaakro | Cerrado | [PR #2](https://github.com/ILUMINX89/Sound_pass/pull/2) mergeado |
| [#5](https://github.com/ILUMINX89/Sound_pass/issues/5) | Estrategia de ramas y plantilla de historias | @imaakro | Cerrado | Configuración de ramas documentada en el issue |
| [#6](https://github.com/ILUMINX89/Sound_pass/issues/6) | Agregar workflow de automatización del tablero | @imaakro | Cerrado | [PR #7](https://github.com/ILUMINX89/Sound_pass/pull/7) mergeado |
| [#8](https://github.com/ILUMINX89/Sound_pass/issues/8) | Mejoras de la interfaz | @Sergioa-aR | Cerrado | [PR #20](https://github.com/ILUMINX89/Sound_pass/pull/20) mergeado |
| [#9](https://github.com/ILUMINX89/Sound_pass/issues/9) | Adaptación responsive | @Sergioa-aR | Cerrado | [PR #23](https://github.com/ILUMINX89/Sound_pass/pull/23) mergeado |
| [#10](https://github.com/ILUMINX89/Sound_pass/issues/10) | Vista de detalle de orden | @Sergioa-aR | Cerrado | [PR #24](https://github.com/ILUMINX89/Sound_pass/pull/24) mergeado |
| [#11](https://github.com/ILUMINX89/Sound_pass/issues/11) | Plantillas de issues detalladas | @imaakro | Abierto | [PR #12](https://github.com/ILUMINX89/Sound_pass/pull/12) mergeado |
| [#13](https://github.com/ILUMINX89/Sound_pass/issues/13) | Rol y campos automáticos en el tablero | @imaakro | Cerrado | [PR #14](https://github.com/ILUMINX89/Sound_pass/pull/14) mergeado |
| [#15](https://github.com/ILUMINX89/Sound_pass/issues/15) | Revisión automática del formato de commits | @imaakro | Cerrado | [PR #16](https://github.com/ILUMINX89/Sound_pass/pull/16) mergeado |
| [#17](https://github.com/ILUMINX89/Sound_pass/issues/17) | Guía de contribución y bitácora de errores | @imaakro | Cerrado | [PR #18](https://github.com/ILUMINX89/Sound_pass/pull/18) mergeado |
| [#21](https://github.com/ILUMINX89/Sound_pass/issues/21) | Bug: no aparecen conciertos porque sus fechas ya pasaron | @imaakro | Cerrado | [PR #22](https://github.com/ILUMINX89/Sound_pass/pull/22) mergeado |
| [#25](https://github.com/ILUMINX89/Sound_pass/issues/25) | Despliegue continuo a la nube | @imaakro | Cerrado | [PR #26](https://github.com/ILUMINX89/Sound_pass/pull/26) mergeado |
| [#28](https://github.com/ILUMINX89/Sound_pass/issues/28) | Apartado de demos musicales por concierto en SoundPass | @Sergioa-aR | Cerrado | [PR #30](https://github.com/ILUMINX89/Sound_pass/pull/30) mergeado |
| [#31](https://github.com/ILUMINX89/Sound_pass/issues/31) | Cuenta regresiva y estados del concierto | @Sergioa-aR | Cerrado | [PR #32](https://github.com/ILUMINX89/Sound_pass/pull/32) mergeado |
| [#33](https://github.com/ILUMINX89/Sound_pass/issues/33) | Integrar el reproductor oficial de Spotify en el detalle de los conciertos | @ILUMINX89 | Cerrado | [PR #35](https://github.com/ILUMINX89/Sound_pass/pull/35) mergeado |
| [#34](https://github.com/ILUMINX89/Sound_pass/issues/34) | Carga de datos iniciales para SoundPass | @Sergioa-aR | Cerrado | [PR #36](https://github.com/ILUMINX89/Sound_pass/pull/36) mergeado |
| [#37](https://github.com/ILUMINX89/Sound_pass/issues/37) | Consultar biografía breve de artistas desde Wikipedia | @ILUMINX89 | Cerrado | [PR #38](https://github.com/ILUMINX89/Sound_pass/pull/38) mergeado |
| [#39](https://github.com/ILUMINX89/Sound_pass/issues/39) | Integración del reproductor oficial de Spotify en el detalle del concierto | @Sergioa-aR | Cerrado | [PR #42](https://github.com/ILUMINX89/Sound_pass/pull/42) mergeado |
| [#40](https://github.com/ILUMINX89/Sound_pass/issues/40) | Consultar próximos conciertos del artista con Ticketmaster | @ILUMINX89 | Cerrado | [PR #41](https://github.com/ILUMINX89/Sound_pass/pull/41) mergeado |
| [#43](https://github.com/ILUMINX89/Sound_pass/issues/43) | Consultar imágenes del artista para una minigalería | @ILUMINX89 | Cerrado | [PR #44](https://github.com/ILUMINX89/Sound_pass/pull/44) mergeado |
| [#45](https://github.com/ILUMINX89/Sound_pass/issues/45) | Descargar boletas en PDF con código QR individual | @ILUMINX89 | Cerrado | [PR #47](https://github.com/ILUMINX89/Sound_pass/pull/47) mergeado |
| [#46](https://github.com/ILUMINX89/Sound_pass/issues/46) | Visualización de la biografía del artista desde Wikipedia | @Sergioa-aR | Cerrado | [PR #50](https://github.com/ILUMINX89/Sound_pass/pull/50) mergeado |
| [#48](https://github.com/ILUMINX89/Sound_pass/issues/48) | Corregir la descarga de boletas para obtener el PDF con QR | @ILUMINX89 | Cerrado | [PR #49](https://github.com/ILUMINX89/Sound_pass/pull/49) mergeado |
| [#51](https://github.com/ILUMINX89/Sound_pass/issues/51) | Integración de próximos conciertos del artista | @Sergioa-aR | Cerrado | [PR #52](https://github.com/ILUMINX89/Sound_pass/pull/52) mergeado |
| [#53](https://github.com/ILUMINX89/Sound_pass/issues/53) | Galería de imágenes del artista | @Sergioa-aR | Cerrado | [PR #54](https://github.com/ILUMINX89/Sound_pass/pull/54) mergeado |

El issue #11 sigue abierto aunque su PR #12 está mergeado. El PR #35 contiene `Closes #N` en lugar de un número válido; aquí se relaciona con #33 por su contenido. Los PRs #50, #52 y #54 corresponden funcionalmente a #46, #51 y #53, aunque sus descripciones no incluyen `Closes`.

La release [PR #55](https://github.com/ILUMINX89/Sound_pass/pull/55) fue mergeada a `production` el 23 de octubre. El estado del workflow de despliegue se consulta en Actions.

---

## Automatización con GitHub Actions

| Workflow | Archivo | Cuándo corre | Qué hace |
|---|---|---|---|
| **CI** | `.github/workflows/ci.yml` | En cada PR | Instala dependencias y comprueba que el backend funcione |
| **Project Automation** | `.github/workflows/project-automation.yml` | Al crear, editar o asignar un issue y al abrir o mergear un PR | Llena Rol, Tipo, Prioridad, Sprint y Estimación desde la plantilla, pone etiquetas para filtrar y mueve la tarjeta: asignado → **In Progress**, PR abierto → **Review**, PR mergeado → **Done** |
| **Revisión de commits** | `.github/workflows/commits.yml` | En cada PR | Falla si algún commit no sigue el formato `tipo: descripción` |
| **Despliegue (CD)** | `.github/workflows/deploy.yml` | Al hacer merge a `production` (o a mano) | Copia el código a la VM por SSH, reconstruye los contenedores y verifica que `/api/health` responda |

**Plantillas de issue** (`.github/ISSUE_TEMPLATE/`): historia de usuario, bug y feedback de usuario externo, con campos obligatorios para que cualquier persona entienda qué hacer sin preguntar.

**Secretos usados:** `PROJECT_TOKEN` (editar el tablero), `VM_HOST`, `VM_USER`, `VM_SSH_KEY`, `VM_APP_DIR` (despliegue).

---

## Métricas del proyecto

Corte del repositorio al **23 de octubre de 2026**; conteo de issues y PRs, no exportación del tablero.

| Métrica | Valor |
|---|---|
| Issues registrados, sin contar PRs | 26 |
| Issues cerrados | 25 |
| Issues abiertos | 1 |
| PRs registrados | 28 |
| PRs mergeados | 27 |
| PRs mergeados hacia development | 25 |
| PRs abiertos | 0 |
| PRs cerrados sin merge | 1 |

No se conservan las antiguas cifras de velocity, burndown, lead time o cycle time: eran un corte anterior y no representan las integraciones actuales. Para recalcularlas por sprint hace falta contrastar los campos y el historial del tablero, las estimaciones y el inicio real de cada trabajo. Los issues cerrados tampoco equivalen automáticamente a historias aceptadas o pruebas completadas.

---

## Instalación y uso en Linux

### Requisitos

- Git y Docker Engine con Docker Compose v2.
- Python 3.12 y soporte `venv` para ejecutar sin contenedor o servir el frontend.
- PostgreSQL 16 si se utiliza una base propia.

### Clonar development

```bash
git clone --branch development https://github.com/ILUMINX89/Sound_pass.git
cd Sound_pass
```

### Opción A: backend y base de datos con Docker

Desde la raíz:

```bash
docker compose up -d --build
docker compose ps
curl -fsS http://127.0.0.1:8000/health
```

| Servicio | Dirección |
|---|---|
| Estado de API | http://127.0.0.1:8000/health |
| Swagger | http://127.0.0.1:8000/docs |
| OpenAPI | http://127.0.0.1:8000/openapi.json |
| PostgreSQL desde el host | `127.0.0.1:5432` |
| PostgreSQL desde el contenedor api | `db:5432` |

El Compose levanta dos servicios, `api` y `db`; no incluye un contenedor para frontend ni nginx. PostgreSQL ejecuta `schema.sql` y `seed.sql` únicamente cuando inicializa un volumen vacío. Una base existente conserva sus datos y requiere las migraciones correspondientes.

Para configurar CORS y proveedores en Docker, crear en la raíz un `docker-compose.override.yml` local:

```yaml
services:
  api:
    environment:
      SECRET_KEY: ${SECRET_KEY:?Definir SECRET_KEY}
      ALLOWED_ORIGINS: http://localhost:5500,http://127.0.0.1:5500
      SPOTIFY_CLIENT_ID: ${SPOTIFY_CLIENT_ID:-}
      SPOTIFY_CLIENT_SECRET: ${SPOTIFY_CLIENT_SECRET:-}
      TICKETMASTER_API_KEY: ${TICKETMASTER_API_KEY:-}
```

Definir los valores en variables de la terminal o en un `.env` local en la raíz usado por Compose y reconstruir con `docker compose up -d --build`. No versionar archivos locales con credenciales. El `backend/.env` no se carga automáticamente en los contenedores del Compose actual.

### Opción B: backend con un entorno virtual

Con PostgreSQL disponible y su esquema inicializado:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
cp .env.example .env
```

Editar `backend/.env` y establecer una única `DATABASE_URL` con el host y puerto reales. Si PostgreSQL viene del Compose actual y el backend corre en el host, el puerto es **5432**. El valor por defecto de `config.py` usa **5433**, por lo que debe ajustarse para ese caso.

```bash
python3 -m uvicorn src.main:app --host 127.0.0.1 --port 8000 --reload
```

Ejecutar desde `backend/` permite que la configuración encuentre el archivo `.env`.

### Frontend local

`frontend/script.js` utiliza `const API_URL = "/api"`. Para conservarlo, servir frontend y API desde un proxy con la configuración nginx de la sección de despliegue.

Para una prueba local sin proxy, cambiar **solo en la copia local** esa línea por:

```javascript
const API_URL = "http://127.0.0.1:8000";
```

Añadir `http://127.0.0.1:5500` a `ALLOWED_ORIGINS` en el entorno que ejecute el backend. Desde otra terminal, en la raíz del proyecto:

```bash
python3 -m http.server 5500 --bind 127.0.0.1 --directory frontend
```

Abrir http://127.0.0.1:5500. Restaurar `API_URL = "/api"` antes de subir cambios destinados al despliegue con nginx. Abrir el HTML con Live Server sin adaptar la URL o configurar un proxy no conecta automáticamente con FastAPI.

### Variables de entorno

| Variable | Uso |
|---|---|
| `DATABASE_URL` | Conexión SQLAlchemy: `postgresql+psycopg2://USUARIO:CLAVE@HOST:PUERTO/soundpass` |
| `SECRET_KEY` | Firma JWT; establecer una clave propia |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Duración del token; valor por defecto: 1440 |
| `ALLOWED_ORIGINS` | Orígenes CORS exactos separados por comas |
| `SPOTIFY_CLIENT_ID` | Identificador de aplicación Spotify |
| `SPOTIFY_CLIENT_SECRET` | Secreto Spotify; solo en backend |
| `TICKETMASTER_API_KEY` | Clave de Ticketmaster Discovery API |

Wikipedia y la generación de PDF no requieren claves adicionales. El archivo `.env.example` actual no enumera todas las variables de los proveedores; añadirlas al entorno que corresponda. En la VM también deben configurarse y pasarse al contenedor. No colocar secretos en JavaScript ni en el repositorio.

### Base existente: migración de boletas

Desde la raíz, usando PostgreSQL del Compose:

```bash
docker compose exec -T db psql -v ON_ERROR_STOP=1 -U soundpass_user -d soundpass < database/migrations/001_issued_tickets.sql
```

Para PostgreSQL externo, ejecutar el mismo archivo con `psql` usando el host, puerto y usuario correspondientes; no pasar directamente la URL con prefijo `postgresql+psycopg2` a `psql`.

La migración crea `issued_tickets` sin borrar las compras existentes. Si el usuario de migraciones es diferente al usuario de la API, conceder a este último permisos sobre la tabla y su secuencia. Reiniciar Docker no aplica automáticamente esta migración. No ejecutar `schema.sql` sobre una base con información que se quiera conservar: contiene `DROP TABLE`.

### Cuentas de demostración

| Correo | Contraseña de ejemplo |
|---|---|
| camila.torres@example.com | demo123 |
| andres.gomez@example.com | demo123 |

También se puede registrar una cuenta nueva. Los datos de ejemplo incluyen fechas de 2027; al pasar esas fechas dejarán de aparecer en el listado de conciertos futuros.

### Verificación básica

```bash
curl -fsS http://127.0.0.1:8000/health
curl -fsS http://127.0.0.1:8000/concerts
```

Probar registro, login, compra, consulta de órdenes, descarga de PDF y cancelación desde el navegador. La descarga debe conservar los mismos códigos al repetirse. Las pruebas reales con PostgreSQL y proveedores no quedan cubiertas por el check de importación del CI.

---

## Despliegue en Azure

### Despliegue automático (CD)

Al hacer merge de `development` a `production`, el workflow **Despliegue (CD)**:

1. Copia `backend`, `frontend`, `database` y `docker-compose.yml` a la VM por SSH.
2. Ejecuta `docker compose up -d --build` y copia el frontend a `/var/www/soundpass/`.
3. Verifica que `http://20.80.47.160/api/health` responda; si no, el workflow sale en rojo.

El workflow no ejecuta migraciones SQL ni configura automáticamente las claves de Spotify o Ticketmaster. Aplicar la migración y configurar esas variables en la VM antes de probar las nuevas funciones. La comprobación `/api/health` valida que el proceso responde, no verifica la conexión a PostgreSQL ni todos los flujos.

También se puede lanzar a mano en **Actions → Despliegue (CD) → Run workflow**.

### Preparación de la máquina virtual (una sola vez)

1. VM Ubuntu en Azure con reglas de entrada para los puertos **22** (SSH) y **80** (HTTP).
2. Instalar nginx y Docker, y agregar el usuario al grupo `docker` para no necesitar `sudo`:
   ```bash
   sudo apt-get update && sudo apt-get install -y nginx
   curl -fsSL https://get.docker.com | sudo sh
   sudo usermod -aG docker soundpass
   ```
3. Agregar la llave pública de despliegue en `~/.ssh/authorized_keys` y guardar la privada como secreto `VM_SSH_KEY` en GitHub.
4. Crear las credenciales del servidor con claves aleatorias, sin que nadie las vea:
   ```bash
   cd ~/Sound_pass
   DBPASS=$(openssl rand -hex 16)
   JWT=$(openssl rand -hex 32)
   cat > docker-compose.override.yml <<EOF
   services:
     db:
       restart: unless-stopped
       environment:
         POSTGRES_PASSWORD: $DBPASS
     api:
       restart: unless-stopped
       environment:
         DATABASE_URL: postgresql+psycopg2://soundpass_user:$DBPASS@db:5432/soundpass
         SECRET_KEY: $JWT
         ALLOWED_ORIGINS: http://20.80.47.160
   EOF
   ```
5. Configurar nginx en `/etc/nginx/sites-available/soundpass`:
   ```nginx
   server {
       listen 80;
       server_name _;
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

Los contenedores usan `restart: unless-stopped` y nginx corre como servicio del sistema, así que la app vuelve sola si la VM se reinicia.

---

## API REST

Documentación interactiva: `/docs` (Swagger UI). En producción todas las rutas van con el prefijo `/api` (por ejemplo `http://20.80.47.160/api/concerts`).

### Autenticación

| Método | Ruta | Descripción |
|---|---|---|
| POST | `/auth/register` | Crea una cuenta. Devuelve 201 |
| POST | `/auth/login` | Devuelve el token JWT |
| GET | `/auth/me` | Datos del usuario autenticado |

### Conciertos

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/concerts` | Lista conciertos futuros. Filtros: `city`, `genre`, `sort` (`date`, `price_asc`, `price_desc`) |
| GET | `/concerts/{id}` | Detalle con recinto y tipos de boleta |
| POST | `/concerts` | Crea un concierto. Devuelve 201 |
| PUT | `/concerts/{id}` | Actualiza un concierto |
| DELETE | `/concerts/{id}` | Elimina un concierto. Devuelve 204 |
| GET | `/concerts/{id}/ticket_types` | Tipos de boleta del concierto |
| GET | `/concerts/{id}/spotify` | Perfil y reproductor oficial del artista |
| GET | `/concerts/{id}/artist-gallery` | Imágenes del artista desde Spotify |
| GET | `/concerts/{id}/artist-bio` | Biografía breve desde Wikipedia en español |
| GET | `/concerts/{id}/upcoming-events` | Próximas presentaciones desde Ticketmaster |

Los endpoints actuales de creación, actualización y eliminación de conciertos y recintos no declaran autenticación ni un rol administrador. Incorporar ese control antes de habilitar gestión administrativa en un entorno público.

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
| POST | `/orders/{id}/cancel` | Cancela una orden y devuelve inventario |
| GET | `/orders/{id}/tickets/pdf` | Descarga autenticada de boletas PDF con QR individual |

Enviar `Authorization: Bearer <token>` en las operaciones protegidas. `/orders/me` permite `status_filter=confirmed` o `status_filter=cancelled`. El PDF requiere una orden confirmada del usuario; responde 404 para una orden inexistente o ajena y 409 si no puede emitirse. La emisión no descuenta nuevamente inventario.

### Utilidad

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/health` | Verificación de estado del servicio |

### Ejemplo de uso

```bash
# Registro
curl -X POST http://20.80.47.160/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"full_name":"Ana Gómez","email":"ana@ejemplo.com","password":"clave123"}'

# Ingreso
curl -X POST http://20.80.47.160/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"ana@ejemplo.com","password":"clave123"}'
```

| Código | Significado |
|---|---|
| 200 / 201 / 204 | Operación exitosa |
| 400 | Tipo de boleta inválido para ese concierto |
| 401 | Falta el token o es inválido |
| 404 | El recurso no existe |
| 409 | Inventario insuficiente o conflicto de estado de una orden |
| 502 / 503 | Error o indisponibilidad de un proveedor externo |
| 422 | El cuerpo de la petición no pasó la validación |

---

## Lecciones Aprendidas

El detalle de cada problema, con causa, solución, pros y contras, está en la [bitácora](docs/bitacora.md). Lo más importante:

**Lo que funcionó bien**
- **Automatizar el tablero.** Las tarjetas se mueven solas y los campos se llenan desde la plantilla, así el tablero refleja el estado real sin esfuerzo manual.
- **Plantillas y guía de contribución.** Con issues detallados y un `CONTRIBUTING.md` paso a paso, cualquier miembro puede tomar una tarea sin preguntarle a los demás.
- **Docker en local y en producción.** El mismo `docker-compose.yml` evitó diferencias entre la máquina de cada uno y la nube.

**Lo que salió mal y qué cambiamos**
- **Credenciales reales en el repositorio.** Se reemplazaron por valores de ejemplo; ahora los valores reales solo van en *Secrets* o en archivos que Git ignora.
- **Merges sin revisión.** Se acordó que nadie mergea su propio PR y se documentó en la guía.
- **`Closes #N` no funciona hacia `development`.** GitHub solo lo reconoce en PRs hacia la rama por defecto; la automatización ahora lee el número de la descripción del PR.
- **Permisos de GitHub Actions.** El token por defecto no podía leer los commits del PR; cada workflow ahora declara los permisos que necesita.
- **El despliegue dependía de una sola persona.** Se montó una VM nueva con una llave solo para despliegues, de modo que GitHub Actions despliega sin intervención humana.
- **Datos de ejemplo con fechas fijas.** Los conciertos de 2025 dejaron de mostrarse en 2026; las fechas de ejemplo deberían ser relativas a la fecha actual.

**Mejoras futuras**
- Proteger `development` y `production` con reglas que exijan 1 aprobación antes del merge.
- Revisar los PRs el mismo día: las métricas muestran que la espera de revisión es el seguimiento del trabajo.
- HTTPS con un dominio propio y Let's Encrypt.
- Pruebas automatizadas del backend dentro del CI.
- Usar IA en la automatización (por ejemplo, revisión automática de PRs o clasificación de issues) en la entrega final.

---

## Estructura del repositorio

```
Sound_pass/
├── README.md
├── CONTRIBUTING.md                 # Cómo trabajar en el proyecto paso a paso
├── docker-compose.yml
├── .github/
│   ├── ISSUE_TEMPLATE/             # Plantillas: historia, bug y feedback externo
│   └── workflows/
│       ├── ci.yml
│       ├── project-automation.yml
│       ├── commits.yml
│       └── deploy.yml
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── .env.example
│   └── src/
│       ├── main.py
│       ├── config.py
│       ├── database.py
│       ├── models.py
│       ├── schemas.py
│       ├── spotify.py
│       ├── wikipedia.py
│       ├── ticketmaster.py
│       ├── ticket_pdf.py
│       ├── security.py
│       └── routers/
│           ├── auth.py
│           ├── concerts.py
│           ├── venues.py
│           ├── orders.py
│           └── tickets.py
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── script.js
├── database/
│   ├── schema.sql
│   ├── seed.sql
│   └── migrations/
│       └── 001_issued_tickets.sql
└── docs/
    ├── api-wikipedia.md
    ├── bitacora.md                 # Errores, causas, soluciones, pros y contras
    └── feedback-externo.md         # Pruebas con usuarios fuera del equipo
```

---

## Enlaces Importantes

- [Aplicación](http://20.80.47.160)
- [GitHub Project](https://github.com/users/ILUMINX89/projects/2)
- [Repositorio](https://github.com/ILUMINX89/Sound_pass)
- [GitHub Actions](https://github.com/ILUMINX89/Sound_pass/actions)
- [Pull requests](https://github.com/ILUMINX89/Sound_pass/pulls?q=is%3Apr)
- [Guía de contribución](CONTRIBUTING.md)
- [Bitácora de errores](docs/bitacora.md)
