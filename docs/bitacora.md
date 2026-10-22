# Bitácora de errores y decisiones

Aquí registramos **cada vez que algo no funcionó** o tuvimos que tomar una decisión que cambió cómo trabajamos. El objetivo es que nadie vuelva a perder tiempo en lo mismo y tener material real para la retrospectiva.

## Metodología

- Trabajamos con **Kanban** en GitHub Projects (Backlog → Ready → In Progress → Review → Done) en 3 sprints.
- Cuando algo sale mal, quien lo vivió agrega una entrada **el mismo día**, en un PR con commit `docs: registrar <tema> en la bitácora`.
- Cada entrada responde siempre las mismas preguntas:

```markdown
### AAAA-MM-DD · Título corto
**Qué pasó:**
**Causa:**
**Cómo se resolvió:**
**Pros de la solución:**
**Contras de la solución:**
**Lección / qué cambiamos:**
**Quién:** @usuario
```

---

## Entradas

### 2026-10-13 · Credenciales reales expuestas en el repositorio
**Qué pasó:** `backend/.env.example` tenía la contraseña real de PostgreSQL de producción y el *client secret* de Spotify.
**Causa:** el archivo de ejemplo se llenó con los valores del despliegue y nadie lo revisó antes de subirlo.
**Cómo se resolvió:** se reemplazaron por valores de ejemplo y se eliminó la integración con Spotify, que además no funcionaba (PR #1, historia #3).
**Pros de la solución:** el código ya no expone credenciales; se quitó una dependencia externa que fallaba.
**Contras de la solución:** las claves siguen en el **historial** de Git; por eso hay que cambiar la contraseña de la base de datos en el servidor y eliminar la app en el panel de Spotify.
**Lección / qué cambiamos:** los valores reales solo van en `backend/.env` (ignorado por Git) o en los *Secrets* de GitHub. Quedó escrito en `CONTRIBUTING.md`.
**Quién:** @imaakro

### 2026-10-13 · Merge de un PR sin revisión
**Qué pasó:** un PR de la plantilla de historias se mergeó sin que nadie más lo revisara.
**Causa:** el autor tenía permisos para mergear y no había una regla que exigiera aprobación.
**Cómo se resolvió:** se dejó el cambio (era pequeño y correcto) y se acordó que nadie mergea su propio PR.
**Pros de la solución:** no hubo que deshacer ni repetir trabajo.
**Contras de la solución:** ese PR quedó sin evidencia de *code review*.
**Lección / qué cambiamos:** la regla "nadie mergea su propio PR" quedó en `CONTRIBUTING.md`. Pendiente: proteger `development` y `production` con un *ruleset* que exija 1 aprobación.
**Quién:** @imaakro

### 2026-10-13 · Commit hecho en la rama equivocada
**Qué pasó:** el commit del workflow de CI quedó en `development` local y la rama `feature/sprint2-ci` subió vacía; GitHub decía "There isn't anything to compare".
**Causa:** se creó la rama, se volvió a `development` sin darse cuenta y se hizo el commit ahí.
**Cómo se resolvió:** se llevó el commit a la rama correcta (`git checkout feature/sprint2-ci` + `git merge development`) y se limpió `development` local con `git reset --hard origin/development`.
**Pros de la solución:** no se perdió el trabajo y `development` quedó igual que en GitHub.
**Contras de la solución:** `reset --hard` es peligroso si no se entiende; se usó solo porque el commit ya estaba a salvo en otra rama.
**Lección / qué cambiamos:** antes de hacer commit, revisar en qué rama se está con `git status`. La solución quedó en la sección "Cómo arreglar un commit" de `CONTRIBUTING.md`.
**Quién:** @imaakro

### 2026-10-13 · Migración a un repositorio nuevo
**Qué pasó:** la guía pedía un repositorio colaborativo nuevo y ya teníamos trabajo en `Gestion_conciertos_nube`.
**Causa:** el proyecto empezó en el repositorio de la entrega anterior.
**Cómo se resolvió:** se creó `Sound_pass` vacío y se subieron todas las ramas con su historial (`git remote rename origin viejo`, `git remote add origin ...`, `git push -u origin --all`). Los PRs abiertos se volvieron a crear en el repo nuevo y se cerraron los viejos.
**Pros de la solución:** se conservó todo el historial de commits y la autoría de cada miembro.
**Contras de la solución:** los PRs, issues y comentarios no se migran solos; hubo que recrearlos y el issue "Boton-ayuda" se transfirió a mano.
**Lección / qué cambiamos:** decidir dónde vive el repositorio **antes** de empezar a abrir PRs e issues.
**Quién:** @imaakro

### 2026-10-13 · No se podía crear el GitHub Project desde la cuenta de un colaborador
**Qué pasó:** desde el repositorio, "Link a project" no mostraba proyectos y un colaborador no podía crear uno.
**Causa:** el repositorio pertenece a una cuenta personal; solo el dueño puede crear proyectos vinculados a ella.
**Cómo se resolvió:** el dueño (@ILUMINX89) creó el proyecto y dio acceso de administrador a los demás.
**Pros de la solución:** el tablero queda en la misma cuenta que el repositorio.
**Contras de la solución:** dependemos del dueño para cambios de permisos.
**Lección / qué cambiamos:** para un proyecto real convendría una **organización** de GitHub, donde los permisos se reparten por equipo.
**Quién:** @imaakro

### 2026-10-13 · Las historias no pasaban a Done al hacer merge a `development`
**Qué pasó:** al mergear un PR con `Closes #N` hacia `development`, el issue no se cerraba y la tarjeta no se movía.
**Causa:** GitHub solo cierra issues automáticamente cuando el merge va a la rama por defecto (`main`). Además, el `GITHUB_TOKEN` de Actions no tiene permiso sobre Projects de una cuenta personal.
**Cómo se resolvió:** workflow propio `project-automation.yml` que usa la API GraphQL de GitHub para mover las tarjetas, con un token personal guardado como secreto `PROJECT_TOKEN` (historia #6).
**Pros de la solución:** el tablero refleja el estado real del código sin moverlo a mano.
**Contras de la solución:** el token pertenece a una persona y **expira** (alrededor del 12 de noviembre de 2026); si vence, la automatización deja de funcionar.
**Lección / qué cambiamos:** documentar quién es dueño de cada secreto y cuándo vence.
**Quién:** @imaakro

### 2026-10-21 · Los PRs hacia `development` no se vinculaban con su historia
**Qué pasó:** el PR de las plantillas decía `Closes #11`, pero en la sección *Development* del PR salía "None yet" y la tarjeta #11 no pasó a Review.
**Causa:** GitHub solo reconoce `Closes #N` cuando el PR va a la rama por defecto (`main`). Nuestros PRs van a `development`, así que la automatización no encontraba la historia.
**Cómo se resolvió:** `project-automation.yml` ahora también lee los números de `Closes/Fixes/Resolves #N` en la descripción del PR, y corre al editar el PR. Para los PRs que ya estaban abiertos se vinculó el issue a mano desde *Development*.
**Pros de la solución:** se mantiene el flujo `feature` → `development` y el tablero se mueve solo.
**Contras de la solución:** depende de que la descripción tenga el formato exacto `Closes #N`.
**Lección / qué cambiamos:** probar la automatización con un PR real hacia la rama que de verdad usamos, no solo hacia `main`.
**Quién:** @imaakro

### 2026-10-16 · Retroalimentación del profesor sobre el avance
**Qué pasó:** en la revisión del avance el profesor señaló puntos a mejorar.
**Cómo se resolvió (acción tomada por cada punto):**

| Punto del profesor | Qué hicimos |
|---|---|
| Que el rol se asigne automático al crear el issue | Las plantillas de issue piden el **Rol**, y `project-automation.yml` pone la etiqueta `rol: ...` y llena el campo Rol del tablero |
| Poder filtrar por roles, características, etc. | Etiquetas `rol:`, `tipo:`, `prioridad:`, `sprint N` y vistas del tablero por rol y por sprint |
| Commits concisos y bien hechos | Formato `tipo: descripción` documentado en `CONTRIBUTING.md` y revisado automáticamente por el workflow `commits.yml` |
| Descripción de issues más precisa | Plantillas con campos obligatorios: contexto, pasos técnicos, criterios de aceptación y definición de terminado |
| Cómo cambiar un commit con errores | Sección "Cómo arreglar un commit" en `CONTRIBUTING.md` |
| Registrar errores, pros y contras | Esta bitácora |
| Que nadie dependa de los demás | `CONTRIBUTING.md` explica de principio a fin cómo trabajar solo |
| Probar la app con alguien externo | Plantilla "Feedback de usuario externo" y registro en `docs/feedback-externo.md` |
| IA en la implementación y automatización | Planeado para la entrega final |

**Quién:** todo el equipo

### 2026-10-22 · Despliegue en una máquina virtual nueva
**Qué pasó:** solo una persona tenía acceso a la VM donde corría la app, así que el resto del equipo no podía desplegar ni configurar el despliegue automático.
**Causa:** la VM se creó con el usuario y la contraseña de un solo miembro y nunca se compartió un acceso para automatización.
**Cómo se resolvió:** se creó una VM nueva (`soundpass-v2`, 20.80.47.160). Se instaló Docker y nginx, se levantó la app con `docker compose` y las credenciales del servidor se generaron con `openssl rand` dentro de la VM, en un `docker-compose.override.yml` que no está en Git. Se creó una llave SSH solo para despliegues y se guardó como secreto `VM_SSH_KEY` en GitHub.
**Pros de la solución:** el despliegue ya no depende de una persona; nadie ve las contraseñas de la base de datos ni la clave JWT; el usuario de la VM no necesita `sudo` para desplegar (está en el grupo `docker` y es dueño de `/var/www/soundpass`).
**Contras de la solución:** hay dos VMs que mantener mientras se apaga la vieja; la llave de despliegue da acceso total a la VM si se filtra.
**Lección / qué cambiamos:** desde el inicio crear un acceso por llave para la automatización, separado de los accesos personales.
**Quién:** @imaakro

### 2026-10-22 · La app no cargaba desde afuera (puerto 80 cerrado)
**Qué pasó:** dentro de la VM `curl http://127.0.0.1/api/health` respondía bien, pero desde el navegador salía `ERR_CONNECTION_TIMED_OUT`.
**Causa:** el *Network Security Group* de Azure solo tenía abierto el puerto 22 (SSH).
**Cómo se resolvió:** se agregó una regla de entrada (*inbound*) para el puerto 80/TCP. Los puertos 8000 (API) y 5432 (base de datos) se dejaron cerrados.
**Pros de la solución:** solo se expone nginx; la API y la base de datos no son accesibles desde internet.
**Contras de la solución:** la regla la tiene que crear quien es dueño de la suscripción de Azure.
**Lección / qué cambiamos:** si funciona por dentro y no por fuera, revisar primero el firewall de la nube antes de tocar la app.
**Quién:** @imaakro

### 2026-10-22 · No aparecía ningún concierto en producción
**Qué pasó:** la app cargaba y se podía crear usuario, pero la lista de conciertos salía vacía.
**Causa:** los conciertos de `database/seed.sql` tenían fechas de 2025 y la API solo muestra conciertos con `event_date >= date.today()`. Al pasar el tiempo, todos quedaron como pasados.
**Cómo se resolvió:** en la VM se movieron las fechas 2 años con un `UPDATE` en PostgreSQL, y en el repositorio se corrigieron las fechas del seed (bug con su propio PR).
**Pros de la solución:** el arreglo en la VM fue inmediato y el del repo evita que vuelva a pasar en una base nueva.
**Contras de la solución:** las fechas del seed siguen siendo fijas; en el futuro volverán a quedar en el pasado.
**Lección / qué cambiamos:** los datos de ejemplo con fechas deberían calcularse relativos a la fecha actual (por ejemplo `CURRENT_DATE + 30`).
**Quién:** @imaakro


