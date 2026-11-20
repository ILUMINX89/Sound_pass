# SoundPass AI

El chat de SoundPass llama a FastAPI con el JWT de la cuenta. FastAPI llama a
`POST /api/chat` de Ollama por la red privada. Cada consulta procesa el mensaje
actual. El asistente orienta sobre la aplicación y remite al catálogo para datos
vigentes. No consulta pedidos ni ejecuta compras o cancelaciones.

| Campo | Valor |
| --- | --- |
| Ruta FastAPI | `POST /assistant/chat` |
| Ruta por nginx | `POST /api/assistant/chat` |
| Autenticación | `Authorization: Bearer <JWT>` de una cuenta existente |
| Solicitud | `{"message":"¿Cómo cancelo una orden?"}` |
| Respuesta 200 | `{"reply":"<texto de Ollama>"}` |
| Validación | Entre 1 y 500 caracteres después de recortar espacios |
| Límite | 3 consultas por usuario en 60 segundos y 2 simultáneas por proceso |
| Tiempo máximo | 55 segundos de espera de Ollama por defecto |
| Modelo por defecto | `qwen2.5:1.5b` |
| Historial | Sin historial del lado del backend |

Los límites se mantienen en memoria y se reinician con el proceso. Cada réplica
o trabajador tiene sus propios contadores. Errores esperados: 401 por
credenciales, 422 por validación, 429 por límite, 502 por fallo del proveedor,
503 sin configuración y 504 por espera agotada. Los logs del asistente registran
el tipo de fallo del proveedor sin guardar las preguntas ni las respuestas.

## Configuración en Linux y en la VM

Primero verifica desde la máquina que ejecuta FastAPI que Ollama sea alcanzable y
que el modelo esté instalado. Para Compose, verifica también desde el contenedor API.

```bash
curl --connect-timeout 5 --max-time 10 -fsS http://100.89.0.83:11434/api/tags
```

Agrega a `backend/.env` si ejecutas Uvicorn directamente, o al `.env` privado de
la raíz si usas Compose. Si `/api/tags` devuelve otra etiqueta, usa la exacta.

```dotenv
OLLAMA_BASE_URL=http://100.89.0.83:11434
OLLAMA_MODEL=qwen2.5:1.5b
OLLAMA_TIMEOUT_SECONDS=55
```

El servicio Docker recibe las variables por Compose. Si se despliega mediante
Kubernetes, configura las mismas variables en el contenedor de la API. Ollama
debe escuchar en la interfaz privada y permitir al backend por Tailscale.
El puerto de Ollama permanece privado. El JWT solo se envía a SoundPass.

Con Compose, reconstruye la API y publica el frontend actualizado por el flujo
habitual de la VM.

```bash
docker compose up -d --build api
docker compose exec -T api python -c 'import os,httpx; print(httpx.get(os.environ["OLLAMA_BASE_URL"].rstrip("/") + "/api/tags",timeout=5,trust_env=False).status_code)'
```

## Prueba funcional

Con el JWT de una cuenta de pruebas, ejecuta desde la máquina del backend:

```bash
curl -fsS http://127.0.0.1:8000/assistant/chat \
  -H "Authorization: Bearer ${SOUNDPASS_TOKEN}" \
  -H 'Content-Type: application/json' \
  -d '{"message":"¿Cómo cancelo una orden?"}'
```

Repite con «¿Cómo descargo mi boleto?» y comprueba que el chat web muestra ambas
respuestas. En la VM, la prueba por el proxy usa `/api/assistant/chat` en el
dominio HTTPS de SoundPass. Swagger está disponible en entorno local.
