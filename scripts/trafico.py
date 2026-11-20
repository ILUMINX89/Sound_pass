"""Genera tráfico de prueba contra la API de SoundPass.

Uso (sin instalar Python, corriendo dentro del clúster):
  Get-Content scripts/trafico.py | kubectl run trafico -i --rm --restart=Never --image=python:3.12-alpine -n soundpass -- python - http://soundpass-api:8000 120 20

Uso con Python local (con el port-forward del frontend abierto):
  python scripts/trafico.py http://localhost:8080/api 120 20

Argumentos: URL base, duración en segundos (120) y número de hilos en paralelo (20).
"""
import random
import sys
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

BASE = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://localhost:8080/api"
DURACION = int(sys.argv[2]) if len(sys.argv) > 2 else 120
HILOS = int(sys.argv[3]) if len(sys.argv) > 3 else 20

# Rutas de solo lectura; /concerts/999999 da 404 a propósito para ver errores en Grafana
RUTAS = ["/concerts?sort=date"] * 5 + ["/concerts/1", "/concerts/2", "/concerts/3", "/venues", "/concerts/999999"]

ok = errores = 0
candado = threading.Lock()


def trabajar(fin):
    global ok, errores
    while time.time() < fin:
        try:
            with urlopen(BASE + random.choice(RUTAS), timeout=10) as r:
                r.read()
            with candado:
                ok += 1
        except (HTTPError, URLError, TimeoutError, ConnectionError):
            with candado:
                errores += 1


fin = time.time() + DURACION
print(f"Enviando tráfico a {BASE} durante {DURACION} s con {HILOS} hilos...", flush=True)
hilos = [threading.Thread(target=trabajar, args=(fin,)) for _ in range(HILOS)]
for h in hilos:
    h.start()
while any(h.is_alive() for h in hilos):
    time.sleep(10)
    print(f"  {ok} respuestas OK, {errores} con error", flush=True)
print(f"Listo: {ok} OK, {errores} con error ({ok / DURACION:.1f} requests por segundo)")
