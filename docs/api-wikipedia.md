# API de biografías de artistas

## Endpoint

GET /concerts/{concert_id}/artist-bio

Consulta Wikipedia en español usando el artista registrado en el concierto.

## Respuesta

- concert_id: identificador del concierto.
- artist: nombre del artista.
- status: ok, not_found, ambiguous o unavailable.
- biography: introducción en texto plano de máximo 600 caracteres, o null.
- article_title: título del artículo, o null.
- article_url: enlace al artículo, o null.
- source: Wikipedia.

## Estados HTTP

- 200: consulta completada; revisar status para conocer el resultado.
- 404: concierto inexistente.
- 503: Wikipedia no disponible.

## Funcionamiento

- Consulta nombres exactos y variantes con calificadores musicales.
- Sigue redirecciones y rechaza páginas de desambiguación.
- Si no puede identificar al artista con suficiente certeza, devuelve ambiguous.
- Caché en memoria por proceso: 600 segundos, máximo 256 entradas.
- Los errores del proveedor no se guardan en caché.
- Tiempo de espera de red: 8 segundos.
- No requiere dependencias adicionales ni variables de entorno nuevas.

## Validación realizada

- Consulta real de The Weeknd: status ok.
- GET /concerts/1/artist-bio: HTTP 200.
- 11 pruebas ejecutadas desde consola: aprobadas.
- Cobertura: éxito, longitud máxima, artículo ausente, ambigüedad,
  artículo ajeno, caché, expiración, error del proveedor y controlador.
- Las pruebas de consola no están incorporadas al CI.
