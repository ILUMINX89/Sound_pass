# Guía de contribución — SoundPass

Esta guía existe para que **cualquier miembro del equipo pueda trabajar solo**, sin tener que preguntarle a los demás cómo se hace algo. Si algo de aquí no está claro o no funciona, corrígelo en un PR y anótalo en la [bitácora](docs/bitacora.md).

## Índice

1. [Preparar el entorno](#1-preparar-el-entorno)
2. [Elegir qué hacer](#2-elegir-qué-hacer)
3. [Ramas](#3-ramas)
4. [Commits](#4-commits)
5. [Pull requests y revisión](#5-pull-requests-y-revisión)
6. [Cómo arreglar un commit](#6-cómo-arreglar-un-commit)
7. [Cuando algo sale mal](#7-cuando-algo-sale-mal)
8. [Release y despliegue](#8-release-y-despliegue)

---

## 1. Preparar el entorno

**Requisitos:** Git, Docker Desktop y VS Code.

```bash
git clone https://github.com/ILUMINX89/Sound_pass.git
cd Sound_pass
git config user.name "Tu Nombre"
git config user.email "el-correo-de-tu-github"
docker compose up -d --build
```

| Qué | Dónde |
|---|---|
| API | http://127.0.0.1:8000 |
| Documentación de la API (Swagger) | http://127.0.0.1:8000/docs |
| Frontend | abrir `frontend/index.html` con Live Server |

La base de datos se crea y se llena sola con `database/schema.sql` y `database/seed.sql` la primera vez.
Para empezar desde cero: `docker compose down -v` y otra vez `docker compose up -d --build`.

> Nunca subas contraseñas ni claves reales. `.env.example` solo lleva valores de ejemplo; los reales van en `backend/.env` (que Git ignora) o en los *Secrets* del repositorio.

## 2. Elegir qué hacer

1. Abre el tablero [SoundPass](https://github.com/users/ILUMINX89/projects/2).
2. Toma una tarjeta de la columna **Ready** que sea de tu rol (filtra con `rol:` en la barra de búsqueda o usa la vista de tu rol).
3. **Asígnatela.** La automatización la mueve sola a **In Progress**.
4. Si vas a crear una historia nueva, usa **Issues → New issue → Historia de usuario**. Al crearla, la automatización le pone las etiquetas y llena Rol, Tipo, Prioridad, Sprint y Estimación en el tablero.

Una buena historia se entiende **sin preguntarle nada a quien la escribió**: dice qué existe hoy, qué archivos tocar y cómo comprobar que quedó bien.

## 3. Ramas

| Rama | Para qué | Quién escribe en ella |
|---|---|---|
| `main` | Versión estable y rama por defecto | Solo por PR desde `production` |
| `production` | Lo que está desplegado en la nube. Cada merge aquí despliega la app | Solo por PR desde `development` |
| `development` | Integración de todo el trabajo del sprint | Solo por PR desde ramas `feature/` o `fix/` |
| `feature/sprintN-nombre` | Una historia de usuario | Quien tiene la historia |
| `fix/nombre` | Corregir un bug | Quien tiene el bug |

Siempre se crea la rama desde `development` actualizada:

```bash
git checkout development
git pull
git checkout -b feature/sprint3-filtro-fecha
```

## 4. Commits

Formato (lo revisa automáticamente el workflow **Revisión de commits** en cada PR):

```
tipo: descripción corta en minúscula y en infinitivo
```

| Tipo | Cuándo usarlo |
|---|---|
| `feat` | Funcionalidad nueva |
| `fix` | Corrección de un error |
| `docs` | Solo documentación |
| `style` | Formato, sin cambiar lógica |
| `refactor` | Reorganizar código sin cambiar lo que hace |
| `test` | Pruebas |
| `ci` | Workflows de GitHub Actions |
| `chore` | Mantenimiento (dependencias, configuración) |
| `perf` | Mejora de rendimiento |
| `build` | Docker, compilación |
| `revert` | Deshacer un commit anterior |

Opcionalmente se indica la parte del código entre paréntesis: `feat(backend): ...`, `fix(frontend): ...`.

| ✅ Bien | ❌ Mal | Por qué |
|---|---|---|
| `feat(backend): agregar filtro de conciertos por fecha` | `cambios` | No dice qué cambió |
| `fix(frontend): mostrar error cuando el login falla` | `arreglé el login y el css y otras cosas` | Mezcla varios cambios |
| `docs: explicar cómo correr la app con docker` | `Update README.md` | No dice qué se documentó |

Reglas:

- **Un commit = un cambio.** Si en la descripción necesitas una "y", probablemente son dos commits.
- Máximo ~70 caracteres en la primera línea.
- Si el porqué no es obvio, explícalo en el cuerpo del commit, dejando una línea en blanco después del título.

## 5. Pull requests y revisión

1. `git push -u origin feature/sprint3-filtro-fecha`
2. Abre el PR con **base: `development`**.
3. En la descripción escribe `Closes #N` (el número de la historia). La tarjeta pasa sola a **Review**.
4. Pide revisión a **otra persona** del equipo.
5. Espera que el **CI** y la **Revisión de commits** salgan en verde.
6. **Nadie mergea su propio PR.** Quien revisa aprueba y hace el merge. La tarjeta pasa sola a **Done**.

Al revisar un PR:

- Descarga la rama y pruébala: `git fetch && git checkout nombre-de-la-rama && docker compose up -d --build`.
- Revisa los criterios de aceptación de la historia uno por uno.
- Si algo falta, usa **Request changes** con un comentario concreto (qué, dónde y por qué).

## 6. Cómo arreglar un commit

Primero identifica tu caso:

| Situación | Qué hacer |
|---|---|
| El mensaje del último commit está mal y **no** has hecho push | `git commit --amend -m "fix: mensaje correcto"` |
| Olvidaste un archivo en el último commit y **no** has hecho push | `git add archivo` y luego `git commit --amend --no-edit` |
| Ya hiciste push, pero es **tu** rama `feature/` y nadie más trabaja en ella | Corrige con `--amend` como arriba y luego `git push --force-with-lease` |
| Varios commits seguidos con mensajes mal en **tu** rama | `git reset --soft HEAD~3` (3 = cuántos commits) y vuelve a hacer los commits bien; luego `git push --force-with-lease` |
| El commit con el error **ya está en `development`, `production` o `main`** | No se reescribe la historia. Crea una rama `fix/...` y usa `git revert <sha>`; abre un PR con el revert |
| Hiciste el commit en la **rama equivocada** (por ejemplo en `development` local) | Ve a la rama correcta y tráelo: `git checkout mi-rama` y `git cherry-pick <sha>`. Luego limpia la otra rama: `git checkout development` y `git reset --hard origin/development` |
| Quieres ver qué cambió un commit antes de decidir | `git show <sha>` o `git log --oneline -10` para ver los últimos |

⚠️ **Nunca** uses `git push --force` sobre `development`, `production` o `main`: borraría el trabajo de los demás.

## 7. Cuando algo sale mal

Todo error, bloqueo o decisión importante se anota en la [bitácora](docs/bitacora.md) con el formato que ahí se explica: qué pasó, la causa, cómo se resolvió, los pros y contras de la solución y qué aprendimos. Así el siguiente que se encuentre con lo mismo no pierde tiempo.

## 8. Release y despliegue

Al final de cada sprint:

1. PR de `development` → `production`, revisado por otra persona.
2. Al hacer merge, el workflow **Despliegue (CD)** copia el código a la máquina virtual, reconstruye los contenedores y verifica que `/api/health` responda.
3. PR de `production` → `main` para dejar la versión estable como rama por defecto.

Si el despliegue falla, el workflow sale en rojo en la pestaña **Actions** con el paso que falló.
