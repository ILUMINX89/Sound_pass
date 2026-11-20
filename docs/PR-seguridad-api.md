Título: feat(backend): proteger la API de SoundPass
Base: development
Rama: feature/sprint3-seguridad-api
Revisores previstos: @Sergioa-aR y @imaakro (solicitarlos al crear el PR).

El perfil público desactiva documentación y valida configuración JWT. Los tokens
inválidos reciben 401; pedidos y PDF conservan 404 para recursos de otra cuenta.
Compose restringe la API a loopback y elimina el puerto publicado de PostgreSQL.
Se incluyen plantilla nginx HTTPS con recursos explícitos, configuración de entorno
y health check HTTPS parametrizado para DevOps.

Se conservan los flujos existentes de escritura del catálogo; definir roles y
administración queda fuera del alcance de esta historia.

Issue: https://github.com/ILUMINX89/Sound_pass/issues/68

Closes #68

Validación: importación y 5 pruebas de seguridad correctas sobre exportación aislada
del índice, con entorno nuevo instalado desde requirements.txt; pip check y
git diff --cached --check correctos.
Ver docs/seguridad-api.md. Pendiente:
Compose/nginx efectivos, TLS, firewall y flujos de navegador en preproducción.
No se ha desplegado ni modificado GitHub. Los cambios del asistente están excluidos.

Antes del merge, completar revisión en Files changed por otro integrante. Vincular
#68 manualmente en Development si hace falta: al apuntar a development, que no es
la rama predeterminada, verificar el vínculo y no asumir cierre automático. Confirmar
el cierre efectivo conforme al flujo hacia la rama predeterminada del repositorio.
